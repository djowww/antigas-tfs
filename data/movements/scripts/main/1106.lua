function onStepIn(creature, item, position, fromPosition)
	doRelocate(item:getPosition(),{x = 32842, y = 32323, z = 9})
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32842, y = 32323, z = 9})
end