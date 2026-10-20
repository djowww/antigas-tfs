local combat = Combat()
combat:setParameter(COMBAT_PARAM_EFFECT, CONST_ME_MAGIC_BLUE)
combat:setParameter(COMBAT_PARAM_DISPEL, CONDITION_PARALYZE)
combat:setParameter(COMBAT_PARAM_AGGRESSIVE, false)
combat:setArea(createCombatArea(AREA_CIRCLE3X3))
local castAmounts = {}
function onTargetCreature(creature, target)
 if Game.getWorldType() == WORLD_TYPE_NO_PVP and not target:isPlayer() then return true end
 if target:getHealth() <= 0 then return true end
 local amount = castAmounts[creature:getId()]
 doTargetCombatHealth(0, target, COMBAT_HEALING, amount, amount, CONST_ME_NONE)
 return true
end
combat:setCallback(CALLBACK_PARAM_TARGETCREATURE, "onTargetCreature")
function onCastSpell(creature, variant)
 local factor = math.max(2 * creature:getLevel() + 3 * creature:getMagicLevel(), 100)
 castAmounts[creature:getId()] = math.floor((200 + math.random(-40, 40)) * factor / 100)
 local result = combat:execute(creature, variant)
 castAmounts[creature:getId()] = nil
 return result
end
