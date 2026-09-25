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

local function addOnlineToken(playerId, token)
    if events[playerId] ~= token then
        return
    end
    local player = Player(playerId)
    if not player or player:getIp() == 0 then
        events[playerId] = nil
        return
    end
    if Economy.run(player,function(ctx)
        return ctx:give(5130,1) and Economy.changed('UPDATE players SET online_time=online_time+1 WHERE id='..player:getGuid()..' AND online_time<2000000000')
    end) then
        player:getPosition():sendMagicEffect(13)
        player:sendTextMessage(MESSAGE_EVENT_ADVANCE,
            "You get 1 Antigas Coin for staying online for 1 hour without logging out.")
    end
    token.eventId = addEvent(addOnlineToken, rewardInterval, playerId, token)
end

function onLogin(player)
    player:registerEvent("OnlineBonusLogout")
    local playerId = player:getId()
    cancelReward(playerId)
    local token = {}
    events[playerId] = token
    token.eventId = addEvent(addOnlineToken, rewardInterval, playerId, token)
    return true
end

function onLogout(player)
    cancelReward(player:getId())
    return true
end
