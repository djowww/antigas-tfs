ACCOUNT_TYPE_NORMAL = 1
ACCOUNT_TYPE_TUTOR = 2
ACCOUNT_TYPE_SENIORTUTOR = 3
ACCOUNT_TYPE_GAMEMASTER = 4
ACCOUNT_TYPE_GOD = 5
MESSAGE_EVENT_ADVANCE = 1

local queryCount = 0
local lastQuery = ""
local lastSetType = nil
local setTypeResult = true
local resultFreed = false
local sentMessages = {}
local cancelMessages = {}

db = {
	escapeString = function(value)
		return "'" .. value .. "'"
	end,
	storeQuery = function(query)
		lastQuery = query
		return 41
	end,
	query = function(query)
		queryCount = queryCount + 1
		lastQuery = query
		return true
	end
}

result = {
	getDataInt = function(_, field)
		if field == "account_type" then return ACCOUNT_TYPE_TUTOR end
		if field == "account_id" then return 7001 end
		return 0
	end,
	getDataString = function()
		return "Offline Tutor"
	end,
	free = function()
		resultFreed = true
	end
}

Player = function()
	return nil
end

local admin = {
	getAccountType = function()
		return ACCOUNT_TYPE_GOD
	end,
	sendCancelMessage = function(_, message)
		cancelMessages[#cancelMessages + 1] = message
	end,
	sendTextMessage = function(_, _, message)
		sentMessages[#sentMessages + 1] = message
	end
}

dofile("data/talkactions/scripts/remove_tutor.lua")

local function onlineAccountPlayer(accountId)
	return {
		getAccountId = function()
			return accountId
		end,
		setAccountType = function(_, accountType)
			lastSetType = accountType
			return setTypeResult
		end
	}
end

local otherCharacter = onlineAccountPlayer(7001)
Game = {getPlayers = function() return {otherCharacter} end}
assert(onSay(admin, "/removetutor", "Offline Tutor") == false)
assert(lastSetType == ACCOUNT_TYPE_NORMAL, "same-account online character must use persistent session-aware setter")
assert(queryCount == 0, "must not bypass session-aware setter with direct SQL")
assert(resultFreed, "query result must be released on success")
assert(#cancelMessages == 0 and #sentMessages == 1, "successful demotion should report success")

lastSetType = nil
setTypeResult = false
resultFreed = false
sentMessages = {}
cancelMessages = {}
Game = {getPlayers = function() return {onlineAccountPlayer(7001)} end}
assert(onSay(admin, "/removetutor", "Offline Tutor") == false)
assert(lastSetType == ACCOUNT_TYPE_NORMAL, "session-aware setter must be attempted")
assert(queryCount == 0, "failed session-aware setter must not fall back to direct SQL")
assert(resultFreed, "query result must be released after setter failure")
assert(#cancelMessages == 1 and #sentMessages == 0, "failed persistence must not report success")

setTypeResult = true
resultFreed = false
sentMessages = {}
cancelMessages = {}
Game = {getPlayers = function() return {onlineAccountPlayer(9002)} end}
assert(onSay(admin, "/removetutor", "Offline Tutor") == false)
assert(queryCount == 1, "no online session for the account should use direct SQL")
assert(lastQuery:find("WHERE `id` = 7001", 1, true), "fallback update must remain scoped to the target account ID")
assert(resultFreed and #cancelMessages == 0 and #sentMessages == 1, "offline account update should report success")

print("PASS: offline tutor demotion synchronizes another same-account session and fails closed.")
