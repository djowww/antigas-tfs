function onUse(player, item, fromPosition, target, toPosition, isHotkey)

	if player:getStorageValue(STORAGEVALUE_RETRO_MAGE) >=1 then
		player:sendCancelMessage("You already got this award.")
		player:getPosition():sendMagicEffect(CONST_ME_POFF)
	else
		player:sendCancelMessage("You won retro mage outfit!")
		player:getPosition():sendMagicEffect(13)
		player:addOutfitAddon(172, 0)
		player:setStorageValue(STORAGEVALUE_RETRO_MAGE, 1)
	end

	return true
end


