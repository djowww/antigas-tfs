InventorySlotStyles = {
  [InventorySlotHead] = "HeadSlot",
  [InventorySlotNeck] = "NeckSlot",
  [InventorySlotBack] = "BackSlot",
  [InventorySlotBody] = "BodySlot",
  [InventorySlotRight] = "RightSlot",
  [InventorySlotLeft] = "LeftSlot",
  [InventorySlotLeg] = "LegSlot",
  [InventorySlotFeet] = "FeetSlot",
  [InventorySlotFinger] = "FingerSlot",
  [InventorySlotAmmo] = "AmmoSlot"
}

Icons = {}
Icons[PlayerStates.Swords] = { tooltip = tr('You may not logout during a fight'), path = '/images/game/states/logout_block', id = 'condition_logout_block' }
Icons[PlayerStates.Poison] = { tooltip = tr('You are poisoned'), path = '/images/game/states/poisoned', id = 'condition_poisoned' }
Icons[PlayerStates.Burn] = { tooltip = tr('You are burning'), path = '/images/game/states/burning', id = 'condition_burning' }
Icons[PlayerStates.Energy] = { tooltip = tr('You are electrified'), path = '/images/game/states/electrified', id = 'condition_electrified' }
Icons[PlayerStates.Drunk] = { tooltip = tr('You are drunk'), path = '/images/game/states/drunk', id = 'condition_drunk' }
Icons[PlayerStates.ManaShield] = { tooltip = tr('You are protected by a magic shield'), path = '/images/game/states/magic_shield', id = 'condition_magic_shield' }
Icons[PlayerStates.Paralyze] = { tooltip = tr('You are paralysed'), path = '/images/game/states/slowed', id = 'condition_slowed' }
Icons[PlayerStates.Haste] = { tooltip = tr('You are hasted'), path = '/images/game/states/haste', id = 'condition_haste' }
Icons[PlayerStates.Drowning] = { tooltip = tr('You are drowning'), path = '/images/game/states/drowning', id = 'condition_drowning' }
Icons[PlayerStates.Freezing] = { tooltip = tr('You are freezing'), path = '/images/game/states/freezing', id = 'condition_freezing' }
Icons[PlayerStates.Dazzled] = { tooltip = tr('You are dazzled'), path = '/images/game/states/dazzled', id = 'condition_dazzled' }
Icons[PlayerStates.Cursed] = { tooltip = tr('You are cursed'), path = '/images/game/states/cursed', id = 'condition_cursed' }
Icons[PlayerStates.PartyBuff] = { tooltip = tr('You are strengthened'), path = '/images/game/states/strengthened', id = 'condition_strengthened' }
Icons[PlayerStates.PzBlock] = { tooltip = tr('You may not logout or enter a protection zone'), path = '/images/game/states/protection_zone_block', id = 'condition_protection_zone_block' }
Icons[PlayerStates.Pz] = { tooltip = tr('You are within a protection zone'), path = '/images/game/states/protection_zone', id = 'condition_protection_zone' }
Icons[PlayerStates.Bleeding] = { tooltip = tr('You are bleeding'), path = '/images/game/states/bleeding', id = 'condition_bleeding' }
Icons[PlayerStates.Hungry] = { tooltip = tr('You are hungry'), path = '/images/game/states/hungry', id = 'condition_hungry' }

AntigasItemRarity = AntigasItemRarity or {}

local ITEM_RARITY_OPCODE = 127
local ITEM_RARITY_PAGE_SIZE = 40
local rarityRequestId = 0
local inventoryRarityRequests = {}
local containerRarityRequests = {}
local itemRarityColors = {
  [1] = '#42C96B',
  [2] = '#3E8BFF',
  [3] = '#A855F7',
  [4] = '#F5C542',
  [5] = '#EF4444'
}
local itemRarityNames = {[1] = 'Incomum', [2] = 'Raro', [3] = 'Épico', [4] = 'Lendário', [5] = 'Mítico'}
local itemRarityCombatNames = {[0] = 'físico', [1] = 'energia', [2] = 'terra', [3] = 'fogo', [8] = 'gelo'}
local itemRaritySkillNames = {[0] = 'luta desarmada', [1] = 'clava', [2] = 'espada', [3] = 'machado',
  [4] = 'distância', [5] = 'escudo', [6] = 'pesca', [7] = 'nível mágico'}

