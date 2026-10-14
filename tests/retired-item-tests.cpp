#include "otpch.h"
#include "game.h"
#include "configmanager.h"
#include "scheduler.h"
#include "databasetasks.h"
#include "rsa.h"
#include "weapons.h"
#include "movement.h"
#include "monster.h"
#include "loot.h"
#include <boost/filesystem.hpp>
#include <fstream>
#include <regex>
#include <stdexcept>

// Real definitions and server core, without persistence, listeners or worker threads.
DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;
extern LuaEnvironment g_luaEnvironment;
extern MoveEvents* g_moveEvents;

static void require(bool condition, const std::string& message)
{
    if (!condition) throw std::runtime_error(message);
}

static std::vector<uint16_t> canonicalIds()
{
    std::ifstream manifest("data/items/retired-items.json");
    require(static_cast<bool>(manifest), "canonical retirement manifest must exist");
    const std::string json((std::istreambuf_iterator<char>(manifest)), std::istreambuf_iterator<char>());
    const std::regex idPattern("\"id\"\\s*:\\s*([0-9]+)");
    std::vector<uint16_t> ids;
    for (auto it = std::sregex_iterator(json.begin(), json.end(), idPattern); it != std::sregex_iterator(); ++it) {
        ids.push_back(static_cast<uint16_t>(std::stoul((*it)[1])));
    }
    require(ids.size() == 346, "frozen retirement scope must contain 346 IDs");
    return ids;
}

static void creationTests()
{
    for (uint16_t id : canonicalIds()) {
        require(Item::items[id].id == id, "retired definition ID must remain stable: " + std::to_string(id));
        require(Item::CreateItem(id) == nullptr, "retired item creation must be rejected: " + std::to_string(id));
        require(Item::CreateItemAsContainer(id, 20) == nullptr, "retired container creation must be rejected");
    }
    for (uint16_t id : {uint16_t(435), uint16_t(2854), uint16_t(3031), uint16_t(3264), uint16_t(3294)}) {
        std::unique_ptr<Item> item(Item::CreateItem(id));
        require(item && item->getID() == id, "classic/map item creation must remain available");
    }
}

static void transformTests(bool direct)
{
    // Force the existing deprecated category independently of manifest loading.
    Item::items.getItemType(3157).group = ITEM_GROUP_DEPRECATED;
    std::unique_ptr<Item> bagItem(Item::CreateItem(2854));
    require(bagItem && bagItem->getContainer(), "classic backpack fixture must exist");
    Item* original = Item::CreateItem(3264);
    require(original != nullptr, "classic sword fixture must exist");
    original->setActionId(777);
    bagItem->getContainer()->internalAddThing(original);
    if (direct) {
        original->setID(3157);
    } else {
        require(g_game.transformItem(original, 3157) == original, "blocked transform must retain the original object");
    }
    require(original->getID() == 3264, "retired target must not bypass creation through an ID update");
    require(original->getActionId() == 777 && original->getParent() == bagItem->getContainer(),
        "blocked transform must retain attributes and container ownership");
    if (!direct) {
        require(g_game.transformItem(original, 3294) == original && original->getID() == 3294,
            "classic-to-classic transform must remain available");
    }
}

static void lookupTests()
{
    require(Item::items.getItemIdByName("cranial basher") == 0, "retired unique name must not resolve");
    require(Item::items.getItemIdByName("ring of wishes") == 0, "retired ring name must not resolve");
    require(Item::items.getItemIdByName("short sword") == 3294, "classic item lookup must remain available");
    for (const auto& entry : Item::items.nameToItems) {
        require(Item::items[entry.second].group != ITEM_GROUP_DEPRECATED, "native name catalog must exclude retired IDs");
    }
}

static void cloneTests()
{
    Item legacy(3157);
    legacy.setActionId(777);
    Item::items.getItemType(3157).group = ITEM_GROUP_DEPRECATED;
    require(legacy.clone() == nullptr, "an existing retired instance must not clone or dereference a rejected factory result");
    Item classic(3264);
    classic.setActionId(778);
    std::unique_ptr<Item> copied(classic.clone());
    require(copied && copied->getID() == 3264 && copied->getActionId() == 778,
        "classic cloning must retain item identity and attributes");
}

static void containerCloneTests()
{
    std::unique_ptr<Item> carrier(Item::CreateItem(2854));
    require(carrier && carrier->getContainer(), "classic carrier must exist");
    Item* legacy = new Item(3157);
    legacy->incrementReferenceCounter();
    carrier->getContainer()->internalAddThing(legacy);
    carrier->getContainer()->internalAddThing(Item::CreateItem(3264));
    Item::items.getItemType(3157).group = ITEM_GROUP_DEPRECATED;
    std::unique_ptr<Item> copied(carrier->clone());
    require(copied && copied->getContainer()->size() == 1 && copied->getContainer()->getItemByIndex(0)->getID() == 3264,
        "cloning a classic container must safely retain only allowed descendants");
    require(copied->getWeight() == Item::items[2854].weight + Item::items[3264].weight,
        "cloned container weight must exclude retired descendants");
    Container retiredCarrier(3253);
    Item::items.getItemType(3253).group = ITEM_GROUP_DEPRECATED;
    require(retiredCarrier.clone() == nullptr, "retired container clone must safely reject the carrier itself");
}

