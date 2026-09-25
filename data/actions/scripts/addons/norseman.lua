local requirements = {
    {5215, 15} -- shard
}

local addons = {186,185}

function onUse(player, item, fromPos, target, toPos, isHotkey)
    if player:hasOutfit(addons[1], 3) and player:hasOutfit(addons[2], 3) then
        player:sendCancelMessage("You already have this outfit.")
        return true
    end

    for _, req in pairs(requirements) do
        if player:getItemCount(req[1]) < req[2] then
            player:sendCancelMessage("Sorry, you need 15 shard.")
            return true
        end
    end

    for _, req in pairs(requirements) do
        player:removeItem(req[1], req[2])
    end

    player:addOutfitAddon(addons[1], 3)
    player:addOutfitAddon(addons[2], 3)
    player:sendTextMessage(MESSAGE_INFO_DESCR, "You received the Norseman addons.")
    item:remove(1)
    return true
end