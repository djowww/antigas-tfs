#include "otpch.h"
#include "configmanager.h"
#include "creatureevent.h"
#include "databasetasks.h"
#include "events.h"
#include "game.h"
#include "legacycombat.h"
#include "movement.h"
#include "rsa.h"
#include "scheduler.h"
#include "spells.h"
#include "weapons.h"
#include <boost/filesystem.hpp>
#include <fstream>
#include <stdexcept>

// Actual core and Lua consumers, without DB, listeners or world threads.
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

static unsigned checks;
static void require(bool value, const std::string& why)
{
 ++checks;
 if (!value) throw std::runtime_error(why);
}

struct LoginGateCoreTestAccess {
 static void prepare(Player& player, Group& group, Tile& tile, uint32_t level = 50, uint32_t magic = 50)
 {
  player.setGroup(&group); player.setParent(&tile);
  require(player.setVocation(4), "knight fixture vocation");
  player.level = level; player.magLevel = magic;
  player.health = player.healthMax = 100000;
  player.mana = player.manaMax = 100000;
  for (auto& skill : player.skills) { skill.level = 80; skill.tries = 0; }
  player.setPremiumDays(30);
 }
 static void attributes(Player& player, uint32_t level, uint32_t magic)
 { player.level = level; player.magLevel = magic; }
 static void defenseClock(Player& player, bool enabled) { player.legacyEarliestDefendTime = enabled ? 0 : std::numeric_limits<int64_t>::max(); }
 static void learning(Player& player, uint8_t credits) { player.legacyLearningCredits = credits; }
 static uint8_t learning(const Player& player) { return player.legacyLearningCredits; }
 static void runtimeId(Player& player, uint32_t id) { player.id = id; }
};

struct CombatConsumerAccess : Combat {
 static void health(Creature* caster, Creature* target, const CombatParams& params, CombatDamage& damage)
 { CombatHealthFunc(caster, target, params, &damage); }
 static CombatDamage damage(const Combat& combat, Creature* caster, Creature* target)
 { auto consumer = &CombatConsumerAccess::getCombatDamage; return (combat.*consumer)(caster,target); }
 static void health(const Combat& combat, Creature* caster, Creature* target)
 {
  auto options = &CombatConsumerAccess::params;
  CombatDamage value = damage(combat,caster,target);
  CombatHealthFunc(caster,target,combat.*options,&value);
 }
};

struct WeaponConsumerAccess : Weapon {
 static int32_t damage(const Weapon& weapon, const Player& player, const Item& item, bool maximum = false, const Creature* target = nullptr)
 {
  auto consumer = &WeaponConsumerAccess::getWeaponDamage;
  return (weapon.*consumer)(&player, target, &item, maximum);
 }
 static void hit(const Weapon& weapon, Player& player, Item& item, Creature& target)
 {
  auto consumer = static_cast<void (Weapon::*)(Player*,Item*,Creature*,int32_t) const>(&WeaponConsumerAccess::internalUseWeapon);
  (weapon.*consumer)(&player,&item,&target,100);
 }
};

static void config()
{
 const auto original = boost::filesystem::current_path();
 const auto scratch = boost::filesystem::temp_directory_path() / boost::filesystem::unique_path("legacy-combat-%%%%-%%%%");
 boost::filesystem::create_directory(scratch);
 { std::ofstream file((scratch / "config.lua").string()); file << "freePremium = false\nrateSkill = 1\nrateMagic = 1\n"; }
 boost::filesystem::current_path(scratch); const bool ok = g_config.load();
 boost::filesystem::current_path(original); boost::filesystem::remove_all(scratch);
 require(ok, "isolated config");
}

