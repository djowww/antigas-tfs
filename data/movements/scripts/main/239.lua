function onStepIn(creature, item, position, fromPosition)
	doRelocate(item:getPosition(),{x = 32791, y = 32331, z = 10})
    Game.sendMagicEffect({x = 32791, y = 32331, z = 10}, 15)
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32791, y = 32331, z = 10})
    Game.sendMagicEffect({x = 32791, y = 32331, z = 10}, 13)
end
