function onStepIn(creature, item, position, fromPosition)
	doRelocate(item:getPosition(),{x = 33150, y = 32559, z = 07})
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 33150, y = 32559, z = 07})
end