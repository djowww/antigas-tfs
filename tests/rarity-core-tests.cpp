#include "otpch.h"
#include "game.h"
#include "configmanager.h"
#include "movement.h"
#include "events.h"
#include "creatureevent.h"
#include "weapons.h"
#include "scheduler.h"
#include "databasetasks.h"
#include "rsa.h"
#include "tools.h"
#include "npc.h"
#include "behaviourdatabase.h"
#include "loot.h"
#include "groundrarity.h"
#include "actions.h"
#include "spells.h"
#include "housetile.h"
#include "house.h"
#include <boost/filesystem.hpp>
#include <fstream>
#include <stdexcept>
#include <cmath>

// Use the production core without starting listeners, threads, a database or the world map.
DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;
extern MoveEvents* g_moveEvents;
extern Events* g_events;
extern CreatureEvents* g_creatureEvents;
extern LuaEnvironment g_luaEnvironment;

static unsigned checks = 0;
static void require(bool success, const char* message)
{
	++checks;
	if (!success) {
		throw std::runtime_error(message);
	}
}

static void luaCheck(const std::string& script)
{
	lua_State* state = g_luaEnvironment.getLuaState();
	if (luaL_dostring(state, script.c_str()) != 0) {
		throw std::runtime_error(lua_tostring(state, -1));
	}
	++checks;
}

static void setLootChance(int32_t chance)
{
	const boost::filesystem::path original = boost::filesystem::current_path();
	const boost::filesystem::path scratch = boost::filesystem::temp_directory_path() / boost::filesystem::unique_path("antigas-rarity-%%%%-%%%%");
	boost::filesystem::create_directory(scratch);
	{
		std::ofstream config((scratch / "config.lua").string());
		config << "itemRarityLootChance = " << chance << "\nrateLoot = 1\n";
	}
	boost::filesystem::current_path(scratch);
	const bool loaded = g_config.load();
	boost::filesystem::current_path(original);
	boost::filesystem::remove_all(scratch);
	require(loaded, "isolated loot config must load");
}

static uint16_t findType(const std::function<bool(const ItemType&)>& predicate)
{
	for (size_t id = 1; id < Item::items.size(); ++id) {
		const ItemType& type = Item::items[id];
		if (type.id && type.group != ITEM_GROUP_DEPRECATED && predicate(type)) {
			return type.id;
		}
	}
	throw std::runtime_error("required item category missing from items.srv");
}

static Item* equip(Player& player, uint16_t id, slots_t slot, ItemRarityBonus_t bonus, uint8_t value,
	uint8_t subtype = 0, ItemRarity_t tier = ITEM_RARITY_UNCOMMON)
{
	Item* item = Item::CreateItem(id);
	require(item != nullptr, "equipment must be created");
	item->setRarityData(tier, bonus, value, subtype);
	static_cast<Cylinder&>(player).internalAddThing(slot, item);
	require(g_moveEvents->onPlayerEquip(&player, item, slot, true) == 1, "equip check must succeed");
	require(!player.isItemRarityEnabled(slot), "equip check must not apply bonuses");
	g_moveEvents->onPlayerEquip(&player, item, slot, false);
	return item;
}

static void unequip(Player& player, Item* item, slots_t slot)
{
	static_cast<Cylinder&>(player).removeThing(item, item->getItemCount());
	g_moveEvents->onPlayerDeEquip(&player, item, slot);
	delete item;
}

