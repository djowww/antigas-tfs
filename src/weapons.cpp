/**
 * Tibia GIMUD Server - a free and open-source MMORPG server emulator
 * Copyright (C) 2017  Alejandro Mujica <alejandrodemujica@gmail.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

#include "otpch.h"
#include "hunt_supply.h"

#include "combat.h"
#include "configmanager.h"
#include "game.h"
#include "pugicast.h"
#include "weapons.h"
#include "legacycombat.h"

extern Game g_game;
extern Vocations g_vocations;
extern ConfigManager g_config;
extern Weapons* g_weapons;

Weapons::Weapons()
{
	scriptInterface.initState();
}

Weapons::~Weapons()
{
	clear();
}

const Weapon* Weapons::getWeapon(const Item* item) const
{
	if (!item || Item::items[item->getID()].group == ITEM_GROUP_DEPRECATED) {
		return nullptr;
	}

	auto it = weapons.find(item->getID());
	if (it == weapons.end()) {
		return nullptr;
	}
	return it->second;
}

void Weapons::clear()
{
	for (const auto& it : weapons) {
		delete it.second;
	}
	weapons.clear();

	scriptInterface.reInitState();
}

LuaScriptInterface& Weapons::getScriptInterface()
{
	return scriptInterface;
}

std::string Weapons::getScriptBaseName() const
{
	return "weapons";
}

void Weapons::loadDefaults()
{
	for (size_t i = 100, size = Item::items.size(); i < size; ++i) {
		const ItemType& it = Item::items.getItemType(i);
		if (it.id == 0 || it.group == ITEM_GROUP_DEPRECATED || weapons.find(i) != weapons.end()) {
			continue;
		}

		switch (it.weaponType) {
			case WEAPON_AXE:
			case WEAPON_SWORD:
			case WEAPON_CLUB: {
				WeaponMelee* weapon = new WeaponMelee(&scriptInterface);
				weapon->configureWeapon(it);
				weapons[i] = weapon;
				break;
			}

			case WEAPON_AMMO:
			case WEAPON_DISTANCE: {
				if (it.weaponType == WEAPON_DISTANCE && it.ammoType != AMMO_NONE) {
					continue;
				}

				WeaponDistance* weapon = new WeaponDistance(&scriptInterface);
				weapon->configureWeapon(it);
				weapons[i] = weapon;
				break;
			}

			default:
				break;
		}
	}
}

Event* Weapons::getEvent(const std::string& nodeName)
{
	if (strcasecmp(nodeName.c_str(), "melee") == 0) {
		return new WeaponMelee(&scriptInterface);
	} else if (strcasecmp(nodeName.c_str(), "distance") == 0) {
		return new WeaponDistance(&scriptInterface);
	} else if (strcasecmp(nodeName.c_str(), "wand") == 0) {
		return new WeaponWand(&scriptInterface);
	}
	return nullptr;
}

bool Weapons::registerEvent(Event* event, const pugi::xml_node&)
{
	Weapon* weapon = static_cast<Weapon*>(event); //event is guaranteed to be a Weapon

	auto result = weapons.emplace(weapon->getID(), weapon);
	if (!result.second) {
		std::cout << "[Warning - Weapons::registerEvent] Duplicate registered item with id: " << weapon->getID() << std::endl;
	}
	return result.second;
}

//monsters
int32_t Weapons::getMaxMeleeDamage(int32_t attackSkill, int32_t attackValue)
{
	return LegacyCombat::maximum(attackValue, attackSkill);
}

//players
int32_t Weapons::getMaxWeaponDamage(uint32_t level, int32_t attackSkill, int32_t attackValue, float attackFactor)
{
	(void)level;
	const uint8_t mode = attackFactor < 1.0f ? 3 : (attackFactor > 1.0f ? 1 : 2);
	return LegacyCombat::maximum(LegacyCombat::attackValue(attackValue, mode), attackSkill);
}

bool Weapon::configureEvent(const pugi::xml_node& node)
{
	pugi::xml_attribute attr;
	if (!(attr = node.attribute("id"))) {
		std::cout << "[Error - Weapon::configureEvent] Weapon without id." << std::endl;
		return false;
	}
	id = pugi::cast<uint16_t>(attr.value());

	if ((attr = node.attribute("level"))) {
		level = pugi::cast<uint32_t>(attr.value());
	}

	if ((attr = node.attribute("maglv")) || (attr = node.attribute("maglevel"))) {
		magLevel = pugi::cast<uint32_t>(attr.value());
	}

	if ((attr = node.attribute("mana"))) {
		mana = pugi::cast<uint32_t>(attr.value());
	}

	if ((attr = node.attribute("manapercent"))) {
		manaPercent = pugi::cast<uint32_t>(attr.value());
	}

	if ((attr = node.attribute("soul"))) {
		soul = pugi::cast<uint32_t>(attr.value());
	}

	if ((attr = node.attribute("prem"))) {
		premium = attr.as_bool();
	}

	if ((attr = node.attribute("breakchance"))) {
		breakChance = std::min<uint8_t>(100, pugi::cast<uint16_t>(attr.value()));
	}

	if ((attr = node.attribute("action"))) {
		action = getWeaponAction(attr.as_string());
		if (action == WEAPONACTION_NONE) {
			std::cout << "[Warning - Weapon::configureEvent] Unknown action " << attr.as_string() << std::endl;
		}
	}

	if ((attr = node.attribute("enabled"))) {
		enabled = attr.as_bool();
	}

	if ((attr = node.attribute("unproperly"))) {
		wieldUnproperly = attr.as_bool();
	}

	std::list<std::string> vocStringList;
	for (auto vocationNode : node.children()) {
		if (!(attr = vocationNode.attribute("name"))) {
			continue;
		}

		int32_t vocationId = g_vocations.getVocationId(attr.as_string());
		if (vocationId != -1) {
			vocWeaponMap[vocationId] = true;
			int32_t promotedVocation = g_vocations.getPromotedVocation(vocationId);
			if (promotedVocation != VOCATION_NONE) {
				vocWeaponMap[promotedVocation] = true;
			}

			if (vocationNode.attribute("showInDescription").as_bool(true)) {
				vocStringList.push_back(asLowerCaseString(attr.as_string()));
			}
		}
	}

	std::string vocationString;
	for (const std::string& str : vocStringList) {
		if (!vocationString.empty()) {
			if (str != vocStringList.back()) {
				vocationString.push_back(',');
				vocationString.push_back(' ');
			} else {
				vocationString += " and ";
			}
		}

		vocationString += str;
		vocationString.push_back('s');
	}

	uint32_t wieldInfo = 0;
	if (getReqLevel() > 0) {
		wieldInfo |= WIELDINFO_LEVEL;
	}

	if (getReqMagLv() > 0) {
		wieldInfo |= WIELDINFO_MAGLV;
	}

	if (!vocationString.empty()) {
		wieldInfo |= WIELDINFO_VOCREQ;
	}

	if (isPremium()) {
		wieldInfo |= WIELDINFO_PREMIUM;
	}

	if (wieldInfo != 0) {
		ItemType& it = Item::items.getItemType(id);
		it.wieldInfo = wieldInfo;
		it.vocationString = vocationString;
		it.minReqLevel = getReqLevel();
		it.minReqMagicLevel = getReqMagLv();
	}

	configureWeapon(Item::items[id]);
	return true;
}

void Weapon::configureWeapon(const ItemType& it)
{
	id = it.id;
}

std::string Weapon::getScriptEventName() const
{
	return "onUseWeapon";
}

int32_t Weapon::playerWeaponCheck(Player* player, Creature* target, uint8_t shootRange) const
{
	const Position& playerPos = player->getPosition();
	const Position& targetPos = target->getPosition();
	if (playerPos.z != targetPos.z) {
		return 0;
	}

	if (std::max<uint32_t>(Position::getDistanceX(playerPos, targetPos), Position::getDistanceY(playerPos, targetPos)) > shootRange) {
		return 0;
	}

	if (!player->hasFlag(PlayerFlag_IgnoreWeaponCheck)) {
		if (!enabled) {
			return 0;
		}

		if (player->getMana() < getManaCost(player)) {
			return 0;
		}

		if (player->getSoul() < soul) {
			return 0;
		}

		if (isPremium() && !player->isPremium()) {
			return 0;
		}

		if (!vocWeaponMap.empty()) {
			if (vocWeaponMap.find(player->getVocationId()) == vocWeaponMap.end()) {
				return 0;
			}
		}

		int32_t damageModifier = 100;
		if (player->getLevel() < getReqLevel()) {
			damageModifier = (isWieldedUnproperly() ? damageModifier / 2 : 0);
		}

		if (player->getMagicLevel() < getReqMagLv()) {
			damageModifier = (isWieldedUnproperly() ? damageModifier / 2 : 0);
		}
		return damageModifier;
	}

	return 100;
}

bool Weapon::useWeapon(Player* player, Item* item, Creature* target) const
{
	int32_t damageModifier = playerWeaponCheck(player, target, item->getShootRange());
	if (damageModifier == 0) {
		return false;
	}

	internalUseWeapon(player, item, target, damageModifier);
	return true;
}

bool Weapon::useFist(Player* player, Creature* target)
{
	if (!Position::areInRange<1, 1>(player->getPosition(), target->getPosition())) {
		return false;
	}

	float attackFactor = player->getAttackFactor();
	int32_t attackSkill = player->getSkillLevel(SKILL_FIST);
	int32_t attackValue = 7;

	int32_t maxDamage = Weapons::getMaxWeaponDamage(player->getLevel(), attackSkill, attackValue, attackFactor);

	CombatParams params;
	params.combatType = COMBAT_PHYSICALDAMAGE;
	params.blockedByArmor = true;
	params.blockedByShield = true;

	CombatDamage damage;
	damage.type = params.combatType;
	(void)maxDamage;
	if (player->consumeLegacyLearningCredit() && !player->hasFlag(PlayerFlag_NotGainSkill)) player->addSkillAdvance(SKILL_FIST, 1);
	attackSkill = player->getSkillLevel(SKILL_FIST);
	damage.value = -LegacyCombat::probe(LegacyCombat::attackValue(attackValue, player->getFightMode()), attackSkill);

	const int32_t priorHealth = target->getHealth(), priorMana = target->getMana();
	Combat::doCombatHealth(player, target, damage, params);
	if (target->getHealth() < priorHealth || target->getMana() < priorMana) player->refreshLegacyLearningCredit();
	return true;
}

void Weapon::internalUseWeapon(Player* player, Item* item, Creature* target, int32_t damageModifier) const
{
	if (scripted) {
		LuaVariant var;
		var.type = VARIANT_NUMBER;
		var.number = target->getID();
		HuntSupplyUse scriptedSupply(player, item);
		executeUseWeapon(player, var);
	} else {
		CombatDamage damage;
		damage.type = params.combatType;
		damage.value = (getWeaponDamage(player, target, item) * damageModifier) / 100;
		const int32_t priorHealth = target->getHealth(), priorMana = target->getMana();
		Combat::doCombatHealth(player, target, damage, params);
		if (target->getHealth() < priorHealth || target->getMana() < priorMana) player->refreshLegacyLearningCredit();
	}

	onUsedWeapon(player, item, target->getTile());
}

void Weapon::internalUseWeapon(Player* player, Item* item, Tile* tile) const
{
	if (scripted) {
		LuaVariant var;
		var.type = VARIANT_TARGETPOSITION;
		var.pos = tile->getPosition();
		HuntSupplyUse scriptedSupply(player, item);
		executeUseWeapon(player, var);
	} else {
		Combat::postCombatEffects(player, tile->getPosition(), params);
		g_game.addMagicEffect(tile->getPosition(), CONST_ME_POFF);
	}

	onUsedWeapon(player, item, tile);
}

void Weapon::onUsedWeapon(Player* player, Item* item, Tile* destTile) const
{
	uint32_t manaCost = getManaCost(player);
	if (manaCost != 0) {
		player->addManaSpent(manaCost);
		player->changeMana(-static_cast<int32_t>(manaCost));
	}

	if (!player->hasFlag(PlayerFlag_HasInfiniteSoul) && soul > 0) {
		player->changeSoul(-static_cast<int32_t>(soul));
	}

	if (breakChance != 0 && uniform_random(1, 100) <= breakChance) {
		HuntSupplyUse supply(player, item);
		Weapon::decrementItemCount(item);
		return;
	}

	switch (action) {
		case WEAPONACTION_REMOVECOUNT: {
			HuntSupplyUse supply(player, item);
			Weapon::decrementItemCount(item);
			break;
		}

		case WEAPONACTION_REMOVECHARGE: {
			HuntSupplyUse supply(player, item);
			uint16_t charges = item->getCharges() - 1;
			if (charges != 0) {
				g_game.transformItem(item, item->getID(), charges);
			} else {
				g_game.internalRemoveItem(item);
			}
			break;
		}

		case WEAPONACTION_MOVE:
			g_game.internalMoveItem(item->getParent(), destTile, INDEX_WHEREEVER, item, 1, nullptr, FLAG_NOLIMIT);
			break;

		default:
			break;
	}
}

uint32_t Weapon::getManaCost(const Player* player) const
{
	if (mana != 0) {
		return mana;
	}

	if (manaPercent == 0) {
		return 0;
	}

	return (player->getMaxMana() * manaPercent) / 100;
}

bool Weapon::executeUseWeapon(Player* player, const LuaVariant& var) const
{
	//onUseWeapon(player, var)
	if (!scriptInterface->reserveScriptEnv()) {
		std::cout << "[Error - Weapon::executeUseWeapon] Call stack overflow" << std::endl;
		return false;
	}

	ScriptEnvironment* env = scriptInterface->getScriptEnv();
	env->setScriptId(scriptId, scriptInterface);

	lua_State* L = scriptInterface->getLuaState();

	scriptInterface->pushFunction(scriptId);
	LuaScriptInterface::pushUserdata<Player>(L, player);
	LuaScriptInterface::setMetatable(L, -1, "Player");
	scriptInterface->pushVariant(L, var);

	return scriptInterface->callFunction(2);
}

void Weapon::decrementItemCount(Item* item)
{
	uint16_t count = item->getItemCount();
	if (count > 1) {
		g_game.transformItem(item, item->getID(), count - 1);
	} else {
		g_game.internalRemoveItem(item);
	}
}

WeaponMelee::WeaponMelee(LuaScriptInterface* interface) :
	Weapon(interface)
{
	params.blockedByArmor = true;
	params.blockedByShield = true;
	params.combatType = COMBAT_PHYSICALDAMAGE;
}

void WeaponMelee::configureWeapon(const ItemType& it)
{
	Weapon::configureWeapon(it);
}

bool WeaponMelee::useWeapon(Player* player, Item* item, Creature* target) const
{
	int32_t damageModifier = playerWeaponCheck(player, target, item->getShootRange());
	if (damageModifier == 0) {
		return false;
	}

	internalUseWeapon(player, item, target, damageModifier);
	return true;
}

bool WeaponMelee::getSkillType(const Player* player, const Item* item,
                               skills_t& skill, uint32_t& skillpoint) const
{
	if (player->getAddAttackSkill() && player->getLastAttackBlockType() != BLOCK_IMMUNITY) {
		skillpoint = 1;
	} else {
		skillpoint = 0;
	}

	WeaponType_t weaponType = item->getWeaponType();
	switch (weaponType) {
		case WEAPON_SWORD: {
			skill = SKILL_SWORD;
			return true;
		}

		case WEAPON_CLUB: {
			skill = SKILL_CLUB;
			return true;
		}

		case WEAPON_AXE: {
			skill = SKILL_AXE;
			return true;
		}

		default:
			break;
	}
	return false;
}

int32_t WeaponMelee::getWeaponDamage(const Player* player, const Creature*, const Item* item, bool maxDamage /*= false*/) const
{
	int32_t attackSkill = player->getWeaponSkill(item);
	int32_t attackValue = std::max<int32_t>(0, item->getAttack());
	float attackFactor = player->getAttackFactor();

	int32_t maxValue = Weapons::getMaxWeaponDamage(player->getLevel(), attackSkill, attackValue, attackFactor);
	if (maxDamage) {
		return -maxValue;
	}

 Player* learner = const_cast<Player*>(player);
 if (learner->consumeLegacyLearningCredit() && !learner->hasFlag(PlayerFlag_NotGainSkill)) {
  skills_t skill; uint32_t ignored;
  if (getSkillType(player, item, skill, ignored)) learner->addSkillAdvance(skill, 1);
 }
 attackSkill = player->getWeaponSkill(item);
	return -LegacyCombat::probe(LegacyCombat::attackValue(attackValue, player->getFightMode()), attackSkill);
}

