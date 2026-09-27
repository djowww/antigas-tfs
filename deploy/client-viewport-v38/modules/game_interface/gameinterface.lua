gameRootPanel = nil
gameMapPanel = nil
gameRightPanels = nil
gameLeftPanels = nil
gameBottomPanel = nil
logoutButton = nil
mouseGrabberWidget = nil
countWindow = nil
logoutWindow = nil
exitWindow = nil
bottomSplitter = nil
limitedZoom = false
hookedMenuOptions = {}
lastDirTime = g_clock.millis()

local fpsUpdateEvent = nil
local viewportEvent = nil
local viewportBusy = false
local viewportAcknowledged = {width = 16, height = 12}
local viewportLastRequest = -1000
local viewportPending = nil

function init()
  g_ui.importStyle('styles/countwindow')

  connect(g_game, {
    onGameStart = onGameStart,
    onGameEnd = onGameEnd,
    onLoginAdvice = onLoginAdvice,
	onLogin = toggleBlueNpcColor,
    onPingBack = updatePing 
  }, true)

  -- Call load AFTER game window has been created and 
  -- resized to a stable state, otherwise the saved 
  -- settings can get overridden by false onGeometryChange
  -- events
  connect(g_app, {
    onRun = load,
    onExit = save
  })
  
  gameRootPanel = g_ui.displayUI('gameinterface')
  gameRootPanel:hide()
  gameRootPanel:lower()
  gameRootPanel.onGeometryChange = updateStretchShrink

  mouseGrabberWidget = gameRootPanel:getChildById('mouseGrabber')
  mouseGrabberWidget.onMouseRelease = onMouseGrabberRelease

  bottomSplitter = gameRootPanel:getChildById('bottomSplitter')
  gameMapPanel = gameRootPanel:getChildById('gameMapPanel')
  gameRightPanels = gameRootPanel:getChildById('gameRightPanels')
  gameLeftPanels = gameRootPanel:getChildById('gameLeftPanels')
  gameBottomPanel = gameRootPanel:getChildById('gameBottomPanel')
  connect(gameLeftPanel, { onVisibilityChange = onLeftPanelVisibilityChange })

  gameRightPanels:addChild(g_ui.createWidget('GameSidePanel'))
 
  refreshViewMode()

  bindKeys()
  
  connect(gameMapPanel, { onGeometryChange = updateSize, onVisibleDimensionChange = updateSize })
  connect(g_game, { onMapChangeAwareRange = onViewportRange })

  if g_game.isOnline() then
    show()
  end
end

function bindKeys()
  gameRootPanel:setAutoRepeatDelay(10)

  local lastAction = 0
  g_keyboard.bindKeyPress('Escape', function() 
    if lastAction + 50 > g_clock.millis() then return end 
    lastAction = g_clock.millis()
    g_game.cancelAttackAndFollow() 
  end, gameRootPanel)
  g_keyboard.bindKeyPress('Ctrl+=', function() if g_game.getFeature(GameNoDebug) then return end gameMapPanel:zoomIn() end, gameRootPanel)
  g_keyboard.bindKeyPress('Ctrl+-', function() if g_game.getFeature(GameNoDebug) then return end gameMapPanel:zoomOut() end, gameRootPanel)
  g_keyboard.bindKeyDown('Ctrl+Q', function() tryLogout(false) end, gameRootPanel)
  g_keyboard.bindKeyDown('Ctrl+L', function() tryLogout(false) end, gameRootPanel)
  g_keyboard.bindKeyDown('Ctrl+W', function() g_map.cleanTexts() modules.game_textmessage.clearMessages() end, gameRootPanel)
end

function terminate()
  hide()

  hookedMenuOptions = {}
  markThing = nil
  

  disconnect(g_game, {
    onGameStart = onGameStart,
    onGameEnd = onGameEnd,
    onLoginAdvice = onLoginAdvice
  })

  disconnect(gameMapPanel, { onGeometryChange = updateSize, onVisibleDimensionChange = updateSize })
  disconnect(g_game, { onMapChangeAwareRange = onViewportRange })
  removeEvent(viewportEvent)
  removeEvent(fpsUpdateEvent)
  viewportEvent, fpsUpdateEvent = nil, nil

  -- logoutButton:destroy()
  gameRootPanel:destroy()
end

function onGameStart()
  viewportAcknowledged = {width = 16, height = 12}
  viewportPending = nil
  viewportLastRequest = -1000
  refreshViewMode()
  show()
  
  -- open tibia has delay in auto walking
  if not g_game.isOfficialTibia() then
    g_game.enableFeature(GameForceFirstAutoWalkStep)
  else
    g_game.disableFeature(GameForceFirstAutoWalkStep)
  end
  
   addEvent(function()
    if modules.client_options.getOption('showPing') and (g_game.getFeature(GameClientPing) or g_game.getFeature(GameExtendedClientPing)) then
      gameRootPanel:getChildById('pingLabel'):show()
    else
      gameRootPanel:getChildById('pingLabel'):hide()      
    end
  end)
  
end

function onGameEnd()
  removeEvent(viewportEvent)
  viewportEvent = nil
  viewportPending = nil
  viewportAcknowledged = {width = 16, height = 12}
  hide()
  modules.client_topmenu.getTopMenu():setImageColor('white')
  gameRootPanel:getChildById('pingLabel'):hide()
end

function toggleBlueNpcColor(value)
  if modules.client_options.getOption('blueNpc') then
  	 g_game.enableFeature(GameBlueNpcNameColor)
  else
	g_game.disableFeature(GameBlueNpcNameColor)
  end
