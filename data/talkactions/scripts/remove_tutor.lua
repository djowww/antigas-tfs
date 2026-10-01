function onSay(player, words, param)
	if player:getAccountType() <= ACCOUNT_TYPE_TUTOR then
		return true
	end

	local resultId = db.storeQuery("SELECT `name`, `account_id`, (SELECT `type` FROM `accounts` WHERE `accounts`.`id` = `account_id`) AS `account_type` FROM `players` WHERE `name` = " .. db.escapeString(param))
	if resultId == false then
		player:sendCancelMessage("A player with that name does not exist.")
		return false
	end

	if result.getDataInt(resultId, "account_type") ~= ACCOUNT_TYPE_TUTOR then
		result.free(resultId)
		player:sendCancelMessage("You can only demote a tutor to a normal player.")
		return false
	end

	local targetName = result.getDataString(resultId, "name")
	local accountId = result.getDataInt(resultId, "account_id")
	local target = Player(param)
	if target ~= nil then
		if not target:setAccountType(ACCOUNT_TYPE_NORMAL) then
			result.free(resultId)
			player:sendCancelMessage("Could not update the player's account type. Please try again later.")
			return false
		end
	else
		local accountSession = nil
		for _, onlinePlayer in ipairs(Game.getPlayers()) do
			if onlinePlayer:getAccountId() == accountId then
				accountSession = onlinePlayer
				break
			end
		end

		if accountSession ~= nil then
			if not accountSession:setAccountType(ACCOUNT_TYPE_NORMAL) then
				result.free(resultId)
				player:sendCancelMessage("Could not update the player's account type. Please try again later.")
				return false
			end
		elseif not db.query("UPDATE `accounts` SET `type` = " .. ACCOUNT_TYPE_NORMAL .. " WHERE `id` = " .. accountId) then
			result.free(resultId)
			player:sendCancelMessage("Could not update the player's account type. Please try again later.")
			return false
		end
	end

	player:sendTextMessage(MESSAGE_EVENT_ADVANCE, "You have demoted " .. targetName .. " to a normal player.")
	result.free(resultId)
	return false
end