WeaponDistance::WeaponDistance(LuaScriptInterface* interface) :
	Weapon(interface)
{
	params.blockedByArmor = true;
	params.combatType = COMBAT_PHYSICALDAMAGE;
}

void WeaponDistance::configureWeapon(const ItemType& it)
{
	params.distanceEffect = it.shootType;

	Weapon::configureWeapon(it);
}

bool WeaponDistance::useWeapon(Player* player, Item* item, Creature* target) const
{
	int32_t damageModifier;
	const ItemType& it = Item::items[id];
	if (it.weaponType == WEAPON_AMMO) {
		Item* mainWeaponItem = player->getWeapon(true);
		const Weapon* mainWeapon = g_weapons->getWeapon(mainWeaponItem);
		if (mainWeapon) {
			damageModifier = mainWeapon->playerWeaponCheck(player, target, mainWeaponItem->getShootRange());
		} else {
			damageModifier = playerWeaponCheck(player, target, mainWeaponItem->getShootRange());
		}
	} else {
		damageModifier = playerWeaponCheck(player, target, item->getShootRange());
	}

	if (damageModifier == 0) {
		return false;
	}

 const Position& source = player->getPosition();
 const Position& destination = target->getPosition();
 int32_t distance = std::max(Position::getDistanceX(source, destination), Position::getDistanceY(source, destination));
 if (distance <= 1) distance = 5;
 const int32_t cap = it.ammoType != AMMO_NONE ? 90 : 75;
 if (player->consumeLegacyLearningCredit() && !player->hasFlag(PlayerFlag_NotGainSkill)) player->addSkillAdvance(SKILL_DISTANCE, 1);
 const bool hits = uniform_random(0, 15 * distance - 1) <= player->getBaseSkill(SKILL_DISTANCE) && uniform_random(0, 99) <= cap;
 if (hits) {
		Weapon::internalUseWeapon(player, item, target, damageModifier);
	} else {
		//miss target
		Tile* destTile = target->getTile();

		if (!Position::areInRange<1, 1, 0>(player->getPosition(), target->getPosition())) {
			static std::vector<std::pair<int32_t, int32_t>> destList {
				{-1, -1}, {0, -1}, {1, -1},
				{-1,  0}, {0,  0}, {1,  0},
				{-1,  1}, {0,  1}, {1,  1}
			};
			std::shuffle(destList.begin(), destList.end(), getRandomGenerator());

			Position destPos = target->getPosition();

			for (const auto& dir : destList) {
				// Blocking tiles or tiles without ground ain't valid targets for spears
				Tile* tmpTile = g_game.map.getTile(destPos.x + dir.first, destPos.y + dir.second, destPos.z);
				if (tmpTile && !tmpTile->hasFlag(TILESTATE_IMMOVABLEBLOCKSOLID) && tmpTile->getGround() != nullptr) {
					destTile = tmpTile;
					break;
				}
			}
		}

		Weapon::internalUseWeapon(player, item, destTile);
	}
	return true;
}

