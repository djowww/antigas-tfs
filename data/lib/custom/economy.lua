-- One player's inventory/bank and SQL commit together. No yielding/notifications
-- inside work(). Detached clones are temporary script items, released by TFS.
Economy = Economy or {}
function Economy.integer(n,low,high)
    return type(n)=='number' and n==n and n%1==0 and n>=low and n<=high
end
function Economy.changed(query)
    if not db.query(query) then return false end
    local r=db.storeQuery('SELECT ROW_COUNT() AS n')
    if not r then return false end
    local ok=result.getDataInt(r,'n')==1
    result.free(r)
    return ok
end
function Economy.owned(player,item)
    if not item or not item:isItem() then return false end
    local parent=item:getTopParent()
    return parent and parent:isPlayer() and parent:getId()==player:getId()
end
function Economy.inventory(player)
    local todo,out,seen={},{},{}
    for slot=1,10 do
        local item=player:getSlotItem(slot)
        if item then todo[#todo+1]={item=item,parent=player,slot=slot} end
    end
    while #todo>0 do
        if #out>=10000 then return nil end
        local e=table.remove(todo)
        local uid=e.item:getUniqueId()
        if not seen[uid] then
            seen[uid]=true;out[#out+1]=e
            if e.item:isContainer() then
                for i=0,e.item:getSize()-1 do
                    local child=e.item:getItem(i)
                    if child then todo[#todo+1]={item=child,parent=e.item} end
                end
            end
        end
    end
    return out
end
function Economy.run(player,work)
    if not player.marketTransaction then return false end
    local ctx={player=player,bank=player:getBankBalance(),removed={},added={},storage={},attributes={}}
    function ctx:take(item,count,knownEntry)
        if not Economy.owned(self.player,item) or not Economy.integer(count,1,10000) then return false end
        local entries=knownEntry and {knownEntry} or Economy.inventory(self.player)
        if not entries then return false end
        for _,e in ipairs(entries) do
            if e.item==item then
                local old=ItemType(item:getId()):isStackable() and item:getCount() or 1
                if count>old then return false end
                local copy=item:clone()
                if not copy then return false end
                local partial=count<old and item or nil
                if not item:remove(count) then copy:remove();return false end
                self.removed[#self.removed+1]={copy=copy,parent=e.parent,slot=e.slot,partial=partial,id=copy:getId(),count=old}
                return true
            end
        end
        return false
    end
    function ctx:takeType(id,count)
        local entries=Economy.inventory(self.player)
        if not entries then return false end
        for _,e in ipairs(entries) do
            if count>0 and e.item:getId()==id and e.item:getActionId()==0 and e.item:getMovementId()==0 then
                local n=math.min(count,e.item:getCount())
                if not self:take(e.item,n,e) then return false end
                count=count-n
            end
        end
        return count==0
    end
    function ctx:give(id,count)
        if not Economy.integer(count,1,10000) then return false end
        local stackable=ItemType(id):isStackable()
        while count>0 do
            if #self.added>=100 then return false end
            local n=stackable and math.min(100,count) or 1
            local item=Game.createItem(id,ItemType(id):isFluidContainer() and FLUID_NONE or n)
            if not item then return false end
            if self.player:addItemEx(item,false,INDEX_WHEREEVER,FLAG_IGNOREAUTOSTACK)~=RETURNVALUE_NOERROR then item:remove();return false end
            self.added[#self.added+1]=item;count=count-n
        end
        return true
    end
    function ctx:setStorage(key,value)
        if self.storage[key]==nil then self.storage[key]=self.player:getStorageValue(key) end
        self.player:setStorageValue(key,value)
    end
    function ctx:setAttribute(item,key,value)
        if not Economy.owned(player,item) then return false end
        self.attributes[#self.attributes+1]={item=item,key=key,exists=item:hasAttribute(key),value=item:getAttribute(key)}
        return item:setAttribute(key,value)
    end
    return player:marketTransaction(function() return work(ctx)==true end,function()
        for i=#ctx.added,1,-1 do if not ctx.added[i]:remove() then return false end end
        player:setBankBalance(ctx.bank)
        for i=#ctx.attributes,1,-1 do
            local a=ctx.attributes[i]
            if a.exists then a.item:setAttribute(a.key,a.value) else a.item:removeAttribute(a.key) end
        end
        for key,value in pairs(ctx.storage) do player:setStorageValue(key,value) end
        for i=#ctx.removed,1,-1 do
            local e=ctx.removed[i]
            if e.partial then
                if not e.partial:transform(e.id,e.count) then return false end
            else
                local flags=FLAG_NOLIMIT+FLAG_IGNOREAUTOSTACK
                local ret=e.slot and player:addItemEx(e.copy,false,e.slot,flags) or e.parent:addItemEx(e.copy,INDEX_WHEREEVER,flags)
                if ret~=RETURNVALUE_NOERROR then return false end
            end
        end
        return true
    end)
end
function Economy.redeemPoints(player,item,points)
    local ok=Economy.run(player,function(ctx)
        return ctx:take(item,1) and Economy.changed('UPDATE accounts SET premium_points=premium_points+'..points..' WHERE id='..player:getAccountId()..' AND premium_points<='..(2000000000-points))
    end)
    if ok then
        player:sendTextMessage(MESSAGE_EVENT_ADVANCE,points..' premium points have been added to your account.')
        player:getPosition():sendMagicEffect(13)
    else player:sendCancelMessage('Keep the coin in your inventory. If the service is unavailable, nothing is consumed.') end
    return true
end
