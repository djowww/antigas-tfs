function onLogin(player)
	if player:getLastLoginSaved() <= 0 or player:getStorageValue(30017) == 1 then
		player:setStorageValue(30017, 0) -- reset storage for first items
		
		-- Starter equipment; avoid duplicates if saving fails during logout.
		if player:getItemCount(2863) == 0 then
			player:addItem(2863, 1, true, -1, CONST_SLOT_BACKPACK)
		end
		if player:getItemCount(3559) == 0 then
			player:addItem(3559, 1, true, -1, CONST_SLOT_LEGS)
		end
		if player:getItemCount(3270) == 0 then
			player:addItem(3270, 1, true, -1, CONST_SLOT_LEFT)
		end
		if player:getItemCount(3562) == 0 then
			player:addItem(3562, 1, true, -1, CONST_SLOT_ARMOR)
		end
		if player:getItemCount(2920) == 0 then
			player:addItem(2920, 1, true, -1, CONST_SLOT_AMMO)
		end
		if player:getItemCount(3585) == 0 then
			local backpack = player:getSlotItem(CONST_SLOT_BACKPACK)
			if backpack then
				backpack:addItem(3585, 1)
			end
		end
	
		-- Load Default Outfit.
		if player:getSex() == PLAYERSEX_FEMALE then
			player:setOutfit({lookType = 136, lookHead = 78, lookBody = 68, lookLegs = 58, lookFeet = 95})
		else
			player:setOutfit({lookType = 128, lookHead = 78, lookBody = 68, lookLegs = 58, lookFeet = 95})
		end
		
		-- Respect the character's starting town (Rookgaard for new players).
		local town = player:getTown()
		if town then
			local templePosition = town:getTemplePosition()
			player:teleportTo(templePosition)
			player:setDirection(DIRECTION_SOUTH)
			templePosition:sendMagicEffect(CONST_ME_TELEPORT)
		end
	end
	return true
end
