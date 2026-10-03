-- Only server-confirmed corpse tokens may create or clear an unopened marker.
local OPCODE, CHANNEL = 128, 10
local MAX_MARKERS, MAX_SEEN, PULSE_MS = 256, 512, 150
local fallbackTints = {[0]='#CCBCA7', '#BDD3C3', '#B9CADD', '#CCBFDA', '#DED1AB', '#DBBAB5'}
local fallbackTextColors = {'#86C39A', '#87AFD4', '#B59ACD', '#D9BE7B', '#D38B83'}
local neutral = '#C8CED8'
local markers, seen, seenOrder = {}, {}, {}
local pulseEvent, helloEvent, ready, helloAttempts

local function integer(value, minimum, maximum)
  return type(value) == 'number' and value == math.floor(value) and value >= minimum and value <= maximum
end

local function cleanName(value, maximum)
  if type(value) ~= 'string' or #value == 0 or #value > maximum * 2 or value:find('[%z\1-\31\127]') then return false end
  -- The server converts legacy Latin-1 names to UTF-8 JSON (up to two bytes).
  local _, characters = value:gsub('[^\128-\191]', '')
  return characters <= maximum
end

local function validId(id)
  return type(id) == 'string' and #id > 0 and #id <= 32 and id:match('^%d+$')
end

local function samePosition(a, b)
  return a and b and a.x == b.x and a.y == b.y and a.z == b.z
end

local function validPosition(pos)
  return type(pos) == 'table' and integer(pos.x, 1, 65534) and integer(pos.y, 1, 65534) and integer(pos.z, 0, 15)
end

local function clearMark(entry)
  if entry.item then
    -- Sprite tint and cursor setMarked are independent native layers.
    g_map.removeThingColor(entry.item)
    local ground = modules.game_groundrarity
    if ground and ground.restoreMark then ground.restoreMark(entry.item) end
  end
  entry.item = nil
  entry.lastColor = nil
end

local function removeMarker(id)
  local entry = markers[id]
  if entry then clearMark(entry); markers[id] = nil end
end

local function containsItem(entry)
  if not entry.item or not samePosition(entry.item:getPosition(), entry.position) then return false end
  local tile = g_map.getTile(entry.position)
  if not tile then return false end
  -- A corpse can change stack position when another corpse lands on the tile.
  -- Native identity, rather than sprite ID, protects two identical corpses.
  for _, thing in ipairs(tile:getThings()) do
    if thing == entry.item then return thing:getId() == entry.corpseId end
  end
  return false
end

local function resolveItem(entry)
  local tile = g_map.getTile(entry.position)
  local item = tile and tile:getThing(entry.stackpos)
  if not item or not item:isItem() or item:getId() ~= entry.corpseId then return false end
  for _, existing in pairs(markers) do
    if existing ~= entry and existing.item == item then return false end
  end
  entry.item = item
  return true
end

local function markerSeed(data)
  local seed = (data.position.x * 31 + data.position.y * 131
    + data.position.z * 17 + data.corpseId * 7 + data.stackpos * 53) % 65521
  for index = 1, #data.id do seed = (seed * 33 + data.id:byte(index)) % 65521 end
  return seed
end

local function colorize(entry, now, force)
  local visuals = modules.game_rarityvisuals
  local color = visuals and visuals.getWorldTint
    and visuals.getWorldTint(entry.tier, now, entry.seed, 'corpse')
    or fallbackTints[entry.tier]
  if force or color ~= entry.lastColor then
    g_map.colorizeThing(entry.item, color)
    entry.lastColor = color
  end
end

function restoreMark(item)
  for _, entry in pairs(markers) do
    if entry.item == item and containsItem(entry) then
      colorize(entry, g_clock.millis(), true)
      return true
    end
  end
  return false
end

function updateMarkers()
  if pulseEvent then removeEvent(pulseEvent) end
  pulseEvent = nil
  if not ready or not g_game.isOnline() then return end
  local now = g_clock.millis()
  local player = g_game.getLocalPlayer()
  local playerPos = player and player:getPosition()
  for id, entry in pairs(markers) do
    if now - entry.created > 1800000 or not playerPos or playerPos.z ~= entry.position.z then
      removeMarker(id)
    elseif entry.item and not containsItem(entry) then
      -- Never bind a replacement with the same sprite without a new server marker.
      removeMarker(id)
    elseif entry.item then
      colorize(entry, now)
    elseif now - entry.created > 2000 then
      removeMarker(id)
    end
  end
  if next(markers) then pulseEvent = scheduleEvent(updateMarkers, PULSE_MS) end
end

