#include "otpch.h"
#include "game.h"
#include "configmanager.h"
#include "events.h"
#include "scheduler.h"
#include "databasetasks.h"
#include "rsa.h"
#include <boost/filesystem.hpp>
#include <fstream>
#include <stdexcept>

// Same production-core globals as the rarity integration test; no sockets,
// database connection, scheduler threads, or live world are started.
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

int main()
{
	const auto original = boost::filesystem::current_path();
	const auto scratch = boost::filesystem::temp_directory_path() /
		boost::filesystem::unique_path("antigas-event-reset-%%%%-%%%%");
	int result = 0;
	try {
		require(Item::items.loadItems(), "test item definitions must load");
		require(g_luaEnvironment.initState(), "Lua environment must initialize");
		Events events;
		Player player(nullptr);
		std::unique_ptr<Item> item(Item::CreateItem(3264));
		require(item != nullptr, "sword fixture must exist");
		boost::filesystem::create_directories(scratch / "data/events/scripts");
		{
			std::ofstream script((scratch / "data/events/scripts/player.lua").string());
			script << "function Player:onUseItem(item, target) return false end\n"
			       << "function Player:onRemoveCount(item, count) return false end\n";
		}
		{
			std::ofstream script((scratch / "data/events/scripts/party.lua").string());
			script << "function Party:onShareExperience(exp) return exp + 7 end\n";
		}
		boost::filesystem::current_path(scratch);
		for (unsigned cycle = 0; cycle < 2; ++cycle) {
			{
				std::ofstream xml("data/events/events.xml");
				xml << "<events><event class=\"Player\" method=\"onUseItem\" enabled=\"1\"/>"
				    << "<event class=\"Player\" method=\"onRemoveCount\" enabled=\"1\"/>"
				    << "<event class=\"Party\" method=\"onShareExperience\" enabled=\"1\"/></events>";
			}
			require(events.load(), "enabled callbacks must load");
			require(!events.eventPlayerOnUseItem(&player, item.get(), nullptr), "enabled use callback must run");
			require(!events.eventPlayerOnRemoveCount(&player, item.get(), 1), "enabled removal callback must run");
			uint64_t exp = 10;
			events.eventPartyOnShareExperience(nullptr, exp);
			require(exp == 17, "enabled party callback must run");
			events.clear();
			{
				std::ofstream xml("data/events/events.xml");
				xml << "<events><event class=\"Player\" method=\"onUseItem\" enabled=\"0\"/>"
				    << "<event class=\"Player\" method=\"onRemoveCount\" enabled=\"0\"/>"
				    << "<event class=\"Party\" method=\"onShareExperience\" enabled=\"0\"/></events>";
			}
			require(events.load(), "disabled event configuration must load");
			require(events.eventPlayerOnUseItem(&player, item.get(), nullptr), "disabled use callback must not survive clear");
			require(events.eventPlayerOnRemoveCount(&player, item.get(), 1), "disabled removal callback must not survive clear");
			events.eventPartyOnShareExperience(nullptr, exp);
			require(exp == 17, "disabled party callback must not survive clear");
		}
		std::cout << "PASS: enabled callbacks run; clear and disabled reload remove old handlers twice." << std::endl;
	} catch (const std::exception& error) {
		std::cerr << "FAIL: " << error.what() << std::endl;
		result = 1;
	}
	boost::filesystem::current_path(original);
	if (boost::filesystem::exists(scratch)) boost::filesystem::remove_all(scratch);
	return result;
}
