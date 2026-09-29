local function getEquippedWeapon(player)
	for _, slot in ipairs({ CONST_SLOT_RIGHT, CONST_SLOT_LEFT }) do
		local item = player:getSlotItem(slot)
		if item then
			local itemType = ItemType(item:getId())
			local weaponType = itemType:getWeaponType()
			if itemType:getAttack() > 0 and (weaponType == WEAPON_SWORD or weaponType == WEAPON_AXE or weaponType == WEAPON_CLUB or weaponType == WEAPON_DISTANCE) then
				return item, itemType
			end
		end
	end
	return nil, nil
end

function onSay(player, words, param)
	if not player:getGroup():getAccess() or player:getAccountType() < ACCOUNT_TYPE_GOD then
		return false
	end

	local item, itemType = getEquippedWeapon(player)
	if not item then
		player:sendCancelMessage("Equip a sword, axe, club, or distance weapon in your hand first.")
		return false
	end

	if words == "/resetatk" then
		if not item:hasAttribute(ITEM_ATTRIBUTE_ATTACK) then
			player:sendCancelMessage("This weapon has no custom attack value to reset.")
			return false
		end

		item:removeAttribute(ITEM_ATTRIBUTE_ATTACK)
		player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "Custom attack removed. The weapon is back to its normal attack.")
		return false
	end

	local amount = tonumber(param)
	if not amount or amount <= 0 or amount % 1 ~= 0 then
		player:sendCancelMessage("Usage: /addatk 10")
		return false
	end

	local currentAttack = itemType:getAttack()
	if item:hasAttribute(ITEM_ATTRIBUTE_ATTACK) then
		currentAttack = item:getAttribute(ITEM_ATTRIBUTE_ATTACK)
	end

	if amount > 2147483647 - currentAttack then
		player:sendCancelMessage("The requested attack value is too high.")
		return false
	end

	local newAttack = currentAttack + amount
	item:setAttribute(ITEM_ATTRIBUTE_ATTACK, newAttack)
	player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, ("Weapon attack increased by %d. New base attack: %d. Use /resetatk to restore it."):format(amount, newAttack))
	return false
end
