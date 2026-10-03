-- Keep the sprite readable, with a restrained shimmer matching its pixel accents.
local families = {
  [0] = { {151, 125, 88}, {189, 161, 112}, {210, 190, 149} },
  [1] = { {93, 139, 110}, {129, 173, 137}, {167, 195, 151} },
  [2] = { {99, 137, 169}, {130, 169, 193}, {169, 195, 207} },
  [3] = { {143, 111, 164}, {172, 143, 184}, {202, 174, 197} },
  [4] = { {178, 139, 78}, {207, 174, 111}, {225, 204, 156} },
  [5] = { {177, 107, 103}, {204, 142, 126}, {225, 177, 151} }
}
-- A native widget can have several Lua userdata wrappers. Weak userdata keys
-- may remain visible after their native pointer was finalized by LuaJIT.
-- Keep a strong wrapper in a plain Lua entry and share its token via the
-- widget's native fields, so callbacks with another wrapper find the same slot.
local slots = {}
local animationEvent
local ANIMATION_MS = 200
local CYCLE_MS = 4200
local TWO_PI = math.pi * 2

local function tierNumber(tier)
  return type(tier) == 'number' and tier == math.floor(tier)
    and tier >= 0 and tier <= 5 and tier or 0
end

local function phaseSeed(seed)
  if type(seed) == 'number' then return seed % CYCLE_MS end
  local value = tostring(seed or '')
  local hash = 0
  for i = 1, math.min(#value, 96) do
    hash = (hash * 31 + value:byte(i)) % CYCLE_MS
  end
  return hash
end

local function mix(a, b, amount)
  return {
    a[1] + (b[1] - a[1]) * amount,
    a[2] + (b[2] - a[2]) * amount,
    a[3] + (b[3] - a[3]) * amount
  }
end

local function hex(rgb)
  return string.format('#%02X%02X%02X',
    math.floor(rgb[1] + 0.5), math.floor(rgb[2] + 0.5), math.floor(rgb[3] + 0.5))
end

local function colorAt(tier, now, seed)
  local family = families[tierNumber(tier)]
  local phase = ((now or g_clock.millis()) + phaseSeed(seed)) / CYCLE_MS * TWO_PI
  local tone = (1 - math.cos(phase)) * 0.5
  if tone < 0.5 then return mix(family[1], family[2], tone * 2) end
  return mix(family[2], family[3], (tone - 0.5) * 2)
end

function getTextColor(tier)
  return hex(families[tierNumber(tier)][2])
end

function getAccentColor(tier, now, seed)
  return hex(colorAt(tier, now, seed))
end

function getSlotTint(tier, now, seed, locked)
  tier = tierNumber(tier)
  if tier == 0 then return '#FFFFFF' end
  now = now or g_clock.millis()
  local phase = (now + phaseSeed(seed)) / CYCLE_MS * TWO_PI
  local shimmer = (1 - math.cos(phase)) * 0.5
  local strength = 0.035 + shimmer * (0.065 + tier * 0.015)
  if locked then strength = strength * 0.45 end
  return hex(mix({255, 255, 255}, colorAt(tier, now, seed), strength))
end

function getWorldTint(tier, now, seed, surface)
  tier = tierNumber(tier)
  now = now or g_clock.millis()
  local phase = (now + phaseSeed(seed)) / CYCLE_MS * TWO_PI
  -- Neither end of the cycle turns white; the hue and intensity move together.
  local wave = (1 - math.cos(phase)) * 0.5
  local strength
  if surface == 'corpse' then
    strength = 0.13 + wave * 0.09
  else
    strength = 0.24 + tier * 0.015 + wave * 0.08
  end
  return hex(mix({255, 255, 255}, colorAt(tier, now, seed), strength))
end

local function alive(widget)
  return widget and not widget:isDestroyed()
end

local function pixel(parent, width, height, horizontal, vertical, insetX, insetY)
  local child = g_ui.createWidget('UIWidget', parent)
  child:setPhantom(true)
  child:setFocusable(false)
  child:setSize({width = width, height = height})
  child:addAnchor(horizontal, 'parent', horizontal)
  child:addAnchor(vertical, 'parent', vertical)
  if horizontal == AnchorLeft then child:setMarginLeft(insetX)
  else child:setMarginRight(insetX) end
  if vertical == AnchorTop then child:setMarginTop(insetY)
  else child:setMarginBottom(insetY) end
  return child
end

local function removeDecoration(entry)
  for _, child in ipairs(entry.children) do
    if alive(child) then child:destroy() end
  end
end

local function paintSlot(widget, entry, now)
  local spriteColor = getSlotTint(entry.tier, now, entry.seed, entry.locked)
  -- Native item color preserves sprite shading; no extra overlay covers its art.
  if entry.spriteColor ~= spriteColor then
    widget:setColor(spriteColor)
    entry.spriteColor = spriteColor
  end
  local color = getAccentColor(entry.tier, now, entry.seed)
  if entry.locked then color = hex(mix(colorAt(entry.tier, now, entry.seed), {94, 91, 87}, 0.45)) end
  if entry.color ~= color then
    for _, child in ipairs(entry.accents) do child:setBackgroundColor(color) end
    entry.color = color
  end
  if entry.glint then
    local travel = ((now + entry.seed) % 5600) / 5600
    -- A short, slow pass along the top edge, followed by a quiet interval.
    local visible = travel < 0.34 and not entry.locked
    entry.glint:setVisible(visible)
    if visible then
      local width = math.max(0, widget:getWidth() - 9)
      entry.glint:setMarginLeft(3 + math.floor(width * travel / 0.34))
      entry.glint:setBackgroundColor(hex(families[entry.tier][3]))
    end
  end
end

local function animateSlots()
  animationEvent = nil
  local now = g_clock.millis()
  for entry in pairs(slots) do
    local widget = entry.widget
    if not alive(widget) then
      slots[entry] = nil
      removeDecoration(entry)
      entry.widget = nil
    elseif widget:isVisible() then
      paintSlot(widget, entry, now)
    end
  end
  if next(slots) then animationEvent = scheduleEvent(animateSlots, ANIMATION_MS) end
end

function clearSlot(widget)
  if not widget then return end
  local entry = widget.antigasRarityVisualEntry
  if not entry then return end
  widget.antigasRarityVisualEntry = nil
  slots[entry] = nil
  if alive(widget) then widget:setColor('#FFFFFF') end
  removeDecoration(entry)
  entry.widget = nil
  if not next(slots) and animationEvent then
    removeEvent(animationEvent)
    animationEvent = nil
  end
end

function applySlot(widget, tier, locked)
  tier = tierNumber(tier)
  if tier == 0 or not alive(widget) or not widget:getItem() then
    clearSlot(widget)
    return
  end
  local entry = widget.antigasRarityVisualEntry
  if entry and entry.tier ~= tier then clearSlot(widget); entry = nil end
  if not entry then
    entry = {widget = widget, tier = tier, seed = phaseSeed(tostring(widget)), children = {}, accents = {}}
    slots[entry] = true
    widget.antigasRarityVisualEntry = entry
    local corners = {
      {AnchorLeft, AnchorTop}, {AnchorRight, AnchorTop},
      {AnchorLeft, AnchorBottom}, {AnchorRight, AnchorBottom}
    }
    for _, corner in ipairs(corners) do
      for _, size in ipairs({{4, 1}, {1, 4}}) do
        local child = pixel(widget, size[1], size[2], corner[1], corner[2], 1, 1)
        entry.children[#entry.children + 1] = child
        entry.accents[#entry.accents + 1] = child
      end
    end
    -- Countable tier marks remain readable without relying only on color.
    for i = 1, tier do
      local child = pixel(widget, 2, 2, AnchorLeft, AnchorBottom, 7 + (i - 1) * 3, 1)
      entry.children[#entry.children + 1] = child
      entry.accents[#entry.accents + 1] = child
    end
    if tier >= 3 then
      entry.glint = pixel(widget, 3, 1, AnchorLeft, AnchorTop, 3, 1)
      entry.children[#entry.children + 1] = entry.glint
    end
  end
  entry.locked = locked == true
  -- Inventory rarity refreshes first restore the native sprite to white.
  entry.spriteColor = nil
  paintSlot(widget, entry, g_clock.millis())
  if not animationEvent then animationEvent = scheduleEvent(animateSlots, ANIMATION_MS) end
end

function resetSlots()
  if animationEvent then removeEvent(animationEvent); animationEvent = nil end
  for entry in pairs(slots) do
    slots[entry] = nil
    if alive(entry.widget) then
      entry.widget.antigasRarityVisualEntry = nil
      entry.widget:setColor('#FFFFFF')
    end
    removeDecoration(entry)
    entry.widget = nil
  end
end

function init()
  connect(g_game, {onGameEnd = resetSlots})
  if g_game.isOnline() then
    -- Restore existing authoritative slot metadata after reloading this module.
    for _, widget in ipairs(g_ui.getRootWidget():recursiveGetChildren()) do
      if alive(widget) and widget:getClassName() == 'UIItem' and widget.rarityTier then
        applySlot(widget, widget.rarityTier, widget.rarityLocked)
      end
    end
  end
end

function terminate()
  disconnect(g_game, {onGameEnd = resetSlots})
  resetSlots()
end
