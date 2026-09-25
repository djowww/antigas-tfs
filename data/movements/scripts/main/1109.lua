function onStepIn(creature, item, position, fromPosition)
	doRelocate(item:getPosition(),{x = 32840, y = 32317, z = 9})
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32840, y = 32317, z = 9})
end