function onUse(player, item, fromPosition, target, toPosition, isHotkey)

		player:sendTextMessage(MESSAGE_INFO_DESCR, "You received the Royal Costumer outfit.")
		player:getPosition():sendMagicEffect(13)
		player:addOutfitAddon(263, 3)
		player:addOutfitAddon(264, 3)
    
	Item(item.uid):remove(1)
 	return true
end