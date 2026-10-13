#include "otpch.h"
#include "configmanager.h"
#include "creatureevent.h"
#include "databasetasks.h"
#include "events.h"
#include "game.h"
#include "movement.h"
#include "rsa.h"
#include "scheduler.h"
#include "spells.h"
#include "tools.h"
#include "weapons.h"
#include <boost/filesystem.hpp>
#include <fstream>
#include <stdexcept>

// Real server core, without listeners, a database, worker threads or a live map.
DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;
extern LuaEnvironment g_luaEnvironment;
extern Events* g_events;
extern MoveEvents* g_moveEvents;
extern CreatureEvents* g_creatureEvents;
extern Weapons* g_weapons;
extern Spells* g_spells;

static unsigned checks = 0;
static void require(bool success, const std::string& message)
{
	++checks;
	if (!success) throw std::runtime_error(message);
}

static void loadFixtureConfig()
{
	const auto original = boost::filesystem::current_path();
	const auto scratch = boost::filesystem::temp_directory_path() /
		boost::filesystem::unique_path("antigas-classic-combat-%%%%-%%%%");
	boost::filesystem::create_directory(scratch);
	{
		std::ofstream config((scratch / "config.lua").string());
		config << "freePremium = false\nremoveChargesFromRunes = true\n";
		require(config.good(), "isolated fixture config must be writable");
	}
	boost::filesystem::current_path(scratch);
	const bool loaded = g_config.load();
	boost::filesystem::current_path(original);
	boost::filesystem::remove_all(scratch);
	require(loaded, "real ConfigManager must load the isolated fixture config");
}

// Populate eligible offline fixtures. No IgnoreWeaponCheck/IgnoreSpellCheck flag
// is used, so a rejection cannot be masked by an administrative bypass.
// Reuse the existing test-only friendship: Player is final. All fixture
// helpers stay here; no test-only method is added to the production class.
struct LoginGateCoreTestAccess
{
		static void eligible(Player& player, Group* fixtureGroup, Tile* fixtureTile, uint16_t vocationId)
		{
			player.setGroup(fixtureGroup);
			player.setParent(fixtureTile);
			require(player.setVocation(vocationId), "fixture vocation must exist");
			player.level = 100;
			player.magLevel = 100;
			player.mana = 10000;
			player.manaMax = 10000;
			player.soul = 100;
			player.health = 1000000;
			player.healthMax = 1000000;
			player.setPremiumDays(30);
		}
};

// Access protected production consumers on the actual registered objects.
// Pointer-to-member access avoids replacing the implementation or casting an
// existing Weapon/Spell to a fabricated derived instance.
struct WeaponUseAccess : Weapon
{
	static void hit(const Weapon& weapon, Player* player, Item* item, Creature* target)
	{
		auto consumer = static_cast<void (Weapon::*)(Player*, Item*, Creature*, int32_t) const>(&WeaponUseAccess::internalUseWeapon);
		(weapon.*consumer)(player, item, target, 100);
	}

	static void miss(const Weapon& weapon, Player* player, Item* item, Tile* destination)
	{
		auto consumer = static_cast<void (Weapon::*)(Player*, Item*, Tile*) const>(&WeaponUseAccess::internalUseWeapon);
		(weapon.*consumer)(player, item, destination);
	}

	static void afterAttack(const Weapon& weapon, Player* player, Item* item, Tile* destination)
	{
		auto consumer = &WeaponUseAccess::onUsedWeapon;
		(weapon.*consumer)(player, item, destination);
	}
};

static Item* spearOn(Tile& tile)
{
	for (Item* item : *tile.getItemList()) {
		if (item->getID() == 3277) return item;
	}
	return nullptr;
}

