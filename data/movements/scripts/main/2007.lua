function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() then 
		doRelocate(item:getPosition(),{x = 32511, y = 31725, z = 14})
		Game.sendMagicEffect({x = 32511, y = 31725, z = 07}, 13)
	end
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32511, y = 31725, z = 14})
	Game.sendMagicEffect({x = 32511, y = 31725, z = 07}, 14)
end