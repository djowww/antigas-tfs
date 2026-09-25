function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() then 
		doRelocate(item:getPosition(),{x = 32220, y = 32600, z = 07})
		Game.sendMagicEffect({x = 32220, y = 32600, z = 07}, 13)
	end
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32220, y = 32600, z = 07})
	Game.sendMagicEffect({x = 32220, y = 32600, z = 07}, 14)
end