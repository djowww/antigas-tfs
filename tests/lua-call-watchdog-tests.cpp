#include "luacallwatchdog.h"
#include <stdexcept>
#include <iostream>

static uint64_t now = 0;
static unsigned warnings = 0;
static uint64_t clockNow() { return now; }
static void warning(const char*, int, uint64_t) { ++warnings; }
static void oldHook(lua_State*, lua_Debug*) {}
static int tick(lua_State*) { ++now; return 0; }
static void require(bool result, const char* message)
{
	if (!result) throw std::runtime_error(message);
}
static void invoke(lua_State* state, const char* source, bool expectError = false)
{
	require(luaL_loadstring(state, source) == 0, "could not load test chunk");
	int result;
	{
		LuaCallWatchdog watchdog(state, 0, clockNow, warning);
		result = lua_pcall(state, 0, 0, 0);
	}
	require((result != 0) == expectError, "unexpected callback result");
	if (result) lua_pop(state, 1);
}

int main()
{
	lua_State* state = luaL_newstate();
	try {
		require(state != nullptr, "Lua allocation failed");
		luaL_openlibs(state);
		lua_register(state, "tick", tick);
		// Model separate callbacks interspersed with map loading and idle time.
		for (unsigned i = 0; i < 200; ++i) {
			now += 20000;
			invoke(state, "local n = 0; for i = 1, 20000 do n = n + i end");
		}
		require(warnings == 0, "unrelated callback or idle time triggered diagnostic");
		require(lua_gethook(state) == nullptr, "hook leaked after callback");
		invoke(state, "for i = 1, 100000 do tick() end");
		require(warnings == 1, "slow callback must report exactly once");
		invoke(state, "for i = 1, 100000 do tick() end");
		require(warnings == 2, "diagnostics must remain enabled for later callbacks");
		lua_sethook(state, oldHook, LUA_MASKCOUNT, 1234);
		invoke(state, "error('expected test exception')", true);
		require(lua_gethook(state) == oldHook && lua_gethookcount(state) == 1234,
		        "Lua error path did not restore existing hook");
		{
			LuaCallWatchdog outer(state, 0, clockNow, warning);
			const lua_Hook outerHook = lua_gethook(state);
			invoke(state, "for i = 1, 100000 do tick() end");
			require(lua_gethook(state) == outerHook, "nested callback lost parent hook");
		}
		require(lua_gethook(state) == oldHook && lua_gethookmask(state) == LUA_MASKCOUNT,
		        "nested scope failed to restore original hook");
		lua_close(state);
		std::cout << "Lua call watchdog tests passed\n";
		return 0;
	} catch (const std::exception& error) {
		std::cerr << error.what() << '\n';
		if (state) lua_close(state);
		return 1;
	}
}