local function sendItemRarityRequest(payload)
  if not g_game.isOnline() or not g_game.getFeature(GameExtendedOpcode) then return end
  local protocol = g_game.getProtocolGame()
  if protocol then protocol:sendExtendedOpcode(ITEM_RARITY_OPCODE, payload) end
end

local function nextRarityRequestId()
  rarityRequestId = rarityRequestId % 2147483647 + 1
  return rarityRequestId
end

local function getItemRarityTooltip(tier, bonusType, bonusValue, subtype)
  local rarityName = itemRarityNames[tier]
  if not rarityName then return nil end

  local value = tonumber(bonusValue) or 0
  local kind = tonumber(bonusType) or 0
  local detail
  if kind == 1 then detail = string.format('+%d%% vida máxima', value)
  elseif kind == 2 then detail = string.format('+%d%% mana máxima', value)
  elseif kind == 3 then detail = string.format('+%d%% resistência a %s', value, itemRarityCombatNames[tonumber(subtype)] or 'elemento')
  elseif kind == 4 then detail = string.format('+%d%% velocidade', value)
  elseif kind == 5 then detail = string.format('+%d %s', value, itemRaritySkillNames[tonumber(subtype)] or 'habilidade')
  elseif kind == 6 then detail = string.format('+%d ataque', value)
  elseif kind == 7 then detail = string.format('+%d defesa', value)
  else return rarityName end
  return rarityName .. '\n' .. detail
end

function AntigasItemRarity.apply(widget, tier, locked, bonusType, bonusValue, subtype)
  if not widget then return end
  tier = tonumber(tier) or 0
  locked = not not locked
  local item = widget:getItem()
  local color = item and itemRarityColors[tier]
  -- UIItem uses its own draw color; native Item:setMarked only affects the map.
  -- Restore white on reuse so an ordinary replacement never inherits the tint.
  widget:setColor(color or '#FFFFFF')
  widget.rarityTier = color and tier or nil
  widget.rarityLocked = locked
  widget.rarityBonusType = tonumber(bonusType) or nil
  widget.rarityBonusValue = tonumber(bonusValue) or nil
  widget.raritySubtype = tonumber(subtype) or nil

  local tooltip = color and getItemRarityTooltip(tier, bonusType, bonusValue, subtype)
  if tooltip then
    local item = widget:getItem()
    local itemTooltip = item and item:getTooltip() or ''
    if itemTooltip ~= '' then tooltip = itemTooltip .. '\n' .. tooltip end
    widget:setTooltip(tooltip)
    widget.rarityTooltip = true
  elseif widget.rarityTooltip then
    local item = widget:getItem()
    widget:setTooltip(item and item:getTooltip() or '')
    widget.rarityTooltip = nil
  end

  if locked then
    widget:setBorderWidth(1)
    widget:setBorderColor('#ff0000')
  elseif color then
    widget:setBorderWidth(1)
    widget:setBorderColor(color)
  else
    widget:setBorderWidth(0)
    widget:setBorderColor('#ffffff')
  end
end

function AntigasItemRarity.restoreBorder(widget)
  if not widget then return end
  if widget.rarityTier or widget.rarityLocked then
    AntigasItemRarity.apply(widget, widget.rarityTier, widget.rarityLocked,
      widget.rarityBonusType, widget.rarityBonusValue, widget.raritySubtype)
  else
    widget:setBorderWidth(0)
  end
end

function AntigasItemRarity.requestInventorySlot(slot)
  local widget = inventoryPanel and inventoryPanel:getChildById('slot' .. slot)
  if not widget then return end
  local requestId = nextRarityRequestId()
  inventoryRarityRequests[slot] = {id = requestId, widget = widget, item = widget:getItem()}
  sendItemRarityRequest(string.format('Q|I|%d|%d', requestId, slot))
