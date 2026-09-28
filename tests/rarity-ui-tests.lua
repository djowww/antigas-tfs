-- Offline protocol integration. Loads the actual client modules in separate
-- sandboxes and passes their requests through the actual server opcode script.
local checks = 0
local function check(value, message)
  assert(value, message)
  checks = checks + 1
end
local function loadSandbox(path, env)
  setmetatable(env, {__index = _G})
  local chunk
  if setfenv then
    chunk = assert(loadfile(path))
    setfenv(chunk, env)
  else
    chunk = assert(loadfile(path, 't', env))
  end
  chunk()
  return env
end
local function getUpvalue(fn, name)
  for i = 1, 100 do
    local key, value = debug.getupvalue(fn, i)
    if key == name then return value end
    if not key then break end
  end
  error('Missing callback ' .. name)
end
local function item(tier, bonusType, value, subtype)
  return {
    getTooltip = function() return 'Original item description' end,
    getRarityInfo = function() return tier, bonusType, value, subtype end
  }
end
local function widget(heldItem)
  return {
    item = heldItem,
    getItem = function(self) return self.item end,
    setItem = function(self, value) self.item = value end,
    setBorderWidth = function(self, value) self.borderWidth = value end,
    setBorderColor = function(self, value) self.borderColor = value end,
    setColor = function(self, value) self.color = value end,
    setTooltip = function(self, value) self.tooltip = value end,
    isVirtual = function() return false end,
    setStyle = function() end,
    destroy = function(self) self.destroyed = true end
  }
end
local function panel(children)
  return {getChildById = function(_, id) return children[id] end}
end

