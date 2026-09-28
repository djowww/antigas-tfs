playerBarsWindow = nil
skillsButton = nil
battleButton = nil
vipButton = nil
logoutButton = nil
huntButton = nil
marketButton = nil
achievementsButton = nil

local bindings = {}
local syncing = false
local achievementUnread = 0
local targets = {skills = 'game_skills', battle = 'game_battle', vip = 'game_viplist', hunt = 'game_lootstatistics'}

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
  if not playerBarsWindow or not marketButton or not achievementsButton then return end
  local buttons = {skillsButton, battleButton, vipButton, huntButton}
  local width = playerBarsWindow:getWidth()
  -- The UI uses integer pixels. An odd container needs an odd gap to keep
  -- four equal columns AND identical outer margins; otherwise prefer 2 px.
  local gap = 2 + width % 2
  local columnWidth = math.floor((width - 2 * 6 - 3 * gap) / 4)
  local gridWidth = 4 * columnWidth + 3 * gap
  for i, button in ipairs(buttons) do
    button:setWidth(columnWidth)
    -- Right/bottom sibling anchors refer to the last pixel, not the next one.
    button:setMarginLeft(i == 1 and (width - gridWidth) / 2 or gap + 1)
  end
  -- Service buttons span the corresponding pair via sibling anchors in OTUI.
  marketButton:setMarginTop(gap + 1)
  achievementsButton:setMarginTop(gap + 1)
  local contents = playerBarsWindow:getChildById('contentsPanel')
  local height = contents:getMarginTop() + contents:getMarginBottom() + 2 * 5 + 3 * skillsButton:getHeight() + 2 * gap
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
  playerBarsWindow, skillsButton, battleButton, vipButton, huntButton, marketButton, achievementsButton = nil, nil, nil, nil, nil, nil, nil
end

function updateMenuToggle()
  if not playerBarsWindow then return end
  local button = playerBarsWindow:getChildById('menuToggle')
  if not button then return end
  local collapsed = playerBarsWindow:isOn()
  local badge = achievementUnread > 0 and (' [' .. achievementUnread .. ']') or ''
  button:setText('Menu' .. badge .. (collapsed and ' [+]' or ' [-]'))
  button:setTooltip(collapsed and 'Expand menu' or 'Minimize menu')
  button:setColor(achievementUnread > 0 and '#ffd36a' or '#e2d4b2')
end

function toggleMenu()
  if not playerBarsWindow then return end
  if playerBarsWindow:isOn() then playerBarsWindow:maximize()
  else playerBarsWindow:minimize() end
end

function setAchievementsUnread(count)
  achievementUnread = math.max(0, tonumber(count) or 0)
  if achievementsButton then
    achievementsButton:setText(achievementUnread > 0 and ('Achievements  [' .. achievementUnread .. ']') or 'Achievements')
    achievementsButton:setColor(achievementUnread > 0 and '#ffd36a' or '#c6c6c6')
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
