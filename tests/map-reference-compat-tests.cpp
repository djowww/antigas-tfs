#include "otpch.h"
#include "game.h"
#include "configmanager.h"
#include "scheduler.h"
#include "databasetasks.h"
#include "rsa.h"
#include "iomap.h"
#include "iomapserialize.h"
#include "teleport.h"
#include "luascript.h"
#include "bed.h"
#include "container.h"
#include "monster.h"
#include "spells.h"
#include "creatureevent.h"
#include "pugicast.h"
#include <boost/filesystem.hpp>
#include <fstream>
#include <stdexcept>
#include <set>

// Same isolated globals as retired-map-tests: no services, DB connection or players.
DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;
extern LuaEnvironment g_luaEnvironment;
extern Spells* g_spells;
extern CreatureEvents* g_creatureEvents;

class FixtureMap : public Map
{
    public:
        uint32_t loadedWidth() const { return width; }
        uint32_t loadedHeight() const { return height; }
};

class FixtureHouseLoader : public IOMapSerialize
{
    public:
        using IOMapSerialize::loadItem;
};

static void require(bool condition, const std::string& message)
{
    if (!condition) throw std::runtime_error(message);
}

template<typename T> static void number(std::string& bytes, T value)
{
    bytes.append(reinterpret_cast<const char*>(&value), sizeof(value));
}

static std::string node(uint8_t kind, const std::string& props, const std::string& children = "")
{
    std::string result(1, char(0xFE));
    result += char(kind);
    for (unsigned char byte : props) {
        if (byte >= 0xFD) result += char(0xFD);
        result += char(byte);
    }
    return result + children + char(0xFF);
}

static std::string item(uint16_t id, uint16_t movementId = 0)
{
    std::string props;
    number(props, id);
    if (movementId) {
        props += char(OTBM_ATTR_MOVEMENT_ID);
        number(props, movementId);
    }
    return node(OTBM_ITEM, props);
}

static std::string area(uint16_t x, uint16_t y, uint8_t z, const std::string& tiles)
{
    std::string props;
    number(props, x);
    number(props, y);
    number(props, z);
    return node(OTBM_TILE_AREA, props, tiles);
}

static std::string tile(uint8_t x, uint8_t y, const std::string& objects)
{
    std::string props;
    number(props, x);
    number(props, y);
    return node(OTBM_TILE, props, objects);
}

static void inspectDefinitions()
{
    for (uint16_t id = 4874; id <= 4880; ++id) {
        const ItemType& type = Item::items.getItemType(id);
        require(type.id == id && !type.isGroundTile(), "reference swamp border must remain an overlay: " + std::to_string(id));
        require(type.alwaysOnTop && type.alwaysOnTopOrder == 1, "reference Clip border must use layer1: " + std::to_string(id));
        require(!type.blockSolid && !type.moveable && type.collisionEvent,
            "reference swamp border must be passable, fixed and retain CollisionEvent: " + std::to_string(id));
    }
    for (uint16_t id = 4809; id <= 4814; ++id) {
        const ItemType& type = Item::items.getItemType(id);
        require(type.id == id && type.isGroundTile() && !type.blockSolid && type.speed == 170,
            "reference shallow water must remain passable ground with speed170: " + std::to_string(id));
        require(!type.moveable && type.collisionEvent && type.fluidSource == FLUID_WATER,
            "reference shallow water must retain immobility and existing water callbacks: " + std::to_string(id));
    }
    const ItemType& teleporter = Item::items.getItemType(5022);
    require(teleporter.id == 5022 && teleporter.isTeleport() && teleporter.group == ITEM_GROUP_TELEPORT,
        "only the proven TeleportAbsolute5022 definition must create a native Teleport");
    require(teleporter.magicEffect == CONST_ME_NONE,
        "TeleportAbsolute support must preserve the current default effect");
    require(!Item::items.getItemType(5023).isTeleport(), "unproven relative5023 must retain its existing type");
    std::unique_ptr<Item> created(Item::CreateItem(5022));
    require(created && created->getID() == 5022 && created->getTeleport(),
        "real Item::CreateItem5022 must select the native Teleport class");
}

