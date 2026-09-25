function onStepIn(creature, item, position, fromPosition)
	doRelocate(item:getPosition(),{x = 32942, y = 32708, z = 08})
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32942, y = 32708, z = 08})
end