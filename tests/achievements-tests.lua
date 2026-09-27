MESSAGE_EVENT_ADVANCE = 19
SKILL_FIST, SKILL_CLUB, SKILL_SWORD, SKILL_AXE = 0, 1, 2, 3
SKILL_DISTANCE, SKILL_SHIELD, SKILL_MAGLEVEL, SKILL_LEVEL = 4, 5, 7, 8
json = {
	encode = function(value) return value end,
	decode = function() return _G.request end
}

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

request = {action='markSeen'}
AntigasAchievements.onExtendedOpcode(player, AntigasAchievements.OPCODE, '{}')
assert(player:getStorageValue(AntigasAchievements.STORAGE.UNREAD) == 0)
assert(player.sent[#player.sent].action == 'seen')
request = {action='getProgress'}
AntigasAchievements.onExtendedOpcode(player, AntigasAchievements.OPCODE, '{}')
local found = false
for _, entry in ipairs(player.sent[#player.sent].entries) do
	if entry.id == 'monsterKills_1' then found = entry.completed and entry.progress == 100 end
end
assert(found, 'achievement summary returns server-owned progress')

local legacy = makePlayer(2)
legacy.storage[3000], legacy.storage[3001] = 10, 10
AntigasAchievements.applySpeed(legacy)
assert(legacy:getStorageValue(AntigasAchievements.STORAGE.PVP_KILLS) == 10)
assert(legacy:getStorageValue(AntigasAchievements.STORAGE.PVP_DAMAGE_PERCENT) == 2)
assert(legacy:getStorageValue(AntigasAchievements.STORAGE.DEATHS) == 10)
assert(legacy:getStorageValue(AntigasAchievements.STORAGE.DEATH_REDUCTION_PERCENT) == 2)

print('PASS Achievements: persistent milestones, rewards, movement filtering, PvP and progress protocol')