int32_t WeaponDistance::getWeaponDamage(const Player* player, const Creature* target, const Item* item, bool maxDamage /*= false*/) const
{
	int32_t attackValue = item->getAttack();

	if (item->getWeaponType() == WEAPON_AMMO) {
		Item* weapon = player->getWeapon(true);
		if (weapon) {
			attackValue += weapon->getAttack();
		}
	}

	int32_t attackSkill = player->getSkillLevel(SKILL_DISTANCE);
	float attackFactor = player->getAttackFactor();

	int32_t maxValue = Weapons::getMaxWeaponDamage(player->getLevel(), attackSkill, attackValue, attackFactor);
	if (maxDamage) {
		return -maxValue;
	}

	(void)target;
 Player* learner = const_cast<Player*>(player);
 if (learner->consumeLegacyLearningCredit() && !learner->hasFlag(PlayerFlag_NotGainSkill)) learner->addSkillAdvance(SKILL_DISTANCE, 1);
 attackSkill = player->getSkillLevel(SKILL_DISTANCE);
	const int32_t amount = -LegacyCombat::probe(LegacyCombat::attackValue(attackValue, player->getFightMode()), attackSkill);
	// The reference calls the target's defense when the shooter has a shield,
	// consuming its timer/training, but discards the resulting defense roll.
	if (target && player->hasShield()) const_cast<Creature*>(target)->rollLegacyDefense();
	return amount;
}

