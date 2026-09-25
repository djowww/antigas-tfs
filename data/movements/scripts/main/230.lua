function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() and creature:getPlayer():isSorcerer() then 
		item:transform(453, 1)
		item:decay()
	 end
	if creature:isPlayer() and not creature:getPlayer():isSorcerer() then
	doRelocate(item:getPosition(),{x = 32308, y = 32267, z = 7})
	Game.sendMagicEffect({x = 32308, y = 32267, z = 7}, 13)
	end
end

function onStepOut(creature, item, position, fromPosition)
	item:transform(452, 1)
	item:decay()
end


