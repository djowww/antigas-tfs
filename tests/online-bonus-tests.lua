ONLINE_STAY_BONUS_STORAGE = 17592
ONLINE_STAY_BONUS_MAX = 24
MESSAGE_EVENT_ADVANCE = 19

local scheduledEvents = {}
local canceledEvents = {}
local players = {}
local nextEventId = 0

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

function Player(playerId)
	return players[playerId]
end

local function makePlayer(playerId, bonus)
	local player = {
		id = playerId,
		bonus = bonus,
		ip = 1,
		messages = {},
		effects = 0,
		registeredEvents = {}
	}

	function player:getId()
		return self.id
	end

	function player:getIp()
		return self.ip
	end

	function player:getStorageValue(key)
		assert(key == ONLINE_STAY_BONUS_STORAGE, "unexpected storage key")
		return self.bonus or -1
	end

	function player:setStorageValue(key, value)
		assert(key == ONLINE_STAY_BONUS_STORAGE, "unexpected storage key")
		self.bonus = value
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

-- One uninterrupted session grants exactly one percentage point per hour,
-- persists the accumulated value, and stops scheduling at the 24% cap.
local player = makePlayer(1001, nil)
assert(onLogin(player) == true)
assert(player.registeredEvents.OnlineBonusLogout)

for expectedBonus = 1, ONLINE_STAY_BONUS_MAX do
	local _, event = popEvent()
	event.callback(unpack(event.args))
	assert(player.bonus == expectedBonus, "incorrect hourly bonus")
	assert(#player.messages == expectedBonus, "missing hourly notification")
	assert(player.messages[#player.messages]:find("+" .. expectedBonus .. "%", 1, true))
	if expectedBonus < ONLINE_STAY_BONUS_MAX then
		assert(next(scheduledEvents) ~= nil, "timer stopped before reaching the cap")
	else
		assert(next(scheduledEvents) == nil, "timer continued after reaching the cap")
		assert(OnlineBonusEvents[player.id] == nil, "timer registry was not cleared at the cap")
	end
end

-- Reconnecting at the cap does not schedule another reward.
assert(onLogin(player) == true)
assert(next(scheduledEvents) == nil)

-- Logout cancels the pending timer; invoking a stale callback cannot reward.
local logoutPlayer = makePlayer(1002, 3)
assert(onLogin(logoutPlayer) == true)
local logoutEventId, logoutEvent = popEvent()
assert(onLogout(logoutPlayer) == true)
assert(canceledEvents[logoutEventId])
logoutEvent.callback(unpack(logoutEvent.args))
assert(logoutPlayer.bonus == 3, "stale callback granted a reward after logout")

-- A callback for a disconnected player does not award or reschedule anything.
local disconnectedPlayer = makePlayer(1003, 4)
assert(onLogin(disconnectedPlayer) == true)
local _, disconnectedEvent = popEvent()
disconnectedPlayer.ip = 0
disconnectedEvent.callback(unpack(disconnectedEvent.args))
assert(disconnectedPlayer.bonus == 4, "disconnected player received a reward")
assert(OnlineBonusEvents[disconnectedPlayer.id] == nil)
assert(next(scheduledEvents) == nil)

-- Load the real player callbacks with a minimal game API and verify their
-- actual XP, magic skill, and regular skill multipliers.
Player = {}
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

local function makeGrowthPlayer(bonus)
	local player = {bonus = bonus, analyzerExperience = 0}
	setmetatable(player, {__index = Player})

	function player:getStorageValue(key)
		if key == ONLINE_STAY_BONUS_STORAGE then
			return self.bonus or -1
		end
		return -1
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
local growthPlayer = makeGrowthPlayer(24)
assert(growthPlayer:onGainExperience(monster, 100, 100) == 124, "XP bonus was not applied")
assert(growthPlayer.analyzerExperience == 124, "analyzer did not receive final XP")
assert(growthPlayer:onGainSkillTries(SKILL_MAGLEVEL, 100) == 124, "magic skill bonus was not applied")
assert(growthPlayer:onGainSkillTries(1, 100) == 124, "regular skill bonus was not applied")

growthPlayer.bonus = 0
assert(growthPlayer:onGainExperience(monster, 100, 100) == 100, "zero XP bonus changed experience")
assert(growthPlayer:onGainSkillTries(1, 100) == 100, "zero bonus changed skill tries")

growthPlayer.bonus = 100
assert(growthPlayer:onGainExperience(monster, 100, 100) == 124, "XP bonus exceeded the cap")
assert(growthPlayer:onGainSkillTries(SKILL_MAGLEVEL, 100) == 124, "skill bonus exceeded the cap")

growthPlayer.bonus = 24
APPLY_SKILL_MULTIPLIER = false
assert(growthPlayer:onGainSkillTries(1, 100) == 100, "manual skill additions were unexpectedly multiplied")

print("PASS: hourly accumulation/cap, login at cap, logout cancellation, disconnected callback, XP, magic skill, regular skill, analyzer value, and manual skill bypass")