end

function show()
  connect(g_app, { onClose = tryExit })
  modules.client_background.hide()
  gameRootPanel:show()
  gameRootPanel:focus()
  gameMapPanel:followCreature(g_game.getLocalPlayer())
  player = g_game.getLocalPlayer()
  
  updateStretchShrink()
  if modules.game_playerbars then
	logoutButton = modules.game_playerbars.logoutButton
	--logoutButton:setTooltip(tr('Logout'))
  end
  updateFps()
  
  local name = g_game.getCharacterName()
  g_window.setTitle(name .. ' - ' .. g_app.getName())
  
  addEvent(function()
    if not limitedZoom or g_game.isGM() then
      gameMapPanel:setMaxZoomOut(513)
      gameMapPanel:setLimitVisibleRange(false)
    else
      gameMapPanel:setMaxZoomOut(11)
      gameMapPanel:setLimitVisibleRange(true)
    end
  end)
end

function hide()
  disconnect(g_app, { onClose = tryExit })
  -- logoutButton:setTooltip(tr('Exit'))

  if logoutWindow then
    logoutWindow:destroy()
    logoutWindow = nil
  end
  if exitWindow then
    exitWindow:destroy()
    exitWindow = nil
  end
  if countWindow then
    countWindow:destroy()
    countWindow = nil
  end
  gameRootPanel:hide()
  modules.client_background.show()
  g_window.setTitle(g_app.getName())
end

function save()
  local settings = {}
  settings.splitterMarginBottom = bottomSplitter:getMarginBottom()
  g_settings.setNode('game_interface', settings)
end

function load()
  local settings = g_settings.getNode('game_interface')
  if settings then
    if settings.splitterMarginBottom then
      bottomSplitter:setMarginBottom(settings.splitterMarginBottom)
    end
  end
end

function updateFps()
  fpsUpdateEvent = scheduleEvent(updateFps, 500)
  text = 'FPS: ' .. g_app.getFps()
  gameRootPanel:getChildById('fpsLabel'):setText(text)
end

function updatePing(ping)
  if g_proxy and g_proxy.getPing() > 0 then
    ping = g_proxy.getPing()
  end
  
  local text = 'Ping: '
  local color
  if ping < 0 then
    text = text .. "??"
    color = 'yellow'
  else
    text = text .. ping .. ' ms'
    if ping >= 500 then
      color = 'red'
    elseif ping >= 250 then
      color = 'yellow'
    else
      color = 'green'
    end
  end
  gameRootPanel:getChildById('pingLabel'):setColor(color)
  gameRootPanel:getChildById('pingLabel'):setText(text)
end

function setPingVisible(enable)
  gameRootPanel:getChildById('pingLabel'):setVisible(enable)
end

function setFpsVisible(enable)
  gameRootPanel:getChildById('fpsLabel'):setVisible(enable)
end

function onLoginAdvice(message)
  displayInfoBox(tr("For Your Information"), message)
end

function forceExit()
	g_game.cancelLogin()
	scheduleEvent(exit, 10)
  return true
end

function tryExit()
  if exitWindow then
    return true
  end

  local exitFunc = function() g_game.safeLogout() forceExit() end
  local logoutFunc = function() g_game.safeLogout() exitWindow:destroy() exitWindow = nil end
  local cancelFunc = function() exitWindow:destroy() exitWindow = nil end

  exitWindow = displayGeneralBox(tr('Exit'), tr("If you shut down the program, your character might stay in the game.\nClick on 'Logout' to ensure that you character leaves the game properly.\nClick on 'Exit' if you want to exit the program without logging out your character."),
  { { text=tr('Force Exit'), callback=exitFunc },
    { text=tr('Logout'), callback=logoutFunc },
    { text=tr('Cancel'), callback=cancelFunc },
    anchor=AnchorHorizontalCenter }, logoutFunc, cancelFunc)

  return true
end

function tryLogout(prompt)
  if type(prompt) ~= "boolean" then
    prompt = true
  end
  if not g_game.isOnline() then
    exit()
    return
  end

  if logoutWindow then
    return
  end

  local msg, yesCallback
  if not g_game.isConnectionOk() then
    msg = 'Your connection is failing, if you logout now your character will be still online, do you want to force logout?'

    yesCallback = function()
      g_game.forceLogout()
      if logoutWindow then
        logoutWindow:destroy()
        logoutWindow=nil
      end
    end
  else
    msg = 'Are you sure you want to leave Antigas?'

    yesCallback = function()
      g_game.safeLogout()
      if logoutWindow then
        logoutWindow:destroy()
        logoutWindow=nil
      end
    end
  end

  local noCallback = function()
    logoutWindow:destroy()
    logoutWindow=nil
  end

  if prompt then
    logoutWindow = displayGeneralBox(tr('Warning'), tr(msg), {
      { text=tr('Yes'), callback=yesCallback },
      { text=tr('No'), callback=noCallback },
    }, yesCallback, noCallback)
  else
     yesCallback()
  end
end

function updateStretchShrink()
  if modules.client_options.getOption('gameView') ~= 2 and modules.client_options.getOption('dontStretchShrink') and not alternativeView then
    gameMapPanel:setVisibleDimension({ width = 15, height = 11 })

    -- Set gameMapPanel size to height = 11 * 32 + 2
    bottomSplitter:setMarginBottom(bottomSplitter:getMarginBottom() + (gameMapPanel:getHeight() - 32 * 11) - 10)
  end
