local requestTimes = {}
local MAX_REQUEST_BYTES = 8192
local MAX_REQUEST_MONSTERS = 200
local REQUEST_INTERVAL = 2
local lastRequestCleanup = 0

function onKill(killer, target)
	if not killer or not killer:isPlayer() or not target or not target:isMonster() then
		return true
	end
	local targetMaster = target:getMaster()
	if targetMaster and targetMaster:isPlayer() then
		return true
	end

	local storageKey = AntigasBestiary.storageKey(target:getName())
	if not storageKey then
		return true
	end

	local kills = math.max(0, math.min(AntigasBestiary.MAX_KILLS, killer:getStorageValue(storageKey)))
	if kills < AntigasBestiary.MAX_KILLS then
		kills = kills + 1
		killer:setStorageValue(storageKey, kills)
		killer:sendExtendedOpcode(AntigasBestiary.OPCODE, json.encode({
			action = "update",
			monster = AntigasBestiary.normalizeName(target:getName()),
			kills = kills
		}))
	end
	return true
end

function onExtendedOpcode(player, opcode, buffer)
	if opcode ~= AntigasBestiary.OPCODE then
		return false
	end
	if type(buffer) ~= "string" or #buffer > MAX_REQUEST_BYTES then
		return false
	end

	local decoded, request = pcall(function() return json.decode(buffer) end)
	if not decoded or type(request) ~= "table" or request.action ~= "getProgress" or type(request.monsters) ~= "table" then
		return false
	end

	local guid = player:getGuid()
	local now = os.time()
	local lastRequest = requestTimes[guid]
	if lastRequest and now - lastRequest < REQUEST_INTERVAL then
		return true
	end
	requestTimes[guid] = now
	if now - lastRequestCleanup >= 60 then
		lastRequestCleanup = now
		for playerGuid, timestamp in pairs(requestTimes) do
			if timestamp < now - 120 then
				requestTimes[playerGuid] = nil
			end
		end
	end

	local counts, seen = {}, {}
	local monsterCount = #request.monsters
	if monsterCount > MAX_REQUEST_MONSTERS then
		return false
	end
	for index = 1, monsterCount do
		local requestedName = request.monsters[index]
		local normalized = AntigasBestiary.normalizeName(requestedName)
		if normalized and not seen[normalized] and MonsterType(normalized) then
			seen[normalized] = true
			local storageKey = AntigasBestiary.storageKey(normalized)
			local kills = math.max(0, math.min(AntigasBestiary.MAX_KILLS, player:getStorageValue(storageKey)))
			counts[requestedName] = kills
		end
	end

	player:sendExtendedOpcode(AntigasBestiary.OPCODE, json.encode({action = "progress", data = counts}))
	return true
end
