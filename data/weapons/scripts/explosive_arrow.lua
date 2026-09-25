local area = createCombatArea({
    {1, 1, 1},
    {1, 3, 1},
    {1, 1, 1}
})

local combat = Combat()
combat:setParameter(COMBAT_PARAM_TYPE, COMBAT_PHYSICALDAMAGE)
combat:setParameter(COMBAT_PARAM_EFFECT, CONST_ME_EXPLOSIONAREA)
combat:setParameter(COMBAT_PARAM_DISTANCEEFFECT, CONST_ANI_BURSTARROW)
--setCombatParam(combat, COMBAT_PARAM_BLOCKSHIELD, true)
--combat:setParameter(COMBAT_PARAM_BLOCKARMOR, true)
combat:setArea(area)

function onGetFormulaValues(player, level, magicLevel)
    local c = 1.2
    local d = 0.5
    local value = math.random((level + (magicLevel * 1.5))*c*d,(level + (magicLevel * 1.5))*c)
    return -value
end

combat:setCallback(CALLBACK_PARAM_LEVELMAGICVALUE, "onGetFormulaValues")

function onUseWeapon(player, variant)
    return combat:execute(player, variant)
end