static void weaponVectors(Player& player, Weapons& weapons)
{
 std::unique_ptr<Item> item(Item::CreateItem(3301));
 require(item != nullptr, "broadsword fixture");
 item->setIntAttr(ITEM_ATTRIBUTE_ATTACK, 50);
 const Weapon* weapon = weapons.getWeapon(item.get());
 require(weapon != nullptr, "real registered melee consumer");
 for (int mode = 1; mode <= 3; ++mode) {
  player.setFightMode(static_cast<fightMode_t>(mode));
  for (unsigned seed = 0; seed < 200; ++seed) {
   getRandomGenerator().seed(seed);
   const int32_t first = uniform_random(0, 99), second = uniform_random(0, 99);
   const int32_t expected = -LegacyCombat::probe(LegacyCombat::attackValue(50, mode), 80, first, second);
   getRandomGenerator().seed(seed);
   require(WeaponConsumerAccess::damage(*weapon, player, *item) == expected, "real melee exact triangular integer draw");
  }
  const int32_t ordinary = WeaponConsumerAccess::damage(*weapon, player, *item, true);
  const int auditedMaximum[] = {0,267,222,133};
  require(ordinary == -auditedMaximum[mode], "actual weapon matches independently audited maxima");
  item->setRarityData(ITEM_RARITY_LEGENDARY, ITEM_RARITY_BONUS_ATTACK, 10, 0);
  require(WeaponConsumerAccess::damage(*weapon, player, *item, true) == ordinary, "rarity attack has no numerical effect");
  item->setRarityData(ITEM_RARITY_NONE, ITEM_RARITY_BONUS_NONE, 0, 0);
 }
 require(LegacyCombat::maximum(42,55) == 135 && LegacyCombat::maximum(80,120) == 514, "audited dragon and demon physical maxima");
}

static void pipeline(Player& attacker, Player& target)
{
 Item* amulet = Item::CreateItem(3084, 2);
 Item* ring = Item::CreateItem(3048, 2);
 require(amulet && ring, "protection fixtures");
 static_cast<Cylinder&>(target).internalAddThing(CONST_SLOT_NECKLACE, amulet);
 static_cast<Cylinder&>(target).internalAddThing(CONST_SLOT_RING, ring);
 target.setItemAbility(CONST_SLOT_NECKLACE, true);
 target.setItemAbility(CONST_SLOT_RING, true);
 int32_t amount = 101;
 require(target.blockHit(&attacker, COMBAT_PHYSICALDAMAGE, amount) == BLOCK_NONE && amount == 35,
  "actual blockHit PvP ceil then sequential floor:101->51->47->35");
 require(amulet->getCharges() == 1 && ring->getCharges() == 1, "both protection uses consumed after reduction");
 amount = 1;
 target.blockHit(&attacker, COMBAT_PHYSICALDAMAGE, amount);
 require(amount == 0 && !target.getInventoryItem(CONST_SLOT_NECKLACE), "last use still protects then expires");
 require(ring->getCharges() == 1, "later slot does not consume after zero damage");
 // Remove remaining equipment to isolate actual resource consumer.
 g_game.internalRemoveItem(ring);
 target.addCondition(Condition::createCondition(CONDITIONID_DEFAULT, CONDITION_MANASHIELD, -1));
 target.changeMana(-target.getMana() + 20);
 CombatDamage damage; damage.type = COMBAT_FIREDAMAGE; damage.value = -51;
 require(!g_game.combatBlockHit(damage, &attacker, &target, false, false), "actual Game block entry");
 require(damage.value == -26, "odd PvP rounds upward once");
 const int32_t health = target.getHealth();
 require(g_game.combatChangeHealth(&attacker, &target, damage), "actual Game resource consumer");
 require(target.getMana() == 0 && target.getHealth() == health - 6, "shield1:1 and HP remainder");
 require(target.hasCondition(CONDITION_MANASHIELD), "empty mana retains shield condition");
 target.removeCondition(CONDITION_MANASHIELD);
 Item* misplaced = Item::CreateItem(3084, 2);
 static_cast<Cylinder&>(target).internalAddThing(CONST_SLOT_LEFT, misplaced);
 target.setItemAbility(CONST_SLOT_LEFT, true);
 amount = 100;
 target.blockHit(nullptr, COMBAT_PHYSICALDAMAGE, amount);
 require(amount == 100 && misplaced->getCharges() == 2, "necklace held in hand neither protects nor wears");
 g_game.internalRemoveItem(misplaced);
}

