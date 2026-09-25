function onStepIn(creature, item, position, fromPosition)
	doRelocate(item:getPosition(),{x = 32806, y = 32327, z = 15})
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32806, y = 32327, z = 15})
end