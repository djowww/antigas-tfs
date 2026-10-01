function onSay(player, words, param)
    if not player:getGroup():getAccess() then
        return true
    end

    local split = param:split(",")
    local name = split[1]
    local reason = tostring(split[2])
    local banDays = tonumber(split[3])
    if not banDays or banDays < 1 or banDays == math.huge or banDays ~= math.floor(banDays) then
        player:sendCancelMessage("Ban duration must be a positive whole number of days.")
        return false
    end

    local target = Player(name)
    local accountId

    if target then
        accountId = target:getAccountId()
        local targetGroup = target:getGroup()
        if targetGroup == nil then
            return false
        end
        if targetGroup:getAccess() then
            player:sendCancelMessage("You cannot ban a player with staff access.")
            return false
        end
    else
        local resultId, querySucceeded = db.storeQueryChecked("SELECT `account_id`, `group_id` FROM `players` WHERE `name` = " .. db.escapeString(name))
        if not querySucceeded then
            player:sendCancelMessage("Could not query the player database. Please try again later.")
            return false
        end
        if resultId == false then
            player:sendCancelMessage("A player with that name does not exist.")
            return false
        end

        accountId = result.getDataInt(resultId, "account_id")
        local targetGroup = Group(result.getDataInt(resultId, "group_id"))
        result.free(resultId)
        if targetGroup == nil then
            player:sendCancelMessage("Could not verify the target player's group.")
            return false
        end
        if targetGroup:getAccess() then
            player:sendCancelMessage("You cannot ban a player with staff access.")
            return false
        end
    end

    if accountId == nil or accountId == 0 then
        player:sendCancelMessage("A player with that name does not exist.")
        return false
    end

    -- Account bans affect every character on the account, so inspect the
    -- persisted account type and every character group before writing the ban.
    local accountResultId, accountQuerySucceeded = db.storeQueryChecked("SELECT `players`.`group_id`, `accounts`.`type` AS `account_type` FROM `players` INNER JOIN `accounts` ON `accounts`.`id` = `players`.`account_id` WHERE `players`.`account_id` = " .. accountId)
    if not accountQuerySucceeded then
        player:sendCancelMessage("Could not verify all characters on the target account.")
        return false
    end
    if accountResultId == false then
        player:sendCancelMessage("Could not verify all characters on the target account.")
        return false
    end

    local accountType = result.getDataInt(accountResultId, "account_type")
    if accountType < ACCOUNT_TYPE_NORMAL or accountType > ACCOUNT_TYPE_GOD then
        result.free(accountResultId)
        player:sendCancelMessage("Could not verify the target account type.")
        return false
    end
    if accountType >= ACCOUNT_TYPE_TUTOR then
        result.free(accountResultId)
        player:sendCancelMessage("You cannot ban a staff account.")
        return false
    end

    local accountHasStaff = false
    local accountGroupUnverified = false
    repeat
        local accountGroup = Group(result.getDataInt(accountResultId, "group_id"))
        if accountGroup == nil then
            accountGroupUnverified = true
            break
        end
        if accountGroup:getAccess() then
            accountHasStaff = true
            break
        end
    until not result.next(accountResultId)
    result.free(accountResultId)

    if accountGroupUnverified then
        player:sendCancelMessage("Could not verify a character's group on the target account.")
        return false
    end
    if accountHasStaff then
        player:sendCancelMessage("You cannot ban an account with staff access.")
        return false
    end

    local resultId, querySucceeded = db.storeQueryChecked("SELECT 1 FROM `account_bans` WHERE `account_id` = " .. accountId)
    if not querySucceeded then
        player:sendCancelMessage("Could not query the ban database. Please try again later.")
        return false
    end
    if resultId ~= false then
        result.free(resultId)
        return false
    end

    local timeNow = os.time()
    local expiresAt = timeNow + (banDays * 86400)
    if not db.query("INSERT INTO `account_bans` (`account_id`, `reason`, `banned_at`, `expires_at`, `banned_by`) VALUES (" ..
            accountId .. ", " .. db.escapeString(reason) .. ", " .. timeNow .. ", " .. expiresAt .. ", " .. player:getGuid() .. ")") then
        player:sendCancelMessage("Could not store the ban. Please try again later.")
        return false
    end

    if target then
        player:sendTextMessage(MESSAGE_EVENT_ADVANCE, target:getName() .. " has been banned.")
        target:remove()
    else
        player:sendTextMessage(MESSAGE_EVENT_ADVANCE, name .. " has been banned.")
    end
    return false
end