end

function onMouseGrabberRelease(self, mousePosition, mouseButton)
  if selectedThing == nil then return false end
  if mouseButton == MouseLeftButton then
    local clickedWidget = gameRootPanel:recursiveGetChildByPos(mousePosition, false)
    if clickedWidget then
      if selectedType == 'use' then
        onUseWith(clickedWidget, mousePosition)
      elseif selectedType == 'trade' then
        onTradeWith(clickedWidget, mousePosition)
      end
    end
  end

  selectedThing = nil
  g_mouse.popCursor('target')
  self:ungrabMouse()
  gameMapPanel:blockNextMouseRelease(true)
  return true
end

function onUseWith(clickedWidget, mousePosition)
  if clickedWidget:getClassName() == 'UIGameMap' then
    local tile = clickedWidget:getTile(mousePosition)
    if tile then      
      if selectedThing:isFluidContainer() or selectedThing:isMultiUse() then      
        if selectedThing:getId() == 3180 or selectedThing:getId() == 3156 then
          -- special version for mwall
          g_game.useWith(selectedThing, tile:getTopUseThing(), selectedSubtype)      
        else
          g_game.useWith(selectedThing, tile:getTopMultiUseThingEx(clickedWidget:getPositionOffset(mousePosition)), selectedSubtype)
        end
      else
        g_game.useWith(selectedThing, tile:getTopUseThing(), selectedSubtype)
      end
    end
  elseif clickedWidget:getClassName() == 'UIItem' and not clickedWidget:isVirtual() then
    g_game.useWith(selectedThing, clickedWidget:getItem(), selectedSubtype)
  elseif clickedWidget:getClassName() == 'UICreatureButton' then
    local creature = clickedWidget:getCreature()
    if creature then
	  if creature:isMonster() then
		g_game.useWith(selectedThing, creature, selectedSubtype)
	  else
		modules.game_textmessage.displayFailureMessage(tr("Sorry, you can't shoot players on the battle window."))
	  end
    end
  end
end

function onTradeWith(clickedWidget, mousePosition)
  if clickedWidget:getClassName() == 'UIGameMap' then
    local tile = clickedWidget:getTile(mousePosition)
    if tile then
      g_game.requestTrade(selectedThing, tile:getTopCreatureEx(clickedWidget:getPositionOffset(mousePosition)))
    end
  elseif clickedWidget:getClassName() == 'UICreatureButton' then
    local creature = clickedWidget:getCreature()
    if creature then
      g_game.requestTrade(selectedThing, creature)
    end
  end
end

function startUseWith(thing, subType)
  gameMapPanel:blockNextMouseRelease()
  if not thing then return end
  if g_ui.isMouseGrabbed() then
    if selectedThing then
      selectedThing = thing
      selectedType = 'use'
    end
    return
  end
  selectedType = 'use'
  selectedThing = thing
  selectedSubtype = subType or 0
  mouseGrabberWidget:grabMouse()
  g_mouse.pushCursor('target')
end

function startTradeWith(thing)
  if not thing then return end
  if g_ui.isMouseGrabbed() then
    if selectedThing then
      selectedThing = thing
      selectedType = 'trade'
    end
    return
  end
  selectedType = 'trade'
  selectedThing = thing
  mouseGrabberWidget:grabMouse()
  g_mouse.pushCursor('target')
end

function isMenuHookCategoryEmpty(category)
  if category then
    for _,opt in pairs(category) do
      if opt then return false end
    end
  end
  return true
end

function addMenuHook(category, name, callback, condition, shortcut)
  if not hookedMenuOptions[category] then
    hookedMenuOptions[category] = {}
  end
  hookedMenuOptions[category][name] = {
    callback = callback,
    condition = condition,
    shortcut = shortcut
  }
end

function removeMenuHook(category, name)
  if not name then
    hookedMenuOptions[category] = {}
  else
    hookedMenuOptions[category][name] = nil
  end
end