static void chargeLessProtection(Player& attacker, Player& target)
{
 Item* legs = Item::CreateItem(3364);
 require(legs != nullptr, "golden legs fixture");
 static_cast<Cylinder&>(target).internalAddThing(CONST_SLOT_LEGS, legs);
 target.setItemAbility(CONST_SLOT_LEGS, true);
 require(legs->getCharges() == 0, "equipment fixture carries no charges");
 int32_t amount = 100;
 require(target.blockHit(&attacker, COMBAT_PHYSICALDAMAGE, amount) == BLOCK_NONE && amount == 49,
  "charge-less protection halves PvP then removes 2 percent");
 require(target.getInventoryItem(CONST_SLOT_LEGS) == legs && !legs->isRemoved(),
  "permanent equipment must survive absorbed damage");
 amount = 100;
 target.blockHit(&attacker, COMBAT_PHYSICALDAMAGE, amount);
 require(amount == 49 && target.getInventoryItem(CONST_SLOT_LEGS) == legs,
  "permanent equipment keeps protecting across hits");
 g_game.internalRemoveItem(legs);
}

static void effects(Player& target)
{
 struct Vector { ConditionType_t type; int force; int total; int cadence; int pulses; };
 for (const Vector& v : {Vector{CONDITION_POISON,100,100,4,60}, {CONDITION_POISON,30,30,4,30},
  {CONDITION_FIRE,70,70,9,7}, {CONDITION_ENERGY,25,25,11,1}, {CONDITION_ENERGY,100,125,11,5}}) {
  ConditionDamage condition(CONDITIONID_COMBAT, v.type);
  condition.setLegacyForce(v.force);
  require(condition.startCondition(&target), "actual damage condition starts");
  const int32_t health = target.getHealth(); int pulses = 0;
  for (int second = 1; second <= v.cadence * v.pulses; ++second) {
   const int32_t prior = target.getHealth();
   condition.executeCondition(&target, 1000);
   if (target.getHealth() != prior) { ++pulses; require(second % v.cadence == 0, "effect logical cadence"); }
  }
  require(health - target.getHealth() == v.total && pulses == v.pulses, "actual condition pulse sum and count");
  require(condition.getLegacyReserve() == 0, "reserve exhausted by raw pulses");
 }
 ConditionDamage original(CONDITIONID_COMBAT, CONDITION_POISON); original.setLegacyForce(100); original.startCondition(&target);
 original.executeCondition(&target, 1000);
 PropWriteStream saved; original.serialize(saved); saved.write<uint8_t>(CONDITIONATTR_END);
 size_t size; const char* bytes = saved.getStream(size); PropStream input(bytes, size);
 std::unique_ptr<Condition> restored(Condition::createCondition(input));
 require(restored && restored->unserialize(input), "condition serialized roundtrip");
 const int hp = target.getHealth();
 restored->executeCondition(&target, 2000);
 require(target.getHealth() == hp, "roundtrip retains partial pulse phase");
 restored->executeCondition(&target, 1000);
 require(target.getHealth() == hp - 5, "roundtrip reaches the original fourth second");
 ConditionDamage smaller(CONDITIONID_COMBAT, CONDITION_POISON); smaller.setLegacyForce(10);
 original.addCondition(&target, &smaller);
 require(original.getLegacyReserve() == 100, "weaker poison does not replace reserve");
 // All nine reference masks exclude applications. A controlled mask proves
 // the generic stage still runs before the cycle division and before immunity.
 Item::items.getItemType(3084).getAbilities().legacyConditionAbsorbPercent[1] = 50;
 Item* amulet = Item::CreateItem(3084, 2);
 static_cast<Cylinder&>(target).internalAddThing(CONST_SLOT_NECKLACE, amulet);
 target.setItemAbility(CONST_SLOT_NECKLACE, true);
 ConditionDamage fire(CONDITIONID_COMBAT, CONDITION_FIRE); fire.setLegacyForce(19);
 require(!fire.startCondition(&target) && fire.getLegacyReserve() == 0, "application protects raw19->9 before fire division");
 require(amulet->getCharges() == 1, "application protection consumes one use without a pulse");
 g_game.internalRemoveItem(amulet);
 Item::items.getItemType(3084).getAbilities().legacyConditionAbsorbPercent[1] = 0;
}

