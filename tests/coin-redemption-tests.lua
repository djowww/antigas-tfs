-- Exercise the actual legacy action and Economy rollback without a live account.
MESSAGE_EVENT_ADVANCE, FLAG_NOLIMIT, FLAG_IGNOREAUTOSTACK = 1, 1, 2
RETURNVALUE_NOERROR = 0
local balance, available, allowCredit, nextUid = 0, true, true, 0
local pending, changed, successfulMessages = 0, 0, 0
ItemType = function(id)
    return {isRetired=function() return false end, isStackable=function() return id == 5130 end}
end
local function coin(count)
    nextUid = nextUid + 1
    local value = {count=count, uid=nextUid}
    function value:isItem() return true end
    function value:isContainer() return false end
    function value:getId() return 5130 end
    function value:getUniqueId() return self.uid end
    function value:getCount() return self.count end
    function value:getTopParent() return self.parent end
    function value:clone() return coin(self.count) end
    function value:remove(n)
        self.count = self.count - (n or self.count)
        if self.count == 0 then
            if self.parent then self.parent.item = nil end
            self.parent = nil
        end
        return true
    end
    function value:transform(_, count) self.count=count; return true end
    return value
end
local function playerWithCoin(count)
    local player = {bank=0}
    player.item = coin(count)
    player.item.parent = player
    function player:isPlayer() return true end
    function player:getId() return 11 end
    function player:getAccountId() return 7 end
    function player:getSlotItem(slot) return slot==1 and self.item or nil end
    function player:getBankBalance() return self.bank end
    function player:setBankBalance(n) self.bank=n end
    function player:addItemEx(item)
        assert(not self.item)
        self.item, item.parent = item, self
        return RETURNVALUE_NOERROR
    end
    function player:marketTransaction(work, undo)
        pending = balance
        if not available then return false end
        local ok = work()
        if ok and not self.failCommit then balance=pending; return true end
        assert(undo(), 'rollback must restore the consumed Coin')
        return false
    end
    function player:sendTextMessage() successfulMessages=successfulMessages+1 end
    function player:sendCancelMessage() end
    function player:getPosition() return {sendMagicEffect=function() end} end
    return player
end
db = {
    query=function(sql)
        assert(sql:find('premium_points=premium_points+1',1,true), 'one Coin must credit one point')
        assert(sql:find('WHERE id=7 AND premium_points<=1999999999',1,true), 'credit must remain bounded and account-scoped')
        changed=allowCredit and pending<=1999999999 and 1 or 0
        pending=pending+changed
        return true
    end,
    storeQuery=function(sql) assert(sql=='SELECT ROW_COUNT() AS n'); return 31 end
}
result = {getDataInt=function(id,field) assert(id==31 and field=='n'); return changed end,
    free=function(id) assert(id==31) end}
dofile('data/lib/custom/economy.lua')
dofile('data/actions/scripts/others/olderac.lua')

local p = playerWithCoin(2)
assert(onUse(p,p.item))
assert(balance==1 and p.item:getCount()==1 and successfulMessages==1)
local last = p.item
assert(onUse(p,last))
assert(balance==2 and p.item==nil and successfulMessages==2, 'last Coin must disappear after credit')
assert(onUse(p,last))
assert(balance==2 and successfulMessages==2, 'reusing a consumed item must never credit twice')

p=playerWithCoin(2); p.failCommit=true
assert(onUse(p,p.item))
assert(balance==2 and p.item:getCount()==2, 'failed commit must restore a partial stack')
p=playerWithCoin(1); p.failCommit=true
assert(onUse(p,p.item))
assert(balance==2 and p.item:getCount()==1, 'failed commit must restore a removed stack')

allowCredit=false; p=playerWithCoin(1)
assert(onUse(p,p.item))
assert(balance==2 and p.item:getCount()==1, 'rejected credit must not consume a Coin')
allowCredit=true; balance=2000000000
assert(onUse(p,p.item))
assert(balance==2000000000 and p.item:getCount()==1, 'overflow must preserve Coin and balance')
available=false; balance=2
assert(onUse(p,p.item))
assert(balance==2 and p.item:getCount()==1, 'database outage must preserve Coin and balance')
available=true
local foreign=coin(1)
assert(onUse(p,foreign))
assert(balance==2 and foreign:getCount()==1, 'ground or other-owner Coins cannot be redeemed')
assert(successfulMessages==2, 'failed transactions must not announce credit')
print('Coin redemption tests passed: success, stacks, duplicate use, ownership, rollback, overflow, outage')
