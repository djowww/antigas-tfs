function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() and not creature:getPlayer():isPremium() then
		doRelocate(item:getPosition(),{x = item:getPosition().x + 3, y = item:getPosition().y, z = 07})
		Game.sendMagicEffect({x = 32060, y = 32193, z = 7}, 13)
	end
end

function onAddItem(item, tileitem, position)
	doRelocate(tileitem:getPosition(),{x = item:getPosition().x + 3, y = item:getPosition().y, z = 07})
	Game.sendMagicEffect({x = 32060, y = 32193, z = 7}, 13)
end