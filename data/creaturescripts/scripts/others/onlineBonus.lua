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

    local currentBonus = player:getOnlineStayBonusUnits()
    local maxBonus = ONLINE_STAY_BONUS_MAX * ONLINE_STAY_BONUS_SCALE
    if currentBonus >= maxBonus then
        player:setOnlineStayBonusUnits(maxBonus)
        events[playerId] = nil
        return
    end

    local newBonus = player:setOnlineStayBonusUnits(currentBonus + ONLINE_STAY_BONUS_STEP)
    local bonusIncrease = newBonus - currentBonus
    player:getPosition():sendMagicEffect(13)
    player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
        "Your online bonus increased by " .. string.format("%.1f", bonusIncrease / ONLINE_STAY_BONUS_SCALE) ..
        "%. You now receive +" .. string.format("%.1f", newBonus / ONLINE_STAY_BONUS_SCALE) ..
        "% experience and skills (maximum +" .. ONLINE_STAY_BONUS_MAX .. "%).")

    if newBonus < maxBonus then
        token.eventId = addEvent(grantOnlineBonus, rewardInterval, playerId, token)
    else
        events[playerId] = nil
    end
end

function onLogin(player)
    player:registerEvent("OnlineBonusLogout")
    local playerId = player:getId()
    cancelReward(playerId)

    local currentBonus = player:getOnlineStayBonusUnits()
    if currentBonus >= ONLINE_STAY_BONUS_MAX * ONLINE_STAY_BONUS_SCALE then
        player:setOnlineStayBonusUnits(ONLINE_STAY_BONUS_MAX * ONLINE_STAY_BONUS_SCALE)
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
