wallLamps = {}
wallLampStateCount = 0
local MAX_LAMP_STATE_ENTRIES = 100000
local MAX_LAMP_STATE_FILE_BYTES = 8 * 1024 * 1024
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
    local maxBytes = 8 * 1024 * 1024
    local maxEntries = 100000
    if type(str) ~= 'string' or #str > maxBytes then
        return nil
    end

    local body = str:match('^%s*{([%s%S]*)}%s*$')
    if not body then
        return nil
    end

    local states, cursor, count = {}, 1, 0
    while true do
        local token = body:find('%S', cursor)
        if not token then
            return states
        end

        local first, last, x, y, z, value = body:find('%["Position%((%d+), (%d+), (%d+)%)"%]%s*=%s*(%d+)', token)
        if first ~= token then
            return nil
        end

        local xValue, yValue, zValue, itemId = tonumber(x), tonumber(y), tonumber(z), tonumber(value)
        if tostring(xValue) ~= x or tostring(yValue) ~= y or tostring(zValue) ~= z or tostring(itemId) ~= value
            or xValue > 65535 or yValue > 65535 or zValue > 15
            or (not lampTransformIds[itemId] and not reverseLampTransformIds[itemId]) then
            return nil
        end

        local position = string.format('Position(%d, %d, %d)', xValue, yValue, zValue)
        if states[position] ~= nil then
            return nil
        end
        count = count + 1
        if count > maxEntries then
            return nil
        end
        states[position] = itemId

        cursor = last + 1
        local separator = body:find('%S', cursor)
        if not separator then
            return states
        end
        if body:sub(separator, separator) ~= ',' then
            return nil
        end
        cursor = separator + 1
    end
end

function serializePos(pos)
    return string.format('Position(%d, %d, %d)', pos.x, pos.y, pos.z)
end

function unserializePos(s)
    if type(s) ~= 'string' then
        return nil
    end
    local x, y, z = s:match('^Position%((%d+), (%d+), (%d+)%)$')
    if not x then
        return nil
    end
    return Position(tonumber(x), tonumber(y), tonumber(z))
end

function dumpLampStates()
	if wallLampStateCount > MAX_LAMP_STATE_ENTRIES then
		return false
	end
	local serialized, contents = pcall(serialize, wallLamps)
	if not serialized or type(contents) ~= 'string' or #contents > MAX_LAMP_STATE_FILE_BYTES then
		return false
	end
    local file = io.open('data/globalevents/lib/lamp_states.lua', 'w')
    if not file then
        return false
    end
	local writeOk, writeResult = pcall(function() return file:write(contents) end)
	local closeOk, closeResult = pcall(function() return file:close() end)
	return writeOk and writeResult ~= nil and closeOk and closeResult ~= nil
end

function canStoreLampState(position)
	local key = serializePos(position)
	return wallLamps[key] ~= nil or wallLampStateCount < MAX_LAMP_STATE_ENTRIES
end

function storeLampState(position, itemId)
	local key = serializePos(position)
	if wallLamps[key] == nil then
		if wallLampStateCount >= MAX_LAMP_STATE_ENTRIES then
			return false
		end
		wallLampStateCount = wallLampStateCount + 1
	end
	wallLamps[key] = itemId
	return dumpLampStates()
end

function loadLampStates()
	wallLamps = {}
	wallLampStateCount = 0
    local file = io.open('data/globalevents/lib/lamp_states.lua')
    if file then
        local contents = file:read(8 * 1024 * 1024 + 1)
        file:close()
        if not contents or #contents > 8 * 1024 * 1024 then
            wallLamps = {}
            return
        end
        local ok, states = pcall(unserialize, contents)
        wallLamps = ok and states or nil
        if type(wallLamps) ~= 'table' then
            wallLamps = {}
            return
        end
		wallLampStateCount = table.size(wallLamps)
        for serializedPos, state in pairs(wallLamps) do
            local searchState = reverseLampTransformIds[state] or lampTransformIds[state]
            if searchState then
                local position = unserializePos(serializedPos)
                local tile = position and Tile(position)
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
