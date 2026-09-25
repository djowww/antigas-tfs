local combat = Combat()
combat:setParameter(COMBAT_PARAM_TYPE, COMBAT_EARTHDAMAGE)
combat:setParameter(COMBAT_PARAM_EFFECT, CONST_ME_GREEN_RINGS)
combat:setArea(createCombatArea(AREA_CIRCLE5X5))

local condition = Condition(CONDITION_POISON)
condition:setParameter(CONDITION_PARAM_DELAYED, true)
condition:setParameter(CONDITION_PARAM_MINVALUE, 20)
condition:setParameter(CONDITION_PARAM_MAXVALUE, 50)
condition:setParameter(CONDITION_PARAM_STARTVALUE, 70)
condition:setParameter(CONDITION_PARAM_TICKINTERVAL, 4000)
condition:setParameter(CONDITION_PARAM_FORCEUPDATE, true)
combat:setCondition(condition)

function onCastSpell(creature, variant)
	return combat:execute(creature, variant)
end