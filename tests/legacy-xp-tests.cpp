#include "otpch.h"
#include "monster.h"
#include <iostream>
#include <memory>
#include <stdexcept>
static unsigned checks=0;
static void require(bool ok,const char* message) {++checks;if(!ok)throw std::runtime_error(message);}
int main() {
 try {
  MonsterType type;type.name="reference";type.info.experience=700;
  Monster victim(&type),a(&type),b(&type);a.setID();b.setID();
  victim.addDamagePoints(&a,300);victim.addDamagePoints(&b,100);
  require(victim.getGainedExperience(&a)==525,"damage300/400 must grant525 of700");
  require(victim.getGainedExperience(&b)==175,"damage100/400 must grant175 of700");
  Monster bounded(&type);std::vector<std::unique_ptr<Monster>> actors;
  for(unsigned i=0;i<21;++i){actors.emplace_back(new Monster(&type));actors.back()->setID();bounded.addDamagePoints(actors.back().get(),1);}
  require(bounded.getGainedExperience(actors.front().get())==0,"21st attacker must evict first contribution");
  require(bounded.getGainedExperience(actors.back().get())==33,"eviction must retain total21 denominator");
  bounded.addDamagePoints(actors.front().get(),1);
  require(bounded.getGainedExperience(actors[1].get())==0,"reinsertion replaces next cyclic slot");
  require(bounded.getGainedExperience(actors.front().get())==31,"reinsertion uses total22 denominator");
  Monster summoned(&type),master(&type),target(&type);summoned.setID();master.setID();summoned.setMaster(&master);
  target.addDamagePoints(&summoned,5);
  require(target.getGainedExperience(&master)==350,"master receives half recorded summon contribution");
  require(target.getGainedExperience(&summoned)==350,"summon retains other half without forwarding quarter");
  summoned.setMaster(nullptr);
  std::cout<<"legacy XP: "<<checks<<" checks passed\n";return 0;
 }catch(const std::exception&e){std::cerr<<"legacy XP: "<<e.what()<<'\n';return 1;}
}