static void contactPoison(Player& attacker, Player& target)
{
 Item* helmet = Item::CreateItem(3351);
 helmet->setIntAttr(ITEM_ATTRIBUTE_ARMOR,2000);
 static_cast<Cylinder&>(target).internalAddThing(CONST_SLOT_HEAD,helmet);
 LoginGateCoreTestAccess::defenseClock(target,false);
 CombatParams params; params.combatType = COMBAT_PHYSICALDAMAGE; params.blockedByShield = true;
 ConditionDamage* poison = new ConditionDamage(CONDITIONID_COMBAT,CONDITION_POISON); poison->setLegacyForce(10);
 params.conditionList.emplace_front(poison);
 unsigned applied = 0;
 for (unsigned seed = 0; seed < 100; ++seed) {
  target.removeCondition(CONDITION_POISON);
  getRandomGenerator().seed(seed); uniform_random(0,999); const bool expected = uniform_random(0,4) == 0;
  getRandomGenerator().seed(seed);
  CombatDamage damage; damage.type = COMBAT_PHYSICALDAMAGE; damage.value = -100;
  CombatConsumerAccess::health(&attacker,&target,params,damage);
  require(target.hasCondition(CONDITION_POISON) == expected, "actual contact poison 1/5 after armor, without HP damage");
  applied += expected;
 }
 require(applied > 0 && applied < 100, "contact vectors exercise both branches");
 target.removeCondition(CONDITION_POISON); g_game.internalRemoveItem(helmet);
 Item* shield = Item::CreateItem(3420); shield->setIntAttr(ITEM_ATTRIBUTE_DEFENSE,10000);
 static_cast<Cylinder&>(target).internalAddThing(CONST_SLOT_LEFT,shield);
 LoginGateCoreTestAccess::defenseClock(target,true);
 getRandomGenerator().seed(74);
 CombatDamage damage; damage.type = COMBAT_PHYSICALDAMAGE; damage.value = -1;
 CombatConsumerAccess::health(&attacker,&target,params,damage);
 require(!target.hasCondition(CONDITION_POISON), "defense block never reaches contact poison fallback");
 g_game.internalRemoveItem(shield);
}

static void fields(Player& target)
{
 Item* item = Item::CreateItem(2118);
 require(item && item->getMagicField(), "native strong fire field fixture");
 static_cast<Cylinder&>(*target.getTile()).internalAddThing(item);
 const int initial = target.getHealth();
 item->getMagicField()->onStepInField(&target);
 auto* fire = static_cast<ConditionDamage*>(target.getCondition(CONDITION_FIRE));
 require(fire && fire->getLegacyReserve() == 7 && target.getHealth() == initial - 20, "native field creates70 fire plus20 separate immediate damage");
 for (unsigned tick = 0; tick < 9; ++tick) target.executeConditions(1000);
 require(fire->getLegacyReserve() == 7 && target.getHealth() == initial - 30, "standing fire renews a cycle after its pulse");
 g_game.internalRemoveItem(item);
 for (unsigned tick = 0; tick < 63; ++tick) target.executeConditions(1000);
 require(!target.hasCondition(CONDITION_FIRE) && target.getHealth() == initial - 100, "leaving fire consumes the seven remaining cycles");

 item = Item::CreateItem(2121); static_cast<Cylinder&>(*target.getTile()).internalAddThing(item);
 item->getMagicField()->onStepInField(&target);
 auto* poison = static_cast<ConditionDamage*>(target.getCondition(CONDITION_POISON));
 require(poison && poison->getLegacyReserve() == 100, "native poison field reserve");
 for (unsigned tick = 0; tick < 400; ++tick) target.executeConditions(1000);
 require(poison->getLegacyReserve() == 39, "native field poison converges to audited reserve39");
 g_game.internalRemoveItem(item); target.removeCondition(CONDITION_POISON);

 item = Item::CreateItem(2131); static_cast<Cylinder&>(*target.getTile()).internalAddThing(item);
 const int before = target.getHealth(); item->getMagicField()->onStepInField(&target);
 require(target.getHealth() == before && !target.hasCondition(CONDITION_FIRE), "peaceful player is ignored by field2131");
 g_game.internalRemoveItem(item);
}

