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


#include "legacydeath.h"
#include <stdexcept>
static unsigned checks=0;
static void require(bool condition) { ++checks; if(!condition) throw std::runtime_error("legacy death assertion failed"); }
#include <iostream>
struct LoginGateCoreTestAccess {
 static void setup(Player& player, Group* group, unsigned profession, unsigned premium, unsigned mask) {
  player.setGroup(group); player.setID(); player.setVocation(profession); player.setPremiumDays(premium?30:0); player.blessings=mask;
 }
 static void resetMarks(Player& player) { player.attackedSet.clear(); player.formerAttackedSet.clear(); player.formerAggressor=false; player.formerMarksClearedAt=0; }
 static void formerParty(Player& player,uint32_t leader) { player.formerPartyLeader=leader; player.partyLeavingAt=OTSYS_TIME()/1000; }
 static void expiry(Player& player,time_t value) { player.playerKillerEnd=value; }
 static void aggression(Player& player,bool value) { player.skull=value?SKULL_WHITE:SKULL_NONE; }
 static uint64_t manaTotal(const Player& player) { uint64_t total=player.manaSpent; for(unsigned i=1;i<=player.magLevel;++i) total+=player.vocation->getReqMana(i); return total; }
 static uint64_t skillTotal(const Player& player) { uint64_t total=player.skills[SKILL_SWORD].tries; for(unsigned i=11;i<=player.skills[SKILL_SWORD].level;++i) total+=player.vocation->getReqSkillTries(SKILL_SWORD,i); return total; }
 static void die(Player& player,Town* town) {
  player.setTown(town); player.level=20; player.experience=100000; player.healthMax=5000; player.manaMax=5000; player.capacity=50000;
  player.magLevel=5; player.manaSpent=123; player.skills[SKILL_SWORD].level=15; player.skills[SKILL_SWORD].tries=9;
  const unsigned percent=player.getLegacyDeathPercent(); const uint64_t beforeMana=manaTotal(player), beforeSkill=skillTotal(player);
  player.death(nullptr);
  require(player.experience==100000-LegacyDeath::loss(100000,percent));
  require(manaTotal(player)==beforeMana-LegacyDeath::loss(beforeMana,percent));
  require(skillTotal(player)==beforeSkill-LegacyDeath::loss(beforeSkill,percent));
  require(player.blessings==0);
 }
 static void loot(Player& player,Group* group,Tile* tile,bool pk) {
  setup(player,group,1,0,0); player.setParent(tile); player.skull=pk?SKULL_RED:SKULL_NONE; player.playerKillerEnd=pk?1:0;
  Item* amulet=Item::CreateItem(ITEM_AMULETOFLOSS,1); Item* coin=Item::CreateItem(3031,1); Item* corpseItem=Item::CreateItem(2853,1);
  require(amulet && coin && corpseItem && corpseItem->getContainer());
  player.internalAddThing(CONST_SLOT_NECKLACE,amulet); player.internalAddThing(CONST_SLOT_RIGHT,coin);
  player.dropLoot(corpseItem->getContainer(),nullptr);
  require(player.inventory[CONST_SLOT_NECKLACE]==nullptr);
  require((player.inventory[CONST_SLOT_RIGHT]==nullptr)==pk);
  corpseItem->decrementReferenceCounter();
 }
 static void history(Player& player,const std::list<time_t>& list) { player.murderTimeStamps=list; }
 static unsigned killing(Player& player) { return player.checkPlayerKilling(); }
};
struct RuneGateAccess : Spell {
 static bool accepts(Spell& spell,Player* actor,const Position& position) {
  auto gate=&RuneGateAccess::playerRuneSpellCheck;
  return (spell.*gate)(actor,position);
 }
};
static unsigned instantGateCalls=0;
struct InstantGateFixture : InstantSpell {
 explicit InstantGateFixture(bool angle):InstantSpell(nullptr) { aggressive=true; selfTarget=!angle; needDirection=angle; scripted=false; function=&observe; }
 static bool observe(const InstantSpell*,Creature*,const std::string&) { ++instantGateCalls; return false; }
};
static void runeSecureGates(Player& actor,Player& victim,Tile& previousVictimTile,Group& group) {
 pugi::xml_document doc; require(doc.load_string("<rune name='secure fixture' id='3152' needtarget='1' aggressive='1' range='-1'/>"));
 RuneSpell directed(nullptr); require(directed.configureEvent(doc.first_child()));
 pugi::xml_document areaDoc; require(areaDoc.load_string("<rune name='secure area fixture' id='3191' needtarget='0' aggressive='1' range='-1'/>"));
 RuneSpell area(nullptr); require(area.configureEvent(areaDoc.first_child()));
 auto tile=new DynamicTile(101,100,7); g_game.map.setTile(tile->getPosition(),tile); tile->internalAddThing(&victim);
 LoginGateCoreTestAccess::resetMarks(actor); LoginGateCoreTestAccess::resetMarks(victim); LoginGateCoreTestAccess::expiry(victim,0); LoginGateCoreTestAccess::aggression(victim,false);
 actor.setSecureMode(true); g_game.setWorldType(WORLD_TYPE_PVP);
 require(!RuneGateAccess::accepts(directed,&actor,tile->getPosition()));
 require(!RuneGateAccess::accepts(area,&actor,tile->getPosition()));
 LoginGateCoreTestAccess::formerParty(actor,777); LoginGateCoreTestAccess::formerParty(victim,777);
 require(actor.getSkullClient(&victim)==SKULL_NONE);
 require(RuneGateAccess::accepts(directed,&actor,tile->getPosition()));
 require(RuneGateAccess::accepts(area,&actor,tile->getPosition()));
 LoginGateCoreTestAccess::formerParty(actor,0); LoginGateCoreTestAccess::formerParty(victim,0);
 g_game.setWorldType(WORLD_TYPE_PVP_ENFORCED);
 require(RuneGateAccess::accepts(directed,&actor,tile->getPosition()));
 require(RuneGateAccess::accepts(area,&actor,tile->getPosition()));
 g_game.setWorldType(WORLD_TYPE_PVP); actor.setSecureMode(false);
 require(RuneGateAccess::accepts(directed,&actor,tile->getPosition()));
 // Initial cast bypass is distinct from the affected-tile PZ filter.
 group.flags=PlayerFlag_IgnoreProtectionZone; tile->setFlag(TILESTATE_PROTECTIONZONE);
 require(RuneGateAccess::accepts(directed,&actor,tile->getPosition()));
 require(Combat::canDoCombat(&actor,tile,true)==RETURNVALUE_ACTIONNOTPERMITTEDINPROTECTIONZONE);
 require(Combat::canDoCombat(&actor,&victim)==RETURNVALUE_YOUMAYNOTATTACKAPERSONINPROTECTIONZONE);
 require(Combat::canTargetCreature(&actor,&victim)==RETURNVALUE_NOERROR);
 tile->resetFlag(TILESTATE_PROTECTIONZONE); group.flags=0;
 tile->removeThing(&victim,1);
 actor.getTile()->internalAddThing(&victim);
 actor.setSecureMode(true); LoginGateCoreTestAccess::resetMarks(actor); LoginGateCoreTestAccess::resetMarks(victim);
 InstantGateFixture mass(false),angle(true); std::string parameter;
 instantGateCalls=0; mass.playerCastInstant(&actor,parameter); require(instantGateCalls==0);
 LoginGateCoreTestAccess::formerParty(actor,777); LoginGateCoreTestAccess::formerParty(victim,777);
 mass.playerCastInstant(&actor,parameter); require(instantGateCalls==1);
 LoginGateCoreTestAccess::formerParty(actor,0); LoginGateCoreTestAccess::formerParty(victim,0);
 g_game.setWorldType(WORLD_TYPE_PVP_ENFORCED); mass.playerCastInstant(&actor,parameter); require(instantGateCalls==2);
 g_game.setWorldType(WORLD_TYPE_PVP); angle.playerCastInstant(&actor,parameter); require(instantGateCalls==3);
 actor.setSecureMode(false); actor.getTile()->removeThing(&victim,1); victim.setParent(&previousVictimTile);
}
int main() {
 require(g_vocations.loadFromXml());
 require(g_luaEnvironment.initState());
 Events events; g_events=&events;
 MoveEvents moves; g_moveEvents=&moves;
 require(Item::items.loadItems());
 Town town(1); town.setTemplePos(Position(100,100,7));
 Group group={};
 g_game.setWorldType(WORLD_TYPE_PVP);
 DynamicTile actorTile(100,100,7), victimTile(101,100,7);
 Player actor(nullptr), victim(nullptr);
 actor.setParent(&actorTile); victim.setParent(&victimTile);
 LoginGateCoreTestAccess::setup(actor,&group,1,0,0);
 LoginGateCoreTestAccess::setup(victim,&group,1,0,0);
 for(unsigned premium=0;premium<2;++premium) for(unsigned promoted=0;promoted<2;++promoted) for(unsigned blessings=0;blessings<=5;++blessings) {
  LoginGateCoreTestAccess::setup(actor,&group,promoted?5:1,premium,(1U<<blessings)-1);
  require(actor.getLegacyDeathPercent()==LegacyDeath::percent(premium,promoted,blessings));
  LoginGateCoreTestAccess::die(actor,&town);
 }
 require(!actor.isAttackJustified(&victim));
 LoginGateCoreTestAccess::expiry(victim,1); require(actor.isAttackJustified(&victim)); require(actor.getSkullClient(&victim)==SKULL_RED);
 LoginGateCoreTestAccess::expiry(victim,0); LoginGateCoreTestAccess::aggression(victim,true); require(actor.isAttackJustified(&victim)); require(actor.getSkullClient(&victim)==SKULL_WHITE);
 LoginGateCoreTestAccess::aggression(victim,false); actor.addAttacked(&victim); require(victim.isAttackJustified(&actor)); require(victim.getSkullClient(&actor)==SKULL_YELLOW);
 actor.clearAttacked(); require(victim.isAttackJustified(&actor)); require(victim.getSkullClient(&actor)==SKULL_NONE);
 g_game.setWorldType(WORLD_TYPE_PVP_ENFORCED); require(actor.isAttackJustified(&victim)); require(actor.getSkullClient(&victim)==SKULL_NONE);
 g_game.setWorldType(WORLD_TYPE_PVP);
 LoginGateCoreTestAccess::aggression(victim,false); actor.clearAttacked(); victim.clearAttacked();
 LoginGateCoreTestAccess::resetMarks(actor); LoginGateCoreTestAccess::resetMarks(victim);
 actor.setSecureMode(true); require(Combat::canTargetCreature(&actor,&victim)==RETURNVALUE_TURNSECUREMODETOATTACKUNMARKEDPLAYERS);
 LoginGateCoreTestAccess::expiry(victim,1); require(Combat::canTargetCreature(&actor,&victim)==RETURNVALUE_NOERROR);
 g_game.setWorldType(WORLD_TYPE_NO_PVP); require(Combat::canTargetCreature(&actor,&victim)==RETURNVALUE_YOUMAYNOTATTACKTHISPLAYER);
 g_game.setWorldType(WORLD_TYPE_PVP); LoginGateCoreTestAccess::expiry(victim,0); actor.setSecureMode(false);
 group.flags=PlayerFlag_CannotUseCombat; require(Combat::canTargetCreature(&actor,&victim)!=RETURNVALUE_NOERROR); group.flags=0;
 runeSecureGates(actor,victim,victimTile,group);
 for(unsigned pk=0;pk<2;++pk) { Player lootPlayer(nullptr); LoginGateCoreTestAccess::loot(lootPlayer,&group,&actorTile,pk); }
 std::list<time_t> threshold; for(unsigned i=0;i<3;++i) threshold.push_back(std::time(nullptr)); LoginGateCoreTestAccess::history(actor,threshold); require(LoginGateCoreTestAccess::killing(actor)==1);
 for(unsigned i=0;i<3;++i) threshold.push_back(std::time(nullptr)); LoginGateCoreTestAccess::history(actor,threshold); require(LoginGateCoreTestAccess::killing(actor)==2);

 for (unsigned premium=0;premium<2;++premium) for(unsigned promoted=0;promoted<2;++promoted) for(unsigned blessings=0;blessings<=5;++blessings) {
  unsigned percent=LegacyDeath::percent(premium,promoted,blessings);
  require(percent==(premium&&promoted?7U:10U)-blessings);
  for(uint64_t value: {0ULL,1ULL,99ULL,100ULL,999999ULL,18446744073709551615ULL}) {
   require(LegacyDeath::loss(value,percent)==value/100*percent+(value%100*percent)/100);
  }
 }
 require(LegacyDeath::withinGrace(100,104)); require(LegacyDeath::withinGrace(100,105)); require(!LegacyDeath::withinGrace(100,106)); require(!LegacyDeath::withinGrace(0,1));
 std::list<time_t> murders; time_t now=3000000;
 murders.push_back(now-86400); require(LegacyDeath::count(murders,now,86400)==0);
 murders.push_back(now-86400+1); require(LegacyDeath::count(murders,now,86400)==1);
 for(unsigned i=0;i<30;++i) LegacyDeath::record(murders,now+i);
 require(murders.size()==20 && murders.front()==now+10);
 // Production drains deferred item releases on its game loop. This isolated
 // fixture starts no loop, so flush the items consumed/transferred by dropLoot.
 g_game.cleanup(true);
 std::cout<<"PASS legacy death "<<checks<<" checks\n";
}
