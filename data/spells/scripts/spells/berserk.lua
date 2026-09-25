local combat = Combat()
combat:setParameter(COMBAT_PARAM_TYPE, COMBAT_PHYSICALDAMAGE)
combat:setParameter(COMBAT_PARAM_EFFECT, CONST_ME_HITAREA)
combat:setParameter(COMBAT_PARAM_BLOCKARMOR, 1)
combat:setParameter(COMBAT_PARAM_BLOCKSHIELD, 1)
combat:setParameter(COMBAT_PARAM_USECHARGES, 1)
combat:setArea(createCombatArea(AREA_SQUARE1X1))
combat:setParameter(COMBAT_PARAM_PVPDAMAGE, 200)

function onGetFormulaValues(player, skill, attack, factor)
	local base = 80
	local variation = 20
	
	local value = math.random(-variation, variation) + base
	local formula = 2 * player:getMagicLevel() + (3 * player:getLevel())
	local total = formula * value / 250
	return -(total * skill / 25 + attack)
end

combat:setCallback(CALLBACK_PARAM_SKILLVALUE, "onGetFormulaValues")

function onCastSpell(creature, variant)
	return combat:execute(creature, variant)
end