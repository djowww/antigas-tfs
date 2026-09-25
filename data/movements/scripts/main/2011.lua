function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() then 
		doRelocate(item:getPosition(),{x = 32689, y = 32299, z = 15})
		Game.sendMagicEffect({x = 32689, y = 32299, z = 15}, 13)
	end
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32689, y = 32299, z = 15})
	Game.sendMagicEffect({x = 32689, y = 32299, z = 15}, 14)
end