static void lootTests()
{
	const size_t initial = LootTracker::size();
	Group group = {};
	Player owner(nullptr);
	owner.setGroup(&group);
	owner.setID();
	owner.setGUID(990001);
	owner.setName("Loot Fixture Owner");
	DynamicTile ground(100, 100, 7);
	owner.setParent(&ground);
	std::unique_ptr<Container> corpse(Item::CreateItem(2853)->getContainer());
	corpse->setParent(&ground);
	require(LootTracker::collect(*corpse).items.empty(), "empty corpse must not invent packaging loot");
	Container* bag = Item::CreateItem(2853)->getContainer();
	Item* sword = Item::CreateItem(3264);
	sword->setRarityData(ITEM_RARITY_LEGENDARY, ITEM_RARITY_BONUS_ATTACK, 4, 0);
	bag->internalAddThing(sword);
	corpse->internalAddThing(bag);
	corpse->internalAddThing(Item::CreateItem(3031, 37));
	const LootContents contents = LootTracker::collect(*corpse);
	require(contents.items.size() == 2 && contents.tier == 4, "loot must flatten generated bag and retain maximum rarity");
	bool sawSword = false, sawGold = false;
	for (const LootEntry& entry : contents.items) {
		sawSword |= entry.id == 3264 && entry.count == 1 && entry.tier == 4;
		sawGold |= entry.id == 3031 && entry.count == 37 && entry.tier == 0;
	}
	require(sawSword && sawGold, "structured loot must describe exact generated item instances and stack counts");
	const uint64_t first = LootTracker::track(*corpse, {990001, 990002}, 4);
	require(first != 0 && LootTracker::track(*corpse, {990003}, 1) == first, "corpse token must remain stable and cannot replace eligible recipients");
	require(LootTracker::eligible(corpse.get(), 990001) && LootTracker::eligible(corpse.get(), 990002), "owner and original party member must be eligible");
	require(!LootTracker::eligible(corpse.get(), 990003), "bystander and later party member must not become eligible");
	std::unique_ptr<Container> second(Item::CreateItem(2853)->getContainer());
	second->setParent(&ground);
	const uint64_t other = LootTracker::track(*second, {990001}, 1);
	require(other != first, "same-tile identical corpses must receive distinct tokens");
	std::unique_ptr<Item> clone(corpse->clone());
	require(LootTracker::token(clone->getContainer()) == 0, "clone must not inherit transient unopened identity");
	DynamicTile destination(101, 100, 7);
	corpse->setParent(&destination);
	require(LootTracker::token(corpse.get()) == first, "moving a live corpse must preserve its instance token");
	const std::string payload = LootTracker::notification(*corpse, contents, "a black knight", first, owner);
	require(payload.size() < 8192 && payload.find("\"stackpos\":-1") != std::string::npos, "offscreen log must be valid while refusing a visible marker");
	lua_State* lua = g_luaEnvironment.getLuaState();
	require(luaL_dofile(lua, "data/lib/core/json.lua") == 0, "production JSON decoder must load");
	lua_pushlstring(lua, payload.data(), payload.size());
	lua_setglobal(lua, "lootFixtureJson");
	luaCheck("local p=json.decode(lootFixtureJson); assert(p.event=='loot' and p.tier==4 and #p.items==2 and p.position.x==101 and p.unopened==false)");
	LootContents large;
	large.tier = 5;
	for (unsigned i = 0; i < 128; ++i) {
		large.items.push_back({3264, 1, 5, std::string(160, static_cast<char>(0xE9))});
	}
	const std::string bounded = LootTracker::notification(*corpse, large, std::string(80, '\\'), first, owner);
	require(bounded.size() < 8192, "fully escaped maximum-size loot must respect real NetworkMessage string limit");
	lua_pushlstring(lua, bounded.data(), bounded.size());
	lua_setglobal(lua, "lootFixtureJson");
	luaCheck("local p=json.decode(lootFixtureJson); assert(#p.items>0 and p.omitted>0 and #p.items+p.omitted==128 and p.tier==5)");
	LootTracker::handleRequest(owner, "{\"event\":\"opened\",\"id\":\"" + std::to_string(first) + "\"}");
	LootTracker::handleRequest(owner, std::string(10000, 'H'));
	require(LootTracker::token(corpse.get()) == first, "malformed handshakes and forged opened messages must not change corpse state");
	LootTracker::opened(*corpse);
	require(!LootTracker::token(corpse.get()) && LootTracker::token(second.get()) == other, "opening one identical corpse must preserve the other");
	second.reset();
	require(LootTracker::size() == initial, "destroying tracked corpse must erase dangling index immediately");

	// Exercise the real native use handler, including house permission and invalid window ids.
	extern Spells* g_spells;
	Spells spells;
	Spells* oldSpells = g_spells;
	g_spells = &spells;
	Actions actions;
	LootTracker::track(*corpse, {990001}, 4);
	require(actions.canUse(&owner, Position(200, 200, 7)) == RETURNVALUE_TOOFARAWAY, "far-away native use must fail before opening");
	require(LootTracker::token(corpse.get()) != 0, "failed range check must preserve unopened state");
	actions.useItem(&owner, corpse->getPosition(), 255, corpse.get());
	require(LootTracker::token(corpse.get()) != 0 && owner.getContainerID(corpse.get()) == -1, "invalid container window must not acknowledge opening");
	House house(900001);
	HouseTile houseTile(102, 100, 7, &house);
	corpse->setParent(&houseTile);
	require(!actions.useItem(&owner, corpse->getPosition(), 0, corpse.get()), "uninvited player must fail native house container use");
	require(LootTracker::token(corpse.get()) != 0, "permission failure must preserve unopened state");
	corpse->setParent(&destination);
	require(actions.useItem(&owner, corpse->getPosition(), 0, corpse.get()), "permitted native container open must succeed");
	require(!LootTracker::token(corpse.get()) && owner.getContainerID(corpse.get()) == 0, "successful registered open alone must consume unopened marker");
	owner.closeContainer(0);
	g_spells = oldSpells;

	// Publish through actual owner/party selection, excluding invited or unrelated players.
	Player member(nullptr), outsider(nullptr);
	member.setGroup(&group);
	member.setGUID(990002);
	member.setID();
	member.setName("Loot Fixture Member");
	outsider.setGroup(&group);
	outsider.setGUID(990003);
	outsider.setID();
	outsider.setName("Loot Fixture Outsider");
	Party party(&owner);
	party.getMembers().push_back(&member);
	member.setParty(&party);
	g_game.addPlayer(&owner);
	corpse->setCorpseOwner(owner.getID());
	LootTracker::publish(*corpse, "a black knight");
	require(LootTracker::eligible(corpse.get(), owner.getGUID()) && LootTracker::eligible(corpse.get(), member.getGUID()), "actual publisher must snapshot owner and party");
	require(!LootTracker::eligible(corpse.get(), outsider.getGUID()), "actual publisher must never grant bystander loot access");
	member.setParty(nullptr);
	owner.setParty(nullptr);
	g_game.removePlayer(&owner);
	LootTracker::forget(corpse.get());

	std::vector<std::unique_ptr<Container>> flood;
	for (unsigned i = 0; i < 4100; ++i) {
		flood.emplace_back(Item::CreateItem(2853)->getContainer());
		LootTracker::track(*flood.back(), {990001}, 1);
	}
	require(LootTracker::size() <= 4096, "unopened registry must have a hard memory bound");
	require(!LootTracker::token(flood.front().get()) && LootTracker::token(flood.back().get()), "pruning must evict oldest tokens before recent loot");
	flood.clear();
	require(LootTracker::size() == initial, "mass corpse destruction must leave no dangling tracking entries");

	std::unique_ptr<Container> overflowing(Item::CreateItem(2853)->getContainer());
	for (unsigned i = 0; i < 140; ++i) {
		overflowing->internalAddThing(Item::CreateItem(3264));
	}
	const LootContents capped = LootTracker::collect(*overflowing);
	require(capped.items.size() == 128 && capped.omitted == 12, "oversized corpse must bound displayed entries and count omitted items");
}

