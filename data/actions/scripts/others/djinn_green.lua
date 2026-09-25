function onUse(player, item, fromPosition, target, toPosition)
    player:setStorageValue(278,3) -- word djanni'hah
    player:setStorageValue(288,3) -- word djanni'hah
	player:sendTextMessage(MESSAGE_INFO_DESCR, "You may now enter the Green djinn fortress.")
	item:remove()
	return true
end