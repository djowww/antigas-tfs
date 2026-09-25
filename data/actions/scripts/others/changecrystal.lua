function onUse(player, item, fromPosition, target, toPosition)
	player:sendTextMessage(MESSAGE_INFO_DESCR, "You have exchanged a life crystal for a life ring.")
	player:getPosition():sendMagicEffect(13)
	player:addItem(3052, 1)
	item:remove()
	return true
end