static void learningSources(Player& attacker, Player& target, Weapons& weapons)
{
 std::unique_ptr<Item> weaponItem(Item::CreateItem(3301)); weaponItem->setIntAttr(ITEM_ATTRIBUTE_ATTACK,50);
 const Weapon* weapon = weapons.getWeapon(weaponItem.get());
 attacker.setFightMode(FIGHTMODE_BALANCED); attacker.setSecureMode(false);
 LoginGateCoreTestAccess::learning(attacker,0); LoginGateCoreTestAccess::defenseClock(target,false);
 getRandomGenerator().seed(74); const int before = target.getHealth();
 WeaponConsumerAccess::hit(*weapon,attacker,*weaponItem,target);
 require(target.getHealth() < before && LoginGateCoreTestAccess::learning(attacker) == 30, "real positive weapon hit replenishes learning credits");

 LoginGateCoreTestAccess::learning(attacker,0);
 CombatParams params; params.combatType = COMBAT_FIREDAMAGE;
 CombatDamage magic; magic.type = COMBAT_FIREDAMAGE; magic.value = -100;
 CombatConsumerAccess::health(&attacker,&target,params,magic);
 require(LoginGateCoreTestAccess::learning(attacker) == 0, "direct spell/rune damage does not replenish weapon training");
 target.changeMana(100);
 target.addCondition(Condition::createCondition(CONDITIONID_DEFAULT,CONDITION_MANASHIELD,-1));
 magic.value = -100; CombatConsumerAccess::health(&attacker,&target,params,magic);
 require(LoginGateCoreTestAccess::learning(attacker) == 0, "mana-shielded spell does not replenish training");
 target.removeCondition(CONDITION_MANASHIELD);

 attacker.setID(); attacker.setGUID(990001); attacker.setName("Legacy origin"); g_game.addPlayer(&attacker);
 struct Unregister { Player& player; ~Unregister() { g_game.removePlayer(&player); } } unregister{attacker};
 ConditionDamage burning(CONDITIONID_COMBAT,CONDITION_FIRE); burning.setLegacyForce(10);
 burning.setParam(CONDITION_PARAM_OWNER,attacker.getID()); require(burning.startCondition(&target), "owned pulse fixture");
 const int pulseBefore = target.getHealth(); burning.executeCondition(&target,9000);
 require(target.getHealth() == pulseBefore - 5 && LoginGateCoreTestAccess::learning(attacker) == 0, "resolved player DoT is PvP-reduced and does not replenish training");

 ConditionDamage persisted(CONDITIONID_COMBAT,CONDITION_POISON); persisted.setLegacyForce(100);
 persisted.setParam(CONDITION_PARAM_OWNER,attacker.getID()); require(persisted.startCondition(&target), "stable owner fixture");
 PropWriteStream saved; persisted.serialize(saved); saved.write<uint8_t>(CONDITIONATTR_END);
 size_t length; const char* bytes = saved.getStream(length);
 const uint32_t priorId = attacker.getID(); g_game.removePlayer(&attacker);
 LoginGateCoreTestAccess::runtimeId(attacker,priorId + 500); g_game.addPlayer(&attacker);
 Player decoy(nullptr); decoy.setGroup(attacker.getGroup()); decoy.setParent(attacker.getTile());
 decoy.setGUID(990002); decoy.setName("Legacy unrelated"); LoginGateCoreTestAccess::runtimeId(decoy,priorId); g_game.addPlayer(&decoy);
 Unregister unregisterDecoy{decoy};
 Player fresh(nullptr); LoginGateCoreTestAccess::prepare(fresh,*attacker.getGroup(),*target.getTile());
 PropStream input(bytes,length); std::unique_ptr<Condition> restored(Condition::createCondition(input));
 require(restored && restored->unserialize(input) && restored->startCondition(&fresh), "restore stable player GUID");
 const int hp = fresh.getHealth(); restored->executeCondition(&fresh,4000);
 require(fresh.getHealth() == hp - 3 && fresh.hasBeenAttacked(attacker.getID()) && !fresh.hasBeenAttacked(decoy.getID()), "persisted effect resolves same GUID at new runtime ID, never its old ID occupant");
 g_game.removePlayer(&attacker);
 PropStream offlineInput(bytes,length); std::unique_ptr<Condition> offline(Condition::createCondition(offlineInput));
 require(offline && offline->unserialize(offlineInput) && offline->startCondition(&fresh), "offline owner restore");
 const int offlineHp = fresh.getHealth(); offline->executeCondition(&fresh,4000); g_game.addPlayer(&attacker);
 require(fresh.getHealth() == offlineHp - 5 && !fresh.hasBeenAttacked(decoy.getID()), "offline GUID is unresolved: damage continues without PvP or false author");
}

