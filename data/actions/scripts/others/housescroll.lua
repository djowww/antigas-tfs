function onUse(player, item, fromPosition, target, toPosition, isHotkey)
    if player:getPremiumDays() <= 0 then
        player:sendCancelMessage("You need a premium account to use house scroll.")
        return true
    end

	local position = player:getPosition()
	position:getNextPosition(player:getDirection())

	local tile = Tile(position)
	local house = tile and tile:getHouse()
	if house == nil then
		player:sendCancelMessage("You have to be looking at the door of the house you would like to buy.")
		return true
	end

	if house:getOwnerGuid() > 0 then
		player:sendCancelMessage("This house already has an owner.")
		return true
	end

	if player:getHouse() then
		player:sendCancelMessage("You are already the owner of a house.")
		return true
	end

	house:setOwnerGuid(player:getGuid())
	player:sendTextMessage(MESSAGE_INFO_DESCR, "You have successfully bought this house, be sure to have the money for the rent in the bank.")
	item:remove(1)
	return true
end