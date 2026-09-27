-- Run from the server root with Lua 5.1/LuaJIT or Lua 5.2.
-- No database or live players are needed.
dofile('data/creaturescripts/scripts/market.lua')

local function upvalue(fn, expected)
    for index = 1, 100 do
        local name, value = debug.getupvalue(fn, index)
        if name == expected then return value end
        if not name then break end
    end
    error('Missing upvalue: ' .. expected)
end

local allowed = upvalue(onExtendedOpcode, 'allowed')
local limits = upvalue(allowed, 'limits')
local now, scans = 120, 0
local originalTime, originalPairs = os.time, pairs
os.time = function() return now end
pairs = function(value)
    if value == limits then scans = scans + 1 end
    return originalPairs(value)
end

local function player(guid)
    return {getGuid = function() return guid end}
end

for guid = 1, 100 do
    local current = player(guid)
    for request = 1, 8 do assert(allowed(current, false)) end
    assert(not allowed(current, false), 'read limit must remain eight')
    for request = 1, 3 do assert(allowed(current, true)) end
    assert(not allowed(current, true), 'write limit must remain three')
end
assert(scans == 1, '100 simultaneous players must trigger only one cleanup')

now = 121
assert(allowed(player(1), false), 'rate limit must reset next second')
assert(scans == 1, 'cleanup must wait for its interval')

now = 181 -- No request happened on the exact minute boundary.
assert(allowed(player(101), false))
assert(scans == 2, 'cleanup must work after a missed minute boundary')
assert(limits[2] == nil, 'inactive player entries must be removed')
assert(limits[1] ~= nil, 'entries at the retention boundary must remain')
assert(limits[101] ~= nil, 'the active player must remain rate limited')

os.time, pairs = originalTime, originalPairs
print('PASS: Market limits, 100-player cleanup, missed minute and retention')