template<typename T> static T readNumber(std::ifstream& file, const std::string& field)
{
    T value;
    file.read(reinterpret_cast<char*>(&value), sizeof(value));
    require(bool(file), "house fixture must contain " + field);
    return value;
}

static uint64_t inspectHouseBlobs(FixtureMap& map, const std::string& path)
{
    std::ifstream file(path, std::ios::binary);
    require(bool(file), "house fixture must open");
    char magic[4];
    file.read(magic, sizeof(magic));
    require(bool(file) && std::string(magic, sizeof(magic)) == "AHB1", "house fixture must use AHB1 framing");
    const uint32_t rowCount = readNumber<uint32_t>(file, "row count");
    require(rowCount > 0 && rowCount <= 39127, "house fixture row count must fit the proven house tiles");
    std::set<Position> positions;
    uint64_t restoredItems = 0;
    for (uint32_t row = 0; row < rowCount; ++row) {
        const uint32_t houseId = readNumber<uint32_t>(file, "house ID");
        const uint32_t blobSize = readNumber<uint32_t>(file, "blob size");
        require(blobSize >= 12 && blobSize <= 1024 * 1024, "house fixture blob size must be bounded");
        std::string blob(blobSize, '\0');
        file.read(&blob[0], blobSize);
        require(bool(file), "house fixture blob must be complete");
        PropStream stream;
        stream.init(blob.data(), blob.size());
        uint16_t x, y;
        uint8_t z;
        uint32_t count;
        require(stream.read(x) && stream.read(y) && stream.read(z) && stream.read(count),
            "native tile_store header must deserialize");
        require(z < MAP_MAX_LAYERS && count > 0 && count <= 22, "house fixture item count must fit source maximum");
        const Position position(x, y, z);
        require(positions.insert(position).second, "house fixture must not duplicate a tile");
        Tile* tile = map.getTile(position);
        HouseTile* houseTile = dynamic_cast<HouseTile*>(tile);
        require(houseTile && houseTile->getHouse()->getId() == houseId,
            "house fixture position and current house ID must match the loaded map");
        for (uint32_t index = 0; index < count; ++index) {
            PropStream itemHeader = stream;
            uint16_t itemId;
            require(itemHeader.read(itemId), "house fixture must contain each item ID");
            const ItemType& type = Item::items.getItemType(itemId);
            require(type.id == itemId && type.group != ITEM_GROUP_DEPRECATED && type.moveable && !type.isGroundTile(),
                "house fixture may restore only active movable decoration omitted by IOMap");
            const size_t before = tile->getThingCount();
            std::set<const Item*> previousItems;
            if (const TileItemVector* items = tile->getItemList())
                for (const Item* item : *items) previousItems.insert(item);
            require(FixtureHouseLoader::loadItem(stream, tile), "native IOMapSerialize must load each decoration item");
            require(tile->getThingCount() == before + 1, "native house restore must add exactly one decoration item");
            unsigned added = 0;
            for (const Item* item : *tile->getItemList()) {
                if (previousItems.count(item)) continue;
                ++added;
                require(item->getID() == itemId, "native house restore must retain the exact decoration ID");
                const Container* container = item->getContainer();
                require(!container || container->empty(), "house templates must not import container inventories");
                const BedItem* bed = item->getBed();
                require(!bed || bed->getSleeper() == 0, "house templates must not import a historical sleeper");
            }
            require(added == 1, "native house restore must add one distinct decoration object");
            ++restoredItems;
        }
        require(stream.size() == 0, "native house parser must consume the entire tile_store blob");
    }
    require(file.peek() == std::ifstream::traits_type::eof(), "house fixture must not contain trailing bytes");
    std::cout << "HOUSE_BLOBS rows=" << rowCount << " restored_movable_decoration=" << restoredItems << '\n';
    return restoredItems;
}

static unsigned forbiddenPlacementIoCalls = 0;

