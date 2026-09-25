function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() then 
		doRelocate(item:getPosition(),{x = 32513, y = 32512, z = 05})
		Game.sendMagicEffect({x = 32513, y = 32512, z = 05}, 13)
	end
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32513, y = 32512, z = 05})
	Game.sendMagicEffect({x = 32513, y = 32512, z = 05}, 14)
end
