local combat = Combat()
combat:setParameter(COMBAT_PARAM_EFFECT, CONST_ME_GREEN_RINGS)
combat:setArea(createCombatArea(AREA_CIRCLE5X5))


local castForce = 0
function onTargetCreature(caster, target)
 local condition = Condition(CONDITION_POISON)
 condition:setParameter(CONDITION_PARAM_MINVALUE, castForce)
 condition:setParameter(CONDITION_PARAM_MAXVALUE, castForce)
 condition:setParameter(CONDITION_PARAM_OWNER, caster:getId())
 target:addCondition(condition)
end
combat:setCallback(CALLBACK_PARAM_TARGETCREATURE, "onTargetCreature")

function onCastSpell(creature, variant)
 if creature:isPlayer() then
  castForce = legacySpellForce(creature:getLevel(), creature:getMagicLevel(), 200, 50)
 else castForce = 200 + math.random(-50, 50) end
 return combat:execute(creature, variant)
end
