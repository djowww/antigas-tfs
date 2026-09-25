-- Login and logout are loaded separately; share their timer registry.
OnlineBonusEvents = OnlineBonusEvents or {}
local events = OnlineBonusEvents
local rewardInterval = 60 * 60 * 1000

local function cancelReward(playerId)
    local pending = events[playerId]
    if pending then
        stopEvent(pending.eventId)
        events[playerId] = nil
    end
end

local function grantOnlineBonus(playerId, token)
    if events[playerId] ~= token then
        return
    end

    local player = Player(playerId)
    if not player or player:getIp() == 0 then
        events[playerId] = nil
        return
    end

    local currentBonus = math.max(0, player:getStorageValue(ONLINE_STAY_BONUS_STORAGE))
    if currentBonus >= ONLINE_STAY_BONUS_MAX then
        player:setStorageValue(ONLINE_STAY_BONUS_STORAGE, ONLINE_STAY_BONUS_MAX)
        events[playerId] = nil
        return
    end

    local newBonus = math.min(ONLINE_STAY_BONUS_MAX, currentBonus + 1)
    player:setStorageValue(ONLINE_STAY_BONUS_STORAGE, newBonus)
    player:getPosition():sendMagicEffect(13)
    player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
        "Your online bonus increased by 1%. You now receive +" .. newBonus .. "% experience and skills (maximum +" .. ONLINE_STAY_BONUS_MAX .. "%).")

    if newBonus < ONLINE_STAY_BONUS_MAX then
        token.eventId = addEvent(grantOnlineBonus, rewardInterval, playerId, token)
    else
        events[playerId] = nil
    end
end

function onLogin(player)
    player:registerEvent("OnlineBonusLogout")
    local playerId = player:getId()
    cancelReward(playerId)

    local currentBonus = math.max(0, player:getStorageValue(ONLINE_STAY_BONUS_STORAGE))
    if currentBonus >= ONLINE_STAY_BONUS_MAX then
        player:setStorageValue(ONLINE_STAY_BONUS_STORAGE, ONLINE_STAY_BONUS_MAX)
        return true
    end

    local token = {}
    events[playerId] = token
    token.eventId = addEvent(grantOnlineBonus, rewardInterval, playerId, token)
    return true
end

function onLogout(player)
    cancelReward(player:getId())
    return true
end
