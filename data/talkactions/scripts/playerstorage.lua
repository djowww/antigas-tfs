function onSay(player, words, param)
	if not player:getGroup():getAccess() then
		return true
	end
 
	local split = param:split(",")
	local target = Player(split[1])
	if target == nil then
		player:sendCancelMessage("A player with that name is not online.")
		return false
	end
 
	local value = tonumber(split[2])
	if value == nil or value <= 0 then
		player:sendCancelMessage("You need to put the storage to verify.")
		return false
	end
 
	local storage = target:getStorageValue(value)
	local key = tonumber(split[3])
	if key == nil then
		player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "[READ] Storage Key: " .. value .. " | Value: " .. storage .. " | Player: "..target:getName())
	else
		target:setStorageValue(value, key)
		player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "[SET] Storage Key: " .. value .. " | Value: " .. key .. " | Player " .. target:getName() .. ".")
	end

	return false
end