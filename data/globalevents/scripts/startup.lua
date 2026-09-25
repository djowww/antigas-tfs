function onStartup()
	math.randomseed(os.mtime())
	
	db.query("TRUNCATE TABLE `players_online`")
	db.asyncQuery("DELETE FROM `guild_wars` WHERE `status` = 0")
	db.asyncQuery("DELETE FROM `players` WHERE `deletion` != 0 AND `deletion` < " .. os.time())
	db.asyncQuery("DELETE FROM `ip_bans` WHERE `expires_at` != 0 AND `expires_at` <= " .. os.time())

	-- Move expired bans to ban history
	local resultId = db.storeQuery("SELECT * FROM `account_bans` WHERE `expires_at` != 0 AND `expires_at` <= " .. os.time())
	if resultId ~= false then
		repeat
			local accountId = result.getDataInt(resultId, "account_id")
			db.asyncQuery("INSERT INTO `account_ban_history` (`account_id`, `reason`, `banned_at`, `expired_at`, `banned_by`) VALUES (" .. accountId .. ", " .. db.escapeString(result.getDataString(resultId, "reason")) .. ", " .. result.getDataLong(resultId, "banned_at") .. ", " .. result.getDataLong(resultId, "expires_at") .. ", " .. result.getDataInt(resultId, "banned_by") .. ")")
			db.asyncQuery("DELETE FROM `account_bans` WHERE `account_id` = " .. accountId)
		until not result.next(resultId)
		result.free(resultId)
	end
  
    -- Check house owner premium status --
    --local resultId = db.storeQuery("SELECT `id`, `owner` FROM `houses` WHERE NOT `owner` = 0 AND (SELECT `premdays` FROM `accounts` WHERE (SELECT `account_id` FROM `players` WHERE `id` = `owner`) = `id`) = 0")
    --if resultId ~= false then
      --  repeat
        --    local house = House(result.getDataInt(resultId, "id"))
          --  if house then
            --    house:setOwnerGuid(0)
            --end
       -- until not result.next(resultId)
       -- result.free(resultId)
    --end
end