local requests, responses, openContainers, serverContainers, equipment = {}, {}, {}, {}, {}
local protocol = {sendExtendedOpcode = function(_, opcode, payload)
  check(opcode == 127, 'Dedicated opcode')
  requests[#requests + 1] = payload
end}
local online, feature = true, true
local globals = {
  tr = function(s) return s end,
  GameExtendedOpcode = 1,
  InventorySlotFirst = 1, InventorySlotLast = 10,
  PlayerStates = setmetatable({}, {__index = function(t, k) t[k] = k; return k end}),
  modules = {},
  g_game = {
    isOnline = function() return online end,
    getFeature = function() return feature end,
    getProtocolGame = function() return protocol end,
    getContainers = function() return openContainers end
  }
}
for slot, name in ipairs({'Head', 'Neck', 'Back', 'Body', 'Right', 'Left', 'Leg', 'Feet', 'Finger', 'Ammo'}) do
  globals['InventorySlot' .. name] = slot
end
setmetatable(globals, {__index = _G})
local function clientSandbox(path)
  local env = setmetatable({}, {__index = globals})
  local chunk = setfenv and assert(loadfile(path)) or assert(loadfile(path, 't', env))
  if setfenv then setfenv(chunk, env) end
  chunk()
  return env
end
local inventory = clientSandbox('../../Cliente/modules/game_inventory/inventory.lua')
globals.modules.game_inventory = inventory
local rarity = inventory.AntigasItemRarity
local callback = getUpvalue(inventory.init, 'onItemRarityOpcode')
local invWidgets = {}
for i = 1, 10 do invWidgets['slot' .. i] = widget() end
inventory.inventoryPanel = panel(invWidgets)
local containerModule = clientSandbox('../../Cliente/modules/game_containers/containers.lua')
globals.UIItem = {}
globals.g_mouse = {popCursor = function() end}
clientSandbox('../../Cliente/modules/gamelib/ui/uiitem.lua')
local server = loadSandbox('data/creaturescripts/scripts/rarity.lua', {CONST_SLOT_HEAD = 1, CONST_SLOT_AMMO = 10})
local player = {
  getSlotItem = function(_, slot) return equipment[slot] end,
  getContainerById = function(_, id) return serverContainers[id] end,
  sendExtendedOpcode = function(_, opcode, payload)
    check(opcode == 127, 'Server opcode')
    responses[#responses + 1] = payload
  end
}
local function sendRequests()
  local outgoing = requests
  requests = {}
  for _, request in ipairs(outgoing) do server.onExtendedOpcode(player, 127, request) end
end
local function receiveResponses()
  local incoming = responses
  responses = {}
  for _, response in ipairs(incoming) do callback(protocol, 127, response) end
end
local function roundtrip() sendRequests(); receiveResponses() end
local function container(id, firstIndex, capacity, locked)
  local c = {id = id, firstIndex = firstIndex, capacity = capacity, locked = locked, widgets = {}, items = {}}
  c.getId = function(self) return self.id end
  c.getFirstIndex = function(self) return self.firstIndex end
  c.getCapacity = function(self) return self.capacity end
  c.isUnlocked = function(self) return not self.locked end
  c.getItem = function(self, slot) return self.items[slot] end
  c.hasPages = function() return false end
  for i = 0, capacity - 1 do c.widgets['item' .. i] = widget() end
  c.itemsPanel = panel(c.widgets)
  c.window = widget()
  openContainers[id] = c
  serverContainers[id] = {getItem = function(_, absoluteIndex) return c.items[absoluteIndex - c.firstIndex] end}
  return c
end
local function setContainerItem(c, slot, heldItem)
  c.items[slot] = heldItem
  c.widgets['item' .. slot]:setItem(heldItem)
end

check(_G.AntigasItemRarity == nil and globals.AntigasItemRarity == nil, 'Rarity API is sandboxed')
local colors = {'#42C96B', '#3E8BFF', '#A855F7', '#F5C542', '#EF4444'}
for tier = 1, 5 do
  local heldItem = item(tier, 6, tier, 0)
  equipment[tier] = heldItem
  inventory.onInventoryChange(nil, tier, heldItem)
end
roundtrip()
for tier = 1, 5 do
  local w = invWidgets['slot' .. tier]
  check(w.borderColor == colors[tier] and w.borderWidth == 1, 'Inventory rarity color ' .. tier)
  check(w.tooltip:find('+' .. tier .. ' ataque', 1, true), 'Tooltip value ' .. tier)
end
local normal = item()
equipment[1] = normal
inventory.onInventoryChange(nil, 1, normal)
roundtrip()
check(invWidgets.slot1.borderWidth == 0, 'Normal item has no rarity border')
check(not invWidgets.slot1.rarityTooltip, 'Normal item clears rarity tooltip')

equipment[1] = item(5, 6, 5, 0)
inventory.onInventoryChange(nil, 1, equipment[1])
sendRequests()
equipment[1] = item(2, 6, 2, 0)
inventory.onInventoryChange(nil, 1, equipment[1])
receiveResponses()
check(not invWidgets.slot1.rarityTier, 'Old inventory response rejected after replacement')
roundtrip()
check(invWidgets.slot1.rarityTier == 2, 'Newest inventory response accepted')
equipment[1] = nil
inventory.onInventoryChange(nil, 1, nil)
roundtrip()
check(invWidgets.slot1.borderWidth == 0 and not invWidgets.slot1.rarityTier, 'Empty inventory slot cleared')

local bag = container(4, 80, 85)
for i = 0, 84 do setContainerItem(bag, i, item(i % 5 + 1, 1, i % 5 + 1, 0)) end
containerModule.refreshContainerItems(bag)
check(#requests == 3, 'Large container page split into bounded queries')
roundtrip()
check(bag.widgets.item0.rarityTier == 1 and bag.widgets.item84.rarityTier == 5, 'Absolute server indices map to visible page slots')

local chunkPushCount = #requests
callback(protocol, 127, 'P|C|4|120|120,4,5,4,7;121,0,0,0,0')
check(#requests == chunkPushCount and bag.widgets.item40.rarityTier == 4,
  'Later pushed metadata chunks map to their absolute visible slots')
callback(protocol, 127, 'P|C|4|165|165,5,6,5,0')
check(bag.widgets.item0.rarityTier == 1, 'Out-of-view pushed metadata is rejected')

local pushedBag = container(11, 0, 2)
setContainerItem(pushedBag, 0, item())
setContainerItem(pushedBag, 1, item(5, 6, 3, 0))
local requestCountBeforePush = #requests
callback(protocol, 127, 'P|C|11|0|0,0,0,0,0;1,5,6,3,0')
check(#requests == requestCountBeforePush, 'Container push colors loot without a query round trip')
check(pushedBag.widgets.item1.rarityTier == 5 and pushedBag.widgets.item1.borderColor == colors[5],
  'Same-packet container metadata applies and preserves the rarity border immediately')

rarity.requestContainerPage(bag)
sendRequests()
setContainerItem(bag, 0, item(3, 2, 3, 0))
containerModule.onContainerUpdateItem(bag, 0, bag.items[0])
receiveResponses()
check(not bag.widgets.item0.rarityTier, 'Page response cannot overwrite newer item request')
check(bag.widgets.item1.rarityTier == 2, 'Other page items still receive response')
roundtrip()
check(bag.widgets.item0.rarityTier == 3, 'Updated container item receives new rarity')

rarity.requestContainerPage(bag)
sendRequests()
bag.firstIndex = 165
containerModule.refreshContainerItems(bag)
receiveResponses()
check(not bag.widgets.item0.rarityTier, 'Response for previous page rejected')
roundtrip()
check(bag.widgets.item0.rarityTier == 3, 'New page response accepted')

rarity.requestContainerPage(bag)
sendRequests()
local replacement = container(4, 165, 2, true)
setContainerItem(replacement, 0, item(4, 5, 4, 7))
containerModule.refreshContainerItems(replacement)
receiveResponses()
check(not replacement.widgets.item0.rarityTier, 'Reused container ID rejects old response')
roundtrip()
local lockedWidget = replacement.widgets.item0
check(lockedWidget.borderColor == '#ff0000' and lockedWidget.rarityTier == 4, 'Locked container retains lock border and rarity metadata')
check(lockedWidget.tooltip:find('+4 nível mágico', 1, true), 'Skill tooltip decoded')
globals.UIItem.onDragLeave(lockedWidget)
check(lockedWidget.borderWidth == 1 and lockedWidget.borderColor == '#ff0000', 'Global UIItem resolves sandbox API on drag end')
replacement.locked = false
rarity.apply(lockedWidget, 4, false, 5, 4, 7)
globals.UIItem.onDragLeave(lockedWidget)
check(lockedWidget.borderColor == colors[4] and lockedWidget.borderWidth == 1, 'Rarity border survives drag')
lockedWidget:setItem(normal)
globals.UIItem.onItemChange(lockedWidget)
check(not lockedWidget.rarityTier and lockedWidget.tooltip == normal:getTooltip(), 'Item change removes obsolete tooltip and border')
local unrelatedWidget = widget(normal)
unrelatedWidget.borderWidth = 2
unrelatedWidget.borderColor = '#123456'
globals.UIItem.onItemChange(unrelatedWidget)
check(unrelatedWidget.borderWidth == 2 and unrelatedWidget.borderColor == '#123456', 'Unrelated item widgets keep their styled borders')

rarity.requestContainerPage(replacement)
sendRequests()
containerModule.destroy(replacement)
receiveResponses()
check(replacement.itemsPanel == nil and replacement.window == nil, 'Closed container clears pending state safely')

local before = #responses
for _, payload in ipairs({'Q|I|1|0', 'Q|I|1|11', 'Q|I|0|1', 'Q|I|2147483648|1', 'Q|I|1|1,1',
  'Q|C|1|16|0|1', 'Q|C|1|4|0|41', 'Q|C|1|4|65535|40', 'Q|C|1|4|0|0', 'Q|C|1|4|-1|1', string.rep('9', 257)}) do
  check(server.onExtendedOpcode(player, 127, payload) == true, 'Malformed request handled')
end
check(#responses == before, 'Malformed requests produce no response/amplification')
check(server.onExtendedOpcode(player, 126, 'Q|I|1|1') == false, 'Other opcodes ignored')
equipment[2] = item(3, 3, 3, 8)
inventory.onInventoryChange(nil, 2, equipment[2])
sendRequests()
local reply = responses[1]
callback({}, 127, reply)
check(not invWidgets.slot2.rarityTier, 'Previous connection response ignored')
receiveResponses()
check(invWidgets.slot2.tooltip:find('gelo', 1, true), 'Resistance subtype preserved')
feature = false
rarity.requestInventorySlot(2)
check(#requests == 0, 'No request without extended opcode support')
local connected, disconnected
globals.connect = function(object, events)
  if object == globals.g_game then connected = events.onGameEnd end
end
globals.disconnect = function(object, events)
  if object == globals.g_game then disconnected = events.onGameEnd end
end
globals.Container = {}
globals.g_ui = {importStyle = function() end}
globals.REGISTRATION_KEY = 'AbcDeFgH'
local originalReload = containerModule.reloadContainers
containerModule.reloadContainers = function() end
containerModule.init()
check(connected == containerModule.clean, 'Game-end cleanup registers a function')
containerModule.terminate()
check(disconnected == connected, 'Unload disconnects the same cleanup function')
containerModule.reloadContainers = originalReload
print('PASS rarity UI/protocol: ' .. checks .. ' assertions')
