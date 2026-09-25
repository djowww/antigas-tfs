local storage = 30018

function onUse(player, item, fromPosition, target, toPosition, isHotkey)
    local voc_id = player:getVocation():getId()
    if voc_id ~= 0 and voc_id < 5 and player:getStorageValue(storage) == 1 then
        player:setVocation(voc_id + 4)
    end
    player:addPremiumDays(7)
    player:sendTextMessage(MESSAGE_INFO_DESCR, "You have received 7 days of premium account.")
    player:getPosition():sendMagicEffect(CONST_ME_MAGIC_GREEN)
    item:remove(1)
    return true
end