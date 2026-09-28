-- Persistent milestone achievements for Antigas. Storage ids are reserved in
-- the 17800 range; counters are server-owned and never accepted from clients.
AntigasAchievements = {
	OPCODE = 126,
	MAX_PACKET_BYTES = 7000,
	ENTRIES_PER_PAGE = 12,
	STORAGE = {
		STEPS = 17800,
		MONSTER_KILLS = 17801,
		DEATHS = 17802,
		PVP_KILLS = 17803,
		ATTACK_PERCENT = 17804,
		PVP_DAMAGE_PERCENT = 17805,
		DEATH_REDUCTION_PERCENT = 17806,
		SPEED = 17807,
		UNREAD = 17808,
		LEVEL_REWARD_BASE = 17820,
		SKILL_REWARD_BASE = 17840
	},
	COUNTER_MILESTONES = {
		steps = {{100, 1}, {1000, 2}, {10000, 3}, {100000, 4}, {1000000, 5}},
		monsterKills = {{100, 1}, {1000, 1}, {10000, 1}, {100000, 1}, {1000000, 1}},
		deaths = {{1, 1}, {10, 1}, {100, 1}, {1000, 1}, {10000, 1}},
		pvpKills = {{1, 1}, {10, 1}, {100, 1}, {1000, 1}, {10000, 1}}
	},
	LEVEL_MILESTONES = {20, 50, 100, 150, 200},
	SKILL_MILESTONES = {40, 60, 80, 100, 120},
}

local A = AntigasAchievements
local progressRequests, lastRequestCleanup = {}, 0
local progressSnapshotId = 0
local counterOrder = {'steps', 'monsterKills', 'deaths', 'pvpKills'}

local function storage(player, key)
	return math.max(0, tonumber(player:getStorageValue(key)) or 0)
end

local function positionKey(position)
	return string.format('%d:%d:%d', position.x, position.y, position.z)
end

local function unlockedTier(value, milestones)
	local tier = 0
	for index, milestone in ipairs(milestones) do
		if value >= milestone[1] then tier = index else break end
	end
	return tier
end

local function notifyCompletion(player, title, reward)
	player:setStorageValue(A.STORAGE.UNREAD, storage(player, A.STORAGE.UNREAD) + 1)
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format('Achievement completed: %s. Reward: %s.', title, reward))
	A.sendProgress(player)
end

local function addCounterReward(player, counterKey, newValue)
	local milestones = A.COUNTER_MILESTONES[counterKey]
	local key = A.STORAGE[string.upper(counterKey:gsub('(%l)(%u)', '%1_%2'))]
	local oldValue = storage(player, key)
	newValue = math.max(oldValue, math.floor(tonumber(newValue) or 0))
	if newValue == oldValue then return end
	player:setStorageValue(key, newValue)

	local oldTier, newTier = unlockedTier(oldValue, milestones), unlockedTier(newValue, milestones)
	for tier = oldTier + 1, newTier do
		local bonus = milestones[tier][2]
		if counterKey == 'steps' then
			player:setStorageValue(A.STORAGE.SPEED, storage(player, A.STORAGE.SPEED) + bonus)
			player:changeSpeed(bonus)
			notifyCompletion(player, string.format('%s steps', milestones[tier][1]), string.format('+%d speed', bonus))
		elseif counterKey == 'monsterKills' then
			player:setStorageValue(A.STORAGE.ATTACK_PERCENT, storage(player, A.STORAGE.ATTACK_PERCENT) + bonus)
			notifyCompletion(player, string.format('%s monster kills', milestones[tier][1]), string.format('+%d%% physical and magic damage', bonus))
		elseif counterKey == 'deaths' then
			player:setStorageValue(A.STORAGE.DEATH_REDUCTION_PERCENT, storage(player, A.STORAGE.DEATH_REDUCTION_PERCENT) + bonus)
			notifyCompletion(player, string.format('%s deaths', milestones[tier][1]), string.format('%d%% less death penalty loss', bonus))
		elseif counterKey == 'pvpKills' then
			player:setStorageValue(A.STORAGE.PVP_DAMAGE_PERCENT, storage(player, A.STORAGE.PVP_DAMAGE_PERCENT) + bonus)
			notifyCompletion(player, string.format('%s PvP kills', milestones[tier][1]), string.format('+%d%% PvP damage', bonus))
		end
	end
end

local function addItemReward(player, itemId, title, reward)
	local item = player:addItem(itemId, 1)
	if not item then
		player:sendTextMessage(MESSAGE_EVENT_ADVANCE, string.format('%s is ready, but your inventory is full. Make space and gain another level or skill advance to receive it.', title))
		return false
	end
	notifyCompletion(player, title, reward)
	return true
end