static void rangedDefense(Player& attacker, Player& target, Weapons& weapons)
{
 Item* shooterShield = Item::CreateItem(3420); Item* defenderShield = Item::CreateItem(3420);
 defenderShield->setIntAttr(ITEM_ATTRIBUTE_DEFENSE,10000);
 static_cast<Cylinder&>(attacker).internalAddThing(CONST_SLOT_LEFT,shooterShield);
 static_cast<Cylinder&>(target).internalAddThing(CONST_SLOT_LEFT,defenderShield);
 LoginGateCoreTestAccess::learning(target,30); LoginGateCoreTestAccess::defenseClock(target,true);
 std::unique_ptr<Item> arrow(Item::CreateItem(3447,1)); const Weapon* weapon = weapons.getWeapon(arrow.get());
 require(weapon != nullptr,"registered arrow consumer");
 getRandomGenerator().seed(74); const int first = uniform_random(0,99), second = uniform_random(0,99);
 const int expected = -LegacyCombat::probe(arrow->getAttack(),80,first,second);
 getRandomGenerator().seed(74);
 const int actual = WeaponConsumerAccess::damage(*weapon,attacker,*arrow,false,&target);
 require(actual == expected && LoginGateCoreTestAccess::learning(target) == 29, "ranged target defense consumes timer/credit but does not subtract its roll");
 g_game.internalRemoveItem(shooterShield); g_game.internalRemoveItem(defenderShield);
 LoginGateCoreTestAccess::learning(target,0);
}

