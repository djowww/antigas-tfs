local responses = {}
local queries = {}
local events = {}
local messages = {}
local resultHandles = {}
local executions = {}
local actorAccess = true
local targetOnline = true
local targetIp = 0x01020304
local targetAccess = false
local groupAccess = {[1] = false, [2] = false, [3] = true}
local insertSucceeds = true
local cleanupSucceeds = true
local escapeSucceeds = true
local targetRemoved = false

ACCOUNT_TYPE_NORMAL = 1
ACCOUNT_TYPE_TUTOR = 2
ACCOUNT_TYPE_SENIORTUTOR = 3
ACCOUNT_TYPE_GAMEMASTER = 4
ACCOUNT_TYPE_GOD = 5

result = {
    getDataLong = function(handle, key)
        return handle.rows[handle.index][key]
    end,
    getDataInt = function(handle, key)
        return handle.rows[handle.index][key]
    end,
    next = function(handle)
        if handle.index >= #handle.rows then
            return false
        end
        handle.index = handle.index + 1
        return true
    end,
    free = function(handle)
        assert(not handle.freed, 'a query result must only be freed once')
        handle.freed = true
        table.insert(events, 'free')
    end,
}

local function makeGroup(access)
    return {getAccess = function() return access end}
end

local actor = {
    getGroup = function() return makeGroup(actorAccess) end,
    sendCancelMessage = function(_, message) table.insert(messages, message) end,
    getGuid = function() return 777 end,
}

local onlineTarget = {
    getGroup = function() return makeGroup(targetAccess) end,
    getIp = function() return targetIp end,
    remove = function()
        targetRemoved = true
        table.insert(events, 'remove')
    end,
}

Group = function(groupId)
    local access = groupAccess[groupId]
    if access == nil then
        return nil
    end
    return makeGroup(access)
end

Player = function(name)
    if name == 'Target' and targetOnline then
        return onlineTarget
    end
    return nil
end

db = {
    escapeString = function(value)
        if not escapeSucceeds then
            return nil
        end
        return "'" .. value .. "'"
    end,
    storeQueryChecked = function(query)
        table.insert(queries, query)
        table.insert(events, 'select')
        local response = table.remove(responses, 1)
        assert(response, 'unexpected database query: ' .. query)
        if not response.success then
            return response.result or false, false
        end
        if not response.rows or #response.rows == 0 then
            return false, true
        end
        local handle = {rows = response.rows, index = 1, freed = false}
        table.insert(resultHandles, handle)
        return handle, true
    end,
    query = function(query)
		table.insert(executions, query)
		if string.find(query, 'DELETE FROM `ip_bans`', 1, true) == 1 then
			table.insert(events, 'cleanup')
			return cleanupSucceeds
		end
		table.insert(events, 'insert')
        return insertSucceeds
    end,
}

dofile('data/talkactions/scripts/ipban.lua')

local function reset(options)
    options = options or {}
    targetIp = options.targetIp or 0x01020304
    responses = options.responses or {
        {success = true, rows = {{lastip = targetIp, group_id = 1, account_id = 42, account_type = ACCOUNT_TYPE_NORMAL}}},
        {success = true, rows = {{group_id = 1}}},
        {success = true, rows = {}},
    }
	queries, executions, events, messages, resultHandles = {}, {}, {}, {}, {}
    actorAccess = options.actorAccess ~= false
    targetOnline = options.targetOnline ~= false
    targetAccess = options.targetAccess == true
    groupAccess = options.groupAccess or {[1] = false, [2] = false, [3] = true}
    insertSucceeds = options.insertSucceeds ~= false
	cleanupSucceeds = options.cleanupSucceeds ~= false
    escapeSucceeds = options.escapeSucceeds ~= false
    targetRemoved = false
end

local function callOnSay()
    return onSay(actor, '/ipban', 'Target')
end

