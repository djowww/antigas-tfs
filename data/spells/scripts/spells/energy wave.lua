local combat = Combat()
combat:setParameter(COMBAT_PARAM_TYPE, COMBAT_ENERGYDAMAGE)
combat:setParameter(COMBAT_PARAM_EFFECT, CONST_ME_TELEPORT)
combat:setArea(createCombatArea(AREA_SQUAREWAVE5))

function onGetFormulaValues(player, level, magicLevel)
 return damageFormula(level, magicLevel, 150, 50, "")
end

combat:setCallback(CALLBACK_PARAM_LEVELMAGICVALUE, "onGetFormulaValues")

function onCastSpell(creature, variant, isHotkey)
    return combat:execute(creature, variant)
end