static void luaTests()
{
    require(g_luaEnvironment.initState(), "production Lua environment must initialize");
    const char* script =
        "assert(type(ItemType(3157).isRetired) == 'function', 'retirement predicate must be exposed')\n"
        "assert(ItemType(3157):isRetired() == true)\n"
        "assert(ItemType(3294):isRetired() == false)\n"
        "assert(Game.createItem(3157) == nil)\n"
        "local bag = Game.createItem(2854)\n"
        "local sword = bag:addItem(3264)\n"
        "assert(sword:transform(3157) == false, 'Lua transform must report retired rejection')\n"
        "assert(sword:getId() == 3264)\n"
        "assert(sword:transform(3294) == true and sword:getId() == 3294)\n";
    lua_State* state = g_luaEnvironment.getLuaState();
    const int result = luaL_dostring(state, script);
    const char* error = result != 0 ? lua_tostring(state, -1) : nullptr;
    require(result == 0, error ? error : "Lua retirement checks failed");
}

static void weaponTests()
{
    Item::items.getItemType(3157).group = ITEM_GROUP_DEPRECATED;
    Weapons weapons;
    weapons.loadDefaults();
    Item retired(3157);
    Item classic(3264);
    require(weapons.getWeapon(&retired) == nullptr, "native weapon catalog must exclude deprecated weapon IDs");
    require(weapons.getWeapon(&classic) != nullptr, "classic weapon catalog must remain available");
}

// Access the protected virtual through a test utility, preserving Monster dispatch.
class CorpseAccess : public Creature
{
public:
    static Item* create(Creature& creature, Creature* owner)
    {
        auto method = &CorpseAccess::getCorpse;
        return (creature.*method)(owner, owner);
    }
};

