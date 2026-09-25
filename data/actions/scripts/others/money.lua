local config={
    [ITEM_GOLD_COIN]={up=ITEM_PLATINUM_COIN},
    [ITEM_PLATINUM_COIN]={up=ITEM_CRYSTAL_COIN,down=ITEM_GOLD_COIN},
    [ITEM_CRYSTAL_COIN]={down=ITEM_PLATINUM_COIN}
}
function onUse(player,item,fromPosition,target,toPosition,isHotkey)
    local coin=config[item:getId()]
    if not coin then return false end
    local id,take,give
    if coin.up and item:getCount()==100 then id,take,give=coin.up,100,1
    elseif coin.down then id,take,give=coin.down,1,100
    else return false end
    local ok=Economy.run(player,function(ctx) return ctx:take(item,take) and ctx:give(id,give) end)
    if ok then Game.sendAnimatedText('$$$',player:getPosition(),TEXTCOLOR_YELLOW)
    else player:sendCancelMessage('Keep the coins in your inventory and leave enough space. Nothing was exchanged.') end
    return true
end
