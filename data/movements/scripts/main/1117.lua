function onStepIn(creature, item, position, fromPosition)
	doRelocate(item:getPosition(),{x = 32767, y = 32227, z = 15})
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32767, y = 32227, z = 15})
end