static int denyPlacementIo(lua_State* state)
{
    ++forbiddenPlacementIoCalls;
    return luaL_error(state, "Database/timer access is forbidden in isolated spawn binding validation");
}

struct PlacementScriptScope
{
    Spells spells;
    CreatureEvents creatureEvents;
    Spells* previousSpells = g_spells;
    CreatureEvents* previousCreatureEvents = g_creatureEvents;
    PlacementScriptScope() { g_spells = &spells; g_creatureEvents = &creatureEvents; }
    ~PlacementScriptScope() { g_spells = previousSpells; g_creatureEvents = previousCreatureEvents; }
};

static void inspectSpawnBindings(FixtureMap& map, const std::string& path)
{
    // Exact private threshold in src/spawn.cpp; no historical assumption.
    static constexpr uint32_t minimumSpawnInterval = 1000;
    require(g_vocations.loadFromXml(), "native vocation definitions must load for monster spell parsing");
    require(g_luaEnvironment.initState(), "isolated spawn binding Lua state must initialize");
    lua_State* lua = g_luaEnvironment.getLuaState();
    lua_pushcfunction(lua, denyPlacementIo);
    lua_setglobal(lua, "__denyPlacementIo");
    require(luaL_dostring(lua, "for k in pairs(db) do db[k] = __denyPlacementIo end; addEvent = __denyPlacementIo; stopEvent = __denyPlacementIo") == 0,
        "isolated placement validation must block Lua database and timer calls");
    PlacementScriptScope scripts;
    require(g_luaEnvironment.loadFile("data/global.lua") == 0, "production Lua definitions must load without database/timer access");
    require(scripts.spells.loadFromXml(), "production spell definitions must load for native monster types");
    require(scripts.creatureEvents.loadFromXml(), "production creature event definitions must load without starting events");
    require(g_monsters.loadFromXml(), "production monster definitions must load");
    require(forbiddenPlacementIoCalls == 0, "loading spawn definitions must not attempt database or timer access");

    pugi::xml_document document;
    require(bool(document.load_file(path.c_str())), "candidate spawn XML must parse natively");
    const pugi::xml_node root = document.child("spawns");
    require(bool(root), "candidate spawn XML must have a spawns root");
    std::map<std::string, std::unique_ptr<Monster>> monsters;
    uint64_t total = 0, centerOkay = 0, fallbackOkay = 0, unbound = 0, npcs = 0, npcMissing = 0;
    // Same complete candidate set as Map::placeCreature(extendedPos=true).
    // The production method shuffles the order; existence of an admissible
    // position is order independent. No creature is inserted or relocated here.
    static const int offsets[12][2] = {
        {0,-2},{-1,-1},{0,-1},{1,-1},{-2,0},{-1,0},{1,0},{2,0},{-1,1},{0,1},{1,1},{0,2}
    };
    for (const auto& group : root.children()) {
        const uint16_t cx = pugi::cast<uint16_t>(group.attribute("centerx").value());
        const uint16_t cy = pugi::cast<uint16_t>(group.attribute("centery").value());
        const uint8_t cz = pugi::cast<uint16_t>(group.attribute("centerz").value());
        for (const auto& child : group.children()) {
            const Position position(
                cx + pugi::cast<uint16_t>(child.attribute("x").value()),
                cy + pugi::cast<uint16_t>(child.attribute("y").value()), cz);
            if (strcasecmp(child.name(), "npc") == 0) {
                ++npcs;
                if (!map.getTile(position)) {
                    ++npcMissing;
                    std::cout << "SPAWN_UNBOUND kind=npc name=" << child.attribute("name").value()
                        << " x=" << position.x << " y=" << position.y << " z=" << unsigned(position.z) << " reason=missing-forced-center-tile\n";
                }
                continue;
            }
            if (strcasecmp(child.name(), "monster") != 0) continue;
            ++total;
            const std::string name = asLowerCaseString(child.attribute("name").as_string());
            auto found = monsters.find(name);
            if (found == monsters.end()) {
                MonsterType* type = g_monsters.getMonsterType(name);
                found = monsters.emplace(name, std::unique_ptr<Monster>(type ? new Monster(type) : nullptr)).first;
            }
            const std::unique_ptr<Monster>& monster = found->second;
            const uint32_t interval = pugi::cast<uint32_t>(child.attribute("spawntime").value()) * 1000;
            Tile* center = map.getTile(position);
            const ReturnValue centerResult = center && monster ? center->queryAdd(0, *monster, 1, FLAG_PLACECHECK) : RETURNVALUE_NOTPOSSIBLE;
            if (monster && interval > minimumSpawnInterval
                && (centerResult == RETURNVALUE_NOERROR || centerResult == RETURNVALUE_PLAYERISNOTINVITED)) {
                ++centerOkay;
                continue;
            }
            bool fallback = false;
            const bool centerPz = center && center->hasFlag(TILESTATE_PROTECTIONZONE);
            if (monster && interval > minimumSpawnInterval) {
                for (const auto& offset : offsets) {
                    Tile* tile = map.getTile(uint16_t(position.x + offset[0]), uint16_t(position.y + offset[1]), position.z);
                    if (!tile || (centerPz && !tile->hasFlag(TILESTATE_PROTECTIONZONE))) continue;
                    if (tile->queryAdd(0, *monster, 1, FLAG_PLACECHECK) == RETURNVALUE_NOERROR) {
                        fallback = true;
                        break;
                    }
                }
            }
            if (fallback) ++fallbackOkay;
            else {
                ++unbound;
                std::cout << "SPAWN_UNBOUND kind=monster name=" << name << " x=" << position.x
                    << " y=" << position.y << " z=" << unsigned(position.z) << " reason="
                    << (!monster ? "missing-native-definition" : interval <= minimumSpawnInterval ? "invalid-native-interval" : "no-admissible-native-placement") << '\n';
            }
        }
    }
    require(forbiddenPlacementIoCalls == 0, "spawn binding checks must not attempt database or timer access");
    std::cout << "SPAWN_BINDINGS monsters=" << total << " center_ok=" << centerOkay << " native_fallback_ok=" << fallbackOkay
        << " unbound=" << unbound << " npcs=" << npcs << " npc_missing=" << npcMissing
        << " unique_monster_types=" << monsters.size() << " database_timer_calls=" << forbiddenPlacementIoCalls << '\n';
    require(total > 0 && unbound == 0 && npcMissing == 0,
        "all retained monster/NPC entries must bind to the selected map through native placement rules");
}

