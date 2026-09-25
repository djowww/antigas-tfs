-- Schema is managed by migrations, not repeatedly recreated while scripts load.

--------------------------------------
---------- START OF CONFIG -----------
--------------------------------------
local customCurrency = '' -- by default bank balance and premium points are included but you can add other stackable currencies like gold nuggets etc here eg, 'gold nugget' or you can use the itemID or the item name
local config = {
    ipCheck = false, -- players from same IP can not place bounty on each other
    minLevelToAddBounty = 20, -- min lvl req to place a bounty
    minLevelToBeTargeted = 20, -- min lvl req to be targeted by a bounty
    broadcastKills = true, -- Should it broadcast a message to the whole game-world when someone was killed?
    broadcastHunt = false, -- Should it broadcast a message to the whole game-world when someone is added to the bounty list?
    mailbox_position = Position(32351,32223,6), -- If you are using a custom currency then we will send it to the players Mailbox, in order to do it you just need to put the location of one mailbox from your map here, doesn't matter which
    currencies = {
        ['gold'] = {  
            minAmount = 1000000, -- Min amount of Gold allowed
            maxAmount = 1000000000, -- Max amount of gold allowed
            func =
                function(player, prize, currency)
                    if player:getBankBalance()>9007199254740991-prize then return false end
                    return player:setBankBalance(player:getBankBalance() + prize)
                end,
            check =
                function(player, amount, currency)
                    if player:getBankBalance() >= amount then
                        return player:setBankBalance(player:getBankBalance() - amount)
                    end
                    return false
                end,
        },
        ['points'] = {
            minAmount = 10, -- Min amount of premium points allowed
            maxAmount = 500, -- Max amount of premium points allowed
            func =
                function(player, prize, currency)
                    return player:addPremiumPoints(prize)
                end,
            check =
                function(player, prize, currency)
                    if player:getPremiumPoints() >= prize then
                        return player:removePremiumPoints(prize)
                    end
                    return false
                end
        },
        [customCurrency] = {
            minAmount = 10, -- Min amount of custom item allowed
            maxAmount = 3000, -- Max amount of custom item allowed
            func =
                function(player, prize, currency)
                    return player:sendParcel(prize)
                end,
            check =
                function(player, amount, currency)
                    local itemID = ItemType(customCurrency):getId()
                    if itemID > 0 and player:getItemCount(itemID) >= amount then
                        player:removeItem(itemID, amount)
                        return true
                    end
                    return false
                end,
        }
    }
}
--------------------------------------
----------- END OF CONFIG ------------
--------------------------------------
-- Only edit below if you know what you are doing --

local function trimString(str)
  return (str:gsub("^%s*(.-)%s*$", "%1"))
end

local function addItemsToBag(bpID, itemID, count)
    local masterBag = Game.createItem(bpID,1)
    local stackable = ItemType(itemID):isStackable()

    if stackable then
        if count > 2000 then
            local bp = Game.createItem(bpID,1)
            masterBag:addItemEx(bp)
            for i = 1, count do
                if bp:getEmptySlots() < 1 then
                    bp = Game.createItem(bpID,1)
                    masterBag:addItemEx(bp)
                end
                bp:addItem(itemID)
            end
        end
        return masterBag
    end

    if count > 20 then
        local bp = Game.createItem(bpID,1)
        masterBag:addItemEx(bp)
        for i = 1, count do
            if bp:getEmptySlots() < 1 then
                bp = Game.createItem(bpID,1)
                masterBag:addItemEx(bp)
            end
            bp:addItem(itemID)
        end
    return masterBag
    end

    for i = 1, count do
        masterBag:addItem(itemID)
    end
    return masterBag
end

function Player:sendParcel(amount)
    local itemID = ItemType(customCurrency):getId()
    if itemID == 0 then
        print('Error in sending parcel. Custom currency was not set properly double check the spelling.')
        return
    end
    local container = Game.createItem(2595, 1)
    container:setAttribute(ITEM_ATTRIBUTE_NAME, 'Bounty Hunters Mail')
    local label = container:addItem(2599, 1)
    label:setAttribute(ITEM_ATTRIBUTE_TEXT, self:getName())
    label:setAttribute(ITEM_ATTRIBUTE_WRITER, "Bounty Hunters Mail")
    local parcel = addItemsToBag(1988, itemID, amount)
    container:addItemEx(parcel)
    container:moveTo(config.mailbox_position)
end

