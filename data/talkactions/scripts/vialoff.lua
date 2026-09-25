function onSay(player,words,param,channel)
    if param:lower():trim()=='collect' then player:returnVials();return false end
    local enabled=player:getStorageValue(50000)<1
    player:setStorageValue(50000,enabled and 1 or 0)
    if enabled then removePlayerVials(player:getId())
    else stopPlayerVials(player:getId());player:returnVials() end
    player:getPosition():sendMagicEffect(enabled and CONST_ME_MAGIC_RED or CONST_ME_MAGIC_GREEN)
    player:sendTextMessage(MESSAGE_INFO_DESCR,enabled and 'Empty vial collection enabled.' or 'Empty vial collection disabled.')
    return false
end
