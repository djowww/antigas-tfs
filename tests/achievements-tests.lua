MESSAGE_EVENT_ADVANCE = 19
SKILL_FIST, SKILL_CLUB, SKILL_SWORD, SKILL_AXE = 0, 1, 2, 3
SKILL_DISTANCE, SKILL_SHIELD, SKILL_MAGLEVEL, SKILL_LEVEL = 4, 5, 7, 8
dofile('data/lib/core/json.lua')

local realTime, now = os.time, 1000
os.time = function() return now end

dofile('data/lib/custom/antigasAchievements.lua')

local function makePlayer(guid)
	local player = {guid=guid, storage={}, messages={}, sent={}, items={}, speed=0, level=1, skills={}, itemAttempts=0}
	function player:isPlayer() return true end
	function player:isCreature() return true end
	function player:getId() return self.guid + 1000 end
	function player:getGuid() return self.guid end
	function player:getStorageValue(key) return self.storage[key] or -1 end
	function player:setStorageValue(key, value) self.storage[key] = value end
	function player:sendTextMessage(kind, message)
		assert(kind == MESSAGE_EVENT_ADVANCE)
		if self.onMessage then self.onMessage(message) end
		self.messages[#self.messages + 1] = message
	end
	function player:sendExtendedOpcode(opcode, payload)
		assert(opcode == AntigasAchievements.OPCODE)
		assert(type(payload) == 'string', 'wire payloads must use the real JSON encoder')
		assert(#payload <= 7000 and #payload <= 8192, 'payload must fit NetworkMessage.addString')
		self.sent[#self.sent + 1] = payload
	end
	function player:changeSpeed(value) self.speed = self.speed + value end
	function player:addItem(itemId, count, canDropOnMap)
		assert(canDropOnMap == false, 'achievement items may never drop on the map')
		self.itemAttempts = self.itemAttempts + 1
		if self.inventoryFull or self.availableSlots == 0 then return nil end
		if self.availableSlots then self.availableSlots = self.availableSlots - 1 end
		self.items[#self.items + 1] = {id=itemId, count=count}
		return self.items[#self.items]
	end
	function player:getPosition() return self.position end
	function player:getLevel() return self.level end
	function player:getMagicLevel() return self.skills[SKILL_MAGLEVEL] or 0 end
	function player:getSkillLevel(skill) return self.skills[skill] or 0 end
	return player
end

local function readSnapshot(subject)
	assert(#subject.sent == 5, 'one operation must emit exactly one five-page snapshot')
	local entries, snapshotId = {}, nil
	for page, encoded in ipairs(subject.sent) do
		local payload = json.decode(encoded)
		assert(payload.page == page and payload.pages == 5)
		snapshotId = snapshotId or payload.snapshotId
		assert(payload.snapshotId == snapshotId, 'all pages belong to the committed operation')
		for _, entry in ipairs(payload.entries) do entries[entry.id] = entry end
	end
	return entries
end

local function request(subject, action)
	return AntigasAchievements.onExtendedOpcode(subject, AntigasAchievements.OPCODE, json.encode({action=action}))
end

local player = makePlayer(1)
local rat = {isCreature=function() return true end, isPlayer=function() return false end,
	isMonster=function() return true end, getMaster=function() return nil end}
for _ = 1, 100 do AntigasAchievements.onKill(player, rat) end
assert(player:getStorageValue(AntigasAchievements.STORAGE.MONSTER_KILLS) == 100)
assert(player:getStorageValue(AntigasAchievements.STORAGE.ATTACK_PERCENT) == 1)

local opponent = {isCreature=function() return true end, isPlayer=function() return true end, getId=function() return 2000 end}
AntigasAchievements.onKill(player, opponent)
assert(player:getStorageValue(AntigasAchievements.STORAGE.PVP_DAMAGE_PERCENT) == 1)
local pvpMessages, pvpPackets = #player.messages, #player.sent
AntigasAchievements.onKill(player, player)
AntigasAchievements.onKill(player, {isCreature=function() return true end, isPlayer=function() return true end,
	getId=function() return player:getId() end})
assert(player:getStorageValue(AntigasAchievements.STORAGE.PVP_KILLS) == 1,
	'self-inflicted deaths cannot count as PvP kills, including separate wrappers for the same creature')
assert(#player.messages == pvpMessages and #player.sent == pvpPackets)
AntigasAchievements.onDeath(player)
assert(player:getStorageValue(AntigasAchievements.STORAGE.DEATH_REDUCTION_PERCENT) == 1)

AntigasAchievements.onAdvance(player, SKILL_LEVEL, 19, 20)
assert(player.items[1].id == 5291, 'level milestones award the existing XP scroll')
AntigasAchievements.onAdvance(player, SKILL_SWORD, 39, 40)
assert(player.items[2].id == 5141, 'sword skill milestone awards a sword training weapon')
AntigasAchievements.onAdvance(player, SKILL_LEVEL, 19, 20)
AntigasAchievements.onAdvance(player, SKILL_SWORD, 39, 40)
assert(#player.items == 2, 'already claimed level and skill rewards cannot be duplicated')

local previous = {x=1,y=1,z=7}
for step = 1, 100 do
	local destination = {x=step+1,y=1,z=7}
	AntigasAchievements.onWalk(player, previous, destination)
	previous = destination
end
assert(player:getStorageValue(AntigasAchievements.STORAGE.STEPS) == 100)
assert(player:getStorageValue(AntigasAchievements.STORAGE.SPEED) == 1)
assert(player.speed == 1)

AntigasAchievements.onWalk(player, previous, {x=1000,y=1,z=7}) -- Teleports are ignored.
AntigasAchievements.onWalk(player, {x=1000,y=1,z=7}, {x=1001,y=1,z=7})
assert(player:getStorageValue(AntigasAchievements.STORAGE.STEPS) == 101)

AntigasAchievements.onExtendedOpcode(player, AntigasAchievements.OPCODE, json.encode({action='markSeen'}))
assert(player:getStorageValue(AntigasAchievements.STORAGE.UNREAD) == 0)
assert(json.decode(player.sent[#player.sent]).action == 'seen')
player.sent = {}
AntigasAchievements.onExtendedOpcode(player, AntigasAchievements.OPCODE, json.encode({action='getProgress', steps=1000000}))
local found = false
for _, encoded in ipairs(player.sent) do
	for _, entry in ipairs(json.decode(encoded).entries) do
		if entry.id == 'monsterKills_1' then found = entry.completed and entry.progress == 100 end
	end
end
assert(found, 'achievement summary returns server-owned progress')
assert(player:getStorageValue(AntigasAchievements.STORAGE.STEPS) == 101, 'client cannot set progress')
local sentCount = #player.sent
AntigasAchievements.onExtendedOpcode(player, AntigasAchievements.OPCODE, json.encode({action='getProgress'}))
assert(#player.sent == sentCount, 'repeated queries are throttled')
assert(not AntigasAchievements.onExtendedOpcode(player, AntigasAchievements.OPCODE, '{invalid'))
assert(not AntigasAchievements.onExtendedOpcode(player, AntigasAchievements.OPCODE, string.rep('a', 513)))
assert(not AntigasAchievements.onExtendedOpcode(player, 125, '{}'))

local legacy = makePlayer(2)
legacy.storage[3000], legacy.storage[3001] = 10, 10
AntigasAchievements.applySpeed(legacy)
assert(legacy:getStorageValue(AntigasAchievements.STORAGE.PVP_KILLS) == 10)
assert(legacy:getStorageValue(AntigasAchievements.STORAGE.PVP_DAMAGE_PERCENT) == 2)
assert(legacy:getStorageValue(AntigasAchievements.STORAGE.DEATHS) == 10)
assert(legacy:getStorageValue(AntigasAchievements.STORAGE.DEATH_REDUCTION_PERCENT) == 2)
assert(#legacy.sent == 5, 'multiple legacy rewards are batched into one snapshot at login')
local messageCount = #legacy.messages
AntigasAchievements.applySpeed(legacy)
assert(#legacy.messages == messageCount, 'legacy migrations only award each milestone once')
assert(#legacy.sent == 5, 'a login without new rewards does not send redundant snapshots')

-- Reading a high-level character must not create, grant or retry any reward.
local qualified = makePlayer(10)
qualified.level = 200
for _, skill in ipairs({0,1,2,3,4,5,7}) do qualified.skills[skill] = 120 end
assert(request(qualified, 'getProgress'))
local reading = readSnapshot(qualified)
assert(qualified.itemAttempts == 0 and next(qualified.storage) == nil)
assert(not reading.level_5.completed and not reading.level_5.ready)
assert(request(qualified, 'claimRewards'))
assert(qualified.itemAttempts == 0 and #qualified.sent == 5, 'reads and claims share the same cooldown')

-- A retrospective grant settles every storage before the sole final snapshot.
qualified.sent = {}
qualified.onMessage = function(message)
	if not message:find('Achievement completed:', 1, true) then return end
	local paid = 0
	for key, value in pairs(qualified.storage) do
		if key > AntigasAchievements.STORAGE.LEVEL_REWARD_BASE and value == 1 then paid = paid + 1 end
	end
	assert(paid == #qualified.items, 'completion notifications follow the delivered reward storage commit')
end
now = now + 2
assert(request(qualified, 'claimRewards'))
local granted = readSnapshot(qualified)
assert(#qualified.items == 40 and qualified.itemAttempts == 40, 'all level and skill rewards are granted once')
assert(qualified:getStorageValue(AntigasAchievements.STORAGE.UNREAD) == 40)
assert(granted.level_5.completed and not granted.level_5.ready and granted.skill_7_5.completed)
assert(request(qualified, 'getProgress'))
assert(#qualified.sent == 5 and qualified.itemAttempts == 40, 'a claim also throttles subsequent reads')
now = now + 2
qualified.sent = {}
assert(request(qualified, 'claimRewards'))
readSnapshot(qualified)
assert(#qualified.items == 40 and qualified.itemAttempts == 40, 'repeated claims acknowledge state without duplicating items')

-- A full inventory records entitlement, including when several thresholds are
-- crossed together, without notifying payment or leaving anything on the map.
local blocked = makePlayer(11)
blocked.level, blocked.skills[SKILL_SWORD], blocked.inventoryFull = 50, 60, true
AntigasAchievements.onAdvance(blocked, SKILL_LEVEL, 19, 50)
local pending = readSnapshot(blocked)
assert(pending.level_1.ready and pending.level_2.ready and not pending.level_1.completed)
assert(blocked.storage[AntigasAchievements.STORAGE.LEVEL_REWARD_BASE + 1] == 2)
blocked.sent = {}
AntigasAchievements.onAdvance(blocked, SKILL_SWORD, 39, 60)
pending = readSnapshot(blocked)
assert(pending.skill_2_1.ready and pending.skill_2_2.ready and #blocked.items == 0)
assert(blocked:getStorageValue(AntigasAchievements.STORAGE.UNREAD) < 1, 'undelivered rewards are not announced as completed')
blocked.sent = {}
assert(request(blocked, 'claimRewards'))
pending = readSnapshot(blocked)
assert(pending.level_1.ready and pending.skill_2_2.ready, 'a claim that still cannot fit returns the full pending snapshot')
local blockedAttempts = blocked.itemAttempts
blocked.sent = {}
assert(request(blocked, 'claimRewards') and #blocked.sent == 0 and blocked.itemAttempts == blockedAttempts)
now = now + 2
assert(request(blocked, 'getProgress'))
assert(blocked.itemAttempts == blockedAttempts, 'getProgress never retries pending deliveries')
readSnapshot(blocked)

-- Recreate a login from persisted storage after losing both level and skill.
local restored = makePlayer(12)
for key,value in pairs(blocked.storage) do restored.storage[key]=value end
restored.level, restored.skills[SKILL_SWORD], restored.availableSlots = 10, 20, 1
AntigasAchievements.applySpeed(restored)
local partial = readSnapshot(restored)
assert(#restored.items == 1 and restored.items[1].id == 5291)
assert(partial.level_1.completed and not partial.level_1.ready and partial.level_1.progress == partial.level_1.target)
assert(partial.level_2.ready and partial.level_2.progress == partial.level_2.target)
assert(partial.skill_2_1.ready and partial.skill_2_1.progress == partial.skill_2_1.target)
assert(not partial.level_3.ready, 'lost levels cannot qualify new milestones')
restored.availableSlots, restored.sent = 3, {}
assert(request(restored, 'claimRewards'))
local retried = readSnapshot(restored)
assert(#restored.items == 4 and retried.level_2.completed and retried.skill_2_2.completed)
assert(not retried.level_2.ready and not retried.skill_2_2.ready)
now = now + 2
restored.sent = {}
assert(request(restored, 'claimRewards'))
readSnapshot(restored)
assert(#restored.items == 4, 'reclaimed persisted rewards remain idempotent')

local previousSnapshotId, largestPacket = 0, 0
local function verifyCatalog(subject, expectedCompleted)
	subject.sent = {}
	assert(AntigasAchievements.sendProgress(subject))
	assert(#subject.sent == 5, 'all 60 achievements are sent in five bounded pages')
	local entries, ids, snapshotId = {}, {}, nil
	for page, encoded in ipairs(subject.sent) do
		assert(#encoded <= AntigasAchievements.MAX_PACKET_BYTES and #encoded <= 8192)
		largestPacket = math.max(largestPacket, #encoded)
		local payload = json.decode(encoded)
		assert(payload.action == 'progress' and payload.page == page and payload.pages == #subject.sent)
		assert(#payload.entries == 12, 'each page carries at most twelve entries')
		assert(type(payload.snapshotId) == 'number' and payload.snapshotId > previousSnapshotId)
		snapshotId = snapshotId or payload.snapshotId
		assert(payload.snapshotId == snapshotId, 'a response must use one coherent snapshot')
		assert(payload.unread == math.max(0, subject:getStorageValue(AntigasAchievements.STORAGE.UNREAD)))
		assert(payload.bonuses.speed == math.max(0, subject:getStorageValue(AntigasAchievements.STORAGE.SPEED)))
		for _, entry in ipairs(payload.entries) do
			assert(not ids[entry.id], 'pages cannot duplicate achievements')
			ids[entry.id] = true
			entries[#entries + 1] = entry
			assert(entry.completed == expectedCompleted)
			assert(entry.ready == false, 'initial and paid catalogs have no pending reward flags')
			assert(entry.progress >= 0 and entry.progress <= entry.target)
		end
	end
	assert(#entries == 60 and ids.steps_1 and ids.monsterKills_5 and ids.level_5 and ids.skill_7_5)
	previousSnapshotId = snapshotId
	-- This reproduces the old regression: even a new character's complete
	-- catalog exceeds the engine's 8192-byte string limit when sent at once.
	assert(#json.encode({action='progress', entries=entries}) > 8192)
end

verifyCatalog(makePlayer(3), false)
local maximum = makePlayer(4)
maximum.level = 2147483647
for _, key in pairs(AntigasAchievements.STORAGE) do maximum.storage[key] = 2147483647 end
for index = 1, 5 do maximum.storage[AntigasAchievements.STORAGE.LEVEL_REWARD_BASE + index] = 1 end
for _, skill in ipairs({SKILL_FIST, SKILL_CLUB, SKILL_SWORD, SKILL_AXE, SKILL_DISTANCE, SKILL_SHIELD, SKILL_MAGLEVEL}) do
	maximum.skills[skill] = 2147483647
	for index = 1, 5 do maximum.storage[AntigasAchievements.STORAGE.SKILL_REWARD_BASE + skill * 8 + index] = 1 end
end
verifyCatalog(maximum, true)

local packetLimit = AntigasAchievements.MAX_PACKET_BYTES
AntigasAchievements.MAX_PACKET_BYTES = 1
maximum.sent = {}
assert(not AntigasAchievements.sendProgress(maximum) and #maximum.sent == 0,
	'an oversized future page cannot send truncated packets or a partial snapshot')
AntigasAchievements.MAX_PACKET_BYTES = packetLimit
os.time = realTime

print(string.format('PASS Achievements: inventory-safe persistent rewards, retry after level loss, pure reads, batched claims, cooldown, movement, PvP and real JSON catalogs (largest packet: %d bytes)', largestPacket))
