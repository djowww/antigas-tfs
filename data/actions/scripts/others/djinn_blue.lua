function onUse(player, item, fromPosition, target, toPosition)
    player:setStorageValue(278,2) -- word djanni'hah
    player:setStorageValue(283,3) -- word djanni'hah
	player:sendTextMessage(MESSAGE_INFO_DESCR, "You may now enter the Blue djinn fortress.")
	item:remove()
	return true
end