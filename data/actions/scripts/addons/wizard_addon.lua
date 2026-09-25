local requirements = {
    {3436, 1}, -- Medusa Shield
    {3386, 1}, -- DSM
	{3382, 1}, -- crown legs
	{3006, 1} -- ROS
}

local addons = {179,178}

function onUse(player, item, fromPos, target, toPos, isHotkey)
    if player:hasOutfit(addons[1], 3) and player:hasOutfit(addons[2], 3) then
        player:sendCancelMessage("You already have this outfit.")
        return true
    end

    for _, req in pairs(requirements) do
        if player:getItemCount(req[1]) < req[2] then
            player:sendCancelMessage("Sorry, you need 1 medusa shield, 1 dragon scale mail, 1 crown legs and ring of the sky.")
            return true
        end
    end

    for _, req in pairs(requirements) do
        player:removeItem(req[1], req[2])
    end

    player:addOutfitAddon(addons[1], 2)
    player:addOutfitAddon(addons[2], 2)
    player:sendTextMessage(MESSAGE_INFO_DESCR, "You received the Wizard addon.")
    item:remove(1)
    return true
end