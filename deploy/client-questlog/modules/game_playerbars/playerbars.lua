playerBarsWindow = nil
skillsButton = nil
battleButton = nil
vipButton = nil
logoutButton = nil
huntButton = nil
marketButton = nil

local bindings = {}
local syncing = false
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
  if not playerBarsWindow or not marketButton then return end
  local buttons = {skillsButton, battleButton, vipButton, huntButton}
  -- Six-pixel outer margins and three-pixel gaps. Keep the original font;
  -- give longer labels more room instead of shrinking or abbreviating them.
  local usable = playerBarsWindow:getWidth() - 12 - 9
  local widths, minimum = {}, 0
  for i, button in ipairs(buttons) do
    widths[i] = math.max(18, button:getTextSize().width + 6)
    minimum = minimum + widths[i]
  end
  local spare = math.max(0, usable - minimum)
  for i, button in ipairs(buttons) do
    local extra = math.floor(spare / (#buttons - i + 1))
    button:setWidth(widths[i] + extra)
    spare = spare - extra
  end
  local serviceWidth=playerBarsWindow:getWidth()-12-3
  marketButton:setWidth(math.floor(serviceWidth/2))
  playerBarsWindow:recursiveGetChildById('questButton'):setWidth(serviceWidth-math.floor(serviceWidth/2))
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
   
    -- Anti-steal code
  if (REGISTRATION_KEY ~= "AbcDeFgH") then
	g_logger.fatal("Invalid serial ID for the server, please contact julianandresbernalv@gmail.com or JulianBernalV#7033")
  end
	
	playerBarsWindow:getChildById('contentsPanel'):setMarginTop(10)
  
	playerBarsWindow:open()
	playerBarsWindow:setup()
  resizeButtons()
end

function terminate()
  for _,name in ipairs({'skills', 'battle', 'vip', 'hunt'}) do unbindPanel(name) end
	disconnect(g_game, {
		onGameStart = online,
		onGameEnd = offline
	})

	playerBarsWindow:destroy()
  playerBarsWindow, skillsButton, battleButton, vipButton, huntButton, marketButton = nil, nil, nil, nil, nil, nil
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
