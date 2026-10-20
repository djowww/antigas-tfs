#ifndef ANTIGAS_LEGACY_DEATH_H
#define ANTIGAS_LEGACY_DEATH_H
#include <cstdint>
#include <ctime>
#include <list>
namespace LegacyDeath {
inline bool withinGrace(int64_t clearedAt,int64_t now) { return clearedAt!=0 && now<=clearedAt+5; }
inline unsigned percent(bool premium,bool promoted,unsigned blessings) { return (premium&&promoted?7U:10U)-(blessings>5?5:blessings); }
inline uint64_t loss(uint64_t value,unsigned percentage) { return value/100*percentage+(value%100*percentage)/100; }
inline unsigned count(const std::list<time_t>& history,time_t now,time_t window) { unsigned result=0; for(time_t t:history) if(t>now-window) ++result; return result; }
inline void record(std::list<time_t>& history,time_t timestamp) { history.push_back(timestamp); while(history.size()>20) history.pop_front(); }
}
#endif