static void groundRarityTests()
{
	Group group = {};
	Player observer(nullptr);
	observer.setGroup(&group);
	DynamicTile tile(123, 124, 7);
	const uint16_t groundId = findType([](const ItemType& type) { return type.isGroundTile() && !type.isMagicField(); });
	tile.internalAddThing(Item::CreateItem(groundId));
	require(GroundRarity::collect(tile, observer).empty(), "ordinary ground must not acquire equipment rarity");
	Item* rare = Item::CreateItem(3264);
	rare->setRarityData(ITEM_RARITY_LEGENDARY, ITEM_RARITY_BONUS_ATTACK, 4, 0);
	tile.internalAddThing(rare);
	Item* common = Item::CreateItem(3264);
	tile.internalAddThing(common);
	auto entries = GroundRarity::collect(tile, observer);
	require(entries.size() == 1 && entries[0].tier == 4, "ground stream must read rarity from the actual equipment instance");
	require(entries[0].stackpos == tile.getStackposOfItem(&observer, rare) && entries[0].stackpos != tile.getStackposOfItem(&observer, common), "identical rare/common sprites must retain distinct native stack identity");
	common->setRarityData(ITEM_RARITY_RARE, ITEM_RARITY_BONUS_ATTACK, 2, 0);
	entries = GroundRarity::collect(tile, observer);
	require(entries.size() == 2 && entries[0].tier == 2 && entries[1].tier == 4, "two rarities with identical sprites on one tile must stay distinct");
	const std::string description = GroundRarity::describe(tile.getPosition(), entries);
	lua_State* lua = g_luaEnvironment.getLuaState();
	const std::string json = '{' + description + '}';
	lua_pushlstring(lua, json.data(), json.size());
	lua_setglobal(lua, "groundFixtureJson");
	luaCheck("local p=json.decode(groundFixtureJson); assert(p.position.x==123 and p.position.y==124 and p.position.z==7 and #p.items==2 and p.items[1].itemId==p.items[2].itemId and p.items[1].stackpos~=p.items[2].stackpos)");
	Container* bag = Item::CreateItem(2853)->getContainer();
	Item* hidden = Item::CreateItem(3264);
	hidden->setRarityData(ITEM_RARITY_MYTHIC, ITEM_RARITY_BONUS_ATTACK, 5, 0);
	bag->internalAddThing(hidden);
	tile.internalAddThing(bag);
	entries = GroundRarity::collect(tile, observer);
	require(entries.size() == 2 && entries[0].tier == 2 && entries[1].tier == 4, "rarity inside a ground bag must never leak into its bag or visible ground stream");
	Player bystander(nullptr);
	bystander.setGroup(&group);
	const auto bystanderEntries = GroundRarity::collect(tile, bystander);
	require(GroundRarity::describe(tile.getPosition(), entries) == GroundRarity::describe(tile.getPosition(), bystanderEntries), "visible ground equipment must be colored for bystanders without loot-owner restrictions");
	const uint8_t before = entries.back().stackpos;
	tile.removeThing(common, 1);
	entries = GroundRarity::collect(tile, observer);
	require(entries.size() == 1 && entries[0].stackpos + 1 == before && entries[0].tier == 4, "removing a duplicate must immediately rebuild the surviving native stack index");
	delete common;
	tile.removeThing(rare, 1);
	bag->internalAddThing(rare);
	require(GroundRarity::collect(tile, observer).empty(), "picking equipment into a container must remove all ground rarity entries");
	bag->removeThing(rare, 1);
	tile.internalAddThing(rare);
	require(GroundRarity::collect(tile, observer).size() == 1, "existing rarity must reappear when equipment is dropped from a bag");
	rare->setIntAttr(ITEM_ATTRIBUTE_RARITY, 255);
	require(GroundRarity::collect(tile, observer).empty(), "invalid stored rarity metadata must never become a colored ground item");
	rare->setRarityData(ITEM_RARITY_UNCOMMON, ITEM_RARITY_BONUS_ATTACK, 1, 0);
	require(GroundRarity::collect(tile, observer).at(0).tier == 1, "in-place equipment rarity changes must update the stream");
	for (unsigned i = 0; i < 12; ++i) tile.internalAddThing(Item::CreateItem(3264));
	require(GroundRarity::collect(tile, observer).empty(), "equipment below native ten-thing tile limit must remain undisclosed");
	for (unsigned i = 0; i < 12; ++i) {
		Item* item = Item::CreateItem(3264);
		item->setRarityData(ITEM_RARITY_MYTHIC, ITEM_RARITY_BONUS_ATTACK, 5, 0);
		tile.internalAddThing(item);
	}
	entries = GroundRarity::collect(tile, observer);
	require(entries.size() == 9, "a ground tile plus oversized equipment stack may expose only nine equipment slots");
	for (const GroundRarityEntry& entry : entries) require(entry.stackpos < 10 && entry.tier == 5, "every transmitted stack slot must exist in the native tile frame");
	std::vector<GroundRarityEntry> overflow(10000, {65535, 9, 5});
	const std::string bounded = GroundRarity::describe(Position(65535, 65535, 15), overflow);
	require(bounded.size() < 1024, "oversized synthetic ground list must produce a packet safely below the 8192-byte limit");
	const std::string boundedJson = '{' + bounded + '}';
	lua_pushlstring(lua, boundedJson.data(), boundedJson.size());
	lua_setglobal(lua, "groundFixtureJson");
	luaCheck("local p=json.decode(groundFixtureJson); assert(#p.items==10 and p.position.z==15)");
	GroundRarity::handleRequest(observer, "S|1");
	GroundRarity::handleRequest(observer, std::string(10000, 'H'));
	GroundRarity::handleRequest(observer, "{\"event\":\"tile\",\"tier\":5}");
	require(GroundRarity::describe(tile.getPosition(), GroundRarity::collect(tile, observer)) == GroundRarity::describe(tile.getPosition(), entries), "unsolicited and forged ground messages must not mutate any ground equipment");
	GroundRarity::handleRequest(observer, "H|1");
	GroundRarity::handleRequest(observer, "H|1");
	GroundRarity::resetMap(observer);
	GroundRarity::resetSession(observer);
	require(GroundRarity::describe(tile.getPosition(), GroundRarity::collect(tile, observer)) == GroundRarity::describe(tile.getPosition(), entries), "handshake, map reset and session reset must leave actual world items unchanged");
}

