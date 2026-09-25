function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() then 
		doRelocate(item:getPosition(),{x = 32223, y = 31891, z = 14})
		Game.sendMagicEffect({x = 32223, y = 31891, z = 14}, 13)
	end
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32223, y = 31891, z = 14})
	Game.sendMagicEffect({x = 32223, y = 31891, z = 14}, 14)
end