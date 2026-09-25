local requirements = {
    {5186, 50} -- holy orchidd
}

local addons = {179,178}

function onUse(player, item, fromPos, target, toPos, isHotkey)
    if player:hasOutfit(addons[1], 3) and player:hasOutfit(addons[2], 3) then
        player:sendCancelMessage("You already have this outfit.")
        return true
    end

    for _, req in pairs(requirements) do
        if player:getItemCount(req[1]) < req[2] then
            player:sendCancelMessage("Sorry, you need 50 holy orchid.")
            return true
        end
    end

    for _, req in pairs(requirements) do
        player:removeItem(req[1], req[2])
    end

    player:addOutfitAddon(addons[1], 1)
    player:addOutfitAddon(addons[2], 1)
    player:sendTextMessage(MESSAGE_INFO_DESCR, "You received the Wizard addon.")
    item:remove(1)
    return true
end