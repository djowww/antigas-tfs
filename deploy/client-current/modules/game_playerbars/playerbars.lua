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
local toolbarIconSize = 12 -- Keep in sync with the icon sizes in playerbars.otui.
local targets = {skills = 'game_skills', battle = 'game_battle', vip = 'game_viplist', hunt = 'game_lootstatistics'}

-- Each classic glyph stays on a 12 px grid: highlight, face, shadow, or transparent.
-- Adjacent pixels of one shade share a rectangle, keeping the static UI bounded.
local glyphPatterns = {
  skills = {
    '............',
    '.........h..',
    '........hf..',
    '.......hfs..',
    '......hfs...',
    '.....hfs....',
    '..h.hfs.....',
    '...hfs......',
    '..sfhf......',
    '..ffs.h.....',
    '.hfs........',
    '..s.........'
  },
  battle = {
    'h..........h',
    'fh........hf',
    'sfh......hfs',
    '.sfh....hfs.',
    '..sfh..hfs..',
    '...sfhhfs...',
    '....hffs....',
    '...hfsfh....',
    '..hf..hfs...',
    '.hf....hfs..',
    '..s......s..',
    '............'
  },
  vip = {
    '............',
    '...hh..hh...',
    '..hffshffs..',
    '..hffshffs..',
    '...ss..ss...',
    '..hhh..hhh..',
    '.hffsshffss.',
    '.hffsshffss.',
    '.hffsshffss.',
    '..sss..sss..',
    '............',
    '............'
  },
  hunt = {
    '.....h......',
    '...hhfhh....',
    '..hf...fs...',
    '.hf.....fs..',
    '.h...h...s..',
    'hf..hfhs..fs',
    '.f...s...s..',
    '.hf.....fs..',
    '..hf...fs...',
    '...ssfss....',
    '.....s......',
    '............'
  },
  market = {
    '............',
    '....hhhh....',
    '...hffffs...',
    '...sfffss...',
    '...sssss....',
    '.hhhhhhhh...',
    'hffffffffs..',
    'sffffffsss..',
    'shhhhhhhss..',
    'sffffffsss..',
    '.ssssssss...',
    '............'
  },
  quest = {
    '..hhhhhhh...',
    '.hfffffffs..',
    '.hfsfffhfs..',
    '..fsfffsfs..',
    '..fhfffhfs..',
    '..fsfffsfs..',
    '..fhfffhfs..',
    '..fsfffsfs..',
    '..fffffhfs..',
    '.hfffffhss..',
    '.sssssssss..',
    '............'
  },
  achievements = {
    '............',
    '.....h......',
    '....hfs.....',
    '....hfs.....',
    '.hhhhfhhhh..',
    '..hfffffs...',
    '...hfffs....',
    '..hfffffs...',
    '..hfssffs...',
    '.hf....ffs..',
    '.s......ss..',
    '............'
  }
}

local glyphPalettes = {
  normal = {f = '#AAA99E', h = '#DDD8C6', s = '#24251F'},
  hover = {f = '#C0BDB0', h = '#F0EADA', s = '#30312B'},
  selected = {f = '#BCA473', h = '#DAC6A0', s = '#29271F'},
  selectedHover = {f = '#CFB782', h = '#EBD7AC', s = '#302B22'},
  pressed = {f = '#85867D', h = '#B1AEA2', s = '#1E201B'},
  selectedPressed = {f = '#98855F', h = '#B7A887', s = '#22231F'},
  disabled = {f = '#686B63', h = '#8C8C81', s = '#2A2B26'}
}

function refreshGlyph(button)
  if not button or button:isDestroyed() then return end
  local entry = button.antigasToolbarGlyph
  if not entry then return end

  local selected = button:isChecked() or button:isOn()
  local palette
  if not button:isEnabled() then
    palette = glyphPalettes.disabled
  elseif button:isPressed() then
    palette = selected and glyphPalettes.selectedPressed or glyphPalettes.pressed
  elseif selected then
    palette = button:isHovered() and glyphPalettes.selectedHover or glyphPalettes.selected
  else
    palette = button:isHovered() and glyphPalettes.hover or glyphPalettes.normal
  end
  if entry.palette == palette then return end
  entry.palette = palette
  for tone, rectangles in pairs(entry.pixels) do
    for _, rectangle in ipairs(rectangles) do
      rectangle:setBackgroundColor(palette[tone])
    end
  end
