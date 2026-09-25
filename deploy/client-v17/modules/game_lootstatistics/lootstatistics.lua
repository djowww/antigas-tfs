local window
local loot = {}
local supplies = {}
local validIds
local syncingButton = false
local MAX_ITEMS = 250
local MAX_COUNT = 2000000000

-- Read only the server's three-field array. Never evaluate serialized Lua.
function decodeEntry(buffer)
  if type(buffer) ~= 'string' or #buffer > 512 then return end
  local name, count, id = buffer:match('^%{%s*"([^"\\\r\n]+)"%s*,%s*(%d+)%s*,%s*(%d+)%s*%}$')
  if not name then
    -- The live serializer writes explicit numeric keys, unlike the compact
    -- array used by older notifications. Accept only these exact three keys.
    name, count, id = buffer:match('^%{%s*%[1%]%s*=%s*"([^"\\\r\n]+)"%s*,%s*%[2%]%s*=%s*(%d+)%s*,%s*%[3%]%s*=%s*(%d+)%s*%}$')
  end
  if not name then return end
  count, id = tonumber(count), tonumber(id)
  if #name > 80 or not count or count < 1 or count > MAX_COUNT or not id or id < 1 or id > 65535 then return end
  return name, count, id
end

local function render(list, entries)
  if not validIds and g_things.isDatLoaded() then
    validIds = {}
    for _,thing in pairs(g_things.getThingTypes(ThingCategoryItem)) do validIds[thing:getId()] = true end
  end
  list:destroyChildren()
  local ordered = {}
  for _,entry in pairs(entries) do ordered[#ordered+1] = entry end
  table.sort(ordered, function(a,b) return a.name < b.name end)
  for _,entry in ipairs(ordered) do
    local row = g_ui.createWidget('AntigasLootRow', list)
    if validIds and validIds[entry.id] then row.icon:setItemId(entry.id) else row.icon:hide() end
    row.description:setText(entry.count .. ' x ' .. entry.name)
  end
end

local function receive(entries, list, buffer)
  local name, count, id = decodeEntry(buffer)
  if not name then return end
  if not entries[id] then
    local n = 0
    for _ in pairs(entries) do n = n + 1 end
    if n >= MAX_ITEMS then return end
    entries[id] = {name = name, id = id, count = 0}
  end
  entries[id].count = math.min(MAX_COUNT, entries[id].count + count)
  if window:isVisible() then render(list, entries) end
end

function onLoot(protocol, opcode, buffer)
  if window then receive(loot, window.lootList, buffer) end
end

function onSupply(protocol, opcode, buffer)
  if window then receive(supplies, window.supplyList, buffer) end
end

function reset()
  loot, supplies = {}, {}
  validIds = nil
  if window then
    window.lootList:destroyChildren()
    window.supplyList:destroyChildren()
  end
end

function hide()
  if window then window:hide() end
  local bars = modules.game_playerbars
  if bars and bars.lootButton then
    syncingButton = true
    bars.lootButton:setChecked(false)
    syncingButton = false
  end
end

function offline()
  hide()
  reset()
end

function toggle()
  if syncingButton or not window or not g_game.isOnline() then return end
  if window:isVisible() then hide() return end
  render(window.lootList, loot)
  render(window.supplyList, supplies)
  window:show()
  window:raise()
  window:focus()
  local bars = modules.game_playerbars
  if bars and bars.lootButton then
    syncingButton = true
    bars.lootButton:setChecked(true)
    syncingButton = false
  end
end

function init()
  window = g_ui.displayUI('lootstatistics')
  window:hide()
  -- The legacy dispatcher unserializes Lua by default; our bounded parser
  -- requires the untouched wire string instead.
  ProtocolGame.registerExtendedOpcode(122, onLoot, true)
  ProtocolGame.registerExtendedOpcode(123, onSupply, true)
  connect(g_game, {onGameStart = reset, onGameEnd = offline})
end

function terminate()
  disconnect(g_game, {onGameStart = reset, onGameEnd = offline})
  ProtocolGame.unregisterExtendedOpcode(122)
  ProtocolGame.unregisterExtendedOpcode(123)
  if window then window:destroy() window = nil end
  loot, supplies = {}, {}
end