function createThingMenu(menuPosition, lookThing, useThing, creatureThing)
  if not g_game.isOnline() then return end

  local menu = g_ui.createWidget('PopupMenu')
  menu:setGameMenu(true)

  local classic = modules.client_options.getOption('classicControl')
  local shortcut = nil

  if not classic then shortcut = '(Shift)' else shortcut = nil end
  if lookThing then
    menu:addOption(tr('Look'), function() g_game.look(lookThing) end, shortcut)
  end

  if not classic then shortcut = '(Ctrl)' else shortcut = nil end
  if useThing then
    if useThing:isContainer() then
      if useThing:getParentContainer() then
        menu:addOption(tr('Open'), function() g_game.open(useThing, useThing:getParentContainer()) end, shortcut)
        menu:addOption(tr('Open in new window'), function() g_game.open(useThing) end)
      else
        menu:addOption(tr('Open'), function() g_game.open(useThing) end, shortcut)
      end
    else
      if useThing:isMultiUse() then
        menu:addOption(tr('Use with ...'), function() startUseWith(useThing) end, shortcut)
      else
        menu:addOption(tr('Use'), function() g_game.use(useThing) end, shortcut)
      end
    end

    if useThing:isRotateable() then
      menu:addOption(tr('Rotate'), function() g_game.rotate(useThing) end)
    end

    if g_game.getFeature(GameBrowseField) and useThing:getPosition().x ~= 0xffff then
      menu:addOption(tr('Browse Field'), function() g_game.browseField(useThing:getPosition()) end)
    end
  end

  if lookThing and not lookThing:isCreature() and not lookThing:isNotMoveable() and lookThing:isPickupable() then
    menu:addSeparator()
    menu:addOption(tr('Trade with ...'), function() startTradeWith(lookThing) end)
  end

  if lookThing then
    local parentContainer = lookThing:getParentContainer()
    if parentContainer and parentContainer:hasParent() then
      menu:addOption(tr('Move up'), function() g_game.moveToParentContainer(lookThing, lookThing:getCount()) end)
    end
  end

  if creatureThing then
    local localPlayer = g_game.getLocalPlayer()
    menu:addSeparator()

    if creatureThing:isLocalPlayer() then
      menu:addOption(tr('Set Outfit'), function() g_game.requestOutfit() end)

      if creatureThing:isPartyMember() and creatureThing:isPartyLeader() then
        if creatureThing:isPartySharedExperienceActive() then
          menu:addOption(tr('Disable Shared Experience'), function() g_game.partyShareExperience(false) end)
        else
          menu:addOption(tr('Enable Shared Experience'), function() g_game.partyShareExperience(true) end)
        end
      end

      if MOUNTS_ENABLED and g_game.getFeature(GamePlayerMounts) then
        if not localPlayer:isMounted() then
          menu:addOption(tr('Mount'), function() localPlayer:mount() end)
        else
          menu:addOption(tr('Dismount'), function() localPlayer:dismount() end)
        end
      end
      
      if g_game.getFeature(GamePrey) and modules.game_prey then
        menu:addOption(tr('Open Prey Dialog'), function() modules.game_prey.show() end)
      end
      
      if creatureThing:isPartyMember() then
        menu:addOption(tr('Leave Party'), function() g_game.partyLeave() end)
      end

    else
      local localPosition = localPlayer:getPosition()
      if not classic then shortcut = '(Alt)' else shortcut = nil end
      if creatureThing:getPosition().z == localPosition.z then
        if g_game.getAttackingCreature() ~= creatureThing then
          menu:addOption(tr('Attack'), function() g_game.attack(creatureThing) end, shortcut)
        else
          menu:addOption(tr('Stop Attack'), function() g_game.cancelAttack() end, shortcut)
        end

        if g_game.getFollowingCreature() ~= creatureThing then
          menu:addOption(tr('Follow'), function() g_game.follow(creatureThing) end)
        else
          menu:addOption(tr('Stop Follow'), function() g_game.cancelFollow() end)
        end
      end

      if creatureThing:isPlayer() then
        menu:addSeparator()
        local creatureName = creatureThing:getName()
        menu:addOption(tr('Message to %s', creatureName), function() g_game.openPrivateChannel(creatureName) end)
        if modules.game_console.getOwnPrivateTab() then
          menu:addOption(tr('Invite to private chat'), function() g_game.inviteToOwnChannel(creatureName) end)
          menu:addOption(tr('Exclude from private chat'), function() g_game.excludeFromOwnChannel(creatureName) end) -- [TODO] must be removed after message's popup labels been implemented
        end
        if not localPlayer:hasVip(creatureName) then
          menu:addOption(tr('Add to VIP list'), function() g_game.addVip(creatureName) end)
        end

        if modules.game_console.isIgnored(creatureName) then
          menu:addOption(tr('Unignore') .. ' ' .. creatureName, function() modules.game_console.removeIgnoredPlayer(creatureName) end)
        else
          menu:addOption(tr('Ignore') .. ' ' .. creatureName, function() modules.game_console.addIgnoredPlayer(creatureName) end)
        end

        local localPlayerShield = localPlayer:getShield()
        local creatureShield = creatureThing:getShield()

        if localPlayerShield == ShieldNone or localPlayerShield == ShieldWhiteBlue then
          if creatureShield == ShieldWhiteYellow then
            menu:addOption(tr('Join %s\'s Party', creatureThing:getName()), function() g_game.partyJoin(creatureThing:getId()) end)
          else
            menu:addOption(tr('Invite to Party'), function() g_game.partyInvite(creatureThing:getId()) end)
          end
        elseif localPlayerShield == ShieldWhiteYellow then
          if creatureShield == ShieldWhiteBlue then
            menu:addOption(tr('Revoke %s\'s Invitation', creatureThing:getName()), function() g_game.partyRevokeInvitation(creatureThing:getId()) end)
          end
        elseif localPlayerShield == ShieldYellow or localPlayerShield == ShieldYellowSharedExp or localPlayerShield == ShieldYellowNoSharedExpBlink or localPlayerShield == ShieldYellowNoSharedExp then
          if creatureShield == ShieldWhiteBlue then
            menu:addOption(tr('Revoke %s\'s Invitation', creatureThing:getName()), function() g_game.partyRevokeInvitation(creatureThing:getId()) end)
          elseif creatureShield == ShieldBlue or creatureShield == ShieldBlueSharedExp or creatureShield == ShieldBlueNoSharedExpBlink or creatureShield == ShieldBlueNoSharedExp then
            menu:addOption(tr('Pass Leadership to %s', creatureThing:getName()), function() g_game.partyPassLeadership(creatureThing:getId()) end)
          else
            menu:addOption(tr('Invite to Party'), function() g_game.partyInvite(creatureThing:getId()) end)
          end
        end
      end
    end

    --if modules.game_ruleviolation.hasWindowAccess() and creatureThing:isPlayer() then
      --menu:addSeparator()
      --menu:addOption(tr('Rule Violation'), function() modules.game_ruleviolation.show(creatureThing:getName()) end)
    --end

    menu:addSeparator()
    menu:addOption(tr('Copy Name'), function() g_window.setClipboardText(creatureThing:getName()) end)
  end

  -- hooked menu options
  for _,category in pairs(hookedMenuOptions) do
    if not isMenuHookCategoryEmpty(category) then
      menu:addSeparator()
      for name,opt in pairs(category) do
        if opt and opt.condition(menuPosition, lookThing, useThing, creatureThing) then
          menu:addOption(name, function() opt.callback(menuPosition, 
            lookThing, useThing, creatureThing) end, opt.shortcut)
        end
      end
    end
  end

  if g_game.getFeature(GameBot) and useThing and useThing:isItem() then
    menu:addSeparator()
    if useThing:getSubType() > 1 then
      menu:addOption("ID: " .. useThing:getId() .. " SubType: " .. useThing:getSubType())    
    else
      menu:addOption("ID: " .. useThing:getId())
    end
  end

  menu:display(menuPosition)