local skillRewards = {
	[SKILL_FIST] = {item = 5143, name = 'Fist'},
	[SKILL_CLUB] = {item = 5143, name = 'Club'},
	[SKILL_SWORD] = {item = 5141, name = 'Sword'},
	[SKILL_AXE] = {item = 5142, name = 'Axe'},
	[SKILL_DISTANCE] = {item = 5144, name = 'Distance'},
	[SKILL_SHIELD] = {item = 5148, name = 'Shield'},
	[SKILL_MAGLEVEL] = {item = 5291, name = 'Magic'}
}
local skillOrder = {SKILL_FIST, SKILL_CLUB, SKILL_SWORD, SKILL_AXE, SKILL_DISTANCE, SKILL_SHIELD, SKILL_MAGLEVEL}

local function checkAdvanceRewards(player, skill, newLevel)
	local milestones = skill == SKILL_LEVEL and A.LEVEL_MILESTONES or A.SKILL_MILESTONES
	local base = skill == SKILL_LEVEL and A.STORAGE.LEVEL_REWARD_BASE or A.STORAGE.SKILL_REWARD_BASE + skill * 8
	local reward = skill == SKILL_LEVEL and {item = 5291, name = 'Experience'} or skillRewards[skill]
	if not reward then return end
	for index, threshold in ipairs(milestones) do
		local key = base + index
		if newLevel >= threshold and storage(player, key) ~= 1 then
			local title = string.format('%s level %d', reward.name, threshold)
			local label = reward.item == 5291 and 'an experience scroll' or string.format('a %s training weapon', reward.name:lower())
			if addItemReward(player, reward.item, title, label) then player:setStorageValue(key, 1) end
		end
	end
end

function A.grantPendingRewards(player)
	checkAdvanceRewards(player, SKILL_LEVEL, player:getLevel())
	for _, skill in ipairs(skillOrder) do
		local current = skill == SKILL_MAGLEVEL and player:getMagicLevel() or player:getSkillLevel(skill)
		checkAdvanceRewards(player, skill, current)
	end
end