static void spearsFallAndRecover(Weapons& weapons, Group& group, Tile& origin, Player& target)
{
	// No game loop runs in this fixture. Drain deferred item releases on normal
	// return and on assertion failure, after the local inventory owners unwind.
	struct ItemReleaseCleanup {
		~ItemReleaseCleanup() { g_game.cleanup(true); }
	} itemReleaseCleanup;
	for (uint16_t count : {1, 20}) {
		Player player(nullptr);
		LoginGateCoreTestAccess::eligible(player, &group, &origin, 0);
		DynamicTile missedTile(102, 100, 7);
		Tile& hitTile = *target.getTile();
		Item* item = Item::CreateItem(3277, count);
		require(item != nullptr, "spear fixture must exist");
		static_cast<Cylinder&>(player).internalAddThing(CONST_SLOT_RIGHT, item);
		const Weapon* weapon = weapons.getWeapon(item);
		require(weapon != nullptr, "spear must have a registered weapon");

		// Exercise both real internal attack overloads and actual item movement.
		// A miss has its own destination; it must not fall on the target tile.
		for (bool hit : {true, false}) {
			Tile& destination = hit ? hitTile : missedTile;
			require(destination.getItemTypeCount(3277) == 0, "recovered destination must start empty");
			for (uint16_t remaining = count; remaining > 0; --remaining) {
				Item* held = player.getInventoryItem(CONST_SLOT_RIGHT);
				require(held && held->getParent() == &player && held->getItemCount() == remaining,
					"each throw must use a spear still held by the player");
				if (hit) WeaponUseAccess::hit(*weapon, &player, held, &target);
				else WeaponUseAccess::miss(*weapon, &player, held, &destination);
				Item* after = player.getInventoryItem(CONST_SLOT_RIGHT);
				require(remaining == 1 ? after == nullptr : after && after->getItemCount() == remaining - 1,
					"spear throw must remove exactly one from the originating hand");
				require(destination.getItemTypeCount(3277) == count - remaining + 1,
					"every unbroken spear must reach the chosen hit/miss tile");
				require((hit ? missedTile : hitTile).getItemTypeCount(3277) == 0,
					"throw must not add a spear to the other destination");
				Item* fallen = spearOn(destination);
				require(fallen && fallen->getParent() == &destination, "fallen spear must belong to the floor");
			}
			require(player.getInventoryItem(CONST_SLOT_RIGHT) == nullptr,
				"exhausted hand must require recovery before further spear attacks");
			Item* fallen = spearOn(destination);
			require(g_game.internalMoveItem(&destination, &player, CONST_SLOT_RIGHT, fallen, count,
				nullptr, FLAG_NOLIMIT) == RETURNVALUE_NOERROR, "real item recovery must succeed");
			require(destination.getItemTypeCount(3277) == 0, "recovery must empty the destination");
			Item* recovered = player.getInventoryItem(CONST_SLOT_RIGHT);
			require(recovered && recovered->getParent() == &player && recovered->getItemCount() == count,
				"recovery must preserve all spears without breakage");
		}
	}
}

struct SpellGateAccess : Spell
{
	static bool accepts(const Spell& spell, Player* player)
	{
		auto consumer = &SpellGateAccess::playerSpellCheck;
		return (spell.*consumer)(player);
	}
};

static void survivesThrows(Weapons& weapons, Player& player, Tile& destination,
	uint16_t id, const char* name)
{
	Item* item = Item::CreateItem(id, 100);
	require(item != nullptr, "throwing fixture must exist");
	static_cast<Cylinder&>(player).internalAddThing(CONST_SLOT_RIGHT, item);
	const Weapon* weapon = weapons.getWeapon(item);
	require(weapon != nullptr, std::string(name) + " must have a registered weapon");
	getRandomGenerator().seed(74);
	for (unsigned use = 0; use < 500; ++use) {
		WeaponUseAccess::afterAttack(*weapon, &player, item, &destination);
		require(item->getItemCount() == 100,
			std::string(name) + " must survive the real post-attack consumer without breaking (use " + std::to_string(use + 1) + ")");
	}
}

static void stockWandsReject(Weapons& weapons, Group& group, Tile& tile, Player& target)
{
	for (uint16_t id : {5292, 5293, 5294, 5295, 5296, 5297, 5298, 5299, 5300, 5301}) {
		Player player(nullptr);
		LoginGateCoreTestAccess::eligible(player, &group, &tile, id < 5297 ? 2 : 1);
		std::unique_ptr<Item> item(Item::CreateItem(id));
		require(item != nullptr, "existing stock wand/rod item must remain creatable");
		const Weapon* weapon = weapons.getWeapon(item.get());
		require(weapon != nullptr, "disabled stock wand/rod definition must remain registered");
		const int32_t manaBefore = player.getMana();
		require(weapon->playerWeaponCheck(&player, &target, item->getShootRange()) == 0,
			"ordinary eligible player must be rejected by stock wand/rod " + std::to_string(id));
		require(!weapon->useWeapon(&player, item.get(), &target), "stock wand/rod attack must fail");
		require(player.getMana() == manaBefore, "rejected wand/rod attack must not spend mana");
	}
}

static void iceRejects(Spells& spells, Player& none, Player& druid)
{
	// The existing XML restricts these instants/conjures to None, not Druid.
	// A matching None fixture ensures disabled is the operative gate.
	for (const char* words : {"exori frigo", "adori frigo", "adori gran frigo"}) {
		InstantSpell* spell = spells.getInstantSpell(words);
		require(spell != nullptr, "ice spell/conjure must remain registered");
		require(spell->canCast(&none), "None ice spell must remain in its existing spell catalogue");
		require(!spell->canCast(&druid), "existing Druid vocation gate must remain intact");
		std::string param;
		const int32_t manaBefore = none.getMana();
		require(!SpellGateAccess::accepts(*spell, &none), std::string(words) + " must reject an otherwise eligible None player");
		require(!spell->playerCastInstant(&none, param), "disabled ice instant/conjure must fail through its public cast entry");
		require(none.getMana() == manaBefore, "disabled ice instant/conjure must not spend mana");
	}
	for (uint16_t id : {3158, 3161}) {
		RuneSpell* spell = spells.getRuneSpell(id);
		require(spell != nullptr, "ice rune definition must remain registered");
		std::unique_ptr<Item> item(Item::CreateItem(id));
		require(item != nullptr, "existing ice rune item must remain creatable");
		const uint16_t chargesBefore = item->getCharges();
		require(!SpellGateAccess::accepts(*spell, &druid), "ice rune must reject an otherwise eligible Druid");
		require(!spell->executeUse(&druid, item.get(), druid.getPosition(), &none, none.getPosition()),
			"disabled ice rune must fail through its public use entry");
		require(item->getCharges() == chargesBefore, "disabled ice rune must preserve its charges");
	}
}

