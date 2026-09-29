playerBarsWindow = nil
skillsButton = nil
battleButton = nil
vipButton = nil
logoutButton = nil
huntButton = nil
marketButton = nil
questButton = nil
achievementsButton = nil

local bindings = {}
local syncing = false
local achievementUnread = 0
local targets = {skills = 'game_skills', battle = 'game_battle', vip = 'game_viplist', hunt = 'game_lootstatistics'}

function setActionSelected(name, selected)
  local buttons = {market = marketButton, quest = questButton, achievements = achievementsButton}
  local button = buttons[name]
  if button then button:setOn(selected == true) end
end

function syncPanel(name)
  local entry = bindings[name]
  if not entry then return end
  local opened = g_game.isOnline() and entry.window:isExplicitlyVisible()
  syncing = true
  entry.button:setChecked(opened)
  if entry.topButton then entry.topButton:setOn(opened) end
  syncing = false
end

function unbindPanel(name)
  local entry = bindings[name]
  if not entry then return end
  disconnect(entry.window, entry.events)
  syncing = true
  entry.button:setChecked(false)
  syncing = false
  bindings[name] = nil
end

function bindPanel(name, window, topButton)
  unbindPanel(name)
  local buttons = {skills = skillsButton, battle = battleButton, vip = vipButton, hunt = huntButton}
  if not buttons[name] then return end
  local events = {
    onVisibilityChange = function() syncPanel(name) end,
    onDestroy = function() unbindPanel(name) end
  }
  bindings[name] = {window = window, button = buttons[name], topButton = topButton, events = events}
  connect(window, events)
  syncPanel(name)
end

function togglePanel(name)
  if syncing then return end
  if not g_game.isOnline() then syncPanel(name) return end
  local target = targets[name] and modules[targets[name]]
  if target and target.toggle then target.toggle() end
  syncPanel(name)
end

function resizeButtons()
  if not playerBarsWindow or not skillsButton or not questButton or not achievementsButton then return end
  local buttons = {skillsButton, battleButton, vipButton, huntButton, marketButton, questButton, achievementsButton}
  local toggle = playerBarsWindow:getChildById('menuToggle')
  local separator = playerBarsWindow:getChildById('menuSeparator')
  if not toggle or not separator then return end
  local width = playerBarsWindow:getWidth()
  local gap = 1
  -- Reserve room for the divider and minimize control before sizing the icons.
  local fixedWidth = (#buttons - 1) * (gap + 1) + 3 + separator:getWidth()
    + separator:getMarginRight() + toggle:getWidth()
  local buttonWidth = math.max(16, math.min(22, math.floor((width - fixedWidth) / #buttons)))
  local toolbarWidth = #buttons * buttonWidth + fixedWidth
  local leftMargin = math.max(0, math.floor((width - toolbarWidth) / 2))
  local rightMargin = math.max(0, width - toolbarWidth - leftMargin)
  for index, button in ipairs(buttons) do
    button:setWidth(buttonWidth)
    button:setHeight(buttonWidth)
    -- Icon-size defines a fixed draw rectangle from the button's top-left.
    -- Move that rectangle to the center whenever responsive sizing changes.
    local iconOffset = math.floor((buttonWidth - 14) / 2)
    button:setIconOffsetX(iconOffset)
    button:setIconOffsetY(iconOffset)
    -- Sibling right anchors refer to the last pixel, not the next one.
    button:setMarginLeft(index == 1 and leftMargin or gap + 1)
  end
  toggle:setMarginRight(rightMargin)
  local contents = playerBarsWindow:getChildById('contentsPanel')
  local height = contents:getMarginTop() + contents:getMarginBottom() + skillsButton:getHeight()
  local visibleHeight = playerBarsWindow:isOn() and playerBarsWindow.minimizedHeight or height
  toggle:setMarginTop(math.floor((visibleHeight - toggle:getHeight()) / 2))
  -- Preserve UIMiniWindow's collapsed title-bar height during geometry changes.
  if not playerBarsWindow:isOn() and contents:isVisible() and playerBarsWindow:getHeight() ~= height then
    playerBarsWindow:setHeight(height)
  end
end

function init()
	connect(g_game, {
		onGameStart = online,
		onGameEnd = offline
	})

	playerBarsWindow = g_ui.loadUI('playerbars', modules.game_interface.getRightPanel())
	playerBarsWindow:disableResize()

	skillsButton = playerBarsWindow:recursiveGetChildById('SkillsButton')
	battleButton = playerBarsWindow:recursiveGetChildById('BattleButton')
	vipButton = playerBarsWindow:recursiveGetChildById('VipButton')
	huntButton = playerBarsWindow:recursiveGetChildById('huntButton')
  marketButton = playerBarsWindow:recursiveGetChildById('marketButton')
  questButton = playerBarsWindow:recursiveGetChildById('questButton')
  achievementsButton = playerBarsWindow:recursiveGetChildById('achievementsButton')

    -- Anti-steal code
  if (REGISTRATION_KEY ~= "AbcDeFgH") then
	g_logger.fatal("Invalid serial ID for the server, please contact julianandresbernalv@gmail.com or JulianBernalV#7033")
  end

	playerBarsWindow:open()
	playerBarsWindow:setup()
  resizeButtons()
  updateMenuToggle()
end

function terminate()
  for _,name in ipairs({'skills', 'battle', 'vip', 'hunt'}) do unbindPanel(name) end
	disconnect(g_game, {
		onGameStart = online,
		onGameEnd = offline
	})

	playerBarsWindow:destroy()
  playerBarsWindow, skillsButton, battleButton, vipButton, huntButton, marketButton, questButton, achievementsButton = nil, nil, nil, nil, nil, nil, nil, nil
end

function updateMenuToggle()
  if not playerBarsWindow then return end
  local button = playerBarsWindow:getChildById('menuToggle')
  if not button then return end
  local collapsed = playerBarsWindow:isOn()
  local unreadHint = achievementUnread > 0 and (' (' .. achievementUnread .. ' '
    .. (achievementUnread == 1 and 'nova' or 'novas') .. ')') or ''
  button:setOn(collapsed)
  button:setTooltip((collapsed and 'Expandir barra' or 'Recolher barra') .. unreadHint)
  button:getChildById('menuUnreadIndicator'):setVisible(achievementUnread > 0)
  resizeButtons()
end

function toggleMenu()
  if not playerBarsWindow then return end
  if playerBarsWindow:isOn() then playerBarsWindow:maximize()
  else playerBarsWindow:minimize() end
end

function setAchievementsUnread(count)
  achievementUnread = math.max(0, tonumber(count) or 0)
  if achievementsButton then
    local unreadHint = achievementUnread > 0 and (': ' .. achievementUnread
      .. (achievementUnread == 1 and ' nova' or ' novas')) or ''
    achievementsButton:setTooltip('Conquistas' .. unreadHint)
    achievementsButton:getChildById('achievementsUnreadIndicator'):setVisible(achievementUnread > 0)
  end
  updateMenuToggle()
end

function offline()
  syncing = true
  for _,button in ipairs({skillsButton, battleButton, vipButton, huntButton}) do button:setChecked(false) end
  syncing = false
end

function online()
  for name in pairs(bindings) do syncPanel(name) end
end

function getCheckedButtons(button)
	if button:isChecked() then
		return 1
	else
		return nil
	end
end

function onMiniWindowClose()
  playerBarsWindow:open()
end