static void spellCallbacks(Player& player)
{
 struct SpellVector { const char* file; int base; int variation; bool minimum; bool maximum; bool berserk; };
 const SpellVector spells[] = {
  {"runes/light magic missile.lua",15,5,true,false,false}, {"runes/heavy magic missile.lua",30,10,true,false,false},
  {"runes/fireball.lua",20,5,true,false,false}, {"runes/great fireball.lua",50,15,true,false,false},
  {"runes/explosion.lua",60,40,false,false,false}, {"runes/sudden death.lua",150,20,false,false,false},
  {"spells/ultimate explosion.lua",250,50,false,false,false}, {"spells/energy wave.lua",150,50,false,false,false},
  {"spells/fire wave.lua",30,10,true,false,false}, {"spells/energy beam.lua",60,20,false,false,false},
  {"spells/great energy beam.lua",120,80,false,false,false}, {"spells/force strike.lua",45,10,false,false,false},
  {"spells/energy strike.lua",45,10,false,false,false}, {"spells/flame strike.lua",45,10,false,false,false},
  {"spells/berserk.lua",80,20,false,true,true}
 };
 for (const auto& v : spells) {
  LuaScriptInterface script("Legacy damage callback"); require(script.initState(), "callback interface init");
  std::set<uint32_t> existing;
  for (uint32_t id = 0; id < 4096; ++id) if (g_luaEnvironment.getCombatObject(id)) existing.insert(id);
  require(script.loadFile(std::string("data/spells/scripts/") + v.file) == 0, "load actual damage Lua file");
  const Combat* actualCombat = nullptr;
  for (uint32_t id = 0; id < 4096; ++id) if (!existing.count(id) && g_luaEnvironment.getCombatObject(id)) { actualCombat = g_luaEnvironment.getCombatObject(id); break; }
  require(actualCombat != nullptr,"actual Lua-created combat and its registered callback");
  for (bool high : {false,true}) {
   require(luaL_dostring(script.getLuaState(), high ? "math.random=function(a,b) return b end" : "math.random=function(a,b) return a end") == 0, "controlled Lua RNG");
   for (int level : {1,50,100}) for (int magic : {0,10,50}) {
    LoginGateCoreTestAccess::attributes(player, level, magic);
    int factor = 2 * level + 3 * magic;
    if (v.minimum) factor = std::max(factor,100);
    if (v.maximum) factor = std::min(factor,100);
    int expected = (v.base + (high ? v.variation : -v.variation)) * factor / 100;
    if (v.berserk) expected = expected * level / 25;
    const CombatDamage damage = CombatConsumerAccess::damage(*actualCombat,&player,nullptr);
    require(damage.value == -expected, std::string("actual Lua callback integer formula: ") + v.file);
   }
  }
  if (v.berserk || std::string(v.file) == "spells/ultimate explosion.lua") {
   Player defender(nullptr); LoginGateCoreTestAccess::prepare(defender,*player.getGroup(),*player.getTile());
   Item* shield = Item::CreateItem(3420); shield->setIntAttr(ITEM_ATTRIBUTE_DEFENSE,10000);
   static_cast<Cylinder&>(defender).internalAddThing(CONST_SLOT_LEFT,shield);
   LoginGateCoreTestAccess::defenseClock(defender,true); LoginGateCoreTestAccess::learning(defender,30);
   LoginGateCoreTestAccess::attributes(player,50,50);
   require(luaL_dostring(script.getLuaState(),"math.random=function(a,b) return a end") == 0,"controlled area spell roll");
   const int expected = v.berserk ? 60 : 250;
   const int health = defender.getHealth(); CombatConsumerAccess::health(*actualCombat,&player,&defender);
   require(defender.getHealth() == health - expected && LoginGateCoreTestAccess::learning(defender) == 30,"actual UE/Berserk Lua combat ignores shield defense and shielding training");
   g_game.internalRemoveItem(shield);
  }
 }
}

int main()
{
 try {
  config(); require(Item::items.loadItems(), "production items load");
  require(g_vocations.loadFromXml(), "production vocations load");
  require(g_luaEnvironment.initState(), "Lua environment");
  require(g_luaEnvironment.loadFile("data/global.lua") == 0, "production Lua libraries");
  Events events; MoveEvents movements; CreatureEvents creatures; Weapons weapons;
  g_events = &events; g_moveEvents = &movements; g_creatureEvents = &creatures; g_weapons = &weapons;
  require(weapons.loadFromXml(), "production weapon registry"); weapons.loadDefaults();
  g_game.setWorldType(WORLD_TYPE_PVP);
  Group group = {}; group.flags = PlayerFlag_NotGainSkill;
  DynamicTile origin(100,100,7), destination(101,100,7);
  Player attacker(nullptr), target(nullptr);
  LoginGateCoreTestAccess::prepare(attacker,group,origin); LoginGateCoreTestAccess::prepare(target,group,destination);
  weaponVectors(attacker,weapons); pipeline(attacker,target); chargeLessProtection(attacker,target); effects(target); contactPoison(attacker,target); fields(target); learningSources(attacker,target,weapons); rangedDefense(attacker,target,weapons); spellCallbacks(attacker);
  g_game.cleanup(true);
  std::cout << "PASS legacy combat: " << checks << " actual core/Lua checks" << std::endl;
  return 0;
 } catch (const std::exception& failure) { std::cerr << "FAIL " << failure.what() << std::endl; return 1; }
}