static void corpseTests()
{
    Item::items.getItemType(4318).group = ITEM_GROUP_DEPRECATED;
    Item::items.getItemType(3157).group = ITEM_GROUP_DEPRECATED;
    Player owner(nullptr);
    owner.setID();
    MonsterType monsterType;
    monsterType.name = "retired corpse fixture";
    monsterType.nameDescription = "a retired corpse fixture";
    monsterType.info.lookcorpse = 4318;
    Monster monster(&monsterType);
    std::unique_ptr<Item> body(CorpseAccess::create(monster, &owner));
    require(body && body->getID() == 2854 && body->getContainer(),
        "retired monster corpse must use the existing classic recovery backpack");
    require(body->getCorpseOwner() == owner.getID(), "recovery container must keep normal corpse ownership");
    body->setParent(VirtualCylinder::virtualCylinder);
    require(body->canDecay() && body->getDuration() == 1200000,
        "recovery corpse must expire at the original corpse stage deadline");
    require(body->getNameDescription().find("temporary corpse") != std::string::npos &&
        body->getDescription(1).find("disappear") != std::string::npos &&
        body->getDescription(1).find("1200") != std::string::npos,
        "temporary corpse identity and expiry warning must be visible to players");
    std::unique_ptr<Item> ordinaryBag(Item::CreateItem(2854));
    ordinaryBag->setParent(VirtualCylinder::virtualCylinder);
    require(!ordinaryBag->canDecay() && Item::items[2854].decayTime == 0 && Item::items[2854].decayTo == -1,
        "normal classic backpack decay policy must remain unchanged");
    require(ordinaryBag->getDescription(1).find("temporary corpse") == std::string::npos,
        "ordinary backpacks must not receive corpse identity or expiry warnings");
    PropWriteStream saved;
    body->serializeAttr(saved);
    size_t savedSize;
    const char* savedBytes = saved.getStream(savedSize);
    PropStream restoredStream;
    restoredStream.init(savedBytes, savedSize);
    std::unique_ptr<Item> restoredBody(Item::CreateItem(2854));
    require(restoredBody->unserializeAttr(restoredStream), "recovery expiry must survive serialization");
    restoredBody->setParent(VirtualCylinder::virtualCylinder);
    require(restoredBody->canDecay() && restoredBody->getDuration() == 1200000,
        "saved recovery corpse must not become a permanent free backpack");
    require(g_luaEnvironment.initState(), "production Lua environment must initialize for corpse predicates");
    MoveEvents moves;
    g_moveEvents = &moves;
    require(g_luaEnvironment.loadFile("data/global.lua") == 0, "production Lua libraries must load");
    require(g_luaEnvironment.loadFile("data/events/scripts/player.lua") == 0, "production player callbacks must load");
    lua_State* lua = g_luaEnvironment.getLuaState();
    LuaScriptInterface::pushUserdata<Item>(lua, body.get());
    LuaScriptInterface::setMetatable(lua, -1, "Container");
    lua_setglobal(lua, "recoveryCorpse");
    LuaScriptInterface::pushUserdata<Item>(lua, ordinaryBag.get());
    LuaScriptInterface::setMetatable(lua, -1, "Container");
    lua_setglobal(lua, "ordinaryBag");
    const char* analyzer =
        "assert(type(recoveryCorpse.isRecoveryCorpse) == 'function')\n"
        "assert(recoveryCorpse:isRecoveryCorpse() and not ordinaryBag:isRecoveryCorpse())\n"
        "assert(not ItemType(2854):isCorpse())\n"
        "local originalTile = Tile; local currentCorpse = recoveryCorpse\n"
        "Tile = function() return {getTopDownItem=function() return currentCorpse end} end\n"
        "local hits=0; local fake={checkAnalyzerLootItem=function(_,id,count) assert(id==3264 and count==1); hits=hits+1 end,"
        "addAnalyzerDrop=function(_,row) assert(row[3]==3264) end}\n"
        "local moved=Game.createItem(3264); local source={getPosition=function() return Position(100,100,7) end}\n"
        "assert(Player.onMoveItem(fake,moved,1,Position(100,100,7),{x=CONTAINER_POSITION},source,nil))\n"
        "assert(hits==1, 'recovery corpse loot must reach Analyzer')\n"
        "currentCorpse=ordinaryBag\n"
        "assert(Player.onMoveItem(fake,moved,1,Position(100,100,7),{x=CONTAINER_POSITION},source,nil))\n"
        "assert(hits==1, 'ordinary backpacks must not become corpses'); Tile=originalTile\n";
    const int analyzerResult = luaL_dostring(lua, analyzer);
    const char* analyzerError = analyzerResult ? lua_tostring(lua, -1) : nullptr;
    require(analyzerResult == 0, analyzerError ? analyzerError : "Analyzer corpse checks failed");
    body->setParent(nullptr); // createLoot may start decay; this isolated owner does not enter the world.
    monsterType.info.lookcorpse = 4251;
    std::unique_ptr<Item> classicBody(CorpseAccess::create(monster, &owner));
    require(classicBody && classicBody->getID() == 4251, "classic monster corpse must remain unchanged");

    const auto previous = boost::filesystem::current_path();
    const auto scratch = boost::filesystem::temp_directory_path() / boost::filesystem::unique_path("retired-loot-%%%%-%%%%");
    boost::filesystem::create_directory(scratch);
    {
        std::ofstream config((scratch / "config.lua").string());
        config << "rateLoot = 10\nmoneyRate = 1\nitemRarityLootChance = 0\nshowMonsterLoot = false\n";
    }
    boost::filesystem::current_path(scratch);
    const bool loaded = g_config.load();
    boost::filesystem::current_path(previous);
    boost::filesystem::remove_all(scratch);
    require(loaded, "isolated deterministic loot config must load");
    LootBlock classicLoot;
    classicLoot.id = 3264;
    classicLoot.countmax = 1;
    classicLoot.chance = MAX_LOOTCHANCE;
    LootBlock retiredLoot = classicLoot;
    retiredLoot.id = 3157;
    monsterType.info.lootItems = {classicLoot, retiredLoot};
    monsterType.createLoot(body->getContainer());
    const LootContents contents = LootTracker::collect(*body->getContainer());
    require(contents.items.size() == 1 && contents.items[0].id == 3264,
        "recovery corpse must retain classic loot while retired loot is rejected");
    monsterType.info.lookcorpse = 4318;
    Item* expiring = CorpseAccess::create(monster, &owner);
    DynamicTile expiryTile(101, 101, 7);
    expiryTile.internalAddThing(expiring);
    expiring->incrementReferenceCounter();
    expiring->setDuration(0);
    g_game.startDecay(expiring);
    require(expiring->isRemoved() && expiryTile.getThingIndex(expiring) == -1,
        "recovery corpse deadline must delete the container through real decay handling");
    g_game.cleanup(true);
    expiring->decrementReferenceCounter();
    g_moveEvents = nullptr;
}

int main(int argc, char** argv)
{
    try {
        require(Item::items.loadItems(), "production item definitions must load");
        const std::string mode = argc > 1 ? argv[1] : "create";
        if (mode == "create") creationTests();
        else if (mode == "transform") transformTests(false);
        else if (mode == "set-id") transformTests(true);
        else if (mode == "lookup") lookupTests();
        else if (mode == "clone") cloneTests();
        else if (mode == "container-clone") containerCloneTests();
        else if (mode == "lua") luaTests();
        else if (mode == "weapons") weaponTests();
        else if (mode == "corpse") corpseTests();
        else throw std::runtime_error("unknown test mode");
        std::cout << "PASS: retired items " << mode << '\n';
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
