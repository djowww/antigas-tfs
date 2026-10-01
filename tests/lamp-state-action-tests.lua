local samePositionMeta = {
    __eq = function(a, b)
        return a.x == b.x and a.y == b.y and a.z == b.z
    end,
}

Position = function(x, y, z)
    return setmetatable({x = x, y = y, z = z}, samePositionMeta)
end

dofile('data/lib/lamp_states.lua')

local houseTile = false
local invited = false
local optionEnabled = true
local writes = 0
local message = nil

RETURNVALUE_CANNOTUSETHISOBJECT = 'cannot_use'
RETURNVALUE_PLAYERISNOTINVITED = 'not_invited'
RETURNVALUE_NOTPOSSIBLE = 'not_possible'
configKeys = {ONLY_INVITED_CAN_MOVE_HOUSE_ITEMS = 1}
configManager = {
    getBoolean = function(key)
        assert(key == configKeys.ONLY_INVITED_CAN_MOVE_HOUSE_ITEMS)
        return optionEnabled
    end,
}

Tile = function()
    if not houseTile then
        return nil
    end
    return {
        getHouse = function()
            return {
                isInvited = function(_, player)
                    assert(player ~= nil)
                    return invited
                end,
            }
        end,
    }
end

local originalOpen = io.open
io.open = function(path, mode)
    if path == 'data/globalevents/lib/lamp_states.lua' and mode == 'w' then
        writes = writes + 1
        return {
            write = function(self) return self end,
            close = function() return true end,
        }
    end
    return originalOpen(path, mode)
end

dofile('data/actions/scripts/others/lamp_states.lua')

local function newItem(id)
    return {
        id = id,
        transforms = 0,
        getId = function(self)
            return self.id
        end,
        transform = function(self, newId)
            self.id = newId
            self.transforms = self.transforms + 1
        end,
    }
end

local function useLamp(fromPosition, toPosition)
    message = nil
    local item = newItem(2907)
    local player = {
        sendCancelMessage = function(_, reason)
            message = reason
        end,
    }
    local result = onUse(player, item, fromPosition, nil, toPosition, false)
    return item, result
end

local housePosition = Position(100, 100, 7)
houseTile = true
invited = false
optionEnabled = true
local before = writes
local item, result = useLamp(Position(100, 100, 7), housePosition)
assert(result == true and item.transforms == 0, 'non-invited player must not toggle a house lamp')
assert(message == RETURNVALUE_PLAYERISNOTINVITED and writes == before, 'denial must happen before persistence')

invited = true
item, result = useLamp(Position(100, 100, 7), Position(100, 100, 7))
assert(result == true and item.id == 2908 and item.transforms == 1, 'invited player may toggle directly')
assert(writes == before + 1 and wallLamps['Position(100, 100, 7)'] == 2908, 'direct house use persists once')

before = writes
item, result = useLamp(Position(99, 100, 7), Position(100, 100, 7))
assert(result == true and item.transforms == 0, 'item-use action on a different house tile must be denied')
assert(message == RETURNVALUE_CANNOTUSETHISOBJECT and writes == before, 'mismatched source must not write')

invited = false
optionEnabled = false
item, result = useLamp(Position(100, 100, 7), Position(100, 100, 7))
assert(result == true and item.id == 2908 and writes == before + 1, 'disabled invitation option preserves public lamp behavior')

houseTile = true
invited = true
optionEnabled = true
wallLampStateCount = 100000
before = writes
item, result = useLamp(Position(101, 100, 7), Position(101, 100, 7))
assert(result == true and item.transforms == 0, 'new lamp state must be denied at the persistence entry limit')
assert(message == RETURNVALUE_NOTPOSSIBLE and writes == before, 'entry-limit denial must precede mutation and disk write')

item, result = useLamp(Position(100, 100, 7), Position(100, 100, 7))
assert(result == true and item.transforms == 1 and writes == before + 1, 'existing saved position remains changeable at capacity')
assert(wallLampStateCount == 100000, 'updating an existing position must not increase saved-state count')

io.open = originalOpen
print('Lamp-state action regression tests passed')
