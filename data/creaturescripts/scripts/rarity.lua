local ITEM_RARITY_OPCODE = 127
local MAX_CONTAINER_PAGE = 40

local function getRarityFields(item)
	if not item then
		return 0, 0, 0, 0, 0
	end

	local tier, bonusType, bonusValue, subtype, extraBonuses = item:getRarityInfo()
	return tier or 0, bonusType or 0, bonusValue or 0, subtype or 0, extraBonuses or 0
end

local function makeRecord(index, item)
	local tier, bonusType, bonusValue, subtype, extraBonuses = getRarityFields(item)
	return string.format("%d,%d,%d,%d,%d,%d", index, tier, bonusType, bonusValue, subtype, extraBonuses)
end

local function sendInventoryRarities(player, requestId, slot)
	player:sendExtendedOpcode(ITEM_RARITY_OPCODE, string.format("R|I|%d|%s", requestId, makeRecord(slot, player:getSlotItem(slot))))
end

local function sendContainerRarities(player, requestId, containerId, firstIndex, count)
	local container = player:getContainerById(containerId)
	if not container then
		return
	end

	local records = {}
	local lastIndex = firstIndex + count - 1
	for index = firstIndex, lastIndex do
		records[#records + 1] = makeRecord(index, container:getItem(index))
	end
	player:sendExtendedOpcode(ITEM_RARITY_OPCODE, string.format("R|C|%d|%d|%d|%s", requestId, containerId, firstIndex, table.concat(records, ";")))
end

function onExtendedOpcode(player, opcode, buffer)
	if opcode ~= ITEM_RARITY_OPCODE then
		return false
	end
	if type(buffer) ~= "string" or #buffer > 256 then
		return true
	end

	local requestId, slot = buffer:match("^Q|I|(%d+)|(%d+)$")
	requestId, slot = tonumber(requestId), tonumber(slot)
	if requestId and requestId > 0 and requestId <= 2147483647 and slot and slot >= CONST_SLOT_HEAD and slot <= CONST_SLOT_AMMO then
		sendInventoryRarities(player, requestId, slot)
		return true
	end

	local containerId, firstIndex, count
	requestId, containerId, firstIndex, count = buffer:match("^Q|C|(%d+)|(%d+)|(%d+)|(%d+)$")
	requestId, containerId, firstIndex, count = tonumber(requestId), tonumber(containerId), tonumber(firstIndex), tonumber(count)
	if requestId and requestId > 0 and requestId <= 2147483647 and containerId and containerId <= 15 and firstIndex and firstIndex <= 65535 and count and count > 0 and count <= MAX_CONTAINER_PAGE and firstIndex + count <= 65536 then
		sendContainerRarities(player, requestId, containerId, firstIndex, count)
		return true
	end

	return true
end
