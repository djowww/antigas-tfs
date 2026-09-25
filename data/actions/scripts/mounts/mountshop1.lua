function onUse(player, item, fromPosition, target, toPosition, isHotkey)
		player:sendTextMessage(MESSAGE_INFO_DESCR, "You received mount.")
		player:getPosition():sendMagicEffect(13)
		player:addMount(10)
        Item(item.uid):remove(1)
 	return true
end