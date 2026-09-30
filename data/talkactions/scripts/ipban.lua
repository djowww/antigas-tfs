local ipBanDays = 7

function onSay(player, words, param)
	if not player:getGroup():getAccess() then
		return true
	end

	local resultId, querySucceeded = db.storeQueryChecked("SELECT `lastip`, `group_id` FROM `players` WHERE `name` = " .. db.escapeString(param))
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

	if not targetIp or targetIp == 0 then
		player:sendCancelMessage("Could not determine a valid IP address for this player.")
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

	local timeNow = os.time()
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
