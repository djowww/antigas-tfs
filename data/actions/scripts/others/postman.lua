function onUse(player, item, fromPosition, target, toPosition)
    player:setStorageValue(250,3) -- word djanni'hah
	player:setStorageValue(250,4) -- word djanni'hah
    player:setStorageValue(250,5) -- word djanni'hah
	player:sendTextMessage(MESSAGE_INFO_DESCR, "You are allowed to make use of certain mailboxes in dangerous areas.")
	item:remove()
	return true
end