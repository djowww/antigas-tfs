function onStepIn(creature, item, position, fromPosition)
	doRelocate(item:getPosition(),{x = 32844, y = 32307, z = 9})
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32844, y = 32307, z = 9})
end