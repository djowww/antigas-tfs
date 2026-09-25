function onUse(player, item, fromPosition, target, toPosition, isHotkey)

		player:sendTextMessage(MESSAGE_INFO_DESCR, "You received the Game Master outfit.")
		player:getPosition():sendMagicEffect(13)
		player:addOutfitAddon(252, 0)
		player:addOutfitAddon(252, 0)
    
	Item(item.uid):remove(1)
 	return true
end