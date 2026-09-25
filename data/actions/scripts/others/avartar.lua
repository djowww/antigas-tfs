function onUse(player, item, fromPosition, target, toPosition)
    player:setStorageValue(11,1) -- banshe last door
	player:sendTextMessage(MESSAGE_INFO_DESCR, "You just received permission to use the Avar Tar!.")
	player:getPosition():sendMagicEffect(13)	
	item:remove()
	return true
end