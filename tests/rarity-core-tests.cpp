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

static Item* equip(Player& player, uint16_t id, slots_t slot, ItemRarityBonus_t bonus, uint8_t value, uint8_t subtype = 0)
{
	Item* item = Item::CreateItem(id);
	require(item != nullptr, "equipment must be created");
	item->setRarityData(ITEM_RARITY_MYTHIC, bonus, value, subtype);
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
		Item* clone = restored->clone();
		require(clone->equals(restored), "clone must preserve rarity attributes");
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
		Item* ringItem = equip(player, ring, CONST_SLOT_RING, ITEM_RARITY_BONUS_SKILL, 5, SKILL_SWORD);
		Item* necklaceItem = equip(player, necklace, CONST_SLOT_NECKLACE, ITEM_RARITY_BONUS_SKILL, 3, SKILL_SWORD);
		require(player.getSkillLevel(SKILL_SWORD) == originalSkill + 8, "ring and necklace skill bonuses must stack");
		unequip(player, necklaceItem, CONST_SLOT_NECKLACE);
		require(player.getSkillLevel(SKILL_SWORD) == originalSkill + 5, "removing necklace must preserve ring bonus");

		// Force the production transform path that replaces the Item instance.
		ItemType& targetType = Item::items.getItemType(necklace);
		const ItemTypes_t originalType = targetType.type;
		targetType.type = ITEM_TYPE_KEY;
		Item* transformed = g_game.transformItem(ringItem, necklace);
		require(transformed && transformed != ringItem, "test must exercise replacement transform");
		require(transformed->getRarityTier() == ITEM_RARITY_MYTHIC, "replacement transform must preserve rarity");
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
		g_game.cleanup();
		std::cout << "PASS: " << checks << " rarity core checks (production C++, isolated from live data)." << std::endl;
		return 0;
	} catch (const std::exception& error) {
		std::cerr << "FAIL: " << error.what() << std::endl;
		return 1;
	}
}
