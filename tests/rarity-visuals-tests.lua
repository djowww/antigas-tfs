-- Focused shared rarity helper regression suite. Run with LuaJIT from repo root.
-- Native UI is unavailable offline, so userdata wrappers share native fields and
-- parent ownership below, matching the lifetime boundary relevant to this helper.
local checks = 0
local function check(value, message)
  assert(value, message)
  checks = checks + 1
end
assert(type(newproxy) == 'function', 'This lifetime suite requires LuaJIT newproxy userdata')

local methods = {}
function methods.isDestroyed(native) return native.destroyed end
function methods.isVisible(native) return native.visible end
function methods.getItem(native) return native.item end
function methods.getWidth(native) return native.width end
function methods.getClassName(native) return native.className end
function methods.recursiveGetChildren(native) return native.rootChildren or {} end
function methods.setColor(native, value)
  assert(not native.destroyed, 'setColor after native widget destruction')
  native.color, native.colorWrites = value, native.colorWrites + 1
end
function methods.setPhantom(native, value) native.phantom = value end
function methods.setFocusable(native, value) native.focusable = value end
function methods.setSize(native, value) native.size = value end
function methods.addAnchor(native, anchor, target, targetAnchor)
  check(target == 'parent' and anchor == targetAnchor, 'Decoration anchors to its own slot')
  native.anchors[anchor] = target
end
function methods.setMarginLeft(native, value) native.marginLeft = value end
function methods.setMarginRight(native, value) native.marginRight = value end
function methods.setMarginTop(native, value) native.marginTop = value end
function methods.setMarginBottom(native, value) native.marginBottom = value end
function methods.setBackgroundColor(native, value)
  assert(not native.destroyed, 'paint after native child destruction')
  native.backgroundColor = value
end
function methods.setVisible(native, value)
  assert(not native.destroyed, 'visibility write after native child destruction')
  native.visible = value
end
function methods.setOpacity(native, value)
  assert(not native.destroyed, 'opacity write after native child destruction')
  check(value >= 0 and value <= 1, 'Pixel opacity stays in the native alpha range')
  native.opacity = value
end
function methods.destroy(native)
  assert(not native.destroyed, 'native child destroyed twice')
  native.destroyed, native.destroyCalls = true, native.destroyCalls + 1
end

local function nativeWidget(className)
  return {
    fields = {}, children = {}, anchors = {}, className = className or 'UIItem',
    destroyed = false, visible = true, width = 34, item = {}, color = '#FFFFFF',
    colorWrites = 0, destroyCalls = 0, borderWidth = 1, borderColor = '#ff0000'
  }
end

local wrapperNatives = setmetatable({}, {__mode = 'k'})
local function wrap(native, tracker)
  tracker = tracker or {finalized = 0}
  local wrapper, finalized = newproxy(true), false
  local mt = getmetatable(wrapper)
  mt.__index = function(_, key)
    assert(not finalized, 'access to a finalized Lua native wrapper')
    if methods[key] then
      return function(_, ...)
        assert(not finalized, 'method call on a finalized Lua native wrapper')
        return methods[key](native, ...)
      end
    end
    return native.fields[key]
  end
  mt.__newindex = function(_, key, value)
    assert(not finalized, 'field write on a finalized Lua native wrapper')
    native.fields[key] = value
  end
  mt.__gc = function()
    finalized = true
    tracker.finalized = tracker.finalized + 1
  end
  wrapperNatives[wrapper] = native
  return wrapper
end

