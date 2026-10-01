local ipBanDays = 7

function onSay(player, words, param)
	if not player:getGroup():getAccess() then
		return true
	end

	local resultId, querySucceeded = db.storeQueryChecked("SELECT `players`.`lastip`, `players`.`group_id`, `players`.`account_id`, `accounts`.`type` AS `account_type` FROM `players` INNER JOIN `accounts` ON `accounts`.`id` = `players`.`account_id` WHERE `players`.`name` = " .. db.escapeString(param))
	if not querySucceeded then
		player:sendCancelMessage("Could not query the player database. Please try again later.")
		return false
	end
	if resultId == false then
		player:sendCancelMessage("A player with that name does not exist.")
		return false
	end

	local targetIp = result.getDataLong(resultId, "lastip")
	local targetGroupId = result.getDataInt(resultId, "group_id")
	local targetAccountId = result.getDataInt(resultId, "account_id")
	local targetAccountType = result.getDataInt(resultId, "account_type")
	result.free(resultId)

	local targetPlayer = Player(param)
	local targetGroup
	if targetPlayer then
		targetGroup = targetPlayer:getGroup()
		targetIp = targetPlayer:getIp()
	else
		targetGroup = Group(targetGroupId)
	end

	if targetGroup == nil then
		player:sendCancelMessage("Could not verify the target player's group.")
		return false
	end

	if targetGroup:getAccess() then
		player:sendCancelMessage("You cannot ban a player with staff access.")
		return false
	end

	if targetAccountType < ACCOUNT_TYPE_NORMAL or targetAccountType > ACCOUNT_TYPE_GOD then
		player:sendCancelMessage("Could not verify the target account type.")
		return false
	end

	if targetAccountType >= ACCOUNT_TYPE_TUTOR then
		player:sendCancelMessage("You cannot IP ban a staff account.")
		return false
	end
	if targetAccountId == nil or targetAccountId <= 0 then
		player:sendCancelMessage("Could not verify the target player's account.")
		return false
	end

	-- An IP ban can affect every character on the named account. Check every
	-- persisted group so a normal character cannot indirectly IP-ban its staff alt.
	local accountGroupResultId, accountQuerySucceeded = db.storeQueryChecked("SELECT `group_id` FROM `players` WHERE `account_id` = " .. targetAccountId)
	if not accountQuerySucceeded or accountGroupResultId == false then
		player:sendCancelMessage("Could not verify all characters on the target account.")
		return false
	end

	local accountHasStaff = false
	local accountGroupUnverified = false
	repeat
		local accountGroup = Group(result.getDataInt(accountGroupResultId, "group_id"))
		if accountGroup == nil then
			accountGroupUnverified = true
			break
		end
		if accountGroup:getAccess() then
			accountHasStaff = true
			break
		end
	until not result.next(accountGroupResultId)
	result.free(accountGroupResultId)

	if accountGroupUnverified then
		player:sendCancelMessage("Could not verify a character's group on the target account.")
		return false
	end
	if accountHasStaff then
		player:sendCancelMessage("You cannot IP ban an account with staff access.")
		return false
	end

	if not targetIp or targetIp == 0 then
		player:sendCancelMessage("Could not determine a valid IP address for this player.")
		return false
	end

	local timeNow = os.time()
	if not db.query("DELETE FROM `ip_bans` WHERE `ip` = " .. targetIp .. " AND `expires_at` != 0 AND `expires_at` <= " .. timeNow) then
		player:sendCancelMessage("Could not clean up expired IP bans. Please try again later.")
		return false
	end

	resultId, querySucceeded = db.storeQueryChecked("SELECT 1 FROM `ip_bans` WHERE `ip` = " .. targetIp)
	if not querySucceeded then
		player:sendCancelMessage("Could not query the ban database. Please try again later.")
		return false
	end
	if resultId ~= false then
		result.free(resultId)
		return false
	end

	if not db.query("INSERT INTO `ip_bans` (`ip`, `reason`, `banned_at`, `expires_at`, `banned_by`) VALUES (" ..
			targetIp .. ", '', " .. timeNow .. ", " .. timeNow + (ipBanDays * 86400) .. ", " .. player:getGuid() .. ")") then
		player:sendCancelMessage("Could not store the IP ban. Please try again later.")
		return false
	end

	if targetPlayer then
		targetPlayer:remove()
	end
	return false
end