end

function AntigasItemRarity.requestContainerPage(container)
  if not container or not container.itemsPanel then return end
  local firstIndex = container:getFirstIndex()
  local pending = {container = container, firstIndex = firstIndex, slots = {}}
  containerRarityRequests[container:getId()] = pending
  for firstSlot = 0, container:getCapacity() - 1, ITEM_RARITY_PAGE_SIZE do
    local requestId = nextRarityRequestId()
    local count = math.min(ITEM_RARITY_PAGE_SIZE, container:getCapacity() - firstSlot)
    for slot = firstSlot, firstSlot + count - 1 do
      local widget = container.itemsPanel:getChildById('item' .. slot)
      if widget then
        pending.slots[firstIndex + slot] = {id = requestId, widget = widget, item = widget:getItem()}
      end
    end
    sendItemRarityRequest(string.format('Q|C|%d|%d|%d|%d', requestId, container:getId(), firstIndex + firstSlot, count))
  end
end

function AntigasItemRarity.requestContainerItem(container, slot)
  if not container or not container.itemsPanel then return end
  local pending = containerRarityRequests[container:getId()]
  if not pending or pending.container ~= container or pending.firstIndex ~= container:getFirstIndex() then
    AntigasItemRarity.requestContainerPage(container)
    return
  end
  local widget = container.itemsPanel:getChildById('item' .. slot)
  if not widget then return end
  local index = container:getFirstIndex() + slot
  local requestId = nextRarityRequestId()
  pending.slots[index] = {id = requestId, widget = widget, item = widget:getItem()}
  sendItemRarityRequest(string.format('Q|C|%d|%d|%d|1', requestId, container:getId(), index))
end

function AntigasItemRarity.forgetContainer(container)
  local pending = container and containerRarityRequests[container:getId()]
  if pending and pending.container == container then containerRarityRequests[container:getId()] = nil end
end

local function onItemRarityOpcode(protocol, opcode, buffer)
  if protocol ~= g_game.getProtocolGame() or type(buffer) ~= 'string' or #buffer > 4096 then return end
  local kind, requestId, payload = buffer:match('^R|([IC])|(%d+)|(.+)$')
  if not kind then return end
  requestId = tonumber(requestId)

  if kind == 'I' then
    for record in payload:gmatch('[^;]+') do
      local slot, tier, bonusType, bonusValue, subtype = record:match('^(%d+),(%d+),(%d+),(%d+),(%d+)$')
      slot = tonumber(slot)
      local pending = slot and inventoryRarityRequests[slot]
      local widget = slot and inventoryPanel and inventoryPanel:getChildById('slot' .. slot)
      if pending and pending.id == requestId and widget == pending.widget and widget:getItem() == pending.item then
        inventoryRarityRequests[slot] = nil
        AntigasItemRarity.apply(widget, tier, false, bonusType, bonusValue, subtype)
      end
    end
    return
  end

  local containerId, firstIndex, records = payload:match('^(%d+)|(%d+)|(.+)$')
  containerId, firstIndex = tonumber(containerId), tonumber(firstIndex)
  if not containerId or not firstIndex then return end

  local containers = g_game.getContainers()
  local container = containers[containerId] or containers[tostring(containerId)]
  if not container or not container.itemsPanel then return end
  local pending = containerRarityRequests[containerId]
  if not pending or pending.container ~= container or pending.firstIndex ~= container:getFirstIndex() then return end
  local locked = not container:isUnlocked()

  for record in records:gmatch('[^;]+') do
    local index, tier, bonusType, bonusValue, subtype = record:match('^(%d+),(%d+),(%d+),(%d+),(%d+)$')
    index, tier = tonumber(index), tonumber(tier)
    if index and tier then
      local visibleSlot = index - container:getFirstIndex()
      if visibleSlot >= 0 and visibleSlot < container:getCapacity() then
        local widget = container.itemsPanel:getChildById('item' .. visibleSlot)
        local expected = pending.slots[index]
        if expected and expected.id == requestId and widget == expected.widget and widget:getItem() == expected.item then
          pending.slots[index] = nil
          AntigasItemRarity.apply(widget, tier, locked, bonusType, bonusValue, subtype)
        end
      end
    end
  end
