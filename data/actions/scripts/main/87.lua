function onUse(player, item, fromPosition, target, toPosition, isHotkey)

	if player:getStorageValue(STORAGEVALUE_NORSEMAN) >=1 then
		player:sendCancelMessage("You already got this award.")
		player:getPosition():sendMagicEffect(CONST_ME_POFF)
	else
		player:sendCancelMessage("You won Norseman outfit!")
		player:getPosition():sendMagicEffect(13)
		player:addOutfitAddon(186, 0)
		player:addOutfitAddon(185, 0)
		player:setStorageValue(STORAGEVALUE_NORSEMAN, 1)
	end

	return true
end