function A.sendProgress(player)
	if not player or not player:isPlayer() then return end
	local milestones = {}
	local counters = {
		steps = {key=A.STORAGE.STEPS, name='Steps walked', rewards=A.COUNTER_MILESTONES.steps},
		monsterKills = {key=A.STORAGE.MONSTER_KILLS, name='Monsters defeated', rewards=A.COUNTER_MILESTONES.monsterKills},
		deaths = {key=A.STORAGE.DEATHS, name='Deaths', rewards=A.COUNTER_MILESTONES.deaths},
		pvpKills = {key=A.STORAGE.PVP_KILLS, name='PvP kills', rewards=A.COUNTER_MILESTONES.pvpKills}
	}
	for _, category in ipairs(counterOrder) do
		local definition = counters[category]
		local value = storage(player, definition.key)
		for tier, reward in ipairs(definition.rewards) do
			local target = reward[1]
			milestones[#milestones + 1] = {id=category .. '_' .. tier, category=definition.name,
				title=string.format('%s: %d', definition.name, target), progress=math.min(value, target), target=target,
				completed=value >= target, reward=category == 'steps' and string.format('+%d speed', reward[2])
					or category == 'monsterKills' and '+1% physical and magic damage'
					or category == 'deaths' and '1% less death penalty loss' or '+1% PvP damage'}
		end
	end
	for index, target in ipairs(A.LEVEL_MILESTONES) do
		local completed = storage(player, A.STORAGE.LEVEL_REWARD_BASE + index) == 1
		milestones[#milestones + 1] = {id='level_' .. index, category='Character level',
			title=string.format('Reach level %d', target), progress=math.min(player:getLevel(), target), target=target,
			completed=completed, reward='One 25% experience scroll'}
	end
	for _, skill in ipairs(skillOrder) do
		local reward = skillRewards[skill]
		local current = skill == SKILL_MAGLEVEL and player:getMagicLevel() or player:getSkillLevel(skill)
		for index, target in ipairs(A.SKILL_MILESTONES) do
			local key = A.STORAGE.SKILL_REWARD_BASE + skill * 8 + index
			local completed = storage(player, key) == 1
			milestones[#milestones + 1] = {id='skill_' .. skill .. '_' .. index, category=reward.name .. ' skill',
				title=string.format('Reach %s skill %d', reward.name:lower(), target), progress=math.min(current, target), target=target,
				completed=completed, reward=reward.item == 5291 and 'One 25% experience scroll' or string.format('One %s training weapon', reward.name:lower())}
		end
	end
	-- NetworkMessage.addString rejects strings above 8192 bytes. A complete
	-- catalog exceeds that limit, so send bounded pages from one snapshot.
	progressSnapshotId = progressSnapshotId % 2147483647 + 1
	local pages = math.ceil(#milestones / A.ENTRIES_PER_PAGE)
	local packets = {}
	local unread = storage(player, A.STORAGE.UNREAD)
	local bonuses = {speed=storage(player,A.STORAGE.SPEED), attack=storage(player,A.STORAGE.ATTACK_PERCENT),
		pvp=storage(player,A.STORAGE.PVP_DAMAGE_PERCENT), deathReduction=storage(player,A.STORAGE.DEATH_REDUCTION_PERCENT)}
	for page = 1, pages do
		local entries = {}
		local first = (page - 1) * A.ENTRIES_PER_PAGE + 1
		for index = first, math.min(first + A.ENTRIES_PER_PAGE - 1, #milestones) do
			entries[#entries + 1] = milestones[index]
		end
		local encoded = json.encode({action='progress', snapshotId=progressSnapshotId, page=page, pages=pages,
			entries=entries, unread=unread, bonuses=bonuses})
		-- Validate every page before sending any, preventing a partial snapshot
		-- or malformed opcode packet if a future catalog change grows a page.
		if #encoded > A.MAX_PACKET_BYTES then
			print('[AntigasAchievements] Progress page exceeds the safe packet size.')
			return false
		end
		packets[#packets + 1] = encoded
	end
	for _, encoded in ipairs(packets) do player:sendExtendedOpcode(A.OPCODE, encoded) end
	return true
end

function A.onWalk(player, fromPosition, toPosition)
	local dx = math.abs(toPosition.x - fromPosition.x)
	local dy = math.abs(toPosition.y - fromPosition.y)
	local dz = math.abs(toPosition.z - fromPosition.z)
	-- Adjacent tiles (including stairs) are a step; teleports and jumps are not.
	if dx <= 1 and dy <= 1 and dz <= 1 and dx + dy + dz > 0 then
		addCounterReward(player, 'steps', storage(player, A.STORAGE.STEPS) + 1)
	end
	return true
end

function A.onKill(killer, target)
	if not killer or not killer:isPlayer() or not target or not target:isCreature() then return true end
	if target:isPlayer() then
		addCounterReward(killer, 'pvpKills', storage(killer, A.STORAGE.PVP_KILLS) + 1)
	elseif target:isMonster() then
		local master = target:getMaster()
		if not (master and master:isPlayer()) then
			addCounterReward(killer, 'monsterKills', storage(killer, A.STORAGE.MONSTER_KILLS) + 1)
		end
	end
	return true
end

function A.onDeath(player, corpse, killer, mostDamageKiller, unjustified, mostDamageUnjustified)
	if player and player:isPlayer() then
		addCounterReward(player, 'deaths', storage(player, A.STORAGE.DEATHS) + 1)
	end
	return true
end

function A.onAdvance(player, skill, oldLevel, newLevel)
	if newLevel <= oldLevel then return true end
	checkAdvanceRewards(player, skill, newLevel)
	return true
end

function A.onExtendedOpcode(player, opcode, buffer)
	if opcode ~= A.OPCODE or type(buffer) ~= 'string' or #buffer > 512 then return false end
	local ok, request = pcall(json.decode, buffer)
	if not ok or type(request) ~= 'table' then return false end
	if request.action == 'getProgress' then
		local now, guid = os.time(), player:getGuid()
		local previous = progressRequests[guid]
		if previous and now - previous < 2 then return true end
		progressRequests[guid] = now
		if now - lastRequestCleanup >= 60 then
			lastRequestCleanup = now
			for playerGuid, timestamp in pairs(progressRequests) do
				if timestamp < now - 120 then progressRequests[playerGuid] = nil end
			end
		end
		A.sendProgress(player)
	elseif request.action == 'markSeen' then
		if storage(player, A.STORAGE.UNREAD) > 0 then player:setStorageValue(A.STORAGE.UNREAD, 0) end
		player:sendExtendedOpcode(A.OPCODE, json.encode({action='seen'}))
	else
		return false
	end
	return true
end

function A.applySpeed(player)
	-- The previous kill/death counter already persisted PvP credits and deaths.
	-- Seed those two achievements once so existing characters keep their history.
	local legacyPvPKills = storage(player, 3000)
	local legacyDeaths = storage(player, 3001)
	if legacyPvPKills > storage(player, AntigasAchievements.STORAGE.PVP_KILLS) then
		addCounterReward(player, 'pvpKills', legacyPvPKills)
	end
	if legacyDeaths > storage(player, AntigasAchievements.STORAGE.DEATHS) then
		addCounterReward(player, 'deaths', legacyDeaths)
	end
	local speed = storage(player, AntigasAchievements.STORAGE.SPEED)
	if speed > 0 then player:changeSpeed(speed) end
	A.grantPendingRewards(player)
end
