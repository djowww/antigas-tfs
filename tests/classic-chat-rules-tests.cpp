#include "otpch.h"
#include "game.h"
#include "configmanager.h"
#include "scheduler.h"
#include "databasetasks.h"
#include "rsa.h"
#include "groups.h"
#include "spells.h"
#include "talkaction.h"
#include "events.h"
#include "creatureevent.h"
#include "party.h"
#include <boost/filesystem.hpp>
#include <fstream>
#include <stdexcept>

// Production core, without a database, listeners, scheduler threads or player saves.
DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;
extern Spells* g_spells;
extern TalkActions* g_talkActions;
extern Events* g_events;
extern CreatureEvents* g_creatureEvents;
extern LuaEnvironment g_luaEnvironment;

static unsigned checks = 0;
static void require(bool success, const char* message)
{
    ++checks;
    if (!success) throw std::runtime_error(message);
}

static void writeFile(const boost::filesystem::path& path, const std::string& content)
{
    std::ofstream file(path.string());
    require(static_cast<bool>(file), "test fixture must be writable");
    file << content;
}

int main()
{
    const auto original = boost::filesystem::current_path();
    const auto scratch = boost::filesystem::temp_directory_path() /
        boost::filesystem::unique_path("antigas-classic-chat-%%%%-%%%%");
    try {
        require(g_vocations.loadFromXml(), "production vocations must load");
        require(g_luaEnvironment.initState(), "production Lua bindings must initialize");
        boost::filesystem::create_directories(scratch / "data/spells/lib");
        boost::filesystem::create_directories(scratch / "data/spells/scripts");
        boost::filesystem::create_directories(scratch / "data/talkactions/lib");
        boost::filesystem::create_directories(scratch / "data/talkactions/scripts");
        writeFile(scratch / "config.lua", "maxMessageBuffer = 4\n");
        writeFile(scratch / "data/spells/lib/spells.lua", "-- isolated fixture\n");
        writeFile(scratch / "data/spells/spells.xml",
            "<spells><instant name=\"Fixture\" words=\"classicfixture\" lvl=\"0\" "
            "mana=\"0\" aggressive=\"0\" selftarget=\"1\" needlearn=\"0\" "
            "cooldown=\"0\" script=\"fixture.lua\" /></spells>\n");
        writeFile(scratch / "data/spells/scripts/fixture.lua",
            "function onCastSpell(creature, variant)\n"
            "  creature:setStorageValue(900777, 1)\n"
            "  return true\nend\n");
        writeFile(scratch / "data/talkactions/lib/talkactions.lua", "-- isolated fixture\n");
        writeFile(scratch / "data/talkactions/talkactions.xml",
            "<talkactions><talkaction words=\"!share\" script=\"experienceshare.lua\" permission=\"public\" />"
            "<talkaction words=\"!protectedfixture\" script=\"protectedfixture.lua\" permission=\"access\" /></talkactions>\n");
        std::ifstream shareScript((original / "data/talkactions/scripts/experienceshare.lua").string(), std::ios::binary);
        require(shareScript.good(), "production share command script must be readable");
        writeFile(scratch / "data/talkactions/scripts/experienceshare.lua",
            std::string(std::istreambuf_iterator<char>(shareScript), std::istreambuf_iterator<char>()));
        writeFile(scratch / "data/talkactions/scripts/protectedfixture.lua",
            "function onSay(player, words, param, type)\n"
            "  player:setStorageValue(900778, 1)\n"
            "  return false\nend\n");
        boost::filesystem::current_path(scratch);
        require(g_config.load(), "isolated config must load");
        Spells spells;
        TalkActions talkActions;
        Events events;
        CreatureEvents creatureEvents;
        g_spells = &spells;
        g_talkActions = &talkActions;
        g_events = &events;
        g_creatureEvents = &creatureEvents;
        require(spells.loadFromXml(), "real spell registration must load fixture");
        require(talkActions.loadFromXml(), "real command registration must load the production share script");
        Group ordinary = {};
        Player player(nullptr);
        player.setGroup(&ordinary);
        player.setID();
        player.setName("Classic Chat Fixture");
        require(player.setVocation(1), "ordinary fixture must have a real vocation");
        auto* tile = new DynamicTile(100, 100, 7);
        g_game.map.setTile(100, 100, 7, tile);
        player.setParent(tile);
        g_game.addPlayer(&player);
        Player member(nullptr);
        member.setGroup(&ordinary);
        member.setID();
        member.setName("Classic Party Member");
        require(member.setVocation(1), "party member must have a real vocation");
        member.setParent(tile);
        g_game.addPlayer(&member);
        Party party(&player);
        require(party.invitePlayer(member) && party.joinParty(member),
            "real party must include its leader and an invited member");
        require(!party.isSharedExperienceActive(), "share command fixture must start inactive");
        int32_t marker = 0;
        g_game.playerSay(player.getID(), 0, TALKTYPE_SAY, "", "classicfixture");
        require(player.getStorageValue(900777, marker) && marker == 1,
            "an unmuted character must still cast through Game::playerSay");
        player.addStorageValue(900777, 0);
        // The first successful cast applies the production exhaustion condition.
        // Remove it so the next assertion isolates mute, rather than exhaustion.
        player.removeCondition(CONDITION_EXHAUST);
        require(!player.hasCondition(CONDITION_EXHAUST),
            "mute scenario must not be masked by spell exhaustion");
        require(player.addCondition(Condition::createCondition(CONDITIONID_DEFAULT,
            CONDITION_MUTED, 60000, 0)), "fixture must acquire a real mute condition");
        require(player.isMuted() > 0, "ordinary fixture must actually be muted");
        g_game.playerSay(player.getID(), 0, TALKTYPE_SAY, "", "classicfixture");
        require(player.getStorageValue(900777, marker) && marker == 0,
            "a muted character must not execute a spell callback through speech");
        g_game.playerSay(player.getID(), 0, TALKTYPE_SAY, "", "!share");
        require(party.isSharedExperienceActive(),
            "muted leader must still enable shared experience exactly once through the real public share command");
        g_game.playerSay(player.getID(), 0, TALKTYPE_SAY, "", "!share");
        require(!party.isSharedExperienceActive(),
            "a second muted share command must disable shared experience exactly once");
        require(member.addCondition(Condition::createCondition(CONDITIONID_DEFAULT,
            CONDITION_MUTED, 60000, 0)), "party member must acquire a real mute condition");
        g_game.playerSay(member.getID(), 0, TALKTYPE_SAY, "", "!share");
        require(!party.isSharedExperienceActive(), "muted non-leader must not change shared experience");
        player.addStorageValue(900778, 0);
        g_game.playerSay(player.getID(), 0, TALKTYPE_SAY, "", "!protectedfixture");
        require(player.getStorageValue(900778, marker) && marker == 0,
            "preserving muted commands must not bypass their access authorization");
        g_game.playerSay(player.getID(), 0, TALKTYPE_SAY, "", "classicfixture");
        require(player.getStorageValue(900777, marker) && marker == 0,
            "dispatching a muted custom command must not reopen spell casting");
        player.removeCondition(CONDITION_MUTED);
        for (unsigned i = 0; i < 5; ++i) player.removeMessageBuffer();
        require(player.isMuted() > 0,
            "enabled production message limiter must mute excessive speech");
        member.setParty(nullptr);
        player.setParty(nullptr);
        g_game.removePlayer(&member);
        g_game.removePlayer(&player);
        g_spells = nullptr;
        g_talkActions = nullptr;
        g_events = nullptr;
        g_creatureEvents = nullptr;
        boost::filesystem::current_path(original);
        boost::filesystem::remove_all(scratch);
        std::cout << "classic chat: " << checks << " checks passed\n";
        return 0;
    } catch (const std::exception& error) {
        boost::filesystem::current_path(original);
        boost::filesystem::remove_all(scratch);
        std::cerr << "classic chat failed: " << error.what() << '\n';
        return 1;
    }
}
