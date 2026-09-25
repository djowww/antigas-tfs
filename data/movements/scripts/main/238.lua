function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() and not creature:getPlayer():isPremium() then
	doRelocate(item:getPosition(),{x = 32791, y = 32334, z = 10})
	Game.sendMagicEffect({x = 32791, y = 32334, z = 10}, 14)
else
	doRelocate(item:getPosition(),{x = 32791, y = 32327, z = 10})
    Game.sendMagicEffect({x = 32791, y = 32327, z = 10}, 15)
	end
end

function onAddItem(item, tileitem, position)
	doRelocate(item:getPosition(),{x = 32791, y = 32327, z = 10})
    Game.sendMagicEffect({x = 32791, y = 32327, z = 10}, 13)
end