bool WeaponDistance::getSkillType(const Player* player, const Item*, skills_t& skill, uint32_t& skillpoint) const
{
	skill = SKILL_DISTANCE;

	if (player->getAddAttackSkill()) {
		switch (player->getLastAttackBlockType()) {
			case BLOCK_NONE: {
				skillpoint = 2;
				break;
			}

			case BLOCK_DEFENSE:
			case BLOCK_ARMOR: {
				skillpoint = 1;
				break;
			}

			default:
				skillpoint = 0;
				break;
		}
	} else {
		skillpoint = 0;
	}
	return true;
}

bool WeaponWand::configureEvent(const pugi::xml_node& node)
{
	if (!Weapon::configureEvent(node)) {
		return false;
	}

	pugi::xml_attribute attr;
	if ((attr = node.attribute("min"))) {
		minChange = pugi::cast<int32_t>(attr.value());
	}

	if ((attr = node.attribute("max"))) {
		maxChange = pugi::cast<int32_t>(attr.value());
	}

	if ((attr = node.attribute("type"))) {
		std::string tmpStrValue = asLowerCaseString(attr.as_string());
		if (tmpStrValue == "earth") {
			params.combatType = COMBAT_EARTHDAMAGE;
		} else if (tmpStrValue == "energy") {
			params.combatType = COMBAT_ENERGYDAMAGE;
		} else if (tmpStrValue == "fire") {
			params.combatType = COMBAT_FIREDAMAGE;
		} else {
			std::cout << "[Warning - WeaponWand::configureEvent] Type \"" << attr.as_string() << "\" does not exist." << std::endl;
		}
	}
	return true;
}

void WeaponWand::configureWeapon(const ItemType& it)
{
	params.distanceEffect = it.shootType;

	Weapon::configureWeapon(it);
}

int32_t WeaponWand::getWeaponDamage(const Player*, const Creature*, const Item* item, bool maxDamage /*= false*/) const
{
	const int32_t rarityAttack = 0;
	if (maxDamage) {
		return -(maxChange + rarityAttack);
	}
	return -uniform_random(minChange + rarityAttack, maxChange + rarityAttack);
}