end

local function positionGlyph(button, width)
  local entry = button.antigasToolbarGlyph
  if not entry then return end
  -- Native centers use inclusive pixel bounds. Correct odd widths to retain the
  -- original floor((width - 12) / 2) position instead of shifting one pixel right.
  local centerCorrection = (width - toolbarIconSize) % 2 == 0 and 0 or -1
  entry.root:setMarginLeft(centerCorrection)
  entry.root:setMarginTop(centerCorrection + (button == achievementsButton and -1 or 0))
end

local function createGlyph(button, name)
  if not button or button.antigasToolbarGlyph then return end
  local root = g_ui.createWidget('UIWidget', button)
  root:setId('toolbarGlyph')
  root:setPhantom(true)
  root:setFocusable(false)
  root:setSize({width = toolbarIconSize, height = toolbarIconSize})
  root:addAnchor(AnchorHorizontalCenter, 'parent', AnchorHorizontalCenter)
  root:addAnchor(AnchorVerticalCenter, 'parent', AnchorVerticalCenter)
  local entry = {root = root, pixels = {h = {}, f = {}, s = {}}}

  for y, row in ipairs(glyphPatterns[name]) do
    local x = 1
    while x <= toolbarIconSize do
      local tone = row:sub(x, x)
      local finish = x
      while finish < toolbarIconSize and row:sub(finish + 1, finish + 1) == tone do
        finish = finish + 1
      end
      if entry.pixels[tone] then
        local rectangle = g_ui.createWidget('UIWidget', root)
        rectangle:setPhantom(true)
        rectangle:setFocusable(false)
        rectangle:setSize({width = finish - x + 1, height = 1})
        rectangle:addAnchor(AnchorLeft, 'parent', AnchorLeft)
        rectangle:addAnchor(AnchorTop, 'parent', AnchorTop)
        rectangle:setMarginLeft(x - 1)
        rectangle:setMarginTop(y - 1)
        table.insert(entry.pixels[tone], rectangle)
      end
      x = finish + 1
    end
  end
  -- Native Lua fields are shared across callback wrappers. The button owns this
  -- strong entry and its children; destruction needs no registry or timer cleanup.
  button.antigasToolbarGlyph = entry
  -- Inherited signals may be shared tables. Detach this button's handler list
  -- before connect appends to it, preserving class callbacks such as tooltips.
  local styleCallbacks = button.onStyleApply
  if type(styleCallbacks) == 'table' then
    local ownCallbacks = {}
    for key, callback in pairs(styleCallbacks) do
      ownCallbacks[key] = callback
    end
    button.onStyleApply = ownCallbacks
  end
  connect(button, {onStyleApply = refreshGlyph})
  positionGlyph(button, button:getWidth())
  refreshGlyph(button)
end

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
    -- Keep the static 12 px glyph at the original responsive icon offsets.
    positionGlyph(button, buttonWidth)
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
  createGlyph(skillsButton, 'skills')
  createGlyph(battleButton, 'battle')
  createGlyph(vipButton, 'vip')
  createGlyph(huntButton, 'hunt')
  createGlyph(marketButton, 'market')
  createGlyph(questButton, 'quest')
  createGlyph(achievementsButton, 'achievements')
end

function terminate()
  for _, button in ipairs({skillsButton, battleButton, vipButton, huntButton, marketButton, questButton, achievementsButton}) do
    if button.antigasToolbarGlyph then
      -- createGlyph gave this button its own signal list; class handlers stay intact.
      disconnect(button, {onStyleApply = refreshGlyph})
    end
  end
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
  local unreadHint = achievementUnread > 0 and (' (' .. achievementUnread .. ' new)') or ''
  button:setOn(collapsed)
  button:setTooltip((collapsed and 'Expand toolbar' or 'Collapse toolbar') .. unreadHint)
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
    local unreadHint = achievementUnread > 0 and (': ' .. achievementUnread .. ' new') or ''
    achievementsButton:setTooltip('Achievements' .. unreadHint)
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