end

function processMouseAction(menuPosition, mouseButton, autoWalkPos, lookThing, useThing, creatureThing, attackCreature, marking)
  local keyboardModifiers = g_keyboard.getModifiers()

  if not modules.client_options.getOption('classicControl') then
    if keyboardModifiers == KeyboardNoModifier and mouseButton == MouseRightButton then
      createThingMenu(menuPosition, lookThing, useThing, creatureThing)
      return true
    elseif lookThing and keyboardModifiers == KeyboardShiftModifier and (mouseButton == MouseLeftButton or mouseButton == MouseRightButton) then
      g_game.look(lookThing)
      return true
    elseif useThing and keyboardModifiers == KeyboardCtrlModifier and (mouseButton == MouseLeftButton or mouseButton == MouseRightButton) then
      if useThing:isContainer() then
        if useThing:getParentContainer() then
          g_game.open(useThing, useThing:getParentContainer())
        else
          g_game.open(useThing)
        end
        return true
      elseif useThing:isMultiUse() then
        startUseWith(useThing)
        return true
      else
        g_game.use(useThing)
        return true
      end
      return true
    elseif attackCreature and g_keyboard.isAltPressed() and (mouseButton == MouseLeftButton or mouseButton == MouseRightButton) then
      g_game.attack(attackCreature)
      return true
    elseif creatureThing and creatureThing:getPosition().z == autoWalkPos.z and g_keyboard.isAltPressed() and (mouseButton == MouseLeftButton or mouseButton == MouseRightButton) then
      g_game.attack(creatureThing)
      return true
    end

  -- classic control
  else
    if useThing and keyboardModifiers == KeyboardNoModifier and mouseButton == MouseRightButton and not g_mouse.isPressed(MouseLeftButton) then
      local player = g_game.getLocalPlayer()
      if attackCreature and attackCreature ~= player then
        g_game.attack(attackCreature)
        return true
      elseif creatureThing and creatureThing ~= player and creatureThing:getPosition().z == autoWalkPos.z then
        g_game.attack(creatureThing)
        return true
      elseif useThing:isContainer() then
        if useThing:getParentContainer() then
          g_game.open(useThing, useThing:getParentContainer())
          return true
        else
          g_game.open(useThing)
          return true
        end
      elseif useThing:isMultiUse() then
        startUseWith(useThing)
        return true
      else
        g_game.use(useThing)
        return true
      end
      return true
    elseif lookThing and keyboardModifiers == KeyboardShiftModifier and (mouseButton == MouseLeftButton or mouseButton == MouseRightButton) then
      g_game.look(lookThing)
      return true
    elseif lookThing and ((g_mouse.isPressed(MouseLeftButton) and mouseButton == MouseRightButton) or (g_mouse.isPressed(MouseRightButton) and mouseButton == MouseLeftButton)) then
      g_game.look(lookThing)
      return true
    elseif useThing and keyboardModifiers == KeyboardCtrlModifier and (mouseButton == MouseLeftButton or mouseButton == MouseRightButton) then
      createThingMenu(menuPosition, lookThing, useThing, creatureThing)
      return true
    elseif attackCreature and g_keyboard.isAltPressed() and (mouseButton == MouseLeftButton or mouseButton == MouseRightButton) then
      g_game.attack(attackCreature)
      return true
    elseif creatureThing and creatureThing:getPosition().z == autoWalkPos.z and g_keyboard.isAltPressed() and (mouseButton == MouseLeftButton or mouseButton == MouseRightButton) then
      g_game.attack(creatureThing)
      return true
    end
  end

  local player = g_game.getLocalPlayer()
  player:stopAutoWalk()  

  if autoWalkPos and keyboardModifiers == KeyboardNoModifier and mouseButton == MouseLeftButton then
    local autoWalkTile = g_map.getTile(autoWalkPos)
    if autoWalkTile and not autoWalkTile:isWalkable(true) then
      modules.game_textmessage.displayFailureMessage(tr('Sorry, not possible.'))
      return false
    end
    player:autoWalk(autoWalkPos)
    return true
  end

  return false
end

