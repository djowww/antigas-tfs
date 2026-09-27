AntigasBestiary = {
	OPCODE = 124,
	STORAGE_BASE = 1500000000,
	STORAGE_HASH_RANGE = 600000000,
	MAX_KILLS = 1000,
	CATALOG_SIZE = 138,
	COMPLETION_STORAGE = 17650,
	XP_REMAINDER_STORAGE = 17651,
	XP_BONUS_UNITS_PER_COMPLETION = 2, -- 0.2 percentage points, in tenths of a percent.
	XP_BONUS_DENOMINATOR = 1000
}

function AntigasBestiary.getCompletedCount(player)
	local count = math.floor(tonumber(player:getStorageValue(AntigasBestiary.COMPLETION_STORAGE)) or 0)
	return math.max(0, math.min(AntigasBestiary.CATALOG_SIZE, count))
end

function AntigasBestiary.setCompletedCount(player, count)
	count = math.floor(tonumber(count) or 0)
	count = math.max(0, math.min(AntigasBestiary.CATALOG_SIZE, count))
	player:setStorageValue(AntigasBestiary.COMPLETION_STORAGE, count)
	return count
end

function AntigasBestiary.addCompletion(player)
	local count = AntigasBestiary.getCompletedCount(player)
	if count >= AntigasBestiary.CATALOG_SIZE then
		return nil
	end
	return AntigasBestiary.setCompletedCount(player, count + 1)
end

function AntigasBestiary.reconcileCompletedCount(player, count)
	local current = AntigasBestiary.getCompletedCount(player)
	count = math.floor(tonumber(count) or 0)
	if count > current then
		return AntigasBestiary.setCompletedCount(player, count)
	end
	return current
end

function AntigasBestiary.migrateCompletedCount(player)
	local stored = tonumber(player:getStorageValue(AntigasBestiary.COMPLETION_STORAGE)) or -1
	if stored >= 0 then
		return AntigasBestiary.getCompletedCount(player), false
	end

	local query = string.format(
		"SELECT COUNT(*) AS completed FROM `player_storage` WHERE `player_id` = %d AND `key` BETWEEN %d AND %d AND `value` >= %d",
		player:getGuid(),
		AntigasBestiary.STORAGE_BASE,
		AntigasBestiary.STORAGE_BASE + AntigasBestiary.STORAGE_HASH_RANGE - 1,
		AntigasBestiary.MAX_KILLS
	)
	local resultId = db.storeQuery(query)
	if not resultId then
		return nil, false
	end

	local completed = result.getNumber(resultId, "completed")
	result.free(resultId)
	return AntigasBestiary.setCompletedCount(player, completed), true
end

function AntigasBestiary.normalizeName(name)
	if type(name) ~= "string" or #name == 0 or #name > 40 then
		return nil
	end
	return name:lower():gsub("%s+", " "):match("^%s*(.-)%s*$")
end

-- Stable per-monster storage key. The range was collision-checked against the
-- current server roster and the complete 7.4 Bestiary catalog.
function AntigasBestiary.storageKey(name)
	local normalized = AntigasBestiary.normalizeName(name)
	if not normalized then
		return nil
	end

	local hash = 5381
	for index = 1, #normalized do
		hash = (hash * 33 + string.byte(normalized, index)) % AntigasBestiary.STORAGE_HASH_RANGE
	end
	return AntigasBestiary.STORAGE_BASE + hash
end
