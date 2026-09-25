local killStorage = 3000
local deathStorage = 3001
local toMostDamage = true
local toKiller = true
function onDeath(creature, corpse, killer, mostDamageKiller, lastHitUnjustified, mostDamageUnjustified)
    if not creature:isPlayer() then return true end
    if creature then
        if killer and killer:isPlayer() and toKiller then
            local killAmount = killer:getStorageValue(killStorage)
            if killAmount == -1 then killAmount = 0 end
            killer:setStorageValue(killStorage, killAmount + 1)
        end
        if mostDamageKiller and mostDamageKiller:isPlayer() and toMostDamage
            and (not toKiller or not killer or killer:getId() ~= mostDamageKiller:getId()) then
            local killAmount = mostDamageKiller:getStorageValue(killStorage)
            if killAmount == -1 then killAmount = 0 end
            mostDamageKiller:setStorageValue(killStorage, killAmount + 1)
        end
        local deathAmount = creature:getStorageValue(deathStorage)
        if deathAmount == -1 then deathAmount = 0 end
        creature:setStorageValue(deathStorage, deathAmount + 1)
    end
    return true
end
