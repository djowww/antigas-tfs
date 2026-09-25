function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() then 
		doRelocate(item:getPosition(),{x = 32518, y = 32520, z = 04})
		Game.sendMagicEffect({x = 32518, y = 32520, z = 04}, 13)
	end
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32519, y = 32520, z = 04})
	Game.sendMagicEffect({x = 32519, y = 32520, z = 04}, 14)
end