static void preservedCustoms(Weapons& weapons, Spells& spells, Group& group, Tile& tile, Player& target)
{
	for (uint16_t id : {5307, 5312, 5337, 5141, 5142, 5143, 5144, 5148}) {
		Player player(nullptr);
		LoginGateCoreTestAccess::eligible(player, &group, &tile, id == 5307 ? 2 : 1);
		std::unique_ptr<Item> item(Item::CreateItem(id));
		require(item != nullptr, "custom/training item must remain creatable");
		const Weapon* weapon = weapons.getWeapon(item.get());
		require(weapon != nullptr, "custom/training weapon must remain registered");
		require(weapon->playerWeaponCheck(&player, &target, item->getShootRange()) == 100,
			"custom/training weapon must still pass the ordinary weapon gate: " + std::to_string(id));
	}
	Player druid(nullptr);
	LoginGateCoreTestAccess::eligible(druid, &group, &tile, 2);
	InstantSpell* flame = spells.getInstantSpell("exori flam");
	require(flame != nullptr && SpellGateAccess::accepts(*flame, &druid), "existing non-ice elemental spell must remain usable");
	RuneSpell* fireball = spells.getRuneSpell(3189);
	require(fireball != nullptr && SpellGateAccess::accepts(*fireball, &druid), "existing non-ice rune must remain usable");
	Player archer(nullptr);
	LoginGateCoreTestAccess::eligible(archer, &group, &tile, 3);
	Item* arrow = Item::CreateItem(3447, 100);
	require(arrow != nullptr, "normal ammunition fixture must exist");
	static_cast<Cylinder&>(archer).internalAddThing(CONST_SLOT_AMMO, arrow);
	const Weapon* ammunition = weapons.getWeapon(arrow);
	require(ammunition != nullptr, "normal ammunition must remain registered");
	WeaponUseAccess::afterAttack(*ammunition, &archer, arrow, target.getTile());
	require(arrow->getItemCount() == 99, "normal ammunition must still be consumed by the real post-attack consumer");
}

int main(int argc, char** argv)
{
	try {
		require(argc == 2, "select one combat regression");
		loadFixtureConfig();
		require(Item::items.loadItems(), "production item definitions must load");
		require(g_vocations.loadFromXml(), "production vocations must load");
		require(g_luaEnvironment.initState(), "production Lua environment must initialize");
		require(g_luaEnvironment.loadFile("data/global.lua") == 0, "production Lua libraries must load");
		Events events;
		MoveEvents moves;
		CreatureEvents creatureEvents;
		Weapons weapons;
		Spells spells;
		g_events = &events;
		g_moveEvents = &moves;
		g_creatureEvents = &creatureEvents;
		g_weapons = &weapons;
		g_spells = &spells;
		require(weapons.loadFromXml(), "production weapons registry must load");
		weapons.loadDefaults();
		require(spells.loadFromXml(), "production spells registry must load");
		Group group = {};
		group.flags = PlayerFlag_NotGainSkill;
		DynamicTile tile(100, 100, 7), targetTile(101, 100, 7);
		Player player(nullptr), druid(nullptr), target(nullptr);
		LoginGateCoreTestAccess::eligible(player, &group, &tile, 0);
		LoginGateCoreTestAccess::eligible(druid, &group, &tile, 2);
		LoginGateCoreTestAccess::eligible(target, &group, &targetTile, 0);
		const std::string mode = argv[1];
		if (mode == "spear") spearsFallAndRecover(weapons, group, tile, target);
		else if (mode == "throwing-star") survivesThrows(weapons, player, targetTile, 3287, "throwing star");
		else if (mode == "stock-wands") stockWandsReject(weapons, group, tile, target);
		else if (mode == "ice") iceRejects(spells, player, druid);
		else if (mode == "preserved-custom") preservedCustoms(weapons, spells, group, tile, target);
		else throw std::runtime_error("unknown combat regression");
		std::cout << "PASS: " << mode << " (" << checks << " real-core checks)" << std::endl;
		return 0;
	} catch (const std::exception& error) {
		std::cerr << "FAIL: " << error.what() << std::endl;
		return 1;
	}
}
