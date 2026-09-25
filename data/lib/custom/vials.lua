-- One timer per session, never one timer per toggle. Ten times fewer scans.
VialTimers=VialTimers or {}
local timers=VialTimers
local storage,vial,interval=50000,2874,1000
function stopPlayerVials(id)
    local token=timers[id]
    if token then stopEvent(token.event);timers[id]=nil end
end
local function scan(id,token)
    if timers[id]~=token then return end
    local player=Player(id)
    if not player or player:getGuid()~=token.guid or player:getStorageValue(storage)<1 then timers[id]=nil;return end
    local count=player:getItemCount(vial,FLUID_NONE)
    local held=math.max(0,player:getStorageValue(vial))
    if count>0 and held+count<=2000000000 and player:removeItem(vial,count,FLUID_NONE) then
        player:setStorageValue(vial,held+count)
    end
    token.event=addEvent(scan,interval,id,token)
end
function removePlayerVials(id)
    stopPlayerVials(id)
    local player=Player(id)
    if not player or player:getStorageValue(storage)<1 then return end
    local token={guid=player:getGuid()}
    timers[id]=token
    scan(id,token)
end
function Player:returnVials()
    local held=math.max(0,self:getStorageValue(vial))
    if held==0 then return true end
    -- Return a bounded batch, decrementing the credit only after safe delivery.
    local count=math.min(held,20)
    local ok=Economy.run(self,function(ctx)
        if not ctx:give(vial,count) then return false end
        ctx:setStorage(vial,held-count)
        return true
    end)
    self:sendTextMessage(MESSAGE_INFO_DESCR,ok and ('Returned '..count..' empty vials. Remaining: '..(held-count)..'. Use !vial collect to collect more.') or 'Make space for up to 20 vials. Your stored vials were preserved.')
    return ok
end
