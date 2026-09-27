-- Read-only quest journal. Clients may never choose a player or storage key.
local OPCODE, PAGE_SIZE = 125, 35
local catalog = dofile('data/lib/custom/questCatalog.lua')
local journal = dofile('data/lib/custom/questJournal.lua')
local byId, requests, lastCleanup = {}, {}, 0
for _, quest in ipairs(catalog) do
    assert(not byId[quest.id], 'Duplicate quest id: ' .. quest.id)
    byId[quest.id] = quest
end

local function progress(player, quest, details)
    local done, known, allDone, steps, previous = 0, 0, 0, {}, {}
    local notes = journal[quest.id] or {}
    for index, rule in ipairs(quest.steps) do
        local value = math.max(0, player:getStorageValue(rule.key))
        local completed = value >= rule.target
        if completed then allDone = allDone + 1 end
        -- A shared storage is a state machine, not a counter for every mission.
        -- E.g. Ape City 6 completes the third task; task four begins at 7.
        local discovered = value >= (previous[rule.key] or 0) + 1
        previous[rule.key] = rule.target
        for _, trigger in ipairs((notes.discover or {})[index] or {}) do
            discovered = discovered or player:getStorageValue(trigger[1]) >= trigger[2]
        end
        if discovered then
            known = known + 1
            if completed then done = done + 1 end
            if details then
                steps[#steps+1] = {name=quest.kind == 'chest' and 'A discovery on my travels' or rule.name,
                    current=completed and 1 or 0, target=1, completed=completed}
            end
        end
    end
    -- Completion still follows the original rules, including access scrolls.
    local completed = allDone == #quest.steps
    if #quest.complete > 0 then
        completed = true
        for _, rule in ipairs(quest.complete) do
            if player:getStorageValue(rule[1]) < rule[2] then completed = false end
        end
    end
    if known == 0 then return nil end
    local result = {id=quest.id, name=quest.name:gsub(' %[%d+%]$', ''), region=quest.region, kind=quest.kind,
        status=completed and 'completed' or 'active', done=done, total=known}
    if details then
        result.description = notes.text or 'I have recorded a discovery from my travels. The rest of the world remains for me to explore.'
        result.rewards, result.steps = '', steps
        if quest.kind == 'chest' then
            if quest.id == 'chest-203' then
                result.description = 'My passage through the Annihilator trial is recorded. These notes do not tell which reward, if any, I took.'
            elseif (quest.rewards or ''):find(' / ',1,true) then
                result.description = 'A reward at this place is recorded in my journal. My notes do not identify which of the choices I took.'
            else
                result.rewards = quest.rewards or ''
            end
        end
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
        local matches, completed, discovered = {}, 0, 0
        for _, quest in ipairs(catalog) do
            local row = progress(player,quest,false)
            if row then
                discovered = discovered+1
                if row.status == 'completed' then completed = completed+1 end
                if (filter == 'all' or row.status == filter) and
                    (query == '' or (row.name .. ' ' .. row.region):lower():find(query,1,true)) then
                    matches[#matches+1] = row
                end
            end
        end
        local pages = math.max(1,math.ceil(#matches/PAGE_SIZE))
        page = math.min(page,pages)
        local entries = {}
        for i=(page-1)*PAGE_SIZE+1,math.min(page*PAGE_SIZE,#matches) do entries[#entries+1]=matches[i] end
        response = {action='list',requestId=serial,entries=entries,page=page,pages=pages,
            matched=#matches,total=discovered,completed=completed}
    elseif request.action == 'detail' then
        if type(request.id) ~= 'string' or #request.id > 64 or not byId[request.id] then return false end
        local quest = progress(player,byId[request.id],true)
        -- Guessing a valid catalog ID must not reveal an undiscovered quest.
        response = {action='detail',requestId=serial,quest=quest,unavailable=not quest or nil}
    else
        return false
    end
    response.journal = 2
    local encoded = json.encode(response)
    if #encoded <= 48000 then player:sendExtendedOpcode(OPCODE,encoded) end
    return true
end
