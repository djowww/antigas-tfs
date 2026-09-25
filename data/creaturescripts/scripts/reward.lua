local table = 
{
	-- [level] = type = "item", id = {ITEM_ID, QUANTIDADE}, msg = "MENSAGEM"},
	-- [level] = type = "bank", id = {QUANTIDADE, 0}, msg = "MENSAGEM"},
	-- [level] = type = "addon", id = {ID_ADDON_FEMALE, ID_ADDON_MALE}, msg = "MENSAGEM"},
	--[50] = {type = "addon", id = {2160, 5}, msg = "Voce ganhou 5 crystal coins por alcancar o level 50!"},
	--[100] = {type = "item", id = {2160, 10}, msg = "Voce ganhou 10 crystal coins por alcancar o level 100!"},
	--[130] = {type = "item", id = {2160, 25}, msg = "Voce ganhou 10 crystal coins por alcancar o level 100!"},
	--[150] = {type = "item", id = {2160, 50}, msg = "Voce ganhou 10 crystal coins por alcancar o level 100!"},
}

local storage = 15000

function onAdvance(player, skill, oldLevel, newLevel)

	if skill ~= SKILL_LEVEL or newLevel <= oldLevel then
		return true
	end

	-- Avoid a database save on every level advance when no rewards are configured.
	if next(table) == nil then
		return true
	end

	for level, _ in pairs(table) do
		if newLevel >= level and player:getStorageValue(storage) < level then
			if table[level].type == "item" then	
				player:addItem(table[level].id[1], table[level].id[2])
			elseif table[level].type == "bank" then
				player:setBankBalance(player:getBankBalance() + table[level].id[1])
			elseif table[level].type == "addon" then
				player:addOutfitAddon(table[level].id[1], 3)
				player:addOutfitAddon(table[level].id[2], 3)
			else
				return false
			end

			player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, table[level].msg)
			player:setStorageValue(storage, level)
		end
	end

	player:save()

	return true
end