end
-- Icons[SkullWhite] = { tooltip = tr('White skull'), path = '/images/game/skulls/condition_skull_white', id = 'skull_white' }
-- Icons[SkullGreen] = { tooltip = tr('Green skull'), path = '/images/game/skulls/condition_skull_green', id = 'skull_green' }
-- Icons[SkullRed] = { tooltip = tr('Red skull'), path = '/images/game/skulls/condition_skull_red', id = 'skull_red' }

inventoryWindow = nil
inventoryPanel = nil
soulLabel = nil
capLabel = nil

fightOffensiveBox = nil
fightBalancedBox = nil
fightDefensiveBox = nil
chaseModeButton = nil
standModeButton = nil

safeFightButton = nil
whiteDoveBox = nil
whiteHandBox = nil
yellowHandBox = nil
redFistBox = nil
fightModeRadioGroup = nil
inventoryMinimized = false
local updatingCombat = false
local conditionStates, conditionSkull = 0, 0
local conditionOrder = {PlayerStates.PzBlock, PlayerStates.ManaShield, PlayerStates.Swords,
  PlayerStates.Pz, PlayerStates.Poison, PlayerStates.Burn, PlayerStates.Energy,
  PlayerStates.Paralyze, PlayerStates.Haste, PlayerStates.Drunk, PlayerStates.Drowning,
  PlayerStates.Freezing, PlayerStates.Dazzled, PlayerStates.Cursed,
  PlayerStates.PartyBuff, PlayerStates.Bleeding, PlayerStates.Hungry}
local skullNames = {[1]='yellow', [2]='green', [3]='white', [4]='red', [5]='black', [6]='orange'}

QUEST_BUTTON = false