function Player:getPremiumPoints(points)
    local points = db.storeQuery("SELECT `premium_points` FROM `accounts` WHERE `id` = " .. self:getAccountId() .. ";")
    if points then
        local pointTotal = result.getDataInt(points, "premium_points")
        result.free(points)
    return pointTotal
    end
    return 0
end

function Player:addPremiumPoints(points)
    if not Economy.integer(points,1,1000000000) then return false end
    return Economy.changed('UPDATE accounts SET premium_points=premium_points+'..points..' WHERE id='..self:getAccountId()..' AND premium_points<='..(2000000000-points))
end

function Player:removePremiumPoints(points)
    if not Economy.integer(points,1,1000000000) then return false end
    return Economy.changed('UPDATE accounts SET premium_points=premium_points-'..points..' WHERE id='..self:getAccountId()..' AND premium_points>='..points)
end

function Player:getBountyInfo()
    local result_plr = db.storeQuery("SELECT prize, id, currencyType FROM `bounty_hunter_system` WHERE `target_id` = "..self:getGuid().." AND `killed` = 0;")
    if (result_plr == false) then
        return {false, 0, 0, 0, 0}
    end
    local prize = tonumber(result.getDataInt(result_plr, "prize"))
    local id = tonumber(result.getDataInt(result_plr, "id"))
    local bounty_type = tostring(result.getDataString(result_plr, "currencyType"))
    result.free(result_plr)
    return {true, prize, id, bounty_type, currency}
end

local function addBountyKill(killer, target, prize, id, bounty_type, currency)
    if not config.currencies[bounty_type] then
        print('error in adding bounty prize')
        return true
    end
    if bounty_type~='gold' and bounty_type~='points' then return false end
    local claimed=Economy.run(killer,function(ctx)
        if not Economy.changed('UPDATE bounty_hunter_system SET killed=1,killer_id='..killer:getGuid()..',dateKilled='..os.time()..' WHERE id='..id..' AND killed=0') then return false end
        return config.currencies[bounty_type].func(killer,prize,currency)
    end)
    if not claimed then return false end
    killer:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE,'[BOUNTY HUNTER SYSTEM] You killed ' .. target:getName() .. ' and earned a reward of ' .. prize .. ' ' .. bounty_type .. 's!')
    if config.broadcastKills then
        Game.broadcastMessage("Bounty Hunter Update:\n " .. killer:getName() .. " has killed " .. target:getName() .. " and earned a reward of " .. prize .. " " .. bounty_type .. "!", MESSAGE_EVENT_ADVANCE)
    end
    return true
end

local function addBountyHunt(player, target, amount, currencyType)
    if not db.query("INSERT INTO `bounty_hunter_system` (`hunter_id`, `target_id`, `killer_id`, `prize`, `currencyType`, `dateAdded`, `killed`, `dateKilled`) VALUES (" .. player:getGuid() .. "," .. target:getGuid() .. ",0," .. amount .. ", " .. db.escapeString(currencyType) .. ", " .. os.time() .. ", 0, 0);") then
        config.currencies[currencyType].func(player, amount, currencyType)
        player:sendTextMessage(MESSAGE_STATUS_CONSOLE_ORANGE, '[BOUNTY HUNTER SYSTEM] Could not record the bounty. Your payment was returned.')
        return false
    end
    player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "[BOUNTY HUNTER SYSTEM] You have placed bounty on " .. target:getName() .. " for a reward of " .. amount .. " " .. currencyType .. "!")
    if config.broadcastHunt then
        Game.broadcastMessage("[BOUNTY_HUNTER_SYSTEM]\n " .. player:getName() .. " has put a bounty on " .. target:getName() .. " for " .. amount .. " " .. currencyType .. ".", MESSAGE_EVENT_ADVANCE)
    end
return false
end

