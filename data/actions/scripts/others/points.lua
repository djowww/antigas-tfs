function onUse(player,item,fromPosition,target,toPosition,isHotkey)
    -- Consume exactly one ticket, even when it is part of a stack.
    return Economy.redeemPoints(player,item,10)
end
