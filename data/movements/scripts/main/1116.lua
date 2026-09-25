function onStepIn(creature, item, position, fromPosition)
	doRelocate(item:getPosition(),{x = 32876, y = 32226, z = 15})
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32876, y = 32226, z = 15})
end