function onBountyHunterSay(player, words, param)
    if player:getLevel() < config.minLevelToAddBounty then
        player:sendTextMessage(MESSAGE_STATUS_CONSOLE_ORANGE, '[BOUNTY_HUNTER_SYSTEM] You need level ' .. config.minLevelToAddBounty .. ' to use this command.')
        return false
    end
    local t = param:split(",")
    local name = t[1] and trimString(t[1])
    local currencyType = t[2] and trimString(t[2]) or nil
    local amount = t[3] and tonumber(t[3]) or nil

    if not (name and currencyType and amount) then
        local item = ItemType(customCurrency)
        local text = '[BOUNTY HUNTER SYSTEM GUIDE]\n\nCommand Usage:\n!hunt playerName, type(gold/' .. customCurrency .. '/points), amount' .. '\n\n' .. 'Hunting for Gold:\n' .. '--> !hunt Joe,gold,150000\n' .. '--> Placed a bounty on Joe for the amount of 150,000 gps.' .. '\n\n' .. 'Hunting for Premium Points:\n' .. '--> !hunt Joe,points,100\n' .. '--> Placed a bounty on Joe for the amount of 100 premium points.'
        text = text .. (item:getId() > 0 and ('\n\n' .. 'Hunting for ' .. item:getPluralName() .. ':\n' .. '--> !hunt Joe,' .. customCurrency .. ',50\n' .. '--> Placed a bounty on Joe for the amount of 50 ' .. item:getPluralName()) or '')
        player:popupFYI(text)
        return false
    end

    local target = Player(name)
    if not target then
        player:sendTextMessage(MESSAGE_STATUS_CONSOLE_ORANGE, '[BOUNTY_HUNTER_SYSTEM] A player with the name of ' .. name .. ' is not online.')
    return false
    end

    if target:getGuid() == player:getGuid() then
        player:sendTextMessage(MESSAGE_STATUS_CONSOLE_ORANGE, '[BOUNTY_HUNTER_SYSTEM] You may not place a bounty on yourself!')
    return false
    end

    if config.ipCheck and target:getIp() == player:getIp() then
        player:sendTextMessage(MESSAGE_STATUS_CONSOLE_ORANGE, '[BOUNTY_HUNTER_SYSTEM] You may not place a bounty on a player from the same IP Address!')
    return false
    end

    if target:getLevel() < config.minLevelToBeTargeted then
        player:sendTextMessage(MESSAGE_STATUS_CONSOLE_ORANGE, '[BOUNTY_HUNTER_SYSTEM] You may only target players level ' .. config.minLevelToBeTargeted .. ' and above!')
    return false
    end

    local info = target:getBountyInfo()
    if info[1] then
        player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "[BOUNTY HUNTER SYSTEM] This player has already been hunted.")
        return false
    end

    local typ = config.currencies[currencyType]
    if not typ or currencyType == '' then
        player:sendTextMessage(MESSAGE_STATUS_CONSOLE_ORANGE, '[BOUNTY_HUNTER_SYSTEM] The currency type "' .. currencyType .. '" is not a valid bounty currency. [Currencies: gold/points' .. (customCurrency ~= '' and '/'..customCurrency..'' or '') .. ']')
    return false
    end

    local minA, maxA = typ.minAmount, typ.maxAmount
    if amount ~= amount or amount % 1 ~= 0 or amount < minA or amount > maxA then
        player:sendTextMessage(MESSAGE_STATUS_CONSOLE_ORANGE, '[BOUNTY_HUNTER_SYSTEM] The currency type of "' .. currencyType .. '" allows the amount to be in the range of ' .. minA .. ' --> ' .. maxA .. '.')
    return false
    end

    if currencyType~='gold' and currencyType~='points' then return false end
    local ok=Economy.run(player,function(ctx)
        if not typ.check(player,amount,currencyType) then return false end
        return db.query('INSERT INTO bounty_hunter_system (hunter_id,target_id,killer_id,prize,currencyType,dateAdded,killed,dateKilled) VALUES ('..player:getGuid()..','..target:getGuid()..',0,'..amount..','..db.escapeString(currencyType)..','..os.time()..',0,0)')
    end)
    if not ok then
        player:sendTextMessage(MESSAGE_STATUS_CONSOLE_ORANGE, '[BOUNTY_HUNTER_SYSTEM] You do not have ' .. amount .. ' ' .. currencyType .. '. [Error: Insufficient Funds]')
    return false
    end

    player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE,'[BOUNTY HUNTER SYSTEM] Bounty recorded for '..target:getName()..': '..amount..' '..currencyType..'.')
    return false
end



function onBountyHunterKill(creature, target)
    if not creature:isPlayer() then
        creature = creature:getMaster()
        if not creature or not creature:isPlayer() then
            return true
        end
    end
    if not target:isPlayer() then
        return true
    end

    if creature:getTile():hasFlag(TILESTATE_PVPZONE) then
        return true
    end

    local info = target:getBountyInfo()
    if not info[1] then
        return true
    end

    return addBountyKill(creature, target, info[2], info[3], info[4], info[5])
end
