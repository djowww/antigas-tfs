wallLamps = {}
lampTransformIds, reverseLampTransformIds = { -- used for direct access to flip ids
    [2907] = 2908,
    [2909] = 2910,
    [2928] = 2929,
    [2930] = 2931,
	[2536] = 2535,
	[2538] = 2537,
	[2540] = 2539,
	[2542] = 2541,
 }, {}

for k, v in pairs(lampTransformIds) do
    reverseLampTransformIds[v] = k
end

function table.size(t)
    local size = 0
    for k, v in pairs(t) do
        size = size + 1
    end
    return size
end

function serialize(s)
    local isTable = type(s) == 'table'
    local ret = {(isTable and "{" or nil)}
    local function doSerialize(s)
        if isTable then
            local size = table.size(s)
            local index = 0
            for k, v in pairs(s) do
                index = index + 1
                local key = (type(k) == 'string') and '"'..k..'"' or k
                local val = (type(v) == 'string') and '"'..v..'"' or v
                local comma = ((index < size) and ', ' or '')
                if type(v) == 'table' then
                    ret[#ret+1] = ('[%s] = {'):format(key)
                    doSerialize(v)
                    ret[#ret+1] = ('}%s'):format(comma)
                else
                    ret[#ret+1] = ('[%s] = %s%s'):format(key, val, comma)
                end
            end
        else
            ret[#ret+1] = s
        end
    end
    doSerialize(s)
    return (table.concat(ret) .. (isTable and "}" or ""))
end

function unserialize(str)
    local f = loadstring("return ".. str)
    return f and f() or nil
end

function serializePos(pos)
    return string.format('Position(%d, %d, %d)', pos.x, pos.y, pos.z)
end

function unserializePos(s)
    return Position(s:match("Position%((%d+), (%d+), (%d+)%)"))
end

function dumpLampStates()
    local file = io.open('data/globalevents/lib/lamp_states.lua', 'w')
    if file then
        file:write(serialize(wallLamps))
        file:close()
    end
end

function loadLampStates()
    local file = io.open('data/globalevents/lib/lamp_states.lua')
    if file then
        local contents = file:read('*a')
        file:close()
        local ok, states = pcall(unserialize, contents)
        wallLamps = ok and states or nil
        if type(wallLamps) ~= 'table' then
            wallLamps = {}
            return
        end
        for serializedPos, state in pairs(wallLamps) do
            local searchState = reverseLampTransformIds[state] or lampTransformIds[state]
            if searchState then
                local position = unserializePos(serializedPos)
                local tile = Tile(position)
                local lamp = tile and tile:getItemById(searchState)
                if lamp then
                    lamp:transform(state)
                end
            end
        end
    else
        local newFile = io.open('data/globalevents/lib/lamp_states.lua', 'w')
        if newFile then
            newFile:close()
        end
    end
end
