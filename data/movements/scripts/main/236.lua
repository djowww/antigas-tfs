function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() then 
		doRelocate(item:getPosition(),{x = 33293, y = 32481, z = 7})
		Game.sendMagicEffect({x = 33293, y = 32481, z = 7}, 11)
	end
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 33325, y = 32166, z = 5})
	Game.sendMagicEffect({x = 33325, y = 32166, z = 5}, 13)
end
