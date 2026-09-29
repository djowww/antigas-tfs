_G.Position = function(x, y, z)
    return {x = x, y = y, z = z}
end

dofile('data/lib/lamp_states.lua')

local file = assert(io.open('data/globalevents/lib/lamp_states.lua', 'r'))
local persisted = file:read('*a')
file:close()

local states = assert(unserialize(persisted), 'the checked-in lamp state must parse')
local count = 0
for position, itemId in pairs(states) do
    assert(unserializePos(position), 'every parsed key must be a valid Position')
    assert(lampTransformIds[itemId] or reverseLampTransformIds[itemId], 'every saved ID must be a known lamp state')
    count = count + 1
end
assert(count > 0, 'the persisted fixture should exercise existing lamp states')

local encoded = serialize({
    ['Position(100, 200, 7)'] = 2908,
    ['Position(101, 201, 8)'] = 2535,
})
local roundTrip = assert(unserialize(encoded))
assert(roundTrip['Position(100, 200, 7)'] == 2908)
assert(roundTrip['Position(101, 201, 8)'] == 2535)
assert(next(assert(unserialize('{}'))) == nil, 'an empty table must remain valid')

_G.lampStateParserExecuted = false
assert(unserialize('{["Position(1, 2, 7)"] = 2908}; lampStateParserExecuted = true') == nil)
assert(not _G.lampStateParserExecuted, 'persisted text must never be executed')
assert(unserialize('{["Position(70000, 2, 7)"] = 2908}') == nil)
assert(unserialize('{["Position(1, 2, 7)"] = 1}') == nil)
assert(unserialize('{["Position(1, 2, 7)"] = 2908 ["Position(2, 3, 7)"] = 2908}') == nil)
assert(unserialize('{["Position(1, 2, 7)"] = 2908, ["Position(1, 2, 7)"] = 2909}') == nil)
assert(unserialize(string.rep(' ', 8 * 1024 * 1024 + 1)) == nil)

local tooManyEntries = {}
for index = 0, 100000 do
    tooManyEntries[#tooManyEntries + 1] = string.format(
        '[\"Position(%d, %d, 7)\"] = 2908',
        index % 65536,
        math.floor(index / 65536)
    )
end
assert(unserialize('{' .. table.concat(tooManyEntries, ', ') .. '}') == nil)

print('Lamp-state parser regression tests passed')
