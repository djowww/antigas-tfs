MESSAGE_EVENT_ADVANCE = 19

local scheduledEvents = {}
local canceledEvents = {}
local players = {}
local nextEventId = 0

Player = setmetatable({}, {
	__call = function(_, playerId)
		return players[playerId]
	end
})

function addEvent(callback, delay, ...)
	assert(delay == 60 * 60 * 1000, "bonus interval must be one hour")
	nextEventId = nextEventId + 1
	scheduledEvents[nextEventId] = {callback = callback, args = {...}}
	return nextEventId
end

function stopEvent(eventId)
	canceledEvents[eventId] = true
	scheduledEvents[eventId] = nil
	return true
end

dofile("data/lib/custom/onlineBonus.lua")
dofile("data/lib/custom/antigasBestiary.lua")

local function makePlayer(playerId, storedBonus)
	local player = {
		id = playerId,
		storage = {},
		ip = 1,
		messages = {},
		effects = 0,
		registeredEvents = {}
	}
	if storedBonus ~= nil then
		player.storage[ONLINE_STAY_BONUS_STORAGE] = storedBonus
	end
	setmetatable(player, {__index = Player})

	function player:getId()
		return self.id
	end

	function player:getIp()
		return self.ip
	end

	function player:getStorageValue(key)
		return self.storage[key] or 0
	end

	function player:setStorageValue(key, value)
		if value == -1 then
			self.storage[key] = nil
		else
			self.storage[key] = value
		end
		return true
	end

	function player:registerEvent(name)
		self.registeredEvents[name] = true
		return true
	end

	function player:getPosition()
		return {sendMagicEffect = function()
			self.effects = self.effects + 1
		end}
	end

	function player:sendTextMessage(messageType, message)
		assert(messageType == MESSAGE_EVENT_ADVANCE)
		self.messages[#self.messages + 1] = message
		return true
	end

	players[playerId] = player
	return player
end

local function popEvent()
	local eventId
	for id in pairs(scheduledEvents) do
		if not eventId or id < eventId then
			eventId = id
		end
	end
	assert(eventId, "expected an online bonus timer")
	local event = scheduledEvents[eventId]
	scheduledEvents[eventId] = nil
	return eventId, event
end

dofile("data/creaturescripts/scripts/others/onlineBonus.lua")

-- Legacy whole-percent values migrate without losing already-earned bonus.
local legacyPlayer = makePlayer(1000, 23)
assert(legacyPlayer:getOnlineStayBonusUnits() == 50, "legacy bonus was not clamped to the new 5% cap")
assert(legacyPlayer.storage[ONLINE_STAY_BONUS_STORAGE] == 1050, "legacy storage was not encoded")
local legacyCappedPlayer = makePlayer(1004, 24)
assert(legacyCappedPlayer:getOnlineStayBonusUnits() == 50, "legacy cap did not clamp to 5%")
assert(onLogin(legacyCappedPlayer) == true)
assert(next(scheduledEvents) == nil, "migrated capped player received another timer")

-- Each uninterrupted hour adds 0.2 percentage points, preserving the 5% cap.
local player = makePlayer(1001)
assert(onLogin(player) == true)
assert(player.registeredEvents.OnlineBonusLogout)
for expectedBonus = ONLINE_STAY_BONUS_STEP, ONLINE_STAY_BONUS_MAX * ONLINE_STAY_BONUS_SCALE, ONLINE_STAY_BONUS_STEP do
	local _, event = popEvent()
	event.callback(unpack(event.args))
	assert(player:getOnlineStayBonusUnits() == expectedBonus, "incorrect hourly bonus")
	assert(#player.messages == expectedBonus / ONLINE_STAY_BONUS_STEP, "missing hourly notification")
	assert(player.messages[#player.messages]:find("+" .. string.format("%.1f", expectedBonus / ONLINE_STAY_BONUS_SCALE) .. "%", 1, true))
	if expectedBonus < ONLINE_STAY_BONUS_MAX * ONLINE_STAY_BONUS_SCALE then
		assert(next(scheduledEvents) ~= nil, "timer stopped before reaching the cap")
	else
		assert(next(scheduledEvents) == nil, "timer continued after reaching the cap")
assert(OnlineBonusEvents[player.id] == nil, "timer registry was not cleared at the cap")
	end
end

-- A migrated 3% character continues from 3.0% to 3.2% after one hour.
local migratedProgressPlayer = makePlayer(1005, 3)
assert(onLogin(migratedProgressPlayer) == true)
local _, migratedEvent = popEvent()
migratedEvent.callback(unpack(migratedEvent.args))
assert(migratedProgressPlayer:getOnlineStayBonusUnits() == 32, "migrated bonus did not continue in 0.2% steps")
assert(migratedProgressPlayer.messages[1]:find("+3.2%", 1, true), "migrated total was displayed incorrectly")
assert(onLogout(migratedProgressPlayer) == true)

-- Reconnecting at the cap does not schedule another reward.
assert(onLogin(player) == true)
assert(next(scheduledEvents) == nil)

-- Logout cancels the pending timer; invoking a stale callback cannot reward.
local logoutPlayer = makePlayer(1002, 3) -- legacy +3.0%
assert(onLogin(logoutPlayer) == true)
local logoutEventId, logoutEvent = popEvent()
assert(onLogout(logoutPlayer) == true)
assert(canceledEvents[logoutEventId])
logoutEvent.callback(unpack(logoutEvent.args))
assert(logoutPlayer:getOnlineStayBonusUnits() == 30, "stale callback granted a reward after logout")

-- A callback for a disconnected player does not award or reschedule anything.
local disconnectedPlayer = makePlayer(1003, 4)
assert(onLogin(disconnectedPlayer) == true)
local _, disconnectedEvent = popEvent()
disconnectedPlayer.ip = 0
disconnectedEvent.callback(unpack(disconnectedEvent.args))
assert(disconnectedPlayer:getOnlineStayBonusUnits() == 40, "disconnected player received a reward")
assert(OnlineBonusEvents[disconnectedPlayer.id] == nil)
assert(next(scheduledEvents) == nil)

-- Load the real player callbacks with a minimal game API and verify growth.
CONDITION_SOUL = 1
CONDITIONID_DEFAULT = 1
CONDITION_PARAM_SOULGAIN = 2
CONDITION_PARAM_SOULTICKS = 3
SKILL_MAGLEVEL = 7
configKeys = {RATE_MAGIC = 1, RATE_SKILL = 2}
configManager = {getNumber = function()
	return 1
end}
Game = {getExperienceStage = function()
	return 1
end}
getGlobalStorageValue = function()
	return 0
end
Condition = function()
	return {
		setTicks = function() end,
		setParameter = function() end
	}
end
APPLY_SKILL_MULTIPLIER = true

dofile("data/events/scripts/player.lua")

local function makeGrowthPlayer(bonusUnits, completedBestiaries)
	local player = {storage = {}, analyzerExperience = 0}
	setmetatable(player, {__index = Player})

	function player:getStorageValue(key)
		return self.storage[key] or 0
	end

	function player:setStorageValue(key, value)
		if value == -1 then
			self.storage[key] = nil
		else
			self.storage[key] = value
		end
		return true
	end
	player:setOnlineStayBonusUnits(bonusUnits)
	if completedBestiaries ~= nil then
		player:setStorageValue(AntigasBestiary.COMPLETION_STORAGE, completedBestiaries)
	end

	function player:getLevel()
		return 10
	end

	function player:getSoul()
		return 100
	end

	function player:getVocation()
		return {getMaxSoul = function()
			return 100
		end}
	end

	function player:getExperience()
		return 0
	end

	function player:addAnalyzerExp(experience)
		self.analyzerExperience = experience
	end

	return player
end

local monster = {isPlayer = function()
	return false
end}
local growthPlayer = makeGrowthPlayer(50)
assert(growthPlayer:onGainExperience(monster, 100, 100) == 105, "XP bonus was not applied")
assert(growthPlayer.analyzerExperience == 105, "analyzer did not receive final XP")
assert(growthPlayer:onGainSkillTries(SKILL_MAGLEVEL, 100) == 105, "magic skill bonus was not applied")
assert(growthPlayer:onGainSkillTries(1, 100) == 105, "regular skill bonus was not applied")

-- Small fractional bonuses accumulate instead of being rounded away per event.
local fractionalPlayer = makeGrowthPlayer(2) -- +0.2%
local totalXp = 0
for _ = 1, 5 do
	totalXp = totalXp + fractionalPlayer:onGainExperience(monster, 100, 100)
end
assert(totalXp == 501, "fractional XP bonus was lost between events")

local bestiaryPlayer = makeGrowthPlayer(0, 5) -- Five completions grant +1.0% XP.
assert(bestiaryPlayer:onGainExperience(monster, 1000, 1000) == 1010, "completed bestiaries must add 0.2% XP each")

local bestiaryFractionalPlayer = makeGrowthPlayer(0, 1)
local bestiaryTotalXp = 0
for _ = 1, 5 do
	bestiaryTotalXp = bestiaryTotalXp + bestiaryFractionalPlayer:onGainExperience(monster, 100, 100)
end
assert(bestiaryTotalXp == 501, "fractional bestiary XP bonus was lost between events")

local stackedBonusPlayer = makeGrowthPlayer(50, 5)
assert(stackedBonusPlayer:onGainExperience(monster, 1000, 1000) == 1060, "online and bestiary bonuses must stack additively")

local zeroBonusPlayer = makeGrowthPlayer(0)
assert(zeroBonusPlayer:onGainExperience(monster, 100, 100) == 100, "zero XP bonus changed experience")
assert(zeroBonusPlayer:onGainSkillTries(1, 100) == 100, "zero bonus changed skill tries")

local cappedPlayer = makeGrowthPlayer(2400)
assert(cappedPlayer:getOnlineStayBonusUnits() == 50, "stored bonus was not clamped to 5%")
assert(cappedPlayer:onGainExperience(monster, 100, 100) == 105, "XP bonus exceeded the cap")
assert(cappedPlayer:onGainSkillTries(SKILL_MAGLEVEL, 100) == 105, "skill bonus exceeded the cap")

-- Script-granted skill tries receive the online bonus without reapplying rates.
local scriptedSkillPlayer = makeGrowthPlayer(2)
APPLY_SKILL_MULTIPLIER = false
local totalTries = 0
for _ = 1, 500 do
	totalTries = totalTries + scriptedSkillPlayer:onGainSkillTries(1, 1)
end
assert(totalTries == 501, "fractional online skill bonus did not accumulate for script grants")

print("PASS: legacy migration, 0.2% hourly accumulation/5% cap, logout safety, fractional XP and skill carries, standard and scripted skill bonuses")
