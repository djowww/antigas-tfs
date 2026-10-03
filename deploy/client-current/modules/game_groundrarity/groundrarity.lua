-- Tile snapshots arrive directly after the native map update they describe.
-- Bind immediately to actual Item objects; sprite IDs alone are not identity.
local OPCODE, MAX_TILES, CHECK_MS = 129, 256, 150
local fallbackTints = {'#BDD3C3', '#B9CADD', '#CCBFDA', '#DED1AB', '#DBBAB5'}
local tiles, tileCount, sequence = {}, 0, 0
local checkEvent, helloEvent, ready, helloAttempts, lastSnapshotRequest

local function colorize(mark, now, force)
  local visuals = modules.game_rarityvisuals
  local color = visuals and visuals.getWorldTint
    and visuals.getWorldTint(mark.tier, now or g_clock.millis(), mark.seed, 'ground')
    or fallbackTints[mark.tier]
  if force or color ~= mark.lastColor then
    g_map.colorizeThing(mark.item, color)
    mark.lastColor = color
  end
end

local function itemSeed(position, itemId, stackpos)
  -- Stable for this snapshot's native object; nearby items breathe out of phase.
  return (position.x * 31 + position.y * 131 + position.z * 17 + itemId * 7 + stackpos * 53) % 65521
end

local function integer(value, minimum, maximum)
  return type(value) == 'number' and value == math.floor(value) and value >= minimum and value <= maximum
end

local function positionKey(pos)
  return pos.x .. ',' .. pos.y .. ',' .. pos.z
end

local function samePosition(a, b)
  return a and b and a.x == b.x and a.y == b.y and a.z == b.z
end

local function validPosition(pos)
  return type(pos) == 'table' and integer(pos.x, 1, 65534) and integer(pos.y, 1, 65534)
    and integer(pos.z, 0, 15)
end

local function containsItem(tile, entry, position)
  if not tile or not samePosition(entry.item:getPosition(), position) or entry.item:getId() ~= entry.itemId then
    return false
  end
  for _, thing in ipairs(tile:getThings()) do
    if thing == entry.item then return true end
  end
  return false
end

local function clearMark(entry)
  -- Native sprite color and cursor/corpse marks are separate render layers.
  g_map.removeThingColor(entry.item)
  entry.lastColor = nil
end

local function removeTile(key)
  local entry = tiles[key]
  if not entry then return end
  tiles[key], tileCount = nil, tileCount - 1
  for _, item in ipairs(entry.items) do clearMark(item) end
end

local function clearTiles()
  if checkEvent then removeEvent(checkEvent); checkEvent = nil end
  for key in pairs(tiles) do removeTile(key) end
  tiles, tileCount, sequence = {}, 0, 0
end

local function requestSnapshot()
  if not ready or not g_game.isOnline() then return end
  local now = g_clock.millis()
  if lastSnapshotRequest and now - lastSnapshotRequest < 5000 then return end
  local protocol = g_game.getProtocolGame()
  if protocol and g_game.getFeature(GameExtendedOpcode) then
    lastSnapshotRequest = now
    protocol:sendExtendedOpcode(OPCODE, 'S|1')
  end
end

-- The sprite keeps its rarity color independently of cursor highlight marks.
function restoreMark(item)
  local pos = item and item:getPosition()
  local entry = pos and tiles[positionKey(pos)]
  if not entry then return false end
  local tile = g_map.getTile(entry.position)
  for _, mark in ipairs(entry.items) do
    if mark.item == item and containsItem(tile, mark, entry.position) then
      -- A different render owner may have cleared the color since the last tick.
      colorize(mark, g_clock.millis(), true)
      return true
    end
  end
  return false
end

function updateMarks()
  if checkEvent then removeEvent(checkEvent); checkEvent = nil end
  if not ready or not g_game.isOnline() then return end
  local now = g_clock.millis()
  local missingNativeItem = false
  for key, entry in pairs(tiles) do
    local tile = g_map.getTile(entry.position)
    for index = #entry.items, 1, -1 do
      local mark = entry.items[index]
      if not containsItem(tile, mark, entry.position) then
        table.remove(entry.items, index)
        clearMark(mark)
        missingNativeItem = true
      else
        colorize(mark, now)
      end
    end
    if #entry.items == 0 then removeTile(key) end
  end
  if missingNativeItem then requestSnapshot() end
  -- One timer for the whole viewport, regardless of the number of rare items.
  if tileCount > 0 then checkEvent = scheduleEvent(updateMarks, CHECK_MS) end
end

local function validSnapshot(data)
  if not integer(data.seq, 1, 9007199254740991) or not validPosition(data.position)
      or type(data.items) ~= 'table' or #data.items > 10 then return false end
  local stacks = {}
  for index, item in pairs(data.items) do
    if not integer(index, 1, #data.items) or type(item) ~= 'table'
        or not integer(item.itemId, 1, 65535) or not integer(item.stackpos, 0, 9)
        or not integer(item.tier, 1, 5) or stacks[item.stackpos] then return false end
    stacks[item.stackpos] = true
  end
  return true
end

local function applySnapshot(data)
  if data.seq <= sequence then return end
  sequence = data.seq
  local key = positionKey(data.position)
  removeTile(key)
  if #data.items == 0 then return end
  local tile = g_map.getTile(data.position)
  if not tile then return end
  local entry = {position=data.position, items={}, seq=data.seq}
  for _, record in ipairs(data.items) do
    local item = tile:getThing(record.stackpos)
    if item and item:isItem() and item:getId() == record.itemId
        and samePosition(item:getPosition(), data.position) then
      entry.items[#entry.items+1] = {item=item, itemId=record.itemId, tier=record.tier,
        seed=itemSeed(data.position, record.itemId, record.stackpos)}
    end
  end
  if #entry.items == 0 then return end
  if tileCount >= MAX_TILES then
    local oldestKey, oldestSequence
    for candidate, current in pairs(tiles) do
      if not oldestSequence or current.seq < oldestSequence then oldestKey, oldestSequence = candidate, current.seq end
    end
    removeTile(oldestKey)
  end
  tiles[key], tileCount = entry, tileCount + 1
  for _, mark in ipairs(entry.items) do
    colorize(mark)
  end
  if not checkEvent then checkEvent = scheduleEvent(updateMarks, CHECK_MS) end
end

function onOpcode(protocol, opcode, buffer)
  if opcode ~= OPCODE or not g_game.isOnline() or protocol ~= g_game.getProtocolGame()
      or type(buffer) ~= 'string' or #buffer > 4096 then return end
  local ok, data = NetworkData.decode(buffer)
  if not ok or type(data) ~= 'table' then return end
  if data.event == 'ready' and data.version == 1 then
    if not integer(data.seq, 1, 9007199254740991) or data.seq <= sequence then return end
    sequence = data.seq
    ready = true
    if helloEvent then removeEvent(helloEvent); helloEvent = nil end
    return
  end
  if not ready then return end
  if data.event == 'reset' then
    if not integer(data.seq, 1, 9007199254740991) or data.seq <= sequence then return end
    clearTiles()
    sequence = data.seq
  elseif data.event == 'tile' and validSnapshot(data) then
    applySnapshot(data)
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
  clearTiles()
  if helloEvent then removeEvent(helloEvent); helloEvent = nil end
  ready, helloAttempts, lastSnapshotRequest = false, 0, nil
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
