function onUse(player,item,fromPosition,target,toPosition,isHotkey)
    local gold=math.floor(player:getItemCount(3031)/100)*100
    local platinum=player:getItemCount(3035)
    local total=platinum+gold/100
    local crystal=math.floor(total/100)
    local remainder=total%100
    if gold==0 and crystal==0 then
        player:sendTextMessage(MESSAGE_INFO_DESCR,'No stacks of coins needed to be converted.')
        return true
    end
    local ok=Economy.run(player,function(ctx)
        if gold>0 and not ctx:takeType(3031,gold) then return false end
        if platinum>0 and not ctx:takeType(3035,platinum) then return false end
        if crystal>0 and not ctx:give(3043,crystal) then return false end
        return remainder==0 or ctx:give(3035,remainder)
    end)
    if ok then
        player:getPosition():sendMagicEffect(CONST_ME_MAGIC_GREEN)
        player:sendTextMessage(MESSAGE_INFO_DESCR,'Coins converted without changing their total value.')
    else player:sendCancelMessage('Not enough space or exchange unavailable. All coins were preserved.') end
    return true
end
