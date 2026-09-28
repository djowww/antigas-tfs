MESSAGE_EVENT_ADVANCE = 19
SKILL_FIST, SKILL_CLUB, SKILL_SWORD, SKILL_AXE = 0, 1, 2, 3
SKILL_DISTANCE, SKILL_SHIELD, SKILL_MAGLEVEL, SKILL_LEVEL = 4, 5, 7, 8
dofile('data/lib/core/json.lua')

dofile('data/lib/custom/antigasAchievements.lua')

local function makePlayer(guid)
	local player = {guid=guid, storage={}, messages={}, sent={}, items={}, speed=0, level=1, skills={}}
	function player:isPlayer() return true end
	function player:getGuid() return self.guid end
	function player:getStorageValue(key) return self.storage[key] or -1 end
	function player:setStorageValue(key, value) self.storage[key] = value end
	function player:sendTextMessage(kind, message)
		assert(kind == MESSAGE_EVENT_ADVANCE)
		self.messages[#self.messages + 1] = message
	end
	function player:sendExtendedOpcode(opcode, payload)
		assert(opcode == AntigasAchievements.OPCODE)
		assert(type(payload) == 'string', 'wire payloads must use the real JSON encoder')
		assert(#payload <= 7000 and #payload <= 8192, 'payload must fit NetworkMessage.addString')
		self.sent[#self.sent + 1] = payload
	end
	function player:changeSpeed(value) self.speed = self.speed + value end
	function player:addItem(itemId, count)
		self.items[#self.items + 1] = {id=itemId, count=count}
		return self.items[#self.items]
	end
	function player:getPosition() return self.position end
	function player:getLevel() return self.level end
	function player:getMagicLevel() return self.skills[SKILL_MAGLEVEL] or 0 end
	function player:getSkillLevel(skill) return self.skills[skill] or 0 end
	return player
end

local player = makePlayer(1)
local rat = {isCreature=function() return true end, isPlayer=function() return false end,
	isMonster=function() return true end, getMaster=function() return nil end}
for _ = 1, 100 do AntigasAchievements.onKill(player, rat) end
assert(player:getStorageValue(AntigasAchievements.STORAGE.MONSTER_KILLS) == 100)
assert(player:getStorageValue(AntigasAchievements.STORAGE.ATTACK_PERCENT) == 1)

local opponent = {isCreature=function() return true end, isPlayer=function() return true end}
AntigasAchievements.onKill(player, opponent)
assert(player:getStorageValue(AntigasAchievements.STORAGE.PVP_DAMAGE_PERCENT) == 1)
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
local messageCount = #legacy.messages
AntigasAchievements.applySpeed(legacy)
assert(#legacy.messages == messageCount, 'legacy migrations only award each milestone once')

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

print(string.format('PASS Achievements: rewards, idempotence, movement, PvP, real JSON and 60-entry paginated catalogs (largest packet: %d bytes)', largestPacket))