local function remember(id)
  if seen[id] then return false end
  seen[id] = true
  seenOrder[#seenOrder + 1] = id
  if #seenOrder > MAX_SEEN then seen[table.remove(seenOrder, 1)] = nil end
  return true
end

local function addMarker(data)
  local existing = markers[data.id]
  if existing and samePosition(existing.position, data.position) and existing.corpseId == data.corpseId
      and containsItem(existing) then
    existing.tier = data.tier
    return
  end
  removeMarker(data.id)
  local count, oldestId, oldest = 0, nil, math.huge
  for id, entry in pairs(markers) do
    count = count + 1
    if entry.created < oldest then oldest, oldestId = entry.created, id end
  end
  if count >= MAX_MARKERS then removeMarker(oldestId) end
  markers[data.id] = {position=data.position, corpseId=data.corpseId, stackpos=data.stackpos,
    tier=data.tier, seed=markerSeed(data), created=g_clock.millis()}
  -- Bind while this server snapshot is current. A later pulse could see a new
  -- identical corpse at the old stack index. Missing items await server replay.
  resolveItem(markers[data.id])
  if not pulseEvent then updateMarkers() end
end

local function validMarker(data, allowOffscreen)
  return validId(data.id) and validPosition(data.position) and integer(data.corpseId, 1, 65535)
    and integer(data.stackpos, allowOffscreen and -1 or 0, 255) and integer(data.tier, 0, 5)
end

local function validLoot(data)
  if not validMarker(data, data.unopened == false) or type(data.unopened) ~= 'boolean'
      or not cleanName(data.name, 80) or type(data.items) ~= 'table' or #data.items > 128 then return false end
  if data.omitted ~= nil and not integer(data.omitted, 0, 65535) then return false end
  for key, item in pairs(data.items) do
    if not integer(key, 1, #data.items) or type(item) ~= 'table' or not integer(item.id, 1, 65535)
        or not cleanName(item.name, 160) or not integer(item.count, 1, 65535) or not integer(item.tier, 0, 5) then
      return false
    end
  end
  return true
end

local function showLoot(data)
  local console = modules.game_console
  local tab = console.getChannelTab(CHANNEL)
  -- The server owns this channel. If the player closed it, keep it closed.
  if not tab then return end
  local rich, plain = {}, {}
  local function append(text, color)
    rich[#rich+1], rich[#rich+2] = text, color
    plain[#plain+1] = text
  end
  append('Loot of ' .. data.name .. ': ', neutral)
  if #data.items == 0 then append('nothing', neutral) end
  for index, item in ipairs(data.items) do
    if index > 1 then append(', ', neutral) end
    local visuals = modules.game_rarityvisuals
    local color = item.tier > 0 and visuals and visuals.getTextColor and visuals.getTextColor(item.tier)
      or fallbackTextColors[item.tier] or neutral
    append(item.name, color)
  end
  if data.omitted and data.omitted > 0 then append(', ... +' .. data.omitted .. ' itens', neutral) end
  console.addTabText(table.concat(plain), {color=neutral}, tab, nil, rich)
end

function onOpcode(protocol, opcode, buffer)
  if opcode ~= OPCODE or not g_game.isOnline() or protocol ~= g_game.getProtocolGame()
      or type(buffer) ~= 'string' or #buffer > 8192 then return end
  local ok, data = NetworkData.decode(buffer)
  if not ok or type(data) ~= 'table' then return end
  if data.event == 'ready' and data.version == 1 then
    ready = true
    if helloEvent then removeEvent(helloEvent); helloEvent = nil end
    return
  end
  if not ready then return end
  if data.event == 'opened' or data.event == 'removed' then
    if validId(data.id) then removeMarker(data.id) end
  elseif data.event == 'marker' then
    if validMarker(data, false) then addMarker(data) end
  elseif data.event == 'loot' and validLoot(data) and remember(data.id) then
    showLoot(data)
    if data.unopened then addMarker(data) end
    -- Native effect/text packets are sent once by the server to each visible
    -- recipient; marker replay never retriggers the drop animation.
  end
end

local function sendHello()
  helloEvent = nil
  if ready or not g_game.isOnline() or helloAttempts >= 12 then return end
  helloAttempts = helloAttempts + 1
  local protocol = g_game.getProtocolGame()
  if protocol and g_game.getFeature(GameExtendedOpcode) then protocol:sendExtendedOpcode(OPCODE, 'H|1') end
  if not ready then helloEvent = scheduleEvent(sendHello, 250) end
end

function reset()
  if pulseEvent then removeEvent(pulseEvent); pulseEvent = nil end
  if helloEvent then removeEvent(helloEvent); helloEvent = nil end
  for _, entry in pairs(markers) do clearMark(entry) end
  markers, seen, seenOrder, ready, helloAttempts = {}, {}, {}, false, 0
end

function online()
  reset()
  helloEvent = scheduleEvent(sendHello, 250)
end

function init()
  reset()
  ProtocolGame.registerExtendedOpcode(OPCODE, onOpcode, true)
  connect(g_game, {onGameStart=online, onGameEnd=reset})
  if g_game.isOnline() then online() end
end

function terminate()
  reset()
  disconnect(g_game, {onGameStart=online, onGameEnd=reset})
  ProtocolGame.unregisterExtendedOpcode(OPCODE)
end
