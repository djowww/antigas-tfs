-- Execute the real client modules. Only the native UI, keyboard, settings and
-- network boundaries are replaced; no hotkey implementation is re-created here.
local function clientFile(relative)
  local prefixes = arg[1] and {arg[1] .. '/'} or
    {'deploy/client-current/', '../Cliente/', 'Cliente/', '../../Cliente/'}
  for _, prefix in ipairs(prefixes) do
    local path = prefix .. relative
    local file = io.open(path, 'r')
    if file then file:close(); return path end
  end
  error('Client file not found: ' .. relative)
end

local function copy(value)
  if type(value) ~= 'table' then return value end
  local result = {}
  for key, child in pairs(value) do result[key] = copy(child) end
  return result
end

local function widget(id)
  local result = {id = id, children = {}, visible = true}
  function result:getChildById(name)
    for _, child in ipairs(self.children) do if child.id == name then return child end end
  end
  function result:getChildren()
    local children = {}
    for index, child in ipairs(self.children) do children[index] = child end
    return children
  end
  function result:getChildCount() return #self.children end
  function result:insertChild(index, child) table.insert(self.children, index, child); child.parent = self end
  function result:destroyChildren() self.children = {} end
  function result:destroy()
    if self.parent then
      for index, child in ipairs(self.parent.children) do
        if child == self then table.remove(self.parent.children, index); break end
      end
    end
  end
  function result:setId(value) self.id = value end
  function result:getId() return self.id end
  function result:setText(value) self.text = value end
  function result:clearText() self.text = '' end
  function result:setColor(value) self.color = value end
  function result:setCurrentIndex(value) self.currentIndex = value end
  function result:setChecked(value) self.checked = value end
  function result:setEnabled(value) self.enabled = value end
  function result:enable() self.enabled = true end
  function result:disable() self.enabled = false end
  function result:show() self.visible = true end
  function result:hide() self.visible = false end
  function result:setVisible(value) self.visible = value end
  function result:isVisible() return self.visible end
  function result:setItemId(value) self.previewId = value end
  function result:setItemSubType(value) self.previewSubType = value end
  function result:clearItem() self.previewId = nil end
  function result:getItem() return {isMultiUse = function() return true end} end
  for _, method in ipairs({'focus', 'raise', 'setCursorPos', 'ensureChildVisible', 'ungrabMouse'}) do
    result[method] = function() end
  end
  function result:focusChild(child) self.focusedChild = child end
  return result
end