static void inspectWorld(const std::string& path, const std::string& houseBlobs, const std::string& spawns)
{
    FixtureMap map;
    IOMap reader;
    require(reader.loadMap(&map, path), "native IOMap must load the complete candidate: " + reader.getLastErrorString());
    require(map.loadedWidth() == 65000 && map.loadedHeight() == 65000,
        "full candidate must preserve the current source header dimensions65000");
    require(map.houses.getHouses().size() == 861, "full candidate must preserve all861 current house IDs");
    uint64_t houseTiles = 0;
    for (const auto& entry : map.houses.getHouses()) houseTiles += entry.second->getTiles().size();
    require(houseTiles == 39127, "full candidate must contain all39127 source house tiles");
    const Town* rook = map.towns.getTown(uint32_t(11));
    require(rook && rook->getName() == "Rookgaard" && rook->getTemplePosition() == Position(32097, 32219, 7),
        "town11 must retain Rookgaard temple32097,32219,7 from the saved native metadata");
    Tile* temple = map.getTile(rook->getTemplePosition());
    require(temple && temple->getGround() && !temple->hasProperty(CONST_PROP_BLOCKSOLID),
        "reset position must have an existing passable temple tile");
    Tile* source = map.getTile(33328, 32184, 5);
    require(source && source->getTeleportItem() && source->getTeleportItem()->getID() == 5022
        && source->getTeleportItem()->getDestPos() == Position(33290, 32481, 6),
        "full candidate must load the exact proven TeleportAbsolute5022 destination33290,32481,6");
    require(map.getTile(33290, 32481, 6) != nullptr, "full candidate must contain the teleport destination");
    for (const Position arena : {Position(31922, 31435, 7), Position(31922, 31451, 7), Position(31922, 31466, 7)})
        require(map.getTile(arena) == nullptr, "retired custom arena destinations must be absent");

    uint64_t tiles = 0, grounds = 0, objects = 0;
    uint32_t maximumStack = 0;
    // Bounds and count are proved by the independent full SEC/OTBM census.
    // Leaf traversal avoids running services or allocating another world.
    for (uint32_t x = 31872; x <= 33407; x += FLOOR_SIZE) {
        for (uint32_t y = 31488; y <= 33023; y += FLOOR_SIZE) {
            const QTreeLeafNode* leaf = map.getQTNode(x, y);
            if (!leaf) continue;
            for (uint8_t z = 0; z < MAP_MAX_LAYERS; ++z) {
                const Floor* floor = leaf->getFloor(z);
                if (!floor) continue;
                for (uint32_t dx = 0; dx < FLOOR_SIZE; ++dx) {
                    for (uint32_t dy = 0; dy < FLOOR_SIZE; ++dy) {
                        const Tile* tile = floor->tiles[dx][dy];
                        if (!tile) continue;
                        ++tiles;
                        if (tile->getGround()) ++grounds;
                        objects += tile->getThingCount();
                        maximumStack = std::max<uint32_t>(maximumStack, tile->getThingCount());
                    }
                }
            }
        }
    }
    require(tiles == 7849464, "native complete world must retain all7849464 source tiles");
    uint64_t houseRestored = 0;
    if (!houseBlobs.empty()) houseRestored = inspectHouseBlobs(map, houseBlobs);
    if (!spawns.empty()) inspectSpawnBindings(map, spawns);
    std::cout << "WORLD_NATIVE tiles=" << tiles << " ground_tiles=" << grounds << " objects_before_house_restore=" << objects
        << " maximum_stack_before_house_restore=" << maximumStack << " houses=" << map.houses.getHouses().size()
        << " house_tiles=" << houseTiles << " towns=" << map.towns.getTowns().size()
        << " restored_house_decoration=" << houseRestored << '\n';
    std::cout << "PASS: complete native world loaded without DB, NPCs, players or network services\n";
}