function moveStackableItem(item, toPos)
  if countWindow then
    return
  end
  if g_keyboard.isCtrlPressed() then
    g_game.move(item, toPos, item:getCount())
    return
  elseif g_keyboard.isShiftPressed() then
    g_game.move(item, toPos, 1)
    return
  end
  local count = item:getCount()

  countWindow = g_ui.createWidget('CountWindow', rootWidget)
  local itembox = countWindow:getChildById('item')
  local scrollbar = countWindow:getChildById('countScrollBar')
  itembox:setItemId(item:getId())
  itembox:setItemCount(count)
  scrollbar:setMaximum(count)
  scrollbar:setMinimum(1)
  scrollbar:setValue(count)

  local spinbox = countWindow:getChildById('spinBox')
  spinbox:setMaximum(count)
  spinbox:setMinimum(0)
  spinbox:setValue(0)
  spinbox:hideButtons()
  spinbox:focus()
  spinbox.firstEdit = true

  local spinBoxValueChange = function(self, value)
    spinbox.firstEdit = false
    scrollbar:setValue(value)
  end
  spinbox.onValueChange = spinBoxValueChange

  local check = function()
    if spinbox.firstEdit then
      spinbox:setValue(spinbox:getMaximum())
      spinbox.firstEdit = false
    end
  end
  local okButton = countWindow:getChildById('buttonOk')
  local moveFunc = function()
    g_game.move(item, toPos, itembox:getItemCount())
    okButton:getParent():destroy()
    countWindow = nil
  end
  local cancelButton = countWindow:getChildById('buttonCancel')
  local cancelFunc = function()
    cancelButton:getParent():destroy()
    countWindow = nil
  end

  
  g_keyboard.bindKeyPress("Up", function() check() spinbox:up() end, spinbox)
  g_keyboard.bindKeyPress("Down", function() check() spinbox:down() end, spinbox)
  g_keyboard.bindKeyPress("Right", function() check() spinbox:up() end, spinbox)
  g_keyboard.bindKeyPress("Left", function() check() spinbox:down() end, spinbox)
  g_keyboard.bindKeyPress("PageUp", function() check() spinbox:setValue(spinbox:getValue()+10) end, spinbox)
  g_keyboard.bindKeyPress("PageDown", function() check() spinbox:setValue(spinbox:getValue()-10) end, spinbox)
  g_keyboard.bindKeyPress("Enter", function() moveFunc() end, spinbox)

  scrollbar.onValueChange = function(self, value)
    itembox:setItemCount(value)
    spinbox.onValueChange = nil
    spinbox:setValue(value)
    spinbox.onValueChange = spinBoxValueChange
  end
  countWindow.onEnter = moveFunc
  countWindow.onEscape = cancelFunc

  okButton.onClick = moveFunc
  cancelButton.onClick = cancelFunc
end

function getRootPanel()
  return gameRootPanel
end

function getMapPanel()
  return gameMapPanel
end

function getRightPanel()
  if gameRightPanels:getChildCount() == 0 then
    addRightPanel()
  end
  return gameRightPanels:getChildByIndex(-1)
end

function getLeftPanel()
  if gameLeftPanels:getChildCount() >= 1 then
    return gameLeftPanels:getChildByIndex(-1)
  end
  return getRightPanel()
end

function getContainerPanel()
  local containerPanel = g_settings.getNumber("containerPanel")
  if containerPanel >= 5 then
    containerPanel = containerPanel - 4
    return gameRightPanels:getChildByIndex(math.min(containerPanel, gameRightPanels:getChildCount()))
  end
  if gameLeftPanels:getChildCount() == 0 then
    return getRightPanel()
  end
  return gameLeftPanels:getChildByIndex(math.min(containerPanel, gameLeftPanels:getChildCount()))
end

local function addRightPanel()
  if gameRightPanels:getChildCount() >= 4 then
    return
  end
  local panel = g_ui.createWidget('GameSidePanel')
  panel:setId("rightPanel" .. (gameRightPanels:getChildCount() + 1))
  gameRightPanels:insertChild(1, panel)
end

local function addLeftPanel()
  if gameLeftPanels:getChildCount() >= 4 then
    return
  end
  local panel = g_ui.createWidget('GameSidePanel')
  panel:setId("leftPanel" .. (gameLeftPanels:getChildCount() + 1))
  gameLeftPanels:addChild(panel)
end

local function removeRightPanel()
  if gameRightPanels:getChildCount() <= 1 then
    return
  end
  local panel = gameRightPanels:getChildByIndex(1)
  panel:moveTo(gameRightPanels:getChildByIndex(2))
  gameRightPanels:removeChild(panel)
end

local function removeLeftPanel()
  if gameLeftPanels:getChildCount() == 0 then
    return
  end
  local panel = gameLeftPanels:getChildByIndex(-1)
  if gameLeftPanels:getChildCount() >= 2 then
    panel:moveTo(gameLeftPanels:getChildByIndex(-2))
  else
    panel:moveTo(gameRightPanels:getChildByIndex(1))
  end
  gameLeftPanels:removeChild(panel)
end

function getBottomPanel()
  return gameBottomPanel
end

