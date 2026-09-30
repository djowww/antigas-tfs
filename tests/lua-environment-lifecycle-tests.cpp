#include "otpch.h"
#include "game.h"
#include "configmanager.h"
#include "scheduler.h"
#include "databasetasks.h"
#include "rsa.h"
#include <boost/filesystem.hpp>
#include <fstream>
#include <stdexcept>

// Preserve the core globals and their normal link layout. No socket, database,
// scheduler/dispatcher thread, world, or production configuration is started.
DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;
extern LuaEnvironment g_luaEnvironment;

static void require(bool ok, const char* message)
{
	if (!ok) throw std::runtime_error(message);
}

static void requireRaidState()
{
	lua_State* state = g_game.raids.getScriptInterface().getLuaState();
	require(state != nullptr && state == g_luaEnvironment.getLuaState(),
	        "raid interface must attach to the live main Lua state");
	const int before = lua_gettop(state);
	const int status = luaL_dostring(state, "return 42");
	const bool valid = status == 0 && lua_isnumber(state, -1) && lua_tointeger(state, -1) == 42;
	lua_settop(state, before);
	require(valid, "attached raid Lua state must remain usable");
}

int main()
{
	const auto original = boost::filesystem::current_path();
	const auto scratch = boost::filesystem::temp_directory_path() /
		boost::filesystem::unique_path("antigas-lua-lifecycle-%%%%-%%%%");
	int result = 0;
	try {
		require(!g_game.raids.isLoaded() && !g_game.raids.isStarted(),
		        "global raids must start unloaded without scheduling work");
		require(g_game.raids.getScriptInterface().getLuaState() == nullptr,
		        "global raid construction must defer its Lua interface initialization");
		boost::filesystem::create_directories(scratch / "data/raids");
		{
			std::ofstream xml((scratch / "data/raids/raids.xml").string());
			xml << "<raids/>";
			require(xml.good(), "synthetic empty raid configuration must be written");
		}
		boost::filesystem::current_path(scratch);
		require(g_game.raids.loadFromXml() && g_game.raids.isLoaded(),
		        "empty real raid XML must initialize and load");
		requireRaidState();
		for (unsigned cycle = 0; cycle < 2; ++cycle) {
			g_game.raids.clear();
			require(!g_game.raids.isLoaded() && !g_game.raids.isStarted(),
			        "raid clear must reset loading and startup state");
			requireRaidState();
			require(g_game.raids.reload() && g_game.raids.isLoaded(),
			        "real raid reload must preserve Lua initialization");
			requireRaidState();
		}
		// Leave the global raid interface initialized. Normal process teardown
		// exercises its closeState even when the main Lua global is destroyed
		// first, as observed with the CI's core-test link layout. Other toolchains
		// may choose the opposite order; this test does not assume a universal one.
		std::cout << "PASS: isolated global raid Lua initialization, clear, reload and pending teardown." << std::endl;
	} catch (const std::exception& error) {
		std::cerr << "FAIL: " << error.what() << std::endl;
		result = 1;
	}
	boost::filesystem::current_path(original);
	if (boost::filesystem::exists(scratch)) boost::filesystem::remove_all(scratch);
	return result;
}