int main(int argc, char** argv)
{
    boost::filesystem::path scratch;
    try {
        require(Item::items.loadItems(), "native definitions must load, including the proven TeleportAbsolute5022 flag");
        inspectDefinitions();
        lua_State* lua = luaL_newstate();
        require(lua != nullptr, "isolated Lua state must open");
        luaL_openlibs(lua);
        const int luaLoad = luaL_loadfile(lua, "tests/classic-decorative-chests.lua");
        const int luaResult = luaLoad == 0 ? lua_pcall(lua, 0, 0, 0) : luaLoad;
        const std::string luaError = luaResult == 0 ? "" : lua_tostring(lua, -1);
        lua_close(lua);
        require(luaResult == 0, "decorative/quest chest behavior: " + luaError);
        if (argc > 1) {
            require(argc >= 3 && argc % 2 == 1 && std::string(argv[1]) == "--map",
                "usage: map-reference-compat-tests [--map candidate.otbm [--houses templates.ahb] [--spawns spawns.xml]]");
            std::string houses, spawns;
            for (int index = 3; index < argc; index += 2) {
                const std::string option = argv[index];
                if (option == "--houses" && houses.empty()) houses = argv[index + 1];
                else if (option == "--spawns" && spawns.empty()) spawns = argv[index + 1];
                else require(false, "unknown or duplicate complete-world option");
            }
            inspectWorld(argv[2], houses, spawns);
            return 0;
        }

        // Exact five-byte destination decoded from the legacy signed integer.
        static const uint16_t destinationX = 33290, destinationY = 32481;
        static const uint8_t destinationZ = 6;
        std::string destination;
        number(destination, destinationX);
        number(destination, destinationY);
        number(destination, destinationZ);
        require(destination.size() == 5, "OTBM teleport destination must occupy exactly five bytes");
        std::string teleportProps;
        number(teleportProps, uint16_t(5022));
        teleportProps += char(OTBM_ATTR_TELE_DEST);
        teleportProps += destination;

        // Real raw order: ground4690 then Clip4874. Ground MovementID stays1000.
        std::string syntheticTiles = tile(0, 0, item(4690, 1000) + item(4874));
        // A22-object tile checks that the known candidate maximum is not truncated.
        std::string highStack = item(4690);
        for (unsigned i = 1; i < 22; ++i) highStack += item(2358);
        syntheticTiles += tile(1, 0, highStack);

        std::string mapData = area(100, 100, 7, syntheticTiles);
        mapData += area(33328, 32184, 5, tile(0, 0, item(486) + node(OTBM_ITEM, teleportProps)));
        mapData += area(destinationX, destinationY, destinationZ, tile(0, 0, item(486)));
        std::string header;
        number(header, uint32_t(2));
        number(header, uint16_t(65535));
        number(header, uint16_t(65535));
        number(header, uint32_t(3));
        number(header, uint32_t(3));
        const std::string fixture = "OTBM" + node(OTBM_ROOTV1, header, node(OTBM_MAP_DATA, "", mapData));
        scratch = boost::filesystem::temp_directory_path() / boost::filesystem::unique_path("map-reference-%%%%-%%%%.otbm");
        {
            std::ofstream file(scratch.string(), std::ios::binary);
            require(bool(file), "temporary native fixture must open");
            file.write(fixture.data(), fixture.size());
            require(bool(file), "temporary native fixture must be fully written");
        }

        FixtureMap map;
        IOMap reader;
        const bool loaded = reader.loadMap(&map, scratch.string());
        require(loaded, "native IOMap must load the reference fixture: " + reader.getLastErrorString());
        require(map.loadedWidth() == 65535 && map.loadedHeight() == 65535, "native loader must preserve header dimensions65535");
        Tile* swamp = map.getTile(100, 100, 7);
        require(swamp && swamp->getGround() && swamp->getGround()->getID() == 4690,
            "ground4690 must survive loading a following border4874");
        require(swamp->getGround()->getMovementId() == 1000, "original ground MovementID1000 must survive native loading");
        require(swamp->getThingCount() == 2 && swamp->getItemList() && swamp->getItemList()->size() == 1,
            "native tile must keep one ground and one distinct border");
        Item* border = swamp->getItemList()->at(0);
        require(border->getID() == 4874 && border->isAlwaysOnTop() && !border->isGroundTile() && !border->isBlocking(),
            "native border4874 must persist as a passable overlay");
        Tile* stack = map.getTile(101, 100, 7);
        require(stack && stack->getThingCount() == 22 && stack->getItemList() && stack->getItemList()->size() == 21,
            "native IOMap must preserve all22 source objects without truncating the stack");

        Tile* source = map.getTile(33328, 32184, 5);
        require(source && source->getTeleportItem(), "source tile must retain a native teleporter5022");
        const Teleport* teleport = source->getTeleportItem();
        require(teleport->getID() == 5022 && teleport->getDestPos() == Position(destinationX, destinationY, destinationZ),
            "native five-byte OTBM destination must remain33290,32481,6");
        require(map.getTile(destinationX, destinationY, destinationZ) != nullptr,
            "fixture must contain the exact decoded destination tile");
        boost::filesystem::remove(scratch);
        std::cout << "PASS: native reference definitions, Clip/ground retention, MovementID1000, stack22 and TeleportAbsolute5022 destination33290,32481,6\n";
        return 0;
    } catch (const std::exception& error) {
        if (!scratch.empty()) boost::filesystem::remove(scratch);
        std::cerr << "FAIL: " << error.what() << '\n';
        return 1;
    }
}
