function onUse(player, item, fromPosition, target, toPosition, isHotkey)

		player:sendTextMessage(MESSAGE_INFO_DESCR, "You received the Golden outfit.")
		player:getPosition():sendMagicEffect(13)
		player:addOutfitAddon(169, 3)
		player:addOutfitAddon(168, 3)
    
	Item(item.uid):remove(1)
 	return true
end