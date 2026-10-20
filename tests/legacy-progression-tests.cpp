#include "otpch.h"
#include "vocation.h"
#include "player.h"
#include "condition.h"
#include "bed.h"
#include "tile.h"
#include "groups.h"
#include "events.h"
#include "creatureevent.h"
#include <stdexcept>
#include <iostream>
extern Vocations g_vocations;
extern Events* g_events;
extern CreatureEvents* g_creatureEvents;
struct LoginGateCoreTestAccess {
 static void gain(Player& p,uint64_t amount) { p.addExperience(nullptr,amount,false); }
 static void prepare(Player& p, Group& group, Tile& tile, uint16_t vocation, bool premium, int hp=50, int mp=50) {
  p.setGroup(&group); p.setParent(&tile); p.setVocation(vocation);
  p.setPremiumDays(premium ? 30 : 0); p.health=hp; p.healthMax=100; p.mana=mp; p.manaMax=100;
 }
 static void clearParent(Player& p) { p.setParent(nullptr); }
 static void regenerateBed(BedItem& bed, Player& player, time_t offline) { player.lastLogout=time(nullptr)-offline; bed.regeneratePlayer(&player); }
 static void resetProgress(Player& p) { p.magLevel=0; p.manaSpent=0; p.level=1; p.experience=0; for (auto& skill:p.skills) {skill.level=10;skill.tries=0;} }
 static uint64_t skillProgress(const Player& p, skills_t skill) { return p.skills[skill].tries; }
 static uint64_t manaProgress(const Player& p) { return p.manaSpent; }
};
static unsigned checks=0;
static void expect(bool ok, const char* why) { ++checks; if (!ok) throw std::runtime_error(why); }
int main() {
 Vocations& vocations = g_vocations; expect(vocations.loadFromXml(), "vocations load");
 std::cerr << "P1 loaded" << std::endl;
 auto* knight=vocations.getVocation(4); auto* paladin=vocations.getVocation(3);
 auto* sorcerer=vocations.getVocation(1); auto* druid=vocations.getVocation(2);
 std::cerr << "P2 vocations=" << (knight!=nullptr) << (paladin!=nullptr) << (sorcerer!=nullptr) << (druid!=nullptr) << std::endl;
 expect(knight->getReqMana(1)==1600, "magic 0 to 1 is 1600");
 expect(knight->getReqMana(6)==388800, "knight magic 5 to 6");
 expect(paladin->getReqMana(6)==8606, "paladin cumulative-floor magic");
 expect(sorcerer->getReqMana(6)==2576, "mage cumulative-floor magic");
 expect(knight->getReqSkillTries(SKILL_SWORD,21)==130, "knight sword20 to21");
 expect(paladin->getReqSkillTries(SKILL_SWORD,21)==310, "paladin sword20 to21");
 expect(sorcerer->getReqSkillTries(SKILL_SWORD,21)==51200, "sorcerer sword20 to21");
 expect(druid->getReqSkillTries(SKILL_SWORD,21)==17853, "druid sword20 to21");
 expect(knight->getReqSkillTries(SKILL_FISHING,21)==52, "fishing cumulative floors");
 expect(vocations.getVocation(5)->getManaGainAmount()==2, "promoted mage gains2 mana");
 expect(vocations.getVocation(0)->getManaGainAmount()==2, "novocation gains2 mana");
 std::cerr << "P3 magic ok" << std::endl;
 // Pinned results from original ELF Increase/GetExpForLevel emulation.
 struct CurveVector {uint16_t vocation; uint8_t skill; uint16_t next; uint64_t cost; uint64_t cumulative;};
 const CurveVector vectors[] = {{4,2,11,50,50},{4,2,21,130,926},{3,2,11,50,50},{3,2,21,310,1607},{1,2,11,50,50},{1,2,21,51200,102350},{2,2,11,50,50},{2,2,21,17853,40105},{4,4,11,30,30},{4,4,21,868,2962},{1,5,11,100,100},{1,5,21,5766,17099},{4,99,1,1600,1600},{4,99,6,388800,582400},{3,99,1,1600,1600},{3,99,6,8606,26118},{1,99,1,1600,1600},{1,99,6,2576,12344},{4,6,11,20,20},{4,6,21,52,370}};
 for (const auto& vector:vectors) {
  Vocation* v=vocations.getVocation(vector.vocation);
  const bool magic=vector.skill==99;
  expect((magic?v->getReqMana(vector.next):v->getReqSkillTries(vector.skill,vector.next))==vector.cost,"original ELF next-cost vector");
  uint64_t cumulative=0;
  for (uint16_t n=magic?1:11;n<=vector.next;++n) cumulative+=magic?v->getReqMana(n):v->getReqSkillTries(vector.skill,n);
  expect(cumulative==vector.cumulative,"original ELF cumulative threshold vector");
 }
 Events events; CreatureEvents creatureEvents;
 std::cerr << "P4 vectors ok" << std::endl;
 g_events=&events; g_creatureEvents=&creatureEvents;
 Group group{}; DynamicTile tile(100,100,7); Player player(nullptr);
 LoginGateCoreTestAccess::prepare(player,group,tile,4,false);
 LoginGateCoreTestAccess::resetProgress(player);
 std::cerr << "P5 player ready" << std::endl;
 player.addManaSpent(1599);
 expect(player.getBaseMagicLevel()==0 && LoginGateCoreTestAccess::manaProgress(player)==1599,"actual mana consumer below threshold");
 player.addManaSpent(1);
 expect(player.getBaseMagicLevel()==1 && LoginGateCoreTestAccess::manaProgress(player)==0,"actual mana consumer exact threshold");
 player.addSkillAdvance(SKILL_FISHING,19);
 expect(player.getSkillLevel(SKILL_FISHING)==10 && LoginGateCoreTestAccess::skillProgress(player,SKILL_FISHING)==19,"actual skill consumer below threshold");
 player.addSkillAdvance(SKILL_FISHING,1);
 expect(player.getSkillLevel(SKILL_FISHING)==11 && LoginGateCoreTestAccess::skillProgress(player,SKILL_FISHING)==0,"actual skill consumer exact threshold");
 const uint64_t twoSkills=knight->getReqSkillTries(SKILL_FISHING,12)+knight->getReqSkillTries(SKILL_FISHING,13);
 player.addSkillAdvance(SKILL_FISHING,twoSkills+1);
 expect(player.getSkillLevel(SKILL_FISHING)==13 && LoginGateCoreTestAccess::skillProgress(player,SKILL_FISHING)==1,"actual skill consumer multiple thresholds");
 LoginGateCoreTestAccess::gain(player,Player::getExpForLevel(4)+1);
 expect(player.getLevel()==4 && player.getExperience()==Player::getExpForLevel(4)+1,"actual XP consumer multiple levels");
 std::cerr << "P6 xp ok" << std::endl;
 expect(!player.consumeLegacyLearningCredit(), "learning starts empty");
 player.refreshLegacyLearningCredit();
 for (int i=0;i<30;++i) expect(player.consumeLegacyLearningCredit(), "30 shared learning points");
 expect(!player.consumeLegacyLearningCredit(), "learning credit exhausted");
 std::cerr << "P7 learning ok" << std::endl;
 for (int food : {7,6,1}) {
  LoginGateCoreTestAccess::prepare(player,group,tile,4,false);
  ConditionRegeneration regen(CONDITIONID_DEFAULT,CONDITION_REGENERATION,food*1000);
  const bool active=regen.executeCondition(&player,1000);
  expect(player.getHealth()==(food==6?50:51), "remaining-food HP phase");
  expect(player.getMana()==(food==6?50:52), "remaining-food mana phase");
  expect(active==(food>1), "final food tick expires");
 }
 LoginGateCoreTestAccess::prepare(player,group,tile,4,false);
 tile.setFlag(TILESTATE_PROTECTIONZONE);
 ConditionRegeneration pz(CONDITIONID_DEFAULT,CONDITION_REGENERATION,7000);
 pz.executeCondition(&player,1000);
 expect(pz.getTicks()==6000 && player.getHealth()==50 && player.getMana()==50,"PZ consumes without regenerating");
 tile.resetFlag(TILESTATE_PROTECTIONZONE);
 LoginGateCoreTestAccess::prepare(player,group,tile,4,false,0);
 ConditionRegeneration dead(CONDITIONID_DEFAULT,CONDITION_REGENERATION,1000);
 dead.executeCondition(&player,1000);
 expect(player.getHealth()==0 && player.getMana()==50,"dead never regenerates");
 for (bool premium : {false,true}) {
  LoginGateCoreTestAccess::prepare(player,group,tile,5,premium);
  ConditionRegeneration regen(CONDITIONID_DEFAULT,CONDITION_REGENERATION,3000);
  regen.executeCondition(&player,1000);
  expect(player.getMana()==(premium?52:50),"promotion premium selected each tick");
 }
 LoginGateCoreTestAccess::prepare(player,group,tile,4,false,99,99);
 ConditionRegeneration full(CONDITIONID_DEFAULT,CONDITION_REGENERATION,1000);
 full.executeCondition(&player,1000);
 expect(player.getHealth()==100 && player.getMana()==100,"resource max caps");
 // Rings retain their configured elapsed clocks, including infinite duration.
 for (int duration : {10000,-1}) {
  LoginGateCoreTestAccess::prepare(player,group,tile,5,true);
  ConditionRegeneration ring(CONDITIONID_RING,CONDITION_REGENERATION,duration);
  ring.setParam(CONDITION_PARAM_HEALTHGAIN,7);
  ring.setParam(CONDITION_PARAM_HEALTHTICKS,2000);
  ring.setParam(CONDITION_PARAM_MANAGAIN,3);
  ring.setParam(CONDITION_PARAM_MANATICKS,1000);
  expect(ring.startCondition(&player), "ring condition starts");
  expect(ring.executeCondition(&player,1000), "ring remains active first tick");
  expect(player.getHealth()==50 && player.getMana()==53,"ring uses configured gains, not promoted vocation");
  expect(ring.executeCondition(&player,1000), "ring remains active second tick");
  expect(player.getHealth()==57 && player.getMana()==56,"ring keeps independent elapsed phases");
  expect(ring.getTicks()==(duration==-1?-1:8000),"ring finite/infinite duration preserved");
 }
 // The phase lives in serialized remaining ticks, not a fresh elapsed timer.
 LoginGateCoreTestAccess::prepare(player,group,tile,4,false);
 ConditionRegeneration saved(CONDITIONID_DEFAULT,CONDITION_REGENERATION,7000);
 PropWriteStream out; saved.serialize(out); out.write<uint8_t>(CONDITIONATTR_END);
 size_t size=0; const char* bytes=out.getStream(size); PropStream input; input.init(bytes,size);
 std::unique_ptr<Condition> restored(Condition::createCondition(input));
 expect(restored && restored->unserialize(input), "food condition persistence roundtrip");
 restored->executeCondition(&player,1000);
 expect(player.getHealth()==51 && player.getMana()==52 && restored->getTicks()==6000,"remaining phase survives roundtrip");
 LoginGateCoreTestAccess::prepare(player,group,tile,4,false);
 expect(player.addCondition(new ConditionRegeneration(CONDITIONID_DEFAULT,CONDITION_REGENERATION,12000)),"bed food fixture");
 BedItem bed(0); LoginGateCoreTestAccess::regenerateBed(bed,player,60);
 expect(player.getHealth()==51 && player.getMana()==54,"bed60seconds HP1 mana4");
 expect(!player.getCondition(CONDITION_REGENERATION,CONDITIONID_DEFAULT),"bed consumes food3perunit");
 LoginGateCoreTestAccess::clearParent(player);
 g_events=nullptr; g_creatureEvents=nullptr;
 std::cout << checks << " legacy progression checks passed\n";
}
