-- Native OTClient offline regression fixture (client v44).
-- Extract the release ZIP into a temporary directory and copy this file there.
-- In that copy only: isolate settings, disable automatic client-release checks,
-- and replace HTTP, g_game.loginWorld and ProtocolLogin.login with functions
-- that reject network access before loading client modules. Do not use accounts.
-- After loadModules(), set RARITY_REAL_REPORT to a relative report filename and
-- dofile this fixture. It exits the client automatically after reporting results.
-- Windows launchers should use Start-Process -WindowStyle Hidden and isolated
-- APPDATA/LOCALAPPDATA/USERPROFILE directories; never use an installed client.
-- Uses native widgets and the registered opcode callback, with a fake transport.
local checks = 0
local function report(message)
  local f = assert(io.open(RARITY_REAL_REPORT, 'a'))
  f:write(message .. '\n')
  f:close()
end
local function check(value, message)
  assert(value, message)
  checks = checks + 1
end
local function run()
  check(not g_game.isOnline(), 'Real client starts offline')
  check(APP_VERSION == 44, 'Packaged client v44 loaded')
  g_game.setClientVersion(772)
  check(modules.game_things.isLoaded(), 'Native item definitions loaded')
  local root = g_ui.getRootWidget()
  local inv = modules.game_inventory
  check(inv and inv.inventoryPanel, 'Real inventory OTUI created')
  local rarity = inv.AntigasItemRarity
  check(rarity and _G.AntigasItemRarity == nil, 'Sandbox API is correctly exported')
  local outgoing, containers = {}, {}
  local protocol = {sendExtendedOpcode = function(_, opcode, data)
    check(opcode == 127, 'Native modules request opcode 127')
    outgoing[#outgoing + 1] = data
  end}
  local online, features, getProtocol, getContainers = g_game.isOnline, g_game.getFeature, g_game.getProtocolGame, g_game.getContainers
  local function restore()
    g_game.isOnline, g_game.getFeature = online, features
    g_game.getProtocolGame, g_game.getContainers = getProtocol, getContainers
  end
  g_game.isOnline = function() return true end
  g_game.getFeature = function(feature) return feature == GameExtendedOpcode or features(feature) end
  g_game.getProtocolGame = function() return protocol end
  g_game.getContainers = function() return containers end
  local function reply(payload) ProtocolGame.onExtendedOpcode(protocol, 127, payload) end
  local colors = {'#42C96B', '#3E8BFF', '#A855F7', '#F5C542', '#EF4444'}
  local reference = g_ui.createWidget('UIWidget', root)
  local function checkColor(widget, color, context)
    reference:setBorderColor(color)
    check(json.encode(widget:getBorderTopColor()) == json.encode(reference:getBorderTopColor()), context .. ' color')
    check(widget:getBorderTopWidth() == 1, context .. ' border width')
  end
  local ok, err = pcall(function()
    for tier = 1, 5 do
      local heldItem = assert(Item.create(2376), 'Native Item.create')
      inv.onInventoryChange(nil, tier, heldItem)
      local token, slot = outgoing[#outgoing]:match('^Q|I|(%d+)|(%d+)$')
      reply(string.format('R|I|%s|%s,%d,6,%d,0', token, slot, tier, tier))
      local widget = inv.inventoryPanel:getChildById('slot' .. tier)
      check(widget:getClassName() == 'UIItem' and widget:getItem() == heldItem, 'Native UIItem ' .. tier)
      checkColor(widget, colors[tier], 'Inventory tier ' .. tier)
      check(widget:getTooltip():find('+' .. tier .. ' ataque', 1, true), 'Native tooltip tier ' .. tier)
      widget:onDragLeave(nil, {x=0,y=0})
      checkColor(widget, colors[tier], 'Drag restore tier ' .. tier)
    end
    inv.onInventoryChange(nil, 1, Item.create(2376))
    local token, slot = outgoing[#outgoing]:match('^Q|I|(%d+)|(%d+)$')
    reply(string.format('R|I|%s|%s,0,0,0,0', token, slot))
    local common = inv.inventoryPanel:getChildById('slot1')
    check(common:getBorderTopWidth() == 0 and not common.rarityTooltip, 'Common item clears native border and tooltip')
    inv.onInventoryChange(nil, 1, nil)
    token, slot = outgoing[#outgoing]:match('^Q|I|(%d+)|(%d+)$')
    reply(string.format('R|I|%s|%s,0,0,0,0', token, slot))
    check(common:getItem() == nil and common:getBorderTopWidth() == 0, 'Empty native inventory slot')

    local items = {}
    for i = 0, 5 do items[i] = Item.create(2376) end
    local bag = {
      getId=function() return 3 end, getFirstIndex=function() return 0 end,
      getCapacity=function() return 6 end, getSize=function() return 6 end,
      getItemsCount=function() return 6 end, getName=function() return 'Rarity QA' end,
      isUnlocked=function() return true end, hasPages=function() return false end,
      hasParent=function() return false end, getContainerItem=function() return Item.create(2854) end,
      getItem=function(_, index) return items[index] end,
      getSlotPosition=function(_, index) return {x=65535,y=67,z=index} end
    }
    containers[3] = bag
    modules.game_containers.onContainerOpen(bag)
    check(bag.window and bag.itemsPanel, 'Real ContainerWindow OTUI and native item panel')
    local records = {}
    for i = 0, 4 do records[#records+1] = string.format('%d,%d,1,%d,0', i, i+1, i+1) end
    records[#records+1] = '5,0,0,0,0'
    local request = outgoing[#outgoing]:match('^Q|C|(%d+)|3|0|6$')
    check(request, 'Cross-module container query emitted')
    reply('R|C|' .. request .. '|3|0|' .. table.concat(records, ';'))
    for tier = 1, 5 do
      local widget = bag.itemsPanel:getChildById('item' .. (tier-1))
      checkColor(widget, colors[tier], 'Container tier ' .. tier)
      check(widget:getTooltip():find('+' .. tier .. '% vida', 1, true), 'Container bonus tooltip ' .. tier)
    end
    check(bag.itemsPanel:getChildById('item5'):getBorderTopWidth() == 0, 'Common container item border')
    local first = bag.itemsPanel:getChildById('item0')
    items[0] = Item.create(2376)
    modules.game_containers.onContainerUpdateItem(bag, 0, items[0])
    request = outgoing[#outgoing]:match('^Q|C|(%d+)|3|0|1$')
    reply('R|C|' .. request .. '|3|0|0,0,0,0,0')
    check(first:getBorderTopWidth() == 0 and not first.rarityTooltip, 'Native container replacement clears rarity')
    modules.game_containers.onContainerClose(bag)
    containers[3] = nil
    check(bag.window == nil and bag.itemsPanel == nil, 'Native container closes cleanly')
  end)
  reference:destroy()
  restore()
  if not ok then error(err) end
  check(not g_game.isOnline(), 'Real connection stays offline')
  report('PASS: OTClient v44 native UI, ' .. checks .. ' assertions, no connection')
end
scheduleEvent(function()
  report('START: native OTClient rarity UI')
  local ok, err = pcall(run)
  if not ok then report('FAIL: ' .. tostring(err)) end
  scheduleEvent(function() g_app.exit() end, 50)
end, 100)