static void groundRarityMovementTests()
{
	// Exercise the exact cache decision used by updateTile, without clocks or a
	// network connection: an unchanged native frame still emits a new binding.
	std::map<uint64_t, std::string> cache;
	const Position position(30123, 30124, 7);
	const std::vector<GroundRarityEntry> items = {{3264, 2, 4}, {3264, 3, 2}};
	const std::string first = GroundRarity::replaceTile(cache, position, items);
	require(!first.empty() && cache.size() == 1, "first visible native tile must produce a rarity frame");
	require(GroundRarity::replaceTile(cache, position, items) == first, "rapid reentry with identical position, sprite, stack and tier must immediately resend a frame without waiting for replay");
	require(GroundRarity::pruneCache(cache, [](const Position&) { return true; }).empty(), "still-visible cached frame must survive housekeeping");
	require(GroundRarity::replaceTile(cache, position, items) == first, "native replacement after housekeeping must still resend an unchanged frame");
	const auto removed = GroundRarity::pruneCache(cache, [](const Position&) { return false; });
	require(removed.size() == 1 && removed[0] == position && cache.empty(), "leaving view must immediately produce the exact removed tile for clearing");
	require(GroundRarity::replaceTile(cache, position, items) == first, "reentry after cache cleanup must immediately restore both identical-sprite rarities");
	const std::string clear = GroundRarity::replaceTile(cache, position, {});
	require(clear == GroundRarity::describe(position, {}) && cache.empty(), "a native tile that became common or empty must immediately emit an empty replacement frame");
	require(GroundRarity::replaceTile(cache, position, {}).empty(), "untracked common tiles must not generate redundant rarity traffic");
	for (uint16_t x = 1000; x < 1256; ++x) {
		require(!GroundRarity::replaceTile(cache, Position(x, 2000, 7), items).empty(), "visible rarity cache must admit its documented 256 tile limit");
	}
	require(cache.size() == 256 && GroundRarity::replaceTile(cache, position, items).empty(), "new tiles may not exceed the bounded rarity cache");
	const auto evicted = GroundRarity::pruneCache(cache, [](const Position& pos) { return pos.x >= 1004; });
	require(evicted.size() == 4 && cache.size() == 252, "movement must free offscreen cache slots before considering new native strips");
	require(GroundRarity::replaceTile(cache, position, items) == first && cache.size() == 253, "a previously full cache must immediately admit entering rarity after bounded pruning");

	// Compare all eight step directions, all floors and classic/custom viewports
	// against the set of newly visible native map coordinates.
	for (const auto& ranges : {std::make_pair(8, 6), std::make_pair(10, 7), std::make_pair(15, 8)}) {
		const int32_t width = 2 * (ranges.first + 1);
		const int32_t height = 2 * (ranges.second + 1);
		for (uint8_t floor = 0; floor < 16; ++floor) {
			const Position oldPos(30000, 30000, floor);
			for (int32_t dx = -1; dx <= 1; ++dx) {
				for (int32_t dy = -1; dy <= 1; ++dy) {
					if (!dx && !dy) continue;
					const Position newPos(uint16_t(oldPos.x + dx), uint16_t(oldPos.y + dy), floor);
					std::vector<GroundRarityMapStrip> strips;
					if (dy < 0) strips.push_back({oldPos.x - ranges.first, newPos.y - ranges.second, floor, width, 1});
					if (dy > 0) strips.push_back({oldPos.x - ranges.first, newPos.y + ranges.second + 1, floor, width, 1});
					if (dx < 0) strips.push_back({newPos.x - ranges.first, newPos.y - ranges.second, floor, 1, height});
					if (dx > 0) strips.push_back({newPos.x + ranges.first + 1, newPos.y - ranges.second, floor, 1, height});
					const auto coordinates = GroundRarity::stripPositions(strips);
					const std::set<Position> actual(coordinates.begin(), coordinates.end());
					require(actual.size() == coordinates.size() && coordinates.size() <= 400, "movement refresh must deduplicate native tiles and stay within two bounded edge strips");
					const int32_t firstFloor = floor <= 7 ? 0 : floor - 2;
					const int32_t lastFloor = floor <= 7 ? 7 : std::min<int32_t>(15, floor + 2);
					size_t entering = 0;
					for (int32_t z = firstFloor; z <= lastFloor; ++z) {
						const int32_t offset = int32_t(floor) - z;
						const int32_t oldLeft = oldPos.x - ranges.first + offset;
						const int32_t oldTop = oldPos.y - ranges.second + offset;
						for (int32_t x = newPos.x - ranges.first + offset; x < newPos.x - ranges.first + offset + width; ++x) {
							for (int32_t y = newPos.y - ranges.second + offset; y < newPos.y - ranges.second + offset + height; ++y) {
								if (x >= oldLeft && x < oldLeft + width && y >= oldTop && y < oldTop + height) continue;
								++entering;
								require(actual.count(Position(uint16_t(x), uint16_t(y), uint8_t(z))) == 1, "every entering native tile on every visible floor must be replayed immediately, including diagonal corners");
							}
						}
						// The player tile lies inside the old viewport, never in an entering strip.
						require(actual.count(Position(uint16_t(newPos.x + offset), uint16_t(newPos.y + offset), uint8_t(z))) == 0, "ordinary movement must not rescan unaffected viewport interiors");
					}
					require(entering > 0 && entering <= coordinates.size(), "each movement direction must include its newly visible native map margin");
				}
			}
		}
	}
	const GroundRarityMapStrip duplicate = {100, 101, 7, 18, 1};
	require(GroundRarity::stripPositions({duplicate, duplicate}).size() == 18 * 8, "overlapping native rectangles must never duplicate rarity frames");
	require(GroundRarity::stripPositions({{0, 0, 7, 1000000, 1}, {0, 0, 7, 32, 18}}).empty(), "invalid or full-viewport rectangles must not turn the walking path into an unbounded scan");
	require(GroundRarity::stripPositions({{0, 0, -1, 1, 1}, {0, 0, 16, 1, 1}}).empty(), "walking strips must reject invalid floors");
	const auto boundary = GroundRarity::stripPositions({{-8, -6, 7, 18, 1}, {65535, 65535, 7, 1, 18}});
	require(boundary.size() <= 18 * 8 + 18 * 8, "world-edge strip coordinates must remain bounded without unsigned wrapping");
}

