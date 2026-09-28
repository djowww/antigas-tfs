-- Run from the server root: lua5.2 tests/killdeathcount-tests.lua
-- Pure Lua mocks; no database, server or player accounts are accessed.
dofile('data/creaturescripts/scripts/killdeathcount.lua')

local function player(id, sharedStorage)
    local subject = {id = id, storage = sharedStorage or {}}
    function subject:isPlayer() return true end
    function subject:getId() return self.id end
    function subject:getStorageValue(key)
        local value = self.storage[key]
        return value == nil and -1 or value
    end
    function subject:setStorageValue(key, value) self.storage[key] = value end
    return subject
end

local function died(victim, killer, mostDamage)
    assert(onDeath(victim, nil, killer, mostDamage, false, false))
    assert(victim:getStorageValue(3001) == 1, 'each death still counts once')
    assert(victim:getStorageValue(3000) == -1, 'the victim cannot receive a PvP kill')
end

local victim = player(1)
died(victim, victim, nil)

victim = player(2)
died(victim, nil, victim)

victim = player(3)
local attacker = player(4)
died(victim, victim, attacker)
assert(attacker:getStorageValue(3000) == 1, 'legitimate most-damage credit must survive a self last hit')

victim, attacker = player(5), player(6)
died(victim, attacker, victim)
assert(attacker:getStorageValue(3000) == 1, 'legitimate last-hit credit must survive self most-damage')

victim, attacker = player(7), player(8)
local attackerAlias = player(attacker:getId(), attacker.storage)
died(victim, attacker, attackerAlias)
assert(attacker:getStorageValue(3000) == 1, 'same attacker in both roles must be credited only once')

victim, attacker = player(9), player(10)
local secondAttacker = player(11)
died(victim, attacker, secondAttacker)
assert(attacker:getStorageValue(3000) == 1 and secondAttacker:getStorageValue(3000) == 1,
    'distinct legitimate last-hit and most-damage attackers keep their existing credits')

victim = player(12)
died(victim, player(victim:getId(), victim.storage), player(victim:getId(), victim.storage))

victim = player(13)
died(victim, nil, nil)

local monster = {isPlayer = function() return false end, getId = function() return 100 end}
victim, attacker = player(14), player(15)
died(victim, monster, attacker)
assert(attacker:getStorageValue(3000) == 1, 'monster last hit must not discard a legitimate player credit')
assert(onDeath(monster, nil, attacker, attacker, false, false))
assert(attacker:getStorageValue(3000) == 1, 'monster deaths must not count as PvP kills')

print('PASS legacy PvP: self last hit, self most damage, victim aliases, legitimate credits and deduplication')
