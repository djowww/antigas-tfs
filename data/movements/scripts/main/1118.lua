function onStepIn(creature, item, position, fromPosition)
	doRelocate(item:getPosition(),{x = 32859, y = 32278, z = 15})
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32859, y = 32278, z = 15})
end