function onStepIn(creature, item, position, fromPosition)
	doRelocate(item:getPosition(),{x = 32671, y = 32069, z = 08})
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32671, y = 32069, z = 08})
end