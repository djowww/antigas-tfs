function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() then 
		doRelocate(item:getPosition(),{x = 32257, y = 31893, z = 10})
		Game.sendMagicEffect({x = 32257, y = 31893, z = 10}, 13)
	end
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32257, y = 31893, z = 10})
	Game.sendMagicEffect({x = 32257, y = 31893, z = 10}, 14)
end