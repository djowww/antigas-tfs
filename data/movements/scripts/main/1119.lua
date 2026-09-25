function onStepIn(creature, item, position, fromPosition)
	doRelocate(item:getPosition(),{x = 32786, y = 32308, z = 15})
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32786, y = 32308, z = 15})
end