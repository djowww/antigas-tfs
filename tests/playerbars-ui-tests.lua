local function clientFile(relative)
  for _, prefix in ipairs({'Cliente/', '../../Cliente/', 'deploy/client-current/', 'Servidor/TFS/deploy/client-current/'}) do
    local path = prefix .. relative
    local file = io.open(path, 'r')
    if file then file:close(); return path end
  end
  error('Client file not found: ' .. relative)
end

-- Read actual inherited and instance children. The regression created two
-- minimizeButton widgets; setup bound the invisible one, leaving the icon inert.
local function readOTUI(relative)
  local file = assert(io.open(clientFile(relative), 'r'))
  local text = file:read('*a'):gsub('\r\n', '\n')
  file:close()
  local root = {indent=-1, children={}}
  local stack = {root}
  for line in (text .. '\n'):gmatch('(.-)\n') do
    local spacing, value = line:match('^(%s*)(.-)%s*$')
    if value ~= '' and value:sub(1, 2) ~= '//' then
      local indent = #spacing
      while stack[#stack].indent >= indent do table.remove(stack) end
      local parent = stack[#stack]
      local key, property = value:match('^([^:]+):%s*(.*)$')
      if key and key:sub(1, 1) ~= '$' then
        parent.props[key] = property
      else
        local name, base = value:match('^(%w+)%s*<%s*(%w+)$')
        local node = {name=name or value, base=base, state=key ~= nil,
          indent=indent, props={}, children={}}
        parent.children[#parent.children+1] = node
        stack[#stack+1] = node
      end
    end
  end
  return root.children
end

local styles, windowNode = {}, nil
for _, relative in ipairs({'data/styles/30-special_miniwindow.otui', 'modules/game_playerbars/playerbars.otui'}) do
  for _, node in ipairs(readOTUI(relative)) do
    if node.base then styles[node.name] = node else windowNode = node end
  end
end
assert(windowNode and windowNode.name == 'SpecialMiniWindow')

local function hasState(styleName, prefix)
  for _, child in ipairs(styles[styleName].children) do
    if child.state and child.name:sub(1, #prefix) == prefix then return true end
  end
  return false
end
for _, state in ipairs({'$hover', '$checked', '$pressed', '$disabled'}) do
  assert(hasState('AntigasSidebarToggle', state), 'toggle style must define ' .. state)
end
for _, state in ipairs({'$hover', '$on', '$pressed', '$disabled'}) do
  assert(hasState('AntigasSidebarAction', state), 'action style must define ' .. state)
end

UIWindow = {}
function extends() return {} end
function signalcall(callback, ...) if callback then callback(...) end end
local settings = {}
g_settings = {
  getNode = function() return settings end,
  setNode = function(_, value) settings = value end
}
UIWidget = {setHeight = function(self, height)
  self.height = height
  signalcall(self.onGeometryChange, self)
end}
dofile(clientFile('modules/corelib/ui/uiminiwindow.lua'))
dofile(clientFile('modules/game_playerbars/playerbars.lua'))
modules = {game_playerbars={toggleMenu=toggleMenu, resizeButtons=resizeButtons,
  updateMenuToggle=updateMenuToggle, onMiniWindowClose=onMiniWindowClose,
  setActionSelected=setActionSelected},
  game_interface={getRightPanel=function() return nil end}}

local methods = {}
function methods:show() self.visible=true end
function methods:hide() self.visible=false end
function methods:setVisible(value) self.visible=value end
function methods:isVisible() return self.visible and (not self.parent or self.parent:isVisible()) end
function methods:isExplicitlyVisible() return self.visible end
function methods:getParent() return self.parent end
function methods:getId() return self.id end
function methods:setOn(value) self.on=value; signalcall(self.onGeometryChange, self) end
function methods:isOn() return self.on or false end
function methods:disable() self.enabled=false end
function methods:isEnabled() return self.enabled end
function methods:setText(value) self.text=value end
function methods:setTooltip(value) self.tooltip=value end
function methods:setColor(value) self.color=value end
function methods:setIconOffsetX(value)
  self.iconOffsetX=value
  self.iconOffsetXCalls=self.iconOffsetXCalls or {}
  self.iconOffsetXCalls[#self.iconOffsetXCalls+1]=value
end
function methods:setIconOffsetY(value)
  self.iconOffsetY=value
  self.iconOffsetYCalls=self.iconOffsetYCalls or {}
  self.iconOffsetYCalls[#self.iconOffsetYCalls+1]=value
end
function methods:setWidth(value) self.width=value end
function methods:setHeight(value) self.height=value end
function methods:getWidth()
  if self.props['anchors.left']=='parent.left' and self.props['anchors.right']=='parent.right' then
    return self.parent:getWidth() - self:getMarginLeft() - self:getMarginRight()
  end
  return self.width
end
function methods:setMarginLeft(value) self.marginLeft=value end
function methods:setMarginRight(value) self.marginRight=value end
function methods:setMarginTop(value) self.marginTop=value end
function methods:getMarginLeft() return self.marginLeft or 0 end
function methods:getMarginRight() return self.marginRight or 0 end
function methods:getMarginTop() return self.marginTop or 0 end
function methods:getMarginBottom() return self.marginBottom or 0 end
function methods:getHeight() return self.height end
function methods:getChildById(id)
  for _, child in ipairs(self.children) do if child.id==id then return child end end
end
function methods:recursiveGetChildById(id)
  local direct=self:getChildById(id)
  if direct then return direct end
  for _, child in ipairs(self.children) do
    local match=child:recursiveGetChildById(id)
    if match then return match end
  end
end

local function expandStyle(node, props, children)
  local style = styles[node.base or node.name]
  if style then expandStyle(style, props, children) end
  for key, value in pairs(node.props) do props[key]=value end
  for _, child in ipairs(node.children) do
    if not child.state then children[#children+1]=child end
  end
end
local function instantiate(node, parent)
  local props, children={}, {}
  expandStyle(node, props, children)
  local result={parent=parent, props=props, children={}, visible=true, enabled=true,
    width=tonumber(props.width) or 0, height=tonumber(props.height) or 0,
    id=props.id, tooltip=props.tooltip, save=props['&save']=='true',
    minimizedHeight=tonumber(props['&minimizedHeight'])}
  setmetatable(result, {__index=function(self, key)
    return (not parent and UIMiniWindow[key]) or methods[key] or methods.getChildById(self, key)
  end})
  for _, edge in ipairs({'Left', 'Right', 'Top', 'Bottom'}) do
    result['margin'..edge]=tonumber(props['margin-'..edge:lower()]) or 0
  end
  if props.size then
    local width, height=props.size:match('^(%d+)%s+(%d+)$')
    result.width, result.height=tonumber(width), tonumber(height)
  end
  for key, value in pairs(props) do
    if key:sub(1, 1)=='@' then
      result[key:sub(2)]=assert((loadstring or load)('return function(self) '..value..' end'))()
    end
  end
  local ids={}
  for _, childNode in ipairs(children) do
    local child=instantiate(childNode, result)
    assert(not child.id or not ids[child.id], 'Duplicate inherited/instance widget id: '..tostring(child.id))
    if child.id then ids[child.id]=true end
    result.children[#result.children+1]=child
  end
  return result
end

local window=instantiate(windowNode)
local contents=assert(window:getChildById('contentsPanel'))
local toggle=assert(window:getChildById('menuToggle'))
local inheritedMinimize=assert(window:getChildById('minimizeButton'))
assert(toggle:getHeight()==14 and toggle:getWidth()==14 and type(toggle.onClick)=='function',
  'the compact minimize control must get its callback from the real @onClick property')
assert(inheritedMinimize.width==0 and inheritedMinimize.height==0,
  'the original invisible minimize button is preserved without a duplicate')
local buttons={}
for _, id in ipairs({'SkillsButton', 'BattleButton', 'VipButton', 'huntButton', 'marketButton', 'questButton', 'achievementsButton'}) do
  buttons[#buttons+1]=assert(contents:getChildById(id), id..' must be inside contentsPanel')
end

local function assertIconOffsets(expectedX, expectedY, expectedAchievementsY, layout)
  for _, button in ipairs(buttons) do
    local wantedY = button == achievementsButton and expectedAchievementsY or expectedY
    local xCalls, yCalls = button.iconOffsetXCalls or {}, button.iconOffsetYCalls or {}
    assert(button.iconOffsetX == expectedX and xCalls[#xCalls] == expectedX
        and button.iconOffsetY == wantedY and yCalls[#yCalls] == wantedY,
      string.format('%s: %s icon offsets should be %d,%d, got %s,%s (setter args %s,%s)',
        layout, button.id, expectedX, wantedY,
        tostring(button.iconOffsetX), tostring(button.iconOffsetY),
        tostring(xCalls[#xCalls]), tostring(yCalls[#yCalls])))
  end
end

local function clearIconOffsetCalls()
  for _, button in ipairs(buttons) do
    button.iconOffsetXCalls, button.iconOffsetYCalls = {}, {}
  end
end

g_game={}
g_ui={loadUI=function() return window end}
function connect() end
REGISTRATION_KEY='AbcDeFgH'
init()
assert(window.height==30 and skillsButton.width==22 and skillsButton.height==22 and skillsButton.marginLeft==2)
assertIconOffsets(5, 5, 4, 'native-width toolbar')
assert(not toggle:isOn() and toggle.tooltip=='Recolher barra')
for _, button in ipairs(buttons) do
  assert(button.width==22 and button.height==22, 'all seven icons share a 22 px click area at native width')
end
assert(buttons[2].tooltip=='Lista de batalha (Ctrl+B).' and buttons[3].tooltip=='Lista VIP (Ctrl+P).'
  and questButton.tooltip=='Diário de missões (Ctrl+J).', 'only verified shortcuts appear in Portuguese tooltips')
assert(marketButton.tooltip=='Mercado.' and huntButton.tooltip=='Estatísticas de caça e loot.'
  and achievementsButton.tooltip=='Conquistas.')
assert(type(inheritedMinimize.onClick)=='function', 'UIMiniWindow setup still binds the inherited control')
toggle:onClick()
assert(window:isOn() and window.height==18 and settings.playerBarsWindow.minimized==true)
for _, button in ipairs(buttons) do assert(not button:isVisible(), 'all menu buttons must disappear when minimized') end
assert(toggle:isVisible() and toggle:isOn() and toggle.tooltip=='Expandir barra')
setAchievementsUnread(3)
assert(toggle:isVisible() and toggle:getChildById('menuUnreadIndicator'):isVisible()
  and toggle.tooltip=='Expandir barra (3 novas)',
  'unread achievements remain noticeable while the menu is collapsed')
assert(achievementsButton.tooltip=='Conquistas: 3 novas'
  and not achievementsButton:isVisible())
clearIconOffsetCalls()
window.width=178
resizeButtons()
assert(window.height==18 and toggle:getWidth()==14, 'sidebar resizing cannot expand the minimized menu')
assert(skillsButton.width==20 and skillsButton.height==20,
  'buttons shrink uniformly when the toolbar has less width')
assertIconOffsets(4, 4, 3, '178 px toolbar')
settings.playerBarsWindow.height=90 -- A saved height from the previous three-row menu.
toggle:onClick()
assert(not window:isOn() and window.height==28 and settings.playerBarsWindow.minimized==false)
for _, button in ipairs(buttons) do assert(button:isVisible(), 'expanding restores every button') end
assert(not toggle:isOn() and toggle:getChildById('menuUnreadIndicator'):isVisible())
assert(skillsButton.width==20 and skillsButton.marginLeft==2 and battleButton.marginLeft==2)
clearIconOffsetCalls()
window.width=160
resizeButtons()
assert(skillsButton.width==18 and skillsButton.height==18 and window.height==26,
  'all controls remain inside a narrower 160 px toolbar')
assertIconOffsets(3, 3, 2, '160 px toolbar')
clearIconOffsetCalls()
window.width=192
resizeButtons()
assert(skillsButton.width==22 and skillsButton.height==22 and window.height==30,
  'the toolbar returns to native 22 px buttons when space is available')
assertIconOffsets(5, 5, 4, '192 px toolbar')
setActionSelected('market', true)
setActionSelected('quest', true)
setActionSelected('achievements', true)
assert(marketButton:isOn() and questButton:isOn() and achievementsButton:isOn(),
  'the amber action-button state follows the visibility reported by its owning module')
setActionSelected('market', false)
setActionSelected('quest', false)
setActionSelected('achievements', false)
setAchievementsUnread(0)
assert(not toggle:isOn() and not toggle:getChildById('menuUnreadIndicator'):isVisible()
  and not achievementsButton:getChildById('achievementsUnreadIndicator'):isVisible()
  and achievementsButton.tooltip=='Conquistas')
toggle:onClick()
window:setup()
assert(window.height==18 and not contents:isVisible() and toggle:isOn(), 'saved minimized state survives setup')
toggle:onClick()
assert(window.height==30 and contents:isVisible() and not toggle:isOn(), 'saved minimization still permits expansion')
print('PASS: unique OTUI ids, icon states, Portuguese tooltips, responsive spacing and icon offsets, minimize behavior and real selected states')
