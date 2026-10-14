function onUse(player, item, fromPosition, target, toPosition)

	local arenaId = item:getMovementId()
	local chestStorage = (500+arenaId)
	if player:getStorageValue(chestStorage) <= 0 then
		local itemList = {
								[7100] = { 
									[1] = 5191,
									[2] = 5191,
									[3] = 5100,
									[4] = 5185
								},
								[7200] = { 
									[1] = 5193,
									[2] = 5193,
									[3] = 5102,
									[4] = 5205
								},
								[7300] = { 
									[1] = 5196,
									[2] = 5196,
									[3] = 5104,
									[4] = 5204
								},
							}
			local pvoc = player:getVocation():getId()
			if pvoc == 5 then
				pvoc = 1
			elseif pvoc == 6 then
				pvoc = 2
			elseif pvoc == 7 then
				pvoc = 3
			elseif pvoc == 8 then
				pvoc = 4
			end
			local rewardId = itemList[arenaId] and itemList[arenaId][pvoc]
			if not rewardId or ItemType(rewardId):isRetired() then
				player:sendTextMessage(MESSAGE_INFO_DESCR, "This item reward is no longer available.")
				return true
			end
			local itemReward = player:addItem(rewardId, 1, false)
			if not itemReward then
				player:sendTextMessage(MESSAGE_INFO_DESCR, "Make room and free capacity before collecting this reward.")
				return true
			end
			item:getPosition():sendMagicEffect(CONST_ME_POFF)
			local itemInfo = ItemType(rewardId)
			player:sendTextMessage(MESSAGE_INFO_DESCR, "You received "..itemInfo:getName())
			itemReward:setAttribute(ITEM_ATTRIBUTE_DESCRIPTION, player:getName().." conquest this reward from arena.")

			player:setStorageValue(chestStorage,1)
	else
		player:sendTextMessage(MESSAGE_INFO_DESCR, "The chest is empty.")
	end
	return true
end
