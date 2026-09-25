function onSay(player, words, param)
    if not player:getGroup():getAccess() then
        return true
    end

    local split = param:split(",")
   
    local name = split[1]
    local reason = tostring(split[2])
    local bandays = tonumber(split[3])
   
    local accountId = getAccountNumberByPlayerName(name)
    if accountId == 0 then
        print("cant find the player")
        return false
    end

    local resultId = db.storeQuery("SELECT 1 FROM `account_bans` WHERE `account_id` = " .. accountId)
    if resultId ~= false then
        result.free(resultId)
        return false
    end

    local timeNow = os.time()
    db.query("INSERT INTO `account_bans` (`account_id`, `reason`, `banned_at`, `expires_at`, `banned_by`) VALUES (" ..
            accountId .. ", " .. db.escapeString(reason) .. ", " .. timeNow .. ", " .. timeNow + (bandays * 86400) .. ", " .. player:getGuid() .. ")")

    local target = Player(name)
    if target ~= nil then
        player:sendTextMessage(MESSAGE_EVENT_ADVANCE, target:getName() .. " has been banned.")
        target:remove()
    else
        player:sendTextMessage(MESSAGE_EVENT_ADVANCE, name .. " has been banned.")
    end
end