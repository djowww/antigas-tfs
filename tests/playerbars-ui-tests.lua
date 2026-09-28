local function clientFile(relative)
  for _, prefix in ipairs({'Cliente/', '../../Cliente/', 'deploy/client-current/', 'Servidor/TFS/deploy/client-current/'}) do
    local path = prefix .. relative
    local file = io.open(path, 'r')
    if file then file:close(); return path end
  end
  error('Client file not found: ' .. relative)
end

local file = assert(io.open(clientFile('modules/game_playerbars/playerbars.otui'), 'r'))
local otui = file:read('*a'):gsub('\r\n', '\n')
file:close()
local body = assert(otui:match('  MiniWindowContents\n(.*)'), 'missing collapsible contents')
for _, id in ipairs({'SkillsButton', 'BattleButton', 'VipButton', 'huntButton', 'marketButton', 'questButton', 'achievementsButton'}) do
  assert(body:find('\n      id: ' .. id .. '\n', 1, true), id .. ' must be inside contentsPanel')
end
assert(otui:find('    size: 14 14', 1, true) and otui:find('    image-source: /images/ui/miniwindow_buttons', 1, true),
  'minimize control needs a visible size and icon')

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
  if self.onGeometryChange then self:onGeometryChange() end
end}
dofile(clientFile('modules/corelib/ui/uiminiwindow.lua'))
dofile(clientFile('modules/game_playerbars/playerbars.lua'))

local function widget(parent)
  local result = {visible=true, parent=parent, height=20}
  function result:show() self.visible=true end
  function result:hide() self.visible=false end
  function result:isVisible() return self.visible and (not self.parent or self.parent:isVisible()) end
  function result:setOn(value) self.on=value end
  function result:setWidth(value) self.width=value end
  function result:setMarginLeft(value) self.marginLeft=value end
  function result:setMarginTop(value) self.marginTop=value end
  function result:getMarginTop() return self.marginTop or 0 end
  function result:getMarginBottom() return self.marginBottom or 0 end
  function result:getHeight() return self.height end
  return result
end

local window = setmetatable({width=192, height=94, minimizedHeight=20, save=true, visible=true}, {__index=UIMiniWindow})
function window:getWidth() return self.width end
function window:getHeight() return self.height end
function window:getId() return 'playerBarsWindow' end
function window:getParent() return nil end
function window:isOn() return self.on or false end
function window:setOn(value) self.on=value; resizeButtons() end
function window:isVisible() return self.visible end
function window:getChildById(id) return self.children[id] end
local contents = widget(window)
contents.marginTop=20
window.children={contentsPanel=contents, miniwindowScrollBar=widget(window), bottomResizeBorder=widget(window), minimizeButton=widget(window)}
window.minimizeButton=window.children.minimizeButton
window.onGeometryChange=resizeButtons
playerBarsWindow=window
skillsButton, battleButton, vipButton, huntButton=widget(contents), widget(contents), widget(contents), widget(contents)
marketButton, achievementsButton=widget(contents), widget(contents)
local questButton=widget(contents)
local buttons={skillsButton,battleButton,vipButton,huntButton,marketButton,questButton,achievementsButton}

resizeButtons()
assert(window.height==94 and skillsButton.width==43 and skillsButton.marginLeft==7)
window:setup()
window.minimizeButton.onClick()
assert(window:isOn() and window.height==20 and settings.playerBarsWindow.minimized==true)
for _, button in ipairs(buttons) do assert(not button:isVisible(), 'all menu buttons must disappear when minimized') end
assert(window.minimizeButton:isVisible(), 'expand control remains accessible')
window.width=193
resizeButtons()
assert(window.height==20, 'sidebar resizing cannot expand the minimized menu')
window.minimizeButton.onClick()
assert(not window:isOn() and window.height==96 and settings.playerBarsWindow.minimized==false)
for _, button in ipairs(buttons) do assert(button:isVisible(), 'expanding restores every button') end
assert(skillsButton.width==43 and skillsButton.marginLeft==6 and battleButton.marginLeft==4)
window:minimize()
window:setup()
assert(window.height==20 and not contents:isVisible(), 'saved minimized settings survive setup')
window:maximize()
assert(window.height==96 and contents:isVisible(), 'saved minimization still permits expansion')
print('PASS: all menu buttons collapse, control remains visible, resize preserves collapse, expand restores layout, saved state restores')