function refreshViewMode()  
  local classic = g_settings.getBoolean("classicView")
  local rightPanels = g_settings.getNumber("rightPanels") - gameRightPanels:getChildCount()
  local leftPanels = g_settings.getNumber("leftPanels") - 1 - gameLeftPanels:getChildCount()

  while rightPanels ~= 0 do
    if rightPanels > 0 then
      addRightPanel()
      rightPanels = rightPanels - 1
    else
      removeRightPanel()
      rightPanels = rightPanels + 1
    end
  end
  while leftPanels ~= 0 do
    if leftPanels > 0 then
      addLeftPanel()
      leftPanels = leftPanels - 1
    else
      removeLeftPanel()
      leftPanels = leftPanels + 1
    end
  end
  
  if not g_game.isOnline() then
    return
  end

  local minimumWidth = (g_settings.getNumber("rightPanels") + g_settings.getNumber("leftPanels") - 1) * 200 + 200
  if classic then
    minimumWidth = minimumWidth + 400
  end
  minimumWidth = math.max(minimumWidth, 800)
  g_window.setMinimumSize({ width = minimumWidth, height = 600 })
  if g_window.getWidth() < minimumWidth then
    local oldPos = g_window.getPosition()
    local size = { width = minimumWidth, height = g_window.getHeight() }
    g_window.resize(size)
    g_window.move(oldPos)
  end

  for i=1,gameRightPanels:getChildCount()+gameLeftPanels:getChildCount() do
    local panel
    if i > gameRightPanels:getChildCount() then
      panel = gameLeftPanels:getChildByIndex(i - gameRightPanels:getChildCount())
    else
      panel = gameRightPanels:getChildByIndex(i)
    end
    if classic then
      panel:setImageColor('white')
    else
      panel:setImageColor('alpha')
    end
  end
  
  if classic then
    gameRightPanels:setMarginTop(0)
    gameLeftPanels:setMarginTop(0)
    gameMapPanel:setMarginLeft(0)
    gameMapPanel:setMarginRight(0)
    gameMapPanel:setMarginTop(0)
  end

  gameMapPanel:setVisibleDimension({ width = 15, height = 11 })
  
  if classic then  
    gameRootPanel:addAnchor(AnchorTop, 'topMenu', AnchorBottom)
    gameMapPanel:addAnchor(AnchorLeft, 'gameLeftPanels', AnchorRight)
    gameMapPanel:addAnchor(AnchorRight, 'gameRightPanels', AnchorLeft)
    gameMapPanel:addAnchor(AnchorBottom, 'gameBottomPanel', AnchorTop)    
    gameMapPanel:setKeepAspectRatio(true)
    gameMapPanel:setLimitVisibleRange(false)
    gameMapPanel:setZoom(11)
	gameMapPanel:setOn(false) -- frame

    gameBottomPanel:addAnchor(AnchorLeft, 'gameLeftPanels', AnchorRight)
    gameBottomPanel:addAnchor(AnchorRight, 'gameRightPanels', AnchorLeft)
    
    modules.client_topmenu.getTopMenu():setImageColor('white')
    gameBottomPanel:setImageColor('white')
  
    if modules.game_console then
      modules.game_console.switchMode(false)
    end
  else
    gameMapPanel:fill('parent')
    gameRootPanel:fill('parent')
    gameMapPanel:setKeepAspectRatio(false)
    gameMapPanel:setLimitVisibleRange(false)
	gameMapPanel:setOn(true)
    gameMapPanel:setZoom(15)
               
    modules.client_topmenu.getTopMenu():setImageColor('#ffffff66')  
    
    if modules.game_console then
      modules.game_console.switchMode(true)
    end
  end
  if modules.game_actionbar then
    modules.game_actionbar.switchMode(not classic)    
  end
  
  if g_settings.getBoolean("cacheMap") then
    g_game.enableFeature(GameBiggerMapCache)
  end
  
  updateSize()
end

function limitZoom()
  limitedZoom = true
end

function onViewportRange(width, height)
  -- OTCv8 sends the range excluding the extra east/south buffer tiles.
  if type(width) ~= 'number' or type(height) ~= 'number' then return end
  viewportAcknowledged = {width = width, height = height}
  viewportPending = nil
  removeEvent(viewportEvent)
  viewportEvent = scheduleEvent(function()
    viewportEvent = nil
    updateSize()
  end, 1)
end

function updateMapViewport()
  if viewportBusy or not gameMapPanel then return end
  viewportBusy = true
  local rect = gameMapPanel:getPaddingRect()
  local dimension = AntigasViewport.calculate(rect.width - 2, rect.height - 2,
    modules.client_options.getOption('gameView'))
  local supported = g_game.isOnline() and g_game.getFeature(GameChangeMapAwareRange)
  local wantedWidth, wantedHeight = AntigasViewport.requestSize(dimension)
  local ready = supported and viewportAcknowledged.width >= wantedWidth and
    viewportAcknowledged.height >= wantedHeight

  -- Until the extended map arrives, retain the complete classic view.
  local render = ready and dimension or {width = 15, height = 11, wide = false}
  gameMapPanel:setMaxZoomOut(AntigasViewport.maxHeight)
  gameMapPanel:setLimitVisibleRange(false)
  gameMapPanel:setKeepAspectRatio(not render.wide)
  gameMapPanel:setVisibleDimension({width = render.width, height = render.height})
  gameMapPanel:setZoom(render.height)
  viewportBusy = false

  if supported and (viewportAcknowledged.width ~= wantedWidth or viewportAcknowledged.height ~= wantedHeight) then
    removeEvent(viewportEvent)
    local delay = math.max(250, 800 - (g_clock.millis() - viewportLastRequest))
    viewportEvent = scheduleEvent(function()
      viewportEvent = nil
      if not g_game.isOnline() then return end
      viewportPending = {width = wantedWidth, height = wantedHeight}
      viewportLastRequest = g_clock.millis()
      g_game.changeMapAwareRange(wantedWidth, wantedHeight)
      -- A resize request may have hit the server cooldown. Retry the latest
      -- geometry, not a captured obsolete rectangle.
      viewportEvent = scheduleEvent(function() viewportEvent = nil updateSize() end, 1000)
    end, delay)
  elseif not viewportPending then
    removeEvent(viewportEvent)
    viewportEvent = nil
  end