local function assertFreed(count)
    assert(#resultHandles == count, 'unexpected number of query-result handles')
    for _, handle in ipairs(resultHandles) do
        assert(handle.freed, 'query result leaked on an early-return path')
    end
end

reset({actorAccess = false})
assert(callOnSay() == true and #queries == 0, 'non-staff caller must be denied before any query')

reset({responses = {{success = false}}})
assert(callOnSay() == false and #queries == 1 and not targetRemoved, 'target lookup failure must fail closed')
assertFreed(0)

reset({responses = {{success = true, rows = {}}}})
assert(callOnSay() == false and #queries == 1 and not targetRemoved, 'missing target must be denied')
assertFreed(0)

reset({targetAccess = true})
assert(callOnSay() == false and #queries == 1 and not targetRemoved, 'online staff target must be denied')
assertFreed(1)

reset({
    targetOnline = false,
    groupAccess = {[1] = false},
    responses = {
        {success = true, rows = {{lastip = targetIp, group_id = 99, account_id = 42, account_type = ACCOUNT_TYPE_NORMAL}}},
    },
})
assert(callOnSay() == false and #queries == 1 and not targetRemoved, 'unknown target group must fail closed')
assertFreed(1)

reset({
    targetOnline = false,
    responses = {
        {success = true, rows = {{lastip = targetIp, group_id = 1, account_id = 42, account_type = ACCOUNT_TYPE_NORMAL}}},
        {success = true, rows = {{group_id = 1}, {group_id = 3}}},
    },
})
assert(callOnSay() == false and #queries == 2 and not targetRemoved, 'staff alt on the same account must block IP ban')
assertFreed(2)

reset({
    targetOnline = false,
    groupAccess = {[1] = false},
    responses = {
        {success = true, rows = {{lastip = targetIp, group_id = 1, account_id = 42, account_type = ACCOUNT_TYPE_NORMAL}}},
        {success = true, rows = {{group_id = 99}}},
    },
})
assert(callOnSay() == false and #queries == 2 and not targetRemoved, 'unknown group in account roster must fail closed')
assertFreed(2)

reset({
    targetOnline = false,
    responses = {
        {success = true, rows = {{lastip = targetIp, group_id = 1, account_id = 42, account_type = ACCOUNT_TYPE_NORMAL}}},
        {success = false},
    },
})
assert(callOnSay() == false and #queries == 2 and not targetRemoved, 'account roster query failure must block IP ban')
assertFreed(1)

reset({
    targetOnline = false,
    responses = {
        {success = true, rows = {{lastip = targetIp, group_id = 1, account_id = 42, account_type = ACCOUNT_TYPE_TUTOR}}},
    },
})
assert(callOnSay() == false and #queries == 1 and not targetRemoved, 'staff account type must be denied')
assertFreed(1)

reset({
    responses = {
        {success = true, rows = {{lastip = targetIp, group_id = 1, account_id = 42, account_type = 99}}},
    },
})
assert(callOnSay() == false and #queries == 1 and not targetRemoved, 'invalid account type must fail closed')
assertFreed(1)

reset({
    responses = {
        {success = true, rows = {{lastip = targetIp, group_id = 1, account_id = 0, account_type = ACCOUNT_TYPE_NORMAL}}},
    },
})
assert(callOnSay() == false and #queries == 1 and not targetRemoved, 'missing account id must fail closed')
assertFreed(1)

reset({
    responses = {
        {success = true, rows = {{lastip = targetIp, group_id = 1, account_id = 42, account_type = ACCOUNT_TYPE_NORMAL}}},
        {success = true, rows = {}},
    },
})
assert(callOnSay() == false and #queries == 2 and not targetRemoved, 'empty account roster must fail closed')
assertFreed(1)

reset({
    responses = {
        {success = true, rows = {{lastip = targetIp, group_id = 1, account_id = 42, account_type = ACCOUNT_TYPE_NORMAL}}},
        {success = true, rows = {{group_id = 1}}},
        {success = false},
    },
})
assert(callOnSay() == false and #queries == 3 and not targetRemoved, 'existing-IP lookup failure must block insert and kick')
assertFreed(2)

reset({
    responses = {
        {success = true, rows = {{lastip = targetIp, group_id = 1, account_id = 42, account_type = ACCOUNT_TYPE_NORMAL}}},
        {success = true, rows = {{group_id = 1}}},
        {success = true, rows = {{ip = targetIp}}},
    },
})
assert(callOnSay() == false and #queries == 3 and not targetRemoved, 'an already-banned IP must not insert or kick')
assertFreed(3)

reset({insertSucceeds = false})
assert(callOnSay() == false and not targetRemoved, 'failed insert must not remove online target')
assertFreed(2)
assert(events[#events] == 'insert', 'failed insert must not be followed by a kick')

reset({cleanupSucceeds = false})
assert(callOnSay() == false and not targetRemoved, 'failed expired-ban cleanup must block the IP ban')
assert(#executions == 1 and string.find(executions[1], '`expires_at` != 0 AND `expires_at` <= ', 1, true), 'expired-ban cleanup must only remove finite bans that have expired')
assertFreed(2)

reset({targetIp = 0})
assert(callOnSay() == false and not targetRemoved, 'zero IP must not be banned')
assertFreed(2)

reset()
assert(callOnSay() == false and targetRemoved, 'valid IP ban should remove an online target after persistence')
assertFreed(2)
assert(string.find(executions[1], 'DELETE FROM `ip_bans`', 1, true) == 1, 'expired bans must be cleaned before the duplicate lookup')
assert(string.find(executions[1], '`expires_at` != 0 AND `expires_at` <= ', 1, true), 'cleanup must preserve permanent and unexpired bans')
assert(string.find(executions[2], 'INSERT INTO `ip_bans`', 1, true) == 1, 'new ban must be inserted after duplicate lookup')
local cleanupIndex, duplicateLookupIndex, insertIndex, removeIndex
for index, event in ipairs(events) do
	if event == 'cleanup' then cleanupIndex = index end
	if event == 'select' then duplicateLookupIndex = index end
    if event == 'insert' then insertIndex = index end
    if event == 'remove' then removeIndex = index end
end
assert(cleanupIndex and duplicateLookupIndex and insertIndex and removeIndex and cleanupIndex < duplicateLookupIndex and duplicateLookupIndex < insertIndex and insertIndex < removeIndex, 'expired cleanup, duplicate lookup, insert, and target removal must occur in order')

reset({targetOnline = false})
assert(callOnSay() == false and not targetRemoved, 'valid offline target should be banned without an online removal')
assertFreed(2)

reset({escapeSucceeds = false})
local ok = pcall(callOnSay)
assert(not ok and #queries == 0 and not targetRemoved, 'escape failure must not reach any query or remove target')

print('IP-ban authorization and persistence regression tests passed')
