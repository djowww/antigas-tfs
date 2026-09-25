function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() then 
		doRelocate(item:getPosition(),{x = 32834, y = 32275, z = 9})
		Game.sendMagicEffect({x = 32834, y = 32275, z = 9}, 13)
	end
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32834, y = 32275, z = 9})
	Game.sendMagicEffect({x = 32834, y = 32275, z = 9}, 14)
end