function init()
  ProtocolGame.registerExtendedOpcode(ITEM_RARITY_OPCODE, onItemRarityOpcode, true)
  connect(Creature, {onSkullChange = onSkullChange})
  inventoryWindow = g_ui.loadUI('inventory', modules.game_interface.getRightPanel())
  inventoryWindow:disableResize()

  fightOffensiveBox = inventoryWindow:recursiveGetChildById('fightOffensiveBox')
  fightBalancedBox = inventoryWindow:recursiveGetChildById('fightBalancedBox')
  fightDefensiveBox = inventoryWindow:recursiveGetChildById('fightDefensiveBox')

  chaseModeBox = inventoryWindow:recursiveGetChildById('chaseModeBox')
  standModeBox = inventoryWindow:recursiveGetChildById('standModeBox')
  safeFightButton = inventoryWindow:recursiveGetChildById('safeFightBox')

  whiteDoveBox = inventoryWindow:recursiveGetChildById('whiteDoveBox')
  whiteHandBox = inventoryWindow:recursiveGetChildById('whiteHandBox')
  yellowHandBox = inventoryWindow:recursiveGetChildById('yellowHandBox')
  redFistBox = inventoryWindow:recursiveGetChildById('redFistBox')
  
  logoutButton = inventoryWindow:recursiveGetChildById('logoutButton')
  
  --hotkeysButton = inventoryWindow:recursiveGetChildById('hotkeysButton')

  fightModeRadioGroup = UIRadioGroup.create()
  fightModeRadioGroup:addWidget(fightOffensiveBox)
  fightModeRadioGroup:addWidget(fightBalancedBox)
  fightModeRadioGroup:addWidget(fightDefensiveBox)

  chaseModeRadioGroup = UIRadioGroup.create()
  chaseModeRadioGroup:addWidget(standModeBox)
  chaseModeRadioGroup:addWidget(chaseModeBox)

  connect(fightModeRadioGroup, { onSelectionChange = onSetFightMode })
  connect(chaseModeRadioGroup, { onSelectionChange = onSetChaseMode })
  connect(safeFightButton, { onCheckChange = onSetSafeFight })

  connect(LocalPlayer, { onInventoryChange = onInventoryChange,
                         onSoulChange = onSoulChange,
                         onFreeCapacityChange = onFreeCapacityChange,
                         onStatesChange = onStatesChange,
						 -- onSkullChange = updateCreatureSkull,
						 })

  connect(g_game, { onGameStart = refresh,
                    onGameEnd = offline,
                    onFightModeChange = update,
                    onChaseModeChange = update,
                    onSafeFightChange = update,
                    onPVPModeChange   = update,
                    onWalk = check,
                    onAutoWalk = check
                  })

  inventoryPanel = inventoryWindow:getChildById('contentsPanel')
  soulLabel = inventoryWindow:recursiveGetChildById('soulLabel')
  soulTitle = inventoryWindow:recursiveGetChildById('soulTitle')
  capLabel = inventoryWindow:recursiveGetChildById('capLabel')
  inventoryWindow:getChildById('contentsPanel'):setMarginTop(3)
  
  -- Anti-steal code
  if (REGISTRATION_KEY ~= "AbcDeFgH") then
	g_logger.fatal("Invalid serial ID for the server, please contact julianandresbernalv@gmail.com or JulianBernalV#7033")
  end
  
  for k,v in pairs(Icons) do
    g_textures.preload(v.path)
  end

  if g_game.isOnline() then
     local localPlayer = g_game.getLocalPlayer()
     onSoulChange(localPlayer, localPlayer:getSoul())
     onFreeCapacityChange(localPlayer, localPlayer:getFreeCapacity())
     onStatesChange(localPlayer, localPlayer:getStates(), 0)
	 -- updateCreatureSkull(localPlayer, localPlayer:getSkull())
	 local lastCombatControls = g_settings.getNode('LastCombatControls') or {}
	 local char = g_game.getCharacterName()
	 if lastCombatControls[char] then
		onInventoryMinimize(lastCombatControls[char].inventoryMinimize)
	 end
     refresh()
  end

  refresh()
  inventoryWindow:setup()
  onInventoryMinimize(inventoryMinimized)
end

function terminate()
  ProtocolGame.unregisterExtendedOpcode(ITEM_RARITY_OPCODE)
  disconnect(Creature, {onSkullChange = onSkullChange})
  if g_game.isOnline() then
    offline()
  end

  disconnect(LocalPlayer, { onInventoryChange = onInventoryChange,
                            onSoulChange = onSoulChange,
                            onFreeCapacityChange = onFreeCapacityChange,
                            onStatesChange = onStatesChange,
                            -- onSkullChange = updateCreatureSkull
							})

  disconnect(g_game, { onGameStart = refresh,
                       onGameEnd = offline,
                       onFightModeChange = update,
                       onChaseModeChange = update,
                       onSafeFightChange = update,
                       onPVPModeChange   = update,
                       onWalk = check,
                       onAutoWalk = check })

  inventoryWindow:destroy()

  fightModeRadioGroup:destroy()
  chaseModeRadioGroup:destroy()
end

function update()
  updatingCombat = true
  local fightMode = g_game.getFightMode()
  if fightMode == FightOffensive then
    fightModeRadioGroup:selectWidget(fightOffensiveBox, true)
  elseif fightMode == FightBalanced then
    fightModeRadioGroup:selectWidget(fightBalancedBox, true)
  else
    fightModeRadioGroup:selectWidget(fightDefensiveBox, true)
  end

  local chaseMode = g_game.getChaseMode()
  if chaseMode == 1 then
     chaseModeRadioGroup:selectWidget(chaseModeBox, true)
  else
     chaseModeRadioGroup:selectWidget(standModeBox, true)
  end

  local safeFight = g_game.isSafeFight()
  safeFightButton:setChecked(not safeFight)
  safeFightButton:setTooltip(safeFight and
    tr('Safe fight is on: unmarked players are protected from your attacks. Click to allow attacks.') or
    tr('Safe fight is off: attacks on unmarked players are allowed. Click to enable protection.'))
  updatingCombat = false