local function sandbox()
  local env = {AnchorLeft = 1, AnchorRight = 2, AnchorTop = 3, AnchorBottom = 4}
  local timers, now, created, clockReads = {}, 0, 0, 0
  env.g_clock = {millis = function() clockReads = clockReads + 1; return now end}
  env.scheduleEvent = function(callback, delay)
    check(type(delay) == 'number' and delay >= 100, 'Animation timer is capped below 10 ticks/second')
    local token = {}
    timers[token] = callback
    return token
  end
  env.removeEvent = function(token) timers[token] = nil end
  env.g_ui = {createWidget = function(style, parent)
    check(style == 'UIWidget', 'Decorations use lightweight native UIWidget')
    local parentNative = assert(wrapperNatives[parent], 'Decoration parent is a native wrapper')
    local childNative = nativeWidget('UIWidget')
    parentNative.children[#parentNative.children + 1] = childNative
    created = created + 1
    return wrap(childNative)
  end}
  setmetatable(env, {__index = _G})
  local chunk = assert(loadfile(arg[1] or 'deploy/client-current/modules/game_rarityvisuals/rarityvisuals.lua'))
  setfenv(chunk, env)
  chunk()
  local control = {}
  function control.timerCount() local count = 0; for _ in pairs(timers) do count = count + 1 end; return count end
  function control.created() return created end
  function control.setTime(value) now = value end
  function control.tick(value)
    now = value
    local token, callback = next(timers)
    check(callback ~= nil, 'Live decorations keep an animation timer')
    timers[token] = nil
    local readsBefore = clockReads
    callback()
    check(clockReads == readsBefore + 1, 'One clock read animates every slot in a frame')
  end
  return env, control
end

local function collect() collectgarbage('collect'); collectgarbage('collect') end
local function allDestroyed(native)
  for _, child in ipairs(native.children) do if not child.destroyed then return false end end
  return true
end
local function destroyNativeTree(native)
  -- The native UI destroys children before dispatching the parent's onDestroy.
  for _, child in ipairs(native.children) do child.destroyed = true end
  native.destroyed = true
end

-- Catches registry keyed by transient userdata and weak keys losing live slots.
do
  local visual, clock = sandbox()
  local native, tracker = nativeWidget(), {finalized = 0}
  local widget = wrap(native, tracker)
  local weakWrapper = setmetatable({widget}, {__mode = 'v'})
  visual.applySlot(widget, 3, false)
  local children = clock.created()
  widget = nil
  collect()
  check(tracker.finalized == 0 and weakWrapper[1] ~= nil, 'Live registry keeps the native wrapper strong across GC')
  local freshWrapper = wrap(native)
  visual.applySlot(freshWrapper, 3, false)
  check(clock.created() == children, 'A second wrapper reuses the same native decorations')
  check(clock.timerCount() == 1, 'Repeated apply keeps one shared timer')
  clock.tick(2100)
  check(native.color ~= '#FFFFFF', 'Native item sprite receives the subtle tier tint')
  visual.clearSlot(freshWrapper)
  check(native.color == '#FFFFFF', 'Fresh-wrapper clear restores the native sprite to white')
  check(native.fields.antigasRarityVisualEntry == nil, 'Fresh-wrapper clear removes native registry token')
  check(allDestroyed(native), 'Fresh-wrapper clear destroys all slot decorations')
  check(clock.timerCount() == 0, 'Clearing the last slot stops the timer immediately')
  collect()
  check(tracker.finalized == 1 and weakWrapper[1] == nil, 'Cleared registry releases its original wrapper for GC')
end

-- Catches stale overlays/tints when common, missing, or invalid tiers replace rarity.
do
  local visual, clock = sandbox()
  local native, widget = nativeWidget()
  widget = wrap(native)
  visual.applySlot(widget, 0, false)
  check(#native.children == 0 and native.color == '#FFFFFF', 'Common items receive no extra slot decoration')
  check(clock.timerCount() == 0, 'Common items create no animation timer')
  for _, replacement in ipairs({0, -1, 6, 2.5, 'rare'}) do
    visual.applySlot(widget, 4, false)
    visual.applySlot(widget, replacement, false)
    check(allDestroyed(native) and native.color == '#FFFFFF', 'Non-rarity tier clears decoration and tint: ' .. tostring(replacement))
    check(clock.timerCount() == 0, 'Non-rarity tier releases animation: ' .. tostring(replacement))
  end
  visual.applySlot(widget, 2, false)
  native.item = nil
  visual.applySlot(wrap(native), 2, false)
  check(allDestroyed(native) and native.color == '#FFFFFF', 'Empty slot clears decoration and tint')
  check(clock.timerCount() == 0, 'Empty slot releases animation')
end

-- Catches native onDestroy double deletion and timer retention after destruction.
do
  local visual, clock = sandbox()
  local native = nativeWidget()
  visual.applySlot(wrap(native), 5, false)
  destroyNativeTree(native)
  visual.clearSlot(wrap(native))
  check(clock.timerCount() == 0, 'Parent destroy callback clears the final timer')
  for _, child in ipairs(native.children) do check(child.destroyCalls == 0, 'Already destroyed native children are not destroyed again') end
  local other = nativeWidget()
  visual.applySlot(wrap(other), 1, false)
  destroyNativeTree(other)
  clock.tick(200)
  check(clock.timerCount() == 0, 'Animation drops a native widget destroyed before its callback')
  collect()
end

-- Catches per-slot timers, uncontrolled allocation, borders overwritten, and reset leaks.
do
  local visual, clock = sandbox()
  local natives, wrappers = {}, {}
  for tier = 1, 5 do
    natives[tier] = nativeWidget()
    wrappers[tier] = wrap(natives[tier])
    visual.applySlot(wrappers[tier], tier, tier == 5)
  end
  check(clock.timerCount() == 1, 'All five tiers share one timer')
  local created = clock.created()
  local colors = {}
  for tier, native in ipairs(natives) do
    colors[tier] = native.color
    check(native.borderWidth == 1 and native.borderColor == '#ff0000', 'Decoration leaves the existing boundary intact for tier ' .. tier)
    for _, child in ipairs(native.children) do
      check(child.phantom == true and child.focusable == false, 'Decoration cannot intercept drag/click/focus')
      check(child.size.width <= 5 and child.size.height <= 4, 'Pixel decoration remains a small rectangle')
    end
  end
  natives[1].visible = false
  local hiddenWrites = natives[1].colorWrites
  for frame = 1, 30 do clock.tick(frame * 200) end
  check(natives[1].colorWrites == hiddenWrites, 'Hidden slots do not repaint')
  check(clock.created() == created and clock.timerCount() == 1, 'Animation neither allocates children nor duplicates timers')
  visual.resetSlots()
  for tier, native in ipairs(natives) do
    check(native.color == '#FFFFFF' and allDestroyed(native), 'Reset removes the tint and every decoration for tier ' .. tier)
    check(native.fields.antigasRarityVisualEntry == nil, 'Reset removes each native slot token')
  end
  check(clock.timerCount() == 0, 'Reset stops the shared timer')
  collect()
end

-- Catches a missing bolt, a bolt that blocks clicks, mismatched hue, or new timers.
do
  local visual, clock = sandbox()
  local natives, entries = {}, {}
  for tier = 1, 5 do
    local native = nativeWidget()
    natives[tier] = native
    visual.applySlot(wrap(native), tier, false)
    local entry = native.fields.antigasRarityVisualEntry
    entries[tier] = entry
    check(type(entry.bolt) == 'table' and #entry.bolt == 7, 'Tier ' .. tier .. ' has a complete pixel bolt')
    local accent = native.children[1].backgroundColor
    for _, child in ipairs(entry.bolt) do
      local pixel = assert(wrapperNatives[child])
      check(pixel.phantom and not pixel.focusable, 'Bolt remains transparent to pointer and focus input')
      check(pixel.size.height == 1 and pixel.size.width >= 2 and pixel.size.width <= 5, 'Bolt uses compact pixel strokes')
      check(pixel.backgroundColor == accent, 'Bolt shares its tier accent hue at each frame')
      check(pixel.opacity >= 0.4 and pixel.opacity <= 0.9, 'Unlocked bolt has a restrained opacity pulse')
    end
  end
  local created = clock.created()
  local firstOpacity = wrapperNatives[entries[1].bolt[1]].opacity
  clock.tick(2100)
  local nextOpacity = wrapperNatives[entries[1].bolt[1]].opacity
  clock.tick(3150)
  local laterOpacity = wrapperNatives[entries[1].bolt[1]].opacity
  check(firstOpacity ~= nextOpacity or firstOpacity ~= laterOpacity, 'Bolt opacity visibly advances over the slow shimmer cycle')
  for tier, entry in ipairs(entries) do
    for _, child in ipairs(entry.bolt) do
      check(wrapperNatives[child].backgroundColor == natives[tier].children[1].backgroundColor, 'Animation keeps bolt and slot accents synchronized')
    end
  end
  visual.applySlot(wrap(natives[5]), 5, true)
  for _, child in ipairs(entries[5].bolt) do
    check(wrapperNatives[child].opacity == 0.3, 'Locked bolt uses steady subdued opacity')
  end
  clock.tick(4200)
  for _, child in ipairs(entries[5].bolt) do
    check(wrapperNatives[child].opacity == 0.3, 'Locked bolt does not flash with the animation cycle')
  end
  check(clock.created() == created and clock.timerCount() == 1, 'Bolt refresh reuses children and the shared timer')
  visual.resetSlots()
  for tier, native in ipairs(natives) do check(allDestroyed(native), 'Reset destroys every bolt stroke for tier ' .. tier) end
end

-- Catches weakening the shared phase, losing colored world drops, or tinting commons.
do
  local visual = sandbox()
  check(visual.getSlotTint(0, 0, 0) == '#FFFFFF' and visual.getSlotTint(0, 2100, 0) == '#FFFFFF', 'Common slot sprites remain white throughout the cycle')
  local seen = {}
  for tier = 1, 5 do
    local start, peak = visual.getSlotTint(tier, 0, 0), visual.getSlotTint(tier, 2100, 0)
    check(start ~= peak, 'Tier ' .. tier .. ' sprite tint shimmers over time')
    check(start ~= '#FFFFFF' and peak ~= '#FFFFFF', 'Tier ' .. tier .. ' sprite retains a colored tint')
    check(visual.getSlotTint(tier, 0, 0) == visual.getSlotTint(tier, 4200, 0), 'Tier ' .. tier .. ' phase repeats slowly')
    check(not seen[visual.getAccentColor(tier, 2100, 0)], 'Each rarity tier has a distinct accent family')
    seen[visual.getAccentColor(tier, 2100, 0)] = true
  end
  for tier = 0, 5 do
    for _, surface in ipairs({'ground', 'corpse'}) do
      check(visual.getWorldTint(tier, 0, 0, surface) ~= '#FFFFFF', 'World ' .. surface .. ' keeps hue at cycle start, tier ' .. tier)
      check(visual.getWorldTint(tier, 2100, 0, surface) ~= '#FFFFFF', 'World ' .. surface .. ' keeps hue at cycle peak, tier ' .. tier)
    end
  end
end

print('PASS rarity visuals/native-wrapper lifecycle: ' .. checks .. ' assertions')