end

function updateSize()
  if viewportBusy or not gameMapPanel then return end
  local classic = g_settings.getBoolean("classicView")
  local height = gameMapPanel:getHeight()
  local width = gameMapPanel:getWidth()
     
  if classic then
    updateMapViewport()
  else
    local rheight = gameRootPanel:getHeight()
    local rwidth = gameRootPanel:getWidth()

    local dimenstion = gameMapPanel:getVisibleDimension()  
    local zoom = gameMapPanel:getZoom()  
    local awareRange = g_map.getAwareRange()
    local dheight = dimenstion.height
    local dwidth = dimenstion.width
    local tileSize = rheight / dheight
    local maxWidth = tileSize * (awareRange.width + 1)
    if g_game.getFeature(GameChangeMapAwareRange) and g_game.getFeature(GameNewWalking) then
      maxWidth = tileSize * (awareRange.width - 1)
    end
    gameMapPanel:setMarginTop(-tileSize)
    if modules.game_stats then
      modules.game_stats.ui:setMarginTop(tileSize)
    end
    if g_settings.getBoolean("cacheMap") then
      gameMapPanel:setMarginLeft(0)
      gameMapPanel:setMarginRight(0)    
    else
      local margin = math.max(0, math.floor((rwidth - maxWidth) / 2))
      gameMapPanel:setMarginLeft(margin)
      gameMapPanel:setMarginRight(margin)
    end
    
    if modules.game_textmessage then
      modules.game_textmessage.messagesPanel:setMarginTop(-gameMapPanel:getMarginTop())
    end
    
  end
  
    --[[
  local maxWidth = math.floor(height * 2)
  local extraMargin = 0
  if width >= maxWidth then
    extraMargin = math.ceil((width - maxWidth) / 2)
  end
  local bottomMaxWidth = 1200  -- something broken, it's not pixels
  local bottomMargin = 0
  if width > bottomMaxWidth then
    bottomMargin = math.ceil((width - bottomMaxWidth) / 2)
  end
  gameMapPanel:setMarginLeft(extraMargin)
  gameMapPanel:setMarginRight(extraMargin) ]]
end

function setupLeftActions()
  if not g_app.isMobile() then return end
  for _, widget in ipairs(gameLeftActions:getChildren()) do
    widget.image:setChecked(false)
    widget.lastClicked = 0
    widget.onClick = function()
      if widget.image:isChecked() then
        widget.image:setChecked(false)
        if widget.doubleClickAction and widget.lastClicked + 200 > g_clock.millis() then
          widget.doubleClickAction()
        end
        return
      end
      resetLeftActions()
      widget.image:setChecked(true)
      widget.lastClicked = g_clock.millis()
    end
  end
  if gameLeftActions.use then
    gameLeftActions.use.doubleClickAction = function()
      local player = g_game.getLocalPlayer()
      local dir = player:getDirection()
      local usePos = player:getPrewalkingPosition(true)
      if dir == North then
        usePos.y = usePos.y - 1
      elseif dir == East then
        usePos.x = usePos.x + 1
      elseif dir == South then
        usePos.y = usePos.y + 1
      elseif dir == West then
        usePos.x = usePos.x - 1
      end
      local tile = g_map.getTile(usePos)
      if not tile then return end
      local thing = tile:getTopUseThing()
      if thing then
        g_game.use(thing)
      end
    end
  end
  if gameLeftActions.attack then
    gameLeftActions.attack.doubleClickAction = function()
      local battlePanel = modules.game_battle.battlePanel
      local attackedCreature = g_game.getAttackingCreature()
      local child = battlePanel:getFirstChild()
      if child and (not child.creature or not child:isOn()) then
        child = nil
      end
      if child then
        g_game.attack(child.creature)
      else
        g_game.attack(nil)
      end
    end
  end
  if gameLeftActions.follow then
    gameLeftActions.follow.doubleClickAction = function()
      local battlePanel = modules.game_battle.battlePanel
      local attackedCreature = g_game.getAttackingCreature()
      local child = battlePanel:getFirstChild()
      if child and (not child.creature or not child:isOn()) then
        child = nil
      end
      if child then
        g_game.follow(child.creature)
      else
        g_game.follow(nil)
      end
    end
  end
  if gameLeftActions.look then
    gameLeftActions.look.doubleClickAction = function()
      local battlePanel = modules.game_battle.battlePanel
      local attackedCreature = g_game.getAttackingCreature()
      local child = battlePanel:getFirstChild()
      if child and (not child.creature or child:isHidden()) then
        child = nil
      end
      if child then
        g_game.look(child.creature)
      end
    end
  end  
  if not gameLeftActions.chat then return end
  gameLeftActions.chat.onClick = function()
    if gameBottomPanel:getHeight() <= 5 then
      gameBottomPanel:setHeight(90)
    else
      gameBottomPanel:setHeight(0)    
    end
  end
end

function resetLeftActions()
  for _, widget in ipairs(gameLeftActions:getChildren()) do
    widget.image:setChecked(false)
    widget.lastClicked = 0
  end
end

function getLeftAction()
  for _, widget in ipairs(gameLeftActions:getChildren()) do
    if widget.image:isChecked() then
      return widget:getId()
    end
  end
  return ""
end

function isChatVisible()
  return gameBottomPanel:getHeight() >= 5
end
