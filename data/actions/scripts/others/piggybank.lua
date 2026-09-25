function onUse(player, item, fromPosition, target, toPosition, isHotkey)
	if math.random(6) == 1 then
		item:getPosition():sendMagicEffect(3)
		item:transform(2996)

		player:addItem(ITEM_GOLD_COIN, 1)
	else
		item:getPosition():sendMagicEffect(22)
		player:addItem(ITEM_PLATINUM_COIN, 1)
	end
	return true
end