end

function check()
	if modules.client_options.getOption('autoChaseOverride') then
		if g_game.isAttacking() and g_game.getChaseMode() == ChaseOpponent then
			g_game.setChaseMode(DontChase)
		end
	end
end

function refresh()
  local player = g_game.getLocalPlayer()
  for i = InventorySlotFirst, InventorySlotLast do
    if g_game.isOnline() then
      onInventoryChange(player, i, player:getInventoryItem(i))
    else
      onInventoryChange(player, i, nil)
    end
  end

  if g_game.isOnline() then
    for _, container in pairs(g_game.getContainers()) do
      AntigasItemRarity.requestContainerPage(container)
    end
  end

  if player then
    onFreeCapacityChange(player, player:getFreeCapacity())
    conditionSkull = player:getSkull()
    onStatesChange(player, player:getStates())
    local char = g_game.getCharacterName()

    local lastCombatControls = g_settings.getNode('LastCombatControls')

    if not table.empty(lastCombatControls) then
      if lastCombatControls[char] then
        g_game.setFightMode(lastCombatControls[char].fightMode)
        g_game.setChaseMode(lastCombatControls[char].chaseMode)
        g_game.setSafeFight(lastCombatControls[char].safeFight)
        if lastCombatControls[char].pvpMode then
          g_game.setPVPMode(lastCombatControls[char].pvpMode)
        end
		onInventoryMinimize(lastCombatControls[char].inventoryMinimize)
      end
    end
  end
  update()
end

function layoutConditions()
  if not inventoryWindow then return end
  local content = inventoryWindow:recursiveGetChildById('conditionPanel')
  if not content then return end
  for i, icon in ipairs(content:getChildren()) do
    icon:setPosition({x=content:getX()+2+((i-1)%3)*10, y=content:getY()+2+math.floor((i-1)/3)*10})
  end
end