int main()
{
	try {
		setLootChance(10000);
		require(Item::items.loadItems(), "production item definitions must load");
		require(g_vocations.loadFromXml(), "production vocations must load");
		require(g_luaEnvironment.initState(), "Lua environment must initialize for core callbacks");
		MoveEvents moves;
		Events events;
		CreatureEvents creatureEvents;
		g_moveEvents = &moves;
		g_events = &events;
		g_creatureEvents = &creatureEvents;
		Group group = {};
		Player player(nullptr);
		player.setGroup(&group);
		player.setID();
		LuaScriptInterface::pushUserdata<Player>(g_luaEnvironment.getLuaState(), &player);
		LuaScriptInterface::setMetatable(g_luaEnvironment.getLuaState(), -1, "Player");
		lua_setglobal(g_luaEnvironment.getLuaState(), "rarityPlayer");
		require(player.setVocation(4), "knight vocation must exist");

		const uint16_t sword = findType([](const ItemType& t) { return t.weaponType == WEAPON_SWORD && !t.stackable; });
		const uint16_t shield = findType([](const ItemType& t) { return t.weaponType == WEAPON_SHIELD && !t.stackable; });
		const uint16_t armor = findType([](const ItemType& t) { return (t.slotPosition & SLOTP_ARMOR) && !t.isContainer(); });
		const uint16_t legs = findType([](const ItemType& t) { return (t.slotPosition & SLOTP_LEGS) && !t.isContainer(); });
		const uint16_t boots = findType([](const ItemType& t) { return (t.slotPosition & SLOTP_FEET) && !t.isContainer(); });
		const uint16_t ring = findType([](const ItemType& t) { return (t.slotPosition & SLOTP_RING) && !t.isContainer(); });
		const uint16_t necklace = findType([](const ItemType& t) { return (t.slotPosition & SLOTP_NECKLACE) && !t.isContainer(); });
		const uint16_t wandId = findType([](const ItemType& t) { return t.weaponType == WEAPON_WAND; });
		const uint16_t bowId = findType([](const ItemType& t) { return t.weaponType == WEAPON_DISTANCE && t.ammoType != AMMO_NONE; });
		const uint16_t ammoId = findType([bowId](const ItemType& t) { return t.weaponType == WEAPON_AMMO && t.ammoType == Item::items[bowId].ammoType; });
		const uint16_t backpack = findType([](const ItemType& t) { return t.isContainer() && (t.slotPosition & SLOTP_BACKPACK); });

		Item* weapon = Item::CreateItem(sword);
		weapon->setRarityData(ITEM_RARITY_MYTHIC, ITEM_RARITY_BONUS_ATTACK, 5, 0);
	const uint32_t expectedExtraBonuses = weapon->getRarityExtraData();
	require(weapon->getRarityBonusCount() == 5, "mythic gear must carry exactly five rarity statuses");
	require(weapon->getRarityDescription().find("Bonus 5:") != std::string::npos,
		"rarity description must expose all statuses");
	require(!weapon->setRarityExtraData(0), "incomplete extra statuses must be rejected");
	require(!weapon->setRarityExtraData(1 | (1 << 5) | (2 << 10) | (3 << 15)),
		"duplicate extra statuses must be rejected");
		weapon->setIntAttr(ITEM_ATTRIBUTE_ATTACK, 47);
		require(weapon->getAttack() == 52, "refine base attack and rarity must add once");
		WeaponMelee melee(nullptr);
		const int32_t rareMeleeDamage = melee.getWeaponDamage(&player, nullptr, weapon, true);
		weapon->setRarityData(ITEM_RARITY_NONE, ITEM_RARITY_BONUS_NONE, 0, 0);
		require(rareMeleeDamage < melee.getWeaponDamage(&player, nullptr, weapon, true), "melee rarity must increase actual maximum damage");
		weapon->setRarityData(ITEM_RARITY_MYTHIC, ITEM_RARITY_BONUS_ATTACK, 5, 0);
		require(weapon->getDescription(1).find("Atk:52") != std::string::npos, "look must show effective attack");
		PropWriteStream saved;
		weapon->serializeAttr(saved);
		size_t size;
		const char* bytes = saved.getStream(size);
		PropStream loaded;
		loaded.init(bytes, size);
		Item* restored = Item::CreateItem(sword);
		require(restored->unserializeAttr(loaded), "serialized rarity must load");
		require(restored->getRarityTier() == ITEM_RARITY_MYTHIC && restored->getAttack() == 52, "rarity and refine must persist together");
	require(restored->getRarityBonusCount() == 5 && restored->getRarityExtraData() == expectedExtraBonuses,
		"all rarity statuses must persist with the item");
		Item* clone = restored->clone();
		require(clone->equals(restored), "clone must preserve rarity attributes");
	require(clone->getRarityExtraData() == expectedExtraBonuses, "clone must preserve extra rarity statuses");
		delete clone;
		delete restored;
		delete weapon;
		require(!Item::isValidRarityData(0), "zero rarity data must be rejected");
		require(!Item::isValidRarityData(5 | (3 << 8) | (5 << 16) | (255u << 24)), "invalid resistance index must be rejected");
		require(!Item::isValidRarityData(5 | (5 << 8) | (255u << 16)), "invalid skill magnitude must be rejected");

		Item* armorItem = equip(player, armor, CONST_SLOT_ARMOR, ITEM_RARITY_BONUS_MAX_HEALTH_PERCENT, 5);
		const int32_t hpBase = player.getDefaultStats(STAT_MAXHITPOINTS);
		require(player.getMaxHealth() == hpBase + static_cast<int32_t>(std::ceil(hpBase * .05)), "armor must add base health percentage");
		g_moveEvents->onPlayerEquip(&player, armorItem, CONST_SLOT_ARMOR, false);
		require(player.getMaxHealth() == hpBase + static_cast<int32_t>(std::ceil(hpBase * .05)), "repeated equip notification must not duplicate bonus");
		require(!player.isItemAbilityEnabled(CONST_SLOT_ARMOR), "rarity must not activate native item abilities");
		Item* legsItem = equip(player, legs, CONST_SLOT_LEGS, ITEM_RARITY_BONUS_MAX_MANA_PERCENT, 5);
		Item* bootsItem = equip(player, boots, CONST_SLOT_FEET, ITEM_RARITY_BONUS_SPEED_PERCENT, 10);
		luaCheck("assert(rarityPlayer:addExperience(" + std::to_string(Player::getExpForLevel(20)) + ", false))");
		const int32_t hpAfterLevel = player.getDefaultStats(STAT_MAXHITPOINTS);
		const int32_t manaAfterLevel = player.getDefaultStats(STAT_MAXMANAPOINTS);
		require(player.getMaxHealth() == hpAfterLevel + static_cast<int32_t>(std::ceil(hpAfterLevel * .05)), "health percentage must follow level changes");
		require(player.getMaxMana() == static_cast<uint32_t>(manaAfterLevel + std::ceil(manaAfterLevel * .05)), "mana percentage must follow level changes");
		require(player.getSpeed() == static_cast<int32_t>(player.getBaseSpeed() + std::round(player.getBaseSpeed() * .10)), "speed percentage must follow base speed changes");
		luaCheck("assert(rarityPlayer:removeExperience(" + std::to_string(Player::getExpForLevel(20)) + "))");
		require(player.getMaxHealth() == player.getDefaultStats(STAT_MAXHITPOINTS) + static_cast<int32_t>(std::ceil(player.getDefaultStats(STAT_MAXHITPOINTS) * .05)), "downgrade must refresh health bonus");
		luaCheck("assert(rarityPlayer:setMaxHealth(1000)); assert(rarityPlayer:getMaxHealth() == 1050); assert(rarityPlayer:setMaxMana(800)); assert(rarityPlayer:getMaxMana() == 840)");
		unequip(player, armorItem, CONST_SLOT_ARMOR);
		unequip(player, legsItem, CONST_SLOT_LEGS);
		unequip(player, bootsItem, CONST_SLOT_FEET);
		require(player.getMaxHealth() == player.getDefaultStats(STAT_MAXHITPOINTS), "health bonus must remove exactly after level changes");
		require(player.getMaxMana() == static_cast<uint32_t>(player.getDefaultStats(STAT_MAXMANAPOINTS)), "mana bonus must remove exactly");
		require(player.getSpeed() == static_cast<int32_t>(player.getBaseSpeed()), "speed bonus must remove exactly");

		Item* carriedArmor = equip(player, armor, CONST_SLOT_RIGHT, ITEM_RARITY_BONUS_MAX_HEALTH_PERCENT, 5);
		require(player.getMaxHealth() == player.getDefaultStats(STAT_MAXHITPOINTS), "carrying armor in hand must not grant armor bonus");
		unequip(player, carriedArmor, CONST_SLOT_RIGHT);
		const int32_t originalSkill = player.getSkillLevel(SKILL_SWORD);
	Item* ringItem = equip(player, ring, CONST_SLOT_RING, ITEM_RARITY_BONUS_SKILL, 5, SKILL_SWORD, ITEM_RARITY_MYTHIC);
		Item* necklaceItem = equip(player, necklace, CONST_SLOT_NECKLACE, ITEM_RARITY_BONUS_SKILL, 3, SKILL_SWORD);
	const uint32_t ringExtras = ringItem->getRarityExtraData();
		require(player.getSkillLevel(SKILL_SWORD) == originalSkill + 8, "ring and necklace skill bonuses must stack");
		unequip(player, necklaceItem, CONST_SLOT_NECKLACE);
		require(player.getSkillLevel(SKILL_SWORD) == originalSkill + 5, "removing necklace must preserve ring bonus");

		// Force the production transform path that replaces the Item instance.
		ItemType& targetType = Item::items.getItemType(necklace);
		const ItemTypes_t originalType = targetType.type;
		targetType.type = ITEM_TYPE_KEY;
		Item* transformed = g_game.transformItem(ringItem, necklace);
		require(transformed && transformed != ringItem, "test must exercise replacement transform");
	require(transformed->getRarityTier() == ITEM_RARITY_MYTHIC && transformed->getRarityExtraData() == ringExtras,
		"replacement transform must preserve rarity and all extra statuses");
		require(player.getSkillLevel(SKILL_SWORD) == originalSkill + 5, "old item removal must not remove replacement bonus");
		targetType.type = originalType;
		unequip(player, transformed, CONST_SLOT_RING);
		require(player.getSkillLevel(SKILL_SWORD) == originalSkill, "transformed bonus must remove once");

		armorItem = equip(player, armor, CONST_SLOT_ARMOR, ITEM_RARITY_BONUS_RESISTANCE, 5, 0);
		legsItem = equip(player, legs, CONST_SLOT_LEGS, ITEM_RARITY_BONUS_RESISTANCE, 5, 0);
		int32_t damage = 100;
		player.blockHit(nullptr, COMBAT_PHYSICALDAMAGE, damage, false, false);
		require(damage == 90, "matching resistance from armor and legs must sum to 10 percent");
		damage = 100;
		player.blockHit(nullptr, COMBAT_FIREDAMAGE, damage, false, false);
		require(damage == 100, "physical resistance must not reduce fire");
		unequip(player, armorItem, CONST_SLOT_ARMOR);
		unequip(player, legsItem, CONST_SLOT_LEGS);

		Item* shieldItem = Item::CreateItem(shield);
		shieldItem->setRarityData(ITEM_RARITY_RARE, ITEM_RARITY_BONUS_DEFENSE, 2, 0);
		shieldItem->setIntAttr(ITEM_ATTRIBUTE_DEFENSE, 30);
		require(shieldItem->getDefense() == 32, "shield refinement and rarity defense must add");
		delete shieldItem;
		WeaponWand wand(nullptr);
		pugi::xml_document wandConfig;
		pugi::xml_node wandNode = wandConfig.append_child("wand");
		wandNode.append_attribute("id") = wandId;
		wandNode.append_attribute("min") = 20;
		wandNode.append_attribute("max") = 20;
		require(wand.configureEvent(wandNode), "wand fixture must configure");
		Item* wandItem = Item::CreateItem(wandId);
		wandItem->setRarityData(ITEM_RARITY_MYTHIC, ITEM_RARITY_BONUS_ATTACK, 5, 0);
		require(wand.getWeaponDamage(&player, nullptr, wandItem) == -25, "wand rarity must affect actual damage");
		delete wandItem;
		Item* bowItem = equip(player, bowId, CONST_SLOT_RIGHT, ITEM_RARITY_BONUS_ATTACK, 5);
		Item* arrow = Item::CreateItem(ammoId, 1);
		WeaponDistance distance(nullptr);
		const int32_t rareDistanceDamage = distance.getWeaponDamage(&player, nullptr, arrow, true);
		bowItem->setRarityData(ITEM_RARITY_NONE, ITEM_RARITY_BONUS_NONE, 0, 0);
		require(rareDistanceDamage < distance.getWeaponDamage(&player, nullptr, arrow, true), "bow rarity must increase ammunition damage");
		delete arrow;
		unequip(player, bowItem, CONST_SLOT_RIGHT);

		MonsterType monster;
		LootBlock loot;
		loot.id = sword;
		loot.chance = MAX_LOOTCHANCE + 1;
		loot.countmax = 1;
		getRandomGenerator().seed(1729);
		unsigned tiers[6] = {};
		for (unsigned roll = 0; roll < 3000; ++roll) {
			auto items = monster.createLootItem(loot);
			require(items.size() == 1 && items.front()->hasRarity(), "100 percent rarity chance must mark eligible loot");
			++tiers[items.front()->getRarityTier()];
			require(items.front()->getRarityBonusCount() == items.front()->getRarityTier(),
				"generated status count must equal rarity tier");
			uint32_t seen = 0;
			for (uint8_t index = 0; index < items.front()->getRarityBonusCount(); ++index) {
				ItemRarityBonus_t type;
				uint8_t value, subtype;
				require(items.front()->getRarityBonus(index, type, value, subtype), "every generated status must decode");
				const uint8_t code = Item::getRarityBonusCode(type, subtype);
				require(code != 0 && (seen & (1u << code)) == 0, "a generated item may not repeat a status");
				if (index > 0) require(type != ITEM_RARITY_BONUS_ATTACK && type != ITEM_RARITY_BONUS_DEFENSE,
					"extra statuses may not duplicate gear-specific attack or defense");
				seen |= 1u << code;
			}
			delete items.front();
		}
		for (unsigned tier = 1; tier <= 5; ++tier) {
			require(tiers[tier] > 0, "every rarity tier must be reachable");
		}
		const unsigned expectedTiers[] = {0, 1500, 810, 420, 210, 60};
		for (unsigned tier = 1; tier <= 5; ++tier) {
			require(tiers[tier] > expectedTiers[tier] * .6 && tiers[tier] < expectedTiers[tier] * 1.4, "seeded rarity frequencies must match configured tier weights");
		}
		const uint16_t categoryIds[] = {armor, legs, boots, ring, necklace, shield, wandId};
		for (uint16_t id : categoryIds) {
			loot.id = id;
			for (unsigned roll = 0; roll < 60; ++roll) {
				auto items = monster.createLootItem(loot);
				require(items.size() == 1 && items.front()->hasRarity(), "each eligible equipment category must roll valid rarity");
				const Item* generated = items.front();
				const ItemRarityBonus_t bonus = generated->getRarityBonusType();
				if (id == armor || id == legs) {
					require(bonus >= ITEM_RARITY_BONUS_MAX_HEALTH_PERCENT && bonus <= ITEM_RARITY_BONUS_RESISTANCE, "armor pool must contain only health, mana and resistance");
				} else if (id == boots) {
					require(bonus == ITEM_RARITY_BONUS_SPEED_PERCENT && generated->getRarityBonusValue() >= 2 * generated->getRarityTier() - 1 && generated->getRarityBonusValue() <= 2 * generated->getRarityTier(), "boots speed must follow rarity band");
				} else if (id == ring || id == necklace) {
					require(bonus == ITEM_RARITY_BONUS_SKILL, "jewelry pool must contain only skills");
				} else {
					require(bonus == (id == shield ? ITEM_RARITY_BONUS_DEFENSE : ITEM_RARITY_BONUS_ATTACK), "weapon and shield pools must contain only their base stat");
				}
				delete generated;
			}
		}
		loot.id = backpack;
		auto containerLoot = monster.createLootItem(loot);
		require(containerLoot.size() == 1 && !containerLoot.front()->hasRarity(), "containers must not roll rarity");
		delete containerLoot.front();
		loot.id = ammoId;
		loot.countmax = 100;
		for (unsigned roll = 0; roll < 100; ++roll) {
			for (Item* ammo : monster.createLootItem(loot)) {
				require(!ammo->hasRarity(), "stackable ammunition must not receive rarity");
				delete ammo;
			}
		}
		setLootChance(0);
		loot.id = sword;
		auto commonLoot = monster.createLootItem(loot);
		require(commonLoot.size() == 1 && !commonLoot.front()->hasRarity(), "zero rarity chance must disable generation");
		delete commonLoot.front();

		Item* rareForSale = equip(player, sword, CONST_SLOT_LEFT, ITEM_RARITY_BONUS_ATTACK, 5);
		require(static_cast<Cylinder&>(player).getItemTypeCount(sword, -1) == 1, "quest count must include rare items");
		require(player.getItemTypeCount(sword, -1, true) == 0, "NPC sale count must exclude rare items");
		require(!player.removeItemOfType(sword, 1, -1, false, true), "NPC sale removal must protect rare items");
		require(player.getInventoryItem(CONST_SLOT_LEFT) == rareForSale, "failed sale must leave rare item intact");

		std::unique_ptr<Npc> npc(Npc::createNpc("aldee"));
		require(npc != nullptr, "real NPC definition must load without world map");
		npc->setCreatureFocus(&player);
		BehaviourDatabase npcRules(npc.get());
		const boost::filesystem::path npcFixture = boost::filesystem::temp_directory_path() / boost::filesystem::unique_path("antigas-npc-rarity-%%%%-%%%%.npc");
		{
			std::ofstream script(npcFixture.string());
			script << "{\nCount(" << sword << ")>=1,\"sell\" -> Amount=1,Price=7,Delete(" << sword << "),CreateMoney\n";
			script << "\"inspect\" -> SetQuestValue(900000,1)\n";
			script << "\"sale\",Count(" << sword << ")>=1 -> Amount=1,Price=7,Delete(" << sword << "),CreateMoney\n";
			script << "\"reverse\" -> Amount=1,Price=9,CreateMoney,Delete(" << sword << ")\n";
			script << "\"quest\",Count(" << sword << ")>=1 -> Amount=1,Delete(" << sword << "),SetQuestValue(900001,1)\n}\n";
		}
		{
			ScriptReader script;
			require(script.open(npcFixture.string()), "NPC fixture must open");
			require(npcRules.loadDatabase(script), "NPC fixture must parse with production parser");
			script.close();
		}
		boost::filesystem::remove(npcFixture);
		npcRules.react(SITUATION_NONE, &player, "inspect");
		int32_t storage = 0;
		require(player.getStorageValue(900000, storage) && storage == 1, "filtered Count before an unmatched word must allow dialogue fallback");
		const uint64_t initialMoney = player.getMoney();
		npcRules.react(SITUATION_NONE, &player, "sale");
		require(player.getInventoryItem(CONST_SLOT_LEFT) == rareForSale && player.getMoney() == initialMoney, "NPC sale with only rare items must neither remove nor pay");
		npcRules.react(SITUATION_NONE, &player, "reverse");
		require(player.getInventoryItem(CONST_SLOT_LEFT) == rareForSale && player.getMoney() == initialMoney, "CreateMoney before failed Delete must not pay");
		Container* bag = Item::CreateItem(backpack)->getContainer();
		require(bag != nullptr, "NPC common sale bag must be a container");
		static_cast<Cylinder&>(player).internalAddThing(CONST_SLOT_BACKPACK, bag);
		bag->internalAddThing(Item::CreateItem(sword));
		npcRules.react(SITUATION_NONE, &player, "sale");
		require(player.getInventoryItem(CONST_SLOT_LEFT) == rareForSale && static_cast<Cylinder&>(player).getItemTypeCount(sword, -1) == 1, "NPC sale must remove common copy and preserve rare copy");
		require(player.getMoney() == initialMoney + 7, "successful common sale must pay exactly once");
		npcRules.react(SITUATION_NONE, &player, "quest");
		require(static_cast<Cylinder&>(player).getItemTypeCount(sword, -1) == 0 && player.getStorageValue(900001, storage), "quest exchange must retain original item acceptance");

		const uint16_t nativeRingId = findType([](const ItemType& t) {
			return (t.slotPosition & SLOTP_RING) && t.transformEquipTo && Item::items[t.transformEquipTo].abilities &&
				Item::items[t.transformEquipTo].abilities->skills[SKILL_SWORD] > 0;
		});
		const uint16_t nativeActiveId = Item::items[nativeRingId].transformEquipTo;
		const int32_t nativeSwordBonus = Item::items[nativeActiveId].abilities->skills[SKILL_SWORD];
		const boost::filesystem::path nativeRoot = boost::filesystem::temp_directory_path() / boost::filesystem::unique_path("antigas-movements-rarity-%%%%-%%%%");
		const boost::filesystem::path nativeOriginal = boost::filesystem::current_path();
		boost::filesystem::create_directories(nativeRoot / "data/movements/lib");
		{
			std::ofstream lib((nativeRoot / "data/movements/lib/movements.lua").string());
			std::ofstream xml((nativeRoot / "data/movements/movements.xml").string());
			xml << "<movements>\n";
			for (uint16_t id : {nativeRingId, nativeActiveId}) {
				xml << "<movevent event=\"Equip\" itemid=\"" << id << "\" slot=\"ring\" function=\"onEquipItem\"/>\n";
				xml << "<movevent event=\"DeEquip\" itemid=\"" << id << "\" slot=\"ring\" function=\"onDeEquipItem\"/>\n";
			}
			xml << "</movements>\n";
		}
		boost::filesystem::current_path(nativeRoot);
		const bool nativeLoaded = moves.loadFromXml();
		boost::filesystem::current_path(nativeOriginal);
		boost::filesystem::remove_all(nativeRoot);
		require(nativeLoaded, "native Equip/DeEquip callbacks must load through production XML parser");
		const int32_t magicBase = player.getMagicLevel();
		Item* nativeRing = equip(player, nativeRingId, CONST_SLOT_RING, ITEM_RARITY_BONUS_SKILL, 5, SKILL_MAGLEVEL);
		require(nativeRing->getID() == nativeActiveId && player.isItemAbilityEnabled(CONST_SLOT_RING), "native equip must transform and activate ring ability");
		require(player.getSkillLevel(SKILL_SWORD) == originalSkill + nativeSwordBonus, "native sword skill must apply alongside rarity");
		require(player.getMagicLevel() == magicBase + 5, "magic level rarity must survive native equip transformation");
		g_moveEvents->onPlayerEquip(&player, nativeRing, CONST_SLOT_RING, false);
		require(player.getSkillLevel(SKILL_SWORD) == originalSkill + nativeSwordBonus && player.getMagicLevel() == magicBase + 5, "repeated native equip must duplicate neither bonus");
		require(g_game.internalMoveItem(&player, bag, INDEX_WHEREEVER, nativeRing, 1, nullptr, FLAG_NOLIMIT) == RETURNVALUE_NOERROR, "native ring must move to backpack using real item movement");
		require(nativeRing->getID() == nativeRingId && nativeRing->hasRarity(), "native unequip transformation must preserve rarity");
		require(!player.isItemAbilityEnabled(CONST_SLOT_RING) && !player.isItemRarityEnabled(CONST_SLOT_RING), "native and rarity state must clear on unequip");
		require(player.getSkillLevel(SKILL_SWORD) == originalSkill && player.getMagicLevel() == magicBase, "native and magic rarity bonuses must both remove exactly");
		lootTests();
		groundRarityTests();
		groundRarityMovementTests();
		g_game.cleanup();
		std::cout << "PASS: " << checks << " rarity core checks (production C++, isolated from live data)." << std::endl;
		return 0;
	} catch (const std::exception& error) {
		std::cerr << "FAIL: " << error.what() << std::endl;
		return 1;
	}
}
