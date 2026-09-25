function onUse(player, item, fromPosition, target, toPosition, isHotkey)

		player:sendTextMessage(MESSAGE_INFO_DESCR, "You received the Demon outfit.")
		player:getPosition():sendMagicEffect(13)
		player:addOutfitAddon(170, 0)
		player:addOutfitAddon(171, 0)
    
	Item(item.uid):remove(1)
 	return true
end