#ifndef FS_LEGACYCOMBAT_H
#define FS_LEGACYCOMBAT_H

#include <algorithm>
#include <cstdint>
#include "tools.h"

// Arithmetic reconstructed from the audited ELF. Keep each integer division at
// its original stage: combining the divisions changes low damage results.
namespace LegacyCombat {
inline int32_t attackValue(int32_t value, uint8_t mode)
{
    if (mode == 1) return value + (2 * value) / 10;
    if (mode == 3) return value - (4 * value) / 10;
    return value;
}
inline int32_t defendValue(int32_t value, uint8_t mode)
{
    if (mode == 1) return value - (4 * value) / 10;
    if (mode == 3) return value + (8 * value) / 10;
    return value;
}
inline int32_t probe(int32_t value, int32_t skill, int32_t first, int32_t second)
{
    return static_cast<int32_t>((int64_t(value) * (5LL * skill + 50) * ((first + second) / 2)) / 10000);
}
inline int32_t probe(int32_t value, int32_t skill)
{
    const int32_t first = uniform_random(0, 99);
    const int32_t second = uniform_random(0, 99);
    return probe(value, skill, first, second);
}
inline int32_t maximum(int32_t value, int32_t skill)
{
    return probe(value, skill, 99, 99);
}
inline int32_t pvp(int32_t damage) { return (damage / 2) + (damage % 2); }
inline int32_t protect(int32_t damage, int32_t percent)
{
    return static_cast<int32_t>(int64_t(damage) * (100 - percent) / 100);
}
inline int32_t armor(int32_t value)
{
    return value <= 1 ? value : value / 2 + uniform_random(0, value / 2 - 1);
}
}
#endif