local function renderConditions()
  if not inventoryWindow then return end
  local content = inventoryWindow:recursiveGetChildById('conditionPanel')
  if not content then return end
  content:destroyChildren()
  local entries, descriptions = {}, {}
  local skull = skullNames[conditionSkull]
  if skull then
    entries[#entries+1] = {id='condition_skull', path='/images/game/skulls/skull_'..skull,
      tooltip=tr('Skull: %s', skull)}
  end
  for _, state in ipairs(conditionOrder) do
    if bit32.band(conditionStates, state) ~= 0 then entries[#entries+1] = Icons[state] end
  end
  for _, entry in ipairs(entries) do descriptions[#descriptions+1] = entry.tooltip end
  local description = #descriptions > 0 and table.concat(descriptions, '\n') or tr('No active conditions.')
  content:setTooltip(description)
  for i, entry in ipairs(entries) do
    if i > 6 then break end
    local icon = g_ui.createWidget('ConditionWidget', content)
    if i == 6 and #entries > 6 then
      icon:setId('condition_more')
      icon:setText('+')
      icon:setTooltip(description)
    else
      icon:setId(entry.id)
      icon:setImageSource(entry.path)
      icon:setTooltip(entry.tooltip)
    end
  end
  layoutConditions()
end

function onSkullChange(creature, skull)
  if creature ~= g_game.getLocalPlayer() then return end
  conditionSkull = skull or 0
  renderConditions()
end

function offline()
  inventoryRarityRequests = {}
  containerRarityRequests = {}
  conditionStates, conditionSkull = 0, 0
  renderConditions()
  inventoryWindow:recursiveGetChildById('conditionPanel'):destroyChildren()
  local lastCombatControls = g_settings.getNode('LastCombatControls')
  if not lastCombatControls then
    lastCombatControls = {}
  end

  local player = g_game.getLocalPlayer()
  if player then
    local char = g_game.getCharacterName()
    lastCombatControls[char] = {
      fightMode = g_game.getFightMode(),
      chaseMode = g_game.getChaseMode(),
      safeFight = g_game.isSafeFight(),
	  inventoryMinimize = inventoryMinimized
    }

    if g_game.getFeature(GamePVPMode) then
      lastCombatControls[char].pvpMode = g_game.getPVPMode()
    end
    -- save last combat control settings
    g_settings.setNode('LastCombatControls', lastCombatControls)
  end
end

function onStatesChange(localPlayer, now, old)
  -- Rebuild from authoritative state rather than toggling XOR bits. Repeated
  -- packets and unknown future bits cannot remove icons or index a nil entry.
  conditionStates = type(now) == 'number' and now == now and math.abs(now) < math.huge and now or 0
  renderConditions()
end

-- hooked events
function onInventoryChange(player, slot, item, oldItem)
  local itemWidget = inventoryPanel:getChildById('slot' .. slot)
  AntigasItemRarity.apply(itemWidget, 0)
  if item then
    itemWidget:setStyle('InventoryItem')
    itemWidget:setItem(item)
  else
    itemWidget:setStyle(InventorySlotStyles[slot])
    itemWidget:setItem(nil)
  end
  AntigasItemRarity.requestInventorySlot(slot)
end

function onFreeCapacityChange(player, freeCapacity)
  if type(freeCapacity) ~= 'number' or freeCapacity ~= freeCapacity or math.abs(freeCapacity) == math.huge then
    capLabel:setText('--')
    capLabel:setTooltip(tr('Character data unavailable.'))
    return
  end
  if freeCapacity > 99 then
    freeCapacity = math.floor(freeCapacity * 10) / 10
  end
  if freeCapacity > 999 then
    freeCapacity = math.floor(freeCapacity)
  end
  -- Preserve this client's existing conversion and rounding. The previous
  -- large-value branch appended "k" before multiplication, causing an error.
  local text = tostring(freeCapacity * 100)
  local amount = freeCapacity * 100
  local display = text
  if amount >= 1000000 then display = string.format('%.1fm', amount / 1000000)
  elseif amount >= 100000 then display = string.format('%.0fk', amount / 1000) end
  capLabel:setText(display)
  capLabel:setTooltip(tr('Free capacity: %s', text))
end

function hideLabels()
  local removeHeight = math.max(capLabel:getMarginRect().height, soulLabel:getMarginRect().height)
  capLabel:setOn(false)
  soulLabel:setOn(false)
  inventoryWindow:setHeight(math.max(inventoryWindow.minimizedHeight, inventoryWindow:getHeight() - removeHeight))
end

function onSoulChange(localPlayer, soul)
  if soul > 0 then
    soulLabel:setText(tr(""))
  else
    soulLabel:setText(soul)
  end
end

function onSetFightMode(self, selectedFightButton)
  if selectedFightButton == nil then return end
  local buttonId = selectedFightButton:getId()
  local fightMode
  
  if buttonId == 'fightOffensiveBox' then
    fightMode = FightOffensive
  elseif buttonId == 'fightBalancedBox' then
    fightMode = FightBalanced
  else
    fightMode = FightDefensive
  end
  g_game.setFightMode(fightMode)
end

function onSetChaseMode(self, selectedButton)
  if not selectedButton then return end
  g_game.setChaseMode(selectedButton == chaseModeBox and ChaseOpponent or DontChase)
end


function onSetSafeFight(self, checked)
  if not updatingCombat then g_game.setSafeFight(not checked) end
end

function onSetPVPMode(self, selectedPVPButton)
  if selectedPVPButton == nil then
    return
  end

  local buttonId = selectedPVPButton:getId()
  local pvpMode = PVPWhiteDove
  if buttonId == 'whiteDoveBox' then
    pvpMode = PVPWhiteDove
  elseif buttonId == 'whiteHandBox' then
    pvpMode = PVPWhiteHand
  elseif buttonId == 'yellowHandBox' then
    pvpMode = PVPYellowHand
  elseif buttonId == 'redFistBox' then
    pvpMode = PVPRedFist
  end

  g_game.setPVPMode(pvpMode)
end

function getPVPBoxByMode(mode)
  local widget = nil
  if mode == PVPWhiteDove then
    widget = whiteDoveBox
  elseif mode == PVPWhiteHand then
    widget = whiteHandBox
  elseif mode == PVPYellowHand then
    widget = yellowHandBox
  elseif mode == PVPRedFist then
    widget = redFistBox
  end
  return widget
end

-- function updateCreatureSkull(creature, skullId)
-- local player = g_game.getLocalPlayer()
  -- if creature ~= player then return end
  -- local skullIcons = {2, 3, 4}
  -- for k,v in pairs(skullIcons) do
    -- content = inventoryWindow:recursiveGetChildById('conditionPanel')
    -- icon = content:getChildById(Icons[v].id)
	 -- if icon then
	    -- icon:destroy()
	 -- end
  -- end
  -- toggleSkullIcon(skullId)
-- end

-- function toggleSkullIcon(skullId)
-- if skullId == 0 then return end
   -- content = inventoryWindow:recursiveGetChildById('conditionPanel')
   -- icon = content:getChildById(Icons[skullId].id)
   -- if not icon then
      -- icon = loadIcon(skullId)
      -- icon:setParent(content)
   -- end
-- end

function onMiniWindowClose()
  inventoryWindow:open()
end

function onInventoryMinimize(value)
  value = not not value
  local function child(id) return inventoryWindow:recursiveGetChildById(id) end
  child('servicePanel'):setVisible(not value)
  child('miniwindowScrollBar'):hide()
  child('soulPanel'):hide()
  soulLabel:hide()
  child('soulTitle'):hide()

  for slot = 1, 10 do child('slot' .. slot):setVisible(not value) end

  if value then
    fightOffensiveBox:setMargin(3, 97)
    fightBalancedBox:setMargin(4, 76)
    fightDefensiveBox:setMargin(3, 54)
    standModeBox:setMargin(25, 97, -15, 9)
    chaseModeBox:setMargin(25, 76, -15, 9)
    safeFightButton:setMargin(25, 54, -15, 9)
  else
    fightOffensiveBox:setMargin(16, 29)
    fightBalancedBox:setMargin(37, 29)
    fightDefensiveBox:setMargin(57, 29)
    standModeBox:setMargin(16, 6, 0, 0)
    chaseModeBox:setMargin(36, 6, 0, 0)
    safeFightButton:setMargin(57, 6, 0, 0)
  end

  local cap = child('capPanel')
  cap:breakAnchors()
  cap:setMargin(0)
  local conditions = child('conditionPanel')
  conditions:breakAnchors()
  conditions:setMargin(0)
  conditions:setSize({width=34,height=24})
  cap:setSize({width=34,height=24})
  if value then
    cap:addAnchor(AnchorTop, 'parent', AnchorTop)
    cap:addAnchor(AnchorLeft, 'parent', AnchorLeft)
    cap:setMarginTop(46)
    cap:setMarginLeft(41)
    conditions:addAnchor(AnchorTop, 'parent', AnchorTop)
    conditions:addAnchor(AnchorLeft, 'parent', AnchorLeft)
    conditions:setMarginTop(46)
    conditions:setMarginLeft(3)
  else
    cap:addAnchor(AnchorTop, 'slot10', AnchorBottom)
    cap:addAnchor(AnchorLeft, 'slot10', AnchorLeft)
    cap:setMarginTop(2)
    conditions:addAnchor(AnchorTop, 'slot9', AnchorBottom)
    conditions:addAnchor(AnchorLeft, 'slot9', AnchorLeft)
    conditions:setMarginTop(2)
  end
  layoutConditions()

  child('teamButton'):setMarginTop(value and 6 or 84)
  child('teamButton'):show()
  child('logoutButton'):setMarginTop(value and 52 or 130)
  child('optionsButton'):setMarginTop(value and 29 or 107)
  for _,id in ipairs({'teamButton', 'logoutButton', 'optionsButton'}) do
    child(id):setMarginRight(value and 8 or 10)
  end
  inventoryMinimized = value
  child('minButton'):setOn(value)
  inventoryWindow:setHeight(value and 76 or 155)
end
