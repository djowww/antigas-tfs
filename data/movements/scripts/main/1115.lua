function onStepIn(creature, item, position, fromPosition)
	doRelocate(item:getPosition(),{x = 32856, y = 32353, z = 15})
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32856, y = 32353, z = 15})
end