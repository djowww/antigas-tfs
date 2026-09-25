local condition = Condition(CONDITION_POISON)
condition:setParameter(CONDITION_PARAM_DELAYED, true)
condition:addDamage(5, 2000, -5)
condition:addDamage(5, 2000, -4)
condition:addDamage(5, 2000, -3)
condition:addDamage(5, 2000, -2)
condition:addDamage(5, 2000, -1)

function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() then
		creature:addCondition(condition)
		creature:getPlayer():setStorageValue(270,1)
		Game.sendMagicEffect({x = 33362, y = 32811, z = 14}, 9)
	end
end
