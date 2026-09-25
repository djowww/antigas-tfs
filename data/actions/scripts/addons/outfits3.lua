function onUse(player, item, fromPosition, target, toPosition, isHotkey)

		player:sendTextMessage(MESSAGE_INFO_DESCR, "You received the Dragon Slayer outfit.")
		player:getPosition():sendMagicEffect(13)
		player:addOutfitAddon(260, 3)
		player:addOutfitAddon(259, 3)
    
	Item(item.uid):remove(1)
 	return true
end