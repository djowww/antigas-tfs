local combat = Combat()
combat:setParameter(COMBAT_PARAM_EFFECT, CONST_ME_CARNIPHILA)
combat:setParameter(COMBAT_PARAM_DISTANCEEFFECT, CONST_ANI_EARTH)


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
  castForce = legacySpellForce(creature:getLevel(), creature:getMagicLevel(), 70, 20)
 else castForce = 70 + math.random(-20, 20) end
 return combat:execute(creature, variant)
end
