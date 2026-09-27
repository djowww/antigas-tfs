-- Read-only quest journal. Clients may never choose a player or storage key.
local OPCODE, PAGE_SIZE = 125, 35
local catalog = dofile('data/lib/custom/questCatalog.lua')
local byId, requests, lastCleanup = {}, {}, 0
for _, quest in ipairs(catalog) do
    assert(not byId[quest.id], 'Duplicate quest id: ' .. quest.id)
    byId[quest.id] = quest
end

local function progress(player, quest, details)
    local done, started, steps = 0, false, {}
    for _, rule in ipairs(quest.steps) do
        local value = math.max(0, player:getStorageValue(rule.key))
        local completed = value >= rule.target
        if completed then done = done + 1 end
        if value > 0 then started = true end
        if details then
            steps[#steps+1] = {name=rule.name, current=math.min(value,rule.target),
                target=rule.target, completed=completed}
        end
    end
    local completed = done == #quest.steps
    if #quest.complete > 0 then
        completed = true
        for _, rule in ipairs(quest.complete) do
            if player:getStorageValue(rule[1]) < rule[2] then completed = false end
        end
    end
    local result = {id=quest.id, name=quest.name, region=quest.region, kind=quest.kind,
        status=completed and 'completed' or (started and 'active' or 'unstarted'),
        done=done, total=#quest.steps}
    if details then
        result.description, result.rewards, result.steps = quest.description, quest.rewards or '', steps
    end
    return result
end

local function allowed(player)
    local now, guid = os.time(), player:getGuid()
    local state = requests[guid]
    if not state then state = {tokens=4,time=now}; requests[guid] = state end
    state.tokens = math.min(4,state.tokens+math.max(0,now-state.time))
    state.time = now
    if now-lastCleanup >= 60 then
        lastCleanup = now
        for key, entry in pairs(requests) do
            if now-entry.time > 120 then requests[key] = nil end
        end
    end
    if state.tokens < 1 then return false end
    state.tokens = state.tokens-1
    return true
end

function onExtendedOpcode(player, opcode, buffer)
    if opcode ~= OPCODE or type(buffer) ~= 'string' or #buffer > 512 then return false end
    if not allowed(player) then return false end
    local ok, request = pcall(json.decode, buffer)
    if not ok or type(request) ~= 'table' then return false end
    local fields = {action=true,requestId=true,page=true,query=true,filter=true,id=true}
    for field in pairs(request) do if not fields[field] then return false end end
    local serial = request.requestId
    if type(serial) ~= 'number' or serial ~= math.floor(serial) or serial < 1 or serial > 1000000000 then return false end
    local response
    if request.action == 'list' then
        local query, filter, page = request.query or '', request.filter or 'all', request.page or 1
        if type(query) ~= 'string' or #query > 48 or query:find('[%c]') then return false end
        if filter ~= 'all' and filter ~= 'active' and filter ~= 'completed' and filter ~= 'unstarted' then return false end
        if type(page) ~= 'number' or page ~= math.floor(page) or page < 1 or page > 1000 then return false end
        query = query:lower()
        local matches, completed = {}, 0
        for _, quest in ipairs(catalog) do
            local row = progress(player,quest,false)
            if row.status == 'completed' then completed = completed+1 end
            if (filter == 'all' or row.status == filter) and
                (query == '' or (quest.name .. ' ' .. quest.region):lower():find(query,1,true)) then
                matches[#matches+1] = row
            end
        end
        local pages = math.max(1,math.ceil(#matches/PAGE_SIZE))
        page = math.min(page,pages)
        local entries = {}
        for i=(page-1)*PAGE_SIZE+1,math.min(page*PAGE_SIZE,#matches) do entries[#entries+1]=matches[i] end
        response = {action='list',requestId=serial,entries=entries,page=page,pages=pages,
            matched=#matches,total=#catalog,completed=completed}
    elseif request.action == 'detail' then
        if type(request.id) ~= 'string' or #request.id > 64 or not byId[request.id] then return false end
        response = {action='detail',requestId=serial,quest=progress(player,byId[request.id],true)}
    else
        return false
    end
    local encoded = json.encode(response)
    if #encoded <= 48000 then player:sendExtendedOpcode(OPCODE,encoded) end
    return true
end