local function newClient(oldSchool, version, presetNodes)
  local env = setmetatable({OLD_SCHOOL = oldSchool, SERVER_VERSION = 772}, {__index = _G})
  local tableLibrary = copy(table)
  tableLibrary.empty = function(value) return value == nil or next(value) == nil end
  tableLibrary.clear = function(value) for key in pairs(value) do value[key] = nil end end
  env.table = tableLibrary
  env.tr = function(format, ...) return string.format(format, ...) end
  env.toboolean = function(value) return value == true or value == 'true' or value == 1 end
  env.g_clock = {millis = function() return 1000 end}
  local effects = {network = {}, sent = {}, edited = {}, actions = {}, scheduled = 0, turns = 0, settingsSaves = 0}
  local item = {id = 3155}
  local player = {kind = 'local-player'}
  local target = {kind = 'attacking-creature', getTile = function() return {} end}
  local attacking = target
  local function record(kind, ...)
    effects.network[#effects.network + 1] = {kind = kind, args = {...}}
  end
  env.g_game = {
    isOnline = function() return true end,
    getCharacterName = function() return 'Fixture' end,
    getClientVersion = function() return version end,
    findPlayerItem = function(id, subtype) record('find', id, subtype); return item end,
    getLocalPlayer = function() return player end,
    getAttackingCreature = function() return attacking end,
    use = function(...) record('use', ...) end,
    useWith = function(...) record('useWith', ...) end,
    useInventoryItem = function(...) record('inventory', ...) end,
    useInventoryItemWith = function(...) record('inventoryWith', ...) end,
  }
  local rootPanel = {}
  env.modules = {
    game_interface = {
      getRootPanel = function() return rootPanel end,
      startUseWith = function(...) record('crosshair', ...) end,
    },
    game_console = {
      isChatEnabled = function() return false end,
      sendMessage = function(value) effects.sent[#effects.sent + 1] = value end,
      setTextEditText = function(value) effects.edited[#effects.edited + 1] = value end,
    },
    game_walking = {checkTurn = function() effects.turns = effects.turns + 1 end},
  }
  env.Item = {create = function(id) record('create', id); return {id = id} end}
  local settings = {}
  env.g_settings = {
    getNode = function(name) assert(name == 'hotkeys'); return settings end,
    setNode = function(name, value) assert(name == 'hotkeys'); settings = value end,
    getNumber = function(name) assert(name == 'hotkeyDelay'); return 50 end,
    save = function() effects.settingsSaves = effects.settingsSaves + 1 end,
  }
  local bindings = {}
  env.g_keyboard = {
    bindKeyPress = function(combo, callback, panel)
      assert(panel == rootPanel); bindings[combo] = callback
    end,
    unbindKeyPress = function(combo, callback, panel)
      assert(panel == rootPanel); if bindings[combo] == callback then bindings[combo] = nil end
    end,
  }
  env.scheduleEvent = function(callback, delay)
    assert(delay == 50); effects.scheduled = effects.scheduled + 1; callback()
  end
  env.g_ui = {createWidget = function(style) assert(style == 'HotkeyListLabel'); return widget() end}
  env.executeExtraHotkey = function(action, repeated)
    effects.actions[#effects.actions + 1] = {action, repeated}
  end
  env.getActionDescription = function(action) return action end
  setfenv(assert(loadfile(clientFile('modules/game_hotkeys/hotkeys_manager.lua'))), env)()
  env.currentHotkeys = widget('currentHotkeys')
  env.hotkeysWindow = widget('hotkeysWindow')
  env.configSelector = widget('configSelector')
  for _, name in ipairs({'removeHotkeyButton', 'hotkeyText', 'hotKeyTextLabel', 'sendAutomatically',
      'selectObjectButton', 'clearObjectButton', 'currentItemPreview', 'useOnSelf', 'useOnTarget', 'useWith'}) do
    env[name] = widget(name)
  end
  env.useRadioGroup = {selectWidget = function() end, clearSelected = function() end}
  local nodes = presetNodes or {{}}
  local saved = {}
  for index, node in ipairs(nodes) do
    local config = {node = copy(node), persisted = copy(node), saves = 0}
    function config:getNode(name) assert(name == 'hotkeys'); return self.node end
    function config:setNode(name, value) assert(name == 'hotkeys'); self.node = value end
    function config:save() self.saves = self.saves + 1; self.persisted = copy(self.node) end
    env.hotkeyConfigs[index] = config
    saved[index] = config
  end
  return env, effects, bindings, saved, function(value) attacking = value end, player, target, item
end

local tests = {}
local function test(name, callback) tests[#tests + 1] = {name, callback} end

-- Removing the OLD_SCHOOL execution guard would dispatch a native item action.
for _, version in ipairs({772, 860}) do
  for _, mode in ipairs({'use', 'self', 'target', 'crosshair', 'target-without-creature'}) do
    test('classic rejects direct item ' .. mode .. ' at protocol ' .. version, function()
      local env, effects, _, _, setTarget = newClient(true, version)
      local useTypes = {self = 1, target = 2, crosshair = 3, ['target-without-creature'] = 2}
      if mode == 'target-without-creature' then setTarget(nil) end
      env.hotkeyList = {F1 = {itemId = 3155, subType = 7, useType = useTypes[mode]}}
      env.doKeyCombo('F1', false)
      assert(#effects.network == 0, 'classic item hotkey reached the native item-use boundary')
    end)
  end
end

test('classic omits saved item keys from the list, active config and keyboard bindings', function()
  local env, _, bindings = newClient(true, 772, {{
    F1 = {itemId = '3155', subType = '7', useType = '2'},
    F2 = {value = 'exura', autoSend = true},
    F3 = {action = 'toggleSharedExperience'},
  }})
  env.load()
  assert(env.currentHotkeys:getChildById('F1') == nil, 'saved item hotkey remains visible')
  assert(env.hotkeyList.F1 == nil, 'saved item hotkey remains executable')
  assert(bindings.F1 == nil and bindings['Ctrl+F1'] == nil, 'saved item hotkey remains bound')
  assert(env.currentHotkeys:getChildCount() == 2, 'text and custom-action hotkeys must remain loaded')
end)

test('classic rejects item keys added directly', function()
  local env, _, bindings = newClient(true, 772)
  env.addKeyCombo('F5', {itemId = 3155, useType = 3})
  assert(env.currentHotkeys:getChildCount() == 0 and bindings.F5 == nil, 'direct item entry was registered')
end)

test('classic text, spell and custom action bindings retain their behavior', function()
  local env, effects, bindings = newClient(true, 772, {{
    F2 = {value = 'exura', autoSend = true},
    F3 = {value = 'hello', autoSend = false},
    F4 = {action = 'toggleSharedExperience'},
  }})
  env.load()
  bindings.F2(nil, nil, 0)
  bindings['Ctrl+F3'](nil, nil, 0)
  bindings.F4(nil, nil, 5)
  assert(effects.sent[1] == 'exura' and #effects.sent == 1, 'spell text must be sent once')
  assert(effects.edited[1] == 'hello' and #effects.edited == 1, 'plain text must populate chat')
  assert(effects.scheduled == 2, 'text bindings must keep their configured delay')
  assert(effects.actions[1][1] == 'toggleSharedExperience' and effects.actions[1][2] == true,
    'custom action and repetition flag must remain intact')
  assert(#effects.network == 0, 'text/action hotkeys must not dispatch an item')
end)

test('classic preserves custom actions carrying obsolete item fields', function()
  local env, effects, bindings = newClient(true, 772, {{
    F4 = {action = 'toggleSharedExperience', itemId = 3155, useType = 3},
  }})
  env.load()
  bindings.F4(nil, nil, 0)
  assert(effects.actions[1][1] == 'toggleSharedExperience' and #effects.network == 0,
    'custom actions take precedence over obsolete item fields')
end)

test('classic text saves preserve hidden items and all five presets', function()
  local nodes = {}
  for index = 1, 5 do
    nodes[index] = {F1 = {itemId = '3155', subType = '7', useType = '2', legacyMetadata = 'keep'},
      F2 = {value = 'exura', autoSend = true}}
  end
  local env, effects, _, saved = newClient(true, 772, nodes)
  for index = 1, 5 do
    env.configSelector.currentIndex = index
    env.onConfigChange()
    assert(env.currentConfig == index, 'preset selection changed')
    env.currentHotkeyLabel = env.currentHotkeys:getChildById('F2')
    env.onHotkeyTextChange('text preset ' .. index)
    env.save()
    assert(saved[index].node.F1.itemId == '3155' and saved[index].node.F1.subType == '7'
      and saved[index].node.F1.useType == '2' and saved[index].node.F1.legacyMetadata == 'keep',
      'saving text discarded a hidden item setting')
    assert(saved[index].node.F2.value == 'text preset ' .. index, 'edited text was not saved')
    env.doKeyCombo('F1', false)
  end
  assert(#effects.network == 0, 'save reactivated a hidden item hotkey')
  assert(#env.hotkeyConfigs == 5, 'custom preset count changed')
end)

test('classic defaults and reset do not overwrite hidden item settings', function()
  local env, effects, _, saved = newClient(true, 772, {{
    F1 = {itemId = '3155', useType = '3', legacyMetadata = 'keep'},
  }})
  env.load()
  for _, child in ipairs(env.currentHotkeys:getChildren()) do
    assert(child.itemId == nil, 'defaults exposed a hidden item setting')
  end
  env.configValueChanged = true
  env.save()
  assert(saved[1].node.F1.itemId == '3155' and saved[1].node.F1.legacyMetadata == 'keep',
    'blank defaults overwrote the hidden item')
  env.doKeyCombo('F1', false)
  env.reset()
  env.configValueChanged = true
  env.save()
  assert(saved[1].node.F1.itemId == '3155', 'reset erased the hidden item')
  env.doKeyCombo('F1', false)
  assert(#effects.network == 0, 'default/save/reset reactivated an item')
end)

test('classic can intentionally replace a hidden item combo with text', function()
  local env, effects, _, saved = newClient(true, 772, {{
    F1 = {itemId = '3155', useType = '3'}, F2 = {value = 'exura', autoSend = true},
  }})
  env.load()
  env.addKeyCombo('F1', {value = 'exori', autoSend = true})
  env.save()
  assert(saved[1].node.F1.itemId == nil and saved[1].node.F1.value == 'exori',
    'explicit text replacement must save on the chosen combo')
  env.doKeyCombo('F1', false)
  assert(effects.sent[1] == 'exori' and #effects.network == 0, 'text replacement must execute as text')
end)

local function presetFixture(oldSchool)
  local nodes = {}
  for index = 1, 5 do
    nodes[index] = {F2 = {value = 'original preset ' .. index, autoSend = true}}
    if oldSchool then
      nodes[index].F1 = {itemId = '3155', subType = '7', useType = '2', legacyMetadata = 'keep ' .. index}
    end
  end
  local env, effects, bindings, saved = newClient(oldSchool, 772, nodes)
  env.load()
  return env, effects, bindings, saved
end

local function selectPreset(env, index)
  env.configSelector.currentIndex = index
  env.onConfigChange()
  assert(env.currentConfig == index, 'preset switch loaded the wrong configuration')
end

local function editPresetText(env, value)
  env.currentHotkeyLabel = env.currentHotkeys:getChildById('F2')
  env.onHotkeyTextChange(value)
end

local function assertHiddenItem(config, index)
  local hidden = config.node.F1
  assert(hidden and hidden.itemId == '3155' and hidden.subType == '7' and hidden.useType == '2'
    and hidden.legacyMetadata == 'keep ' .. index, 'hidden legacy item or metadata was discarded')
end

local function assertPresetsUnwritten(saved, effects)
  assert(effects.settingsSaves == 0, 'settings were persisted before OK')
  for index, config in ipairs(saved) do
    assert(config.saves == 0 and config.node.F2.value == 'original preset ' .. index
      and config.persisted.F2.value == 'original preset ' .. index,
      'draft mutated the stored preset before OK')
  end
end

for _, oldSchool in ipairs({true, false}) do
  local mode = oldSchool and 'classic' or 'modern'

  test(mode .. ' Reset followed by OK persists defaults through reload', function()
    local env, effects, _, saved = presetFixture(oldSchool)
    env.reset()
    assert(env.currentHotkeys:getChildById('F2').value == '', 'Reset did not load defaults')
    env.ok()
    env.reload()
    assert(env.currentHotkeys:getChildById('F2').value == '', 'OK lost Reset defaults on reload')
    assert(saved[1].persisted.F2.value == '' and saved[1].saves == 1, 'Reset defaults were not persisted')
    if oldSchool then assertHiddenItem(saved[1], 1) end
  end)

  test(mode .. ' Reset followed by Cancel restores the stored preset', function()
    local env, effects, _, saved = presetFixture(oldSchool)
    env.reset()
    env.cancel()
    assert(env.currentHotkeys:getChildById('F2').value == 'original preset 1', 'Cancel retained Reset defaults')
    assertPresetsUnwritten(saved, effects)
  end)

  test(mode .. ' preset switching retains drafts without writing configurations', function()
    local env, effects, _, saved = presetFixture(oldSchool)
    editPresetText(env, 'draft A')
    selectPreset(env, 2)
    editPresetText(env, 'draft B')
    selectPreset(env, 1)
    assert(env.currentHotkeys:getChildById('F2').value == 'draft A', 'A draft disappeared after A to B to A')
    selectPreset(env, 2)
    assert(env.currentHotkeys:getChildById('F2').value == 'draft B', 'B draft disappeared on return')
    assertPresetsUnwritten(saved, effects)
  end)

  test(mode .. ' OK persists drafts from all five presets including Reset', function()
    local env, effects, bindings, saved = presetFixture(oldSchool)
    for index = 1, 5 do
      selectPreset(env, index)
      if index == 2 then env.reset() else editPresetText(env, 'draft preset ' .. index) end
    end
    assertPresetsUnwritten(saved, effects)
    local currentBinding = bindings.F2
    env.ok()
    assert(bindings.F2 == currentBinding, 'saving another preset rebound the active hotkey')
    for index, config in ipairs(saved) do
      local expected = index == 2 and '' or 'draft preset ' .. index
      assert(config.persisted.F2.value == expected and config.saves == 1, 'OK did not persist every draft')
      if oldSchool then assertHiddenItem(config, index) end
      selectPreset(env, index)
      assert(env.currentHotkeys:getChildById('F2').value == expected, 'saved draft did not survive reload')
      if oldSchool then assert(env.hotkeyList.F1 == nil, 'saving drafts reactivated a hidden item') end
    end
    assert(effects.settingsSaves == 1, 'OK must persist selection once')
  end)

  test(mode .. ' OK persists outgoing drafts when the selected preset is unchanged', function()
    local env, effects, _, saved = presetFixture(oldSchool)
    editPresetText(env, 'draft A')
    selectPreset(env, 2)
    env.ok()
    assert(saved[1].persisted.F2.value == 'draft A' and saved[1].saves == 1,
      'OK ignored an outgoing draft while the active preset was clean')
    assert(saved[2].saves == 0 and saved[2].persisted.F2.value == 'original preset 2',
      'OK rewrote an unchanged destination preset')
    assert(env.currentConfig == 2 and env.g_settings.getNode('hotkeys').Fixture_772 == 2,
      'OK persisted the outgoing selection instead of the selected preset')
  end)

  test(mode .. ' Cancel discards every preset draft including Reset', function()
    local env, effects, _, saved = presetFixture(oldSchool)
    editPresetText(env, 'discard A')
    selectPreset(env, 2)
    env.reset()
    selectPreset(env, 3)
    editPresetText(env, 'discard C')
    env.cancel()
    assert(env.currentConfig == 3, 'Cancel changed the currently selected preset')
    for index = 1, 5 do
      selectPreset(env, index)
      assert(env.currentHotkeys:getChildById('F2').value == 'original preset ' .. index,
        'Cancel left a draft in another preset')
      if oldSchool then assertHiddenItem(saved[index], index) end
    end
    env.ok()
    assertPresetsUnwritten(saved, effects)
  end)

  test(mode .. ' hiding and reopening retain drafts for later OK', function()
    local env, effects, _, saved = presetFixture(oldSchool)
    editPresetText(env, 'draft A')
    selectPreset(env, 2)
    editPresetText(env, 'draft B')
    env.toggle()
    env.toggle()
    selectPreset(env, 1)
    assert(env.currentHotkeys:getChildById('F2').value == 'draft A', 'visibility toggle lost outgoing drafts')
    assertPresetsUnwritten(saved, effects)
    env.ok()
    assert(saved[1].persisted.F2.value == 'draft A' and saved[2].persisted.F2.value == 'draft B',
      'OK did not save drafts kept through a visibility toggle')
  end)

  test(mode .. ' removing the last visible hotkey retains an empty draft across presets', function()
    local env, effects, _, saved = presetFixture(oldSchool)
    env.currentHotkeyLabel = env.currentHotkeys:getChildById('F2')
    env.removeHotkey()
    assert(env.currentHotkeys:getChildCount() == 0, 'last hotkey was not removed')
    selectPreset(env, 2)
    selectPreset(env, 1)
    assert(env.currentHotkeys:getChildCount() == 0, 'empty draft was replaced with default hotkeys')
    assertPresetsUnwritten(saved, effects)
    env.ok()
    assert(saved[1].persisted.F2 == nil and saved[1].saves == 1, 'OK did not persist the deletion')
    if oldSchool then
      assertHiddenItem(saved[1], 1)
      for combo in pairs(saved[1].persisted) do
        assert(combo == 'F1', 'defaults were persisted over an empty visible draft')
      end
    else
      assert(next(saved[1].persisted) == nil, 'defaults were persisted over an empty draft')
    end
  end)

  test(mode .. ' Cancel discards an empty draft after switching presets', function()
    local env, effects, _, saved = presetFixture(oldSchool)
    env.currentHotkeyLabel = env.currentHotkeys:getChildById('F2')
    env.removeHotkey()
    selectPreset(env, 2)
    env.cancel()
    selectPreset(env, 1)
    assert(env.currentHotkeys:getChildById('F2').value == 'original preset 1', 'Cancel retained deletion draft')
    assertPresetsUnwritten(saved, effects)
  end)
end

test('empty stored configurations use defaults when there is no draft', function()
  local env = newClient(false, 772, {{}})
  env.load()
  assert(env.currentHotkeys:getChildCount() == 16, 'empty stored preset no longer falls back to defaults')
end)

test('Reset explicitly loads defaults after deleting the last hotkey', function()
  local env, _, _, saved = presetFixture(false)
  env.currentHotkeyLabel = env.currentHotkeys:getChildById('F2')
  env.removeHotkey()
  selectPreset(env, 2)
  selectPreset(env, 1)
  env.reset()
  assert(env.currentHotkeys:getChildCount() == 16, 'Reset did not replace the empty draft with defaults')
  env.ok()
  assert(saved[1].persisted.F2 and saved[1].persisted.F2.value == '', 'OK did not persist explicit Reset defaults')
end)

for _, lifecycle in ipairs({'reload', 'online', 'offline'}) do
  test('classic ' .. lifecycle .. ' discards drafts without persisting them', function()
    local env, effects, _, saved = presetFixture(true)
    editPresetText(env, 'discard A')
    selectPreset(env, 2)
    editPresetText(env, 'discard B')
    env[lifecycle]()
    if lifecycle == 'offline' then env.online() end
    selectPreset(env, 1)
    assert(env.currentHotkeys:getChildById('F2').value == 'original preset 1', 'lifecycle retained A draft')
    selectPreset(env, 2)
    assert(env.currentHotkeys:getChildById('F2').value == 'original preset 2', 'lifecycle retained B draft')
    env.ok()
    assertPresetsUnwritten(saved, effects)
  end)
end

test('classic drafts retain explicit text replacements of hidden item combos', function()
  local env, effects, _, saved = presetFixture(true)
  env.addKeyCombo('F1', {value = 'exori', autoSend = true})
  selectPreset(env, 2)
  selectPreset(env, 1)
  local replacement = env.currentHotkeys:getChildById('F1')
  assert(replacement and replacement.value == 'exori', 'preset switch lost the explicit item-to-text draft')
  assertPresetsUnwritten(saved, effects)
  env.ok()
  assert(saved[1].persisted.F1.itemId == nil and saved[1].persisted.F1.value == 'exori',
    'OK restored a hidden item over its explicit text replacement')
  env.doKeyCombo('F1', false)
  assert(effects.sent[1] == 'exori' and #effects.network == 0, 'saved replacement did not execute as text')
end)

test('classic Reset replaces the current draft while retaining other preset drafts', function()
  local env, effects, _, saved = presetFixture(true)
  editPresetText(env, 'draft A')
  selectPreset(env, 2)
  editPresetText(env, 'draft B')
  selectPreset(env, 1)
  env.reset()
  selectPreset(env, 2)
  assert(env.currentHotkeys:getChildById('F2').value == 'draft B', 'Reset discarded another preset draft')
  env.ok()
  assert(saved[1].persisted.F2.value == '' and saved[2].persisted.F2.value == 'draft B',
    'OK did not save current Reset and other preset draft')
  assertHiddenItem(saved[1], 1)
  assertHiddenItem(saved[2], 2)
end)

-- Removing the non-classic branch would break clients that support item hotkeys.
for _, version in ipairs({772, 860}) do
  for _, mode in ipairs({'use', 'self', 'target', 'crosshair'}) do
    test('modern retains item ' .. mode .. ' at protocol ' .. version, function()
      local env, effects, bindings, _, _, player, target, item = newClient(false, version, {{
        F1 = {itemId = 3155, subType = 7, useType = ({self = 1, target = 2, crosshair = 3})[mode]},
      }})
      env.load()
      bindings.F1(nil, nil, 0)
      local last = effects.network[#effects.network]
      local expected = mode == 'crosshair' and 'crosshair' or
        (mode == 'use' and (version < 800 and 'use' or 'inventory') or
          (version < 800 and 'useWith' or 'inventoryWith'))
      assert(last and last.kind == expected, 'supported item hotkey reached the wrong boundary')
      if version < 800 then
        assert(last.args[1] == item, 'supported item hotkey changed its inventory item')
      elseif mode == 'crosshair' then
        assert(last.args[1].id == 3155, 'supported crosshair hotkey changed its item ID')
      else
        assert(last.args[1] == 3155, 'supported item hotkey changed its item ID')
      end
      if mode == 'self' then assert(last.args[2] == player, 'self hotkey changed its target') end
      if mode == 'target' then assert(last.args[2] == target, 'target hotkey changed its target') end
    end)
  end
end

for _, oldSchool in ipairs({true, false}) do
  test((oldSchool and 'classic' or 'modern') .. ' feature negotiation preserves the item-hotkey policy', function()
    local env = setmetatable({OLD_SCHOOL = oldSchool, SERVER_VERSION = 772}, {__index = _G})
    setfenv(assert(loadfile(clientFile('modules/gamelib/const.lua'))), env)()
    local features, loads = {}, 0
    env.g_game = {
      resetFeatures = function() features = {} end,
      enableFeature = function(feature) assert(feature ~= nil); features[feature] = true end,
    }
    env.modules = {game_things = {load = function() loads = loads + 1 end}}
    setfenv(assert(loadfile(clientFile('modules/game_features/features.lua'))), env)()
    env.updateFeatures(772)
    assert((features[env.GameForceAllowItemHotkeys] == true) == (not oldSchool),
      'native forced-item-hotkey feature violates OLD_SCHOOL')
    assert(features[env.GameExtendedOpcode] and features[env.GameExtendedClientPing]
      and features[env.GameNewWalking] and features[env.GamePlayerAddons] and features[env.GamePlayerMounts],
      'custom protocol features must remain available')
    assert(loads == 1, 'feature negotiation must still load game data')
  end)
end

local failures = 0
for _, entry in ipairs(tests) do
  local ok, message = pcall(entry[2])
  print((ok and 'PASS ' or 'FAIL ') .. entry[1])
  if not ok then failures = failures + 1; print('  ' .. tostring(message)) end
end
assert(failures == 0, string.format('Classic hotkey regressions: %d of %d failed', failures, #tests))
print(string.format('Classic hotkey regression tests passed: %d/%d', #tests, #tests))
