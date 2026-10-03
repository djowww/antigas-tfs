local OPCODE = 126
local window, refreshEvent, timeoutEvent, startupEvent, requestEvent
local current, incoming, latestSnapshot, lastRequest
local statusFilter, categoryFilter = 'next', 'all'
local categories = {}
local readyCount = 0
local ranks = {
  {name='Novice', numeral='I', fraction=0},
  {name='Adventurer', numeral='II', fraction=0.10},
  {name='Veteran', numeral='III', fraction=0.25},
  {name='Elite', numeral='IV', fraction=0.50},
  {name='Master', numeral='V', fraction=0.75},
  {name='Legend', numeral='VI', fraction=1}
}
-- Horizontal runs of the three tones in a native 9 x 9 pixel star.
local rankStarRectangles = {
  h={{4,0,1},{3,1,1},{3,2,1},{0,3,4},{1,4,1},{2,5,1},{2,6,1},{1,7,1},{1,8,1}},
  f={{4,1,1},{4,2,1},{4,3,3},{2,4,5},{3,5,3},{3,6,3},{2,7,1},{5,7,1}},
  s={{5,1,1},{5,2,1},{7,3,2},{7,4,1},{6,5,1},{6,6,1},{3,7,1},{6,7,2},{2,8,1},{6,8,2}}
}
local rankStarPalettes = {
  earned={h='#DAC6A0', f='#BCA473', s='#29271F'},
  locked={h='#8A8B7E', f='#62645B', s='#252720'}
}

local function cancel(event) if event then removeEvent(event) end end

local function paintRankStar(star, earned)
  if not star then return end
  star:setPhantom(true)
  star:setFocusable(false)
  local pixels = star.antigasRankStarPixels
  if not pixels then
    pixels = {h={}, f={}, s={}}
    local left = math.max(0, math.floor((star:getWidth() - 9) / 2))
    local top = math.max(0, math.floor((star:getHeight() - 9) / 2))
    for tone, runs in pairs(rankStarRectangles) do
      for _, run in ipairs(runs) do
        local rectangle = g_ui.createWidget('UIWidget', star)
        rectangle:setPhantom(true)
        rectangle:setFocusable(false)
        rectangle:setSize({width=run[3], height=1})
        rectangle:addAnchor(AnchorLeft, 'parent', AnchorLeft)
        rectangle:addAnchor(AnchorTop, 'parent', AnchorTop)
        rectangle:setMarginLeft(left + run[1])
        rectangle:setMarginTop(top + run[2])
        pixels[tone][#pixels[tone] + 1] = rectangle
      end
    end
    -- The authored star owns its pixel children and this strong Lua field.
    star.antigasRankStarPixels = pixels
  end
  local palette = earned and rankStarPalettes.earned or rankStarPalettes.locked
  for tone, rectangles in pairs(pixels) do
    for _, rectangle in ipairs(rectangles) do rectangle:setBackgroundColor(palette[tone]) end
  end
end

local function updateRank(completed, total)
  if not window then return end
  local banner = window:getChildById('rankBanner')
  if not banner then return end
  local rankIndex, thresholds = 1, {}
  for index, rank in ipairs(ranks) do
    thresholds[index] = math.ceil(total * rank.fraction)
    if total > 0 and completed >= thresholds[index] then rankIndex = index end
  end
  local rank = ranks[rankIndex]
  banner:recursiveGetChildById('rankName'):setText('Rank ' .. rank.numeral .. ' - ' .. rank.name)
  local progress = banner:recursiveGetChildById('rankProgress')
  local percent = 0
  if total == 0 then
    progress:setText('Complete achievements to advance your rank.')
  elseif rankIndex == #ranks then
    progress:setText(string.format('All %d / %d completed - Legend achieved.', completed, total))
    percent = 100
  else
    local nextThreshold = thresholds[rankIndex + 1]
    progress:setText(string.format('Next: %s at %d / %d completed | %d remaining',
      ranks[rankIndex + 1].name, nextThreshold, total, nextThreshold - completed))
    percent = math.max(0, math.min(100, 100 * (completed - thresholds[rankIndex]) /
      (nextThreshold - thresholds[rankIndex])))
  end
  banner:recursiveGetChildById('rankBar'):setPercent(percent)
  local stars = banner:recursiveGetChildById('rankStars')
  for index = 1, 5 do paintRankStar(stars:getChildById('star' .. index), index < rankIndex) end
  local milestones = banner:recursiveGetChildById('rankMilestones')
  for index, milestone in ipairs(ranks) do
    local label = milestones:getChildById('rank' .. index)
    label:setText(milestone.name .. '\n' .. (total > 0 and tostring(thresholds[index]) or '--') .. ' completed')
    label:setColor(index < rankIndex and '#BCA473' or (index == rankIndex and '#DDD8C6'
      or (index == rankIndex + 1 and '#C3C3BC' or '#AAA99E')))
  end
end

local function fit(label, text)
  label:setTooltip(text)
  local lines, current = {}, ''
  local width = math.max(40, label:getWidth() - 2)
  for word in text:gmatch('%S+') do
    label:setText(word)
    if label:getTextSize().width > width then
      if current ~= '' then lines[#lines + 1] = current; current = '' end
      local part = ''
      for char in word:gmatch('.') do
        label:setText(part .. char)
        if part ~= '' and label:getTextSize().width > width then
          lines[#lines + 1] = part; part = char
        else part = part .. char end
      end
      word = part
    end
    local candidate = current == '' and word or current .. ' ' .. word
    label:setText(candidate)
    if current ~= '' and label:getTextSize().width > width then
      lines[#lines + 1] = current; current = word
    else current = candidate end
  end
  if current ~= '' then lines[#lines + 1] = current end
  label:setText(table.concat(lines, '\n'))
  label:setHeight(math.max(14, #lines * 14 + 2))
end

local function syncPlayerBarSelection()
  local playerBars = modules.game_playerbars
  if playerBars and playerBars.setActionSelected then
    playerBars.setActionSelected('achievements', window and window:isVisible())
  end
end

local function send(action)
  if not g_game.isOnline() or not g_game.getFeature(GameExtendedOpcode) then return false end
  local protocol = g_game.getProtocolGame()
  if not protocol then return false end
  protocol:sendExtendedOpcode(OPCODE, json.encode({action = action}))
  return true
end

local function updateUnread(count)
  if modules.game_playerbars and modules.game_playerbars.setAchievementsUnread then
    modules.game_playerbars.setAchievementsUnread(math.max(0, tonumber(count) or 0) + readyCount)
  end
end

local function updateClaimButton()
  if window then
    window.claimButton:setEnabled(readyCount > 0 and not timeoutEvent and not requestEvent
      and g_game.isOnline() and g_game.getFeature(GameExtendedOpcode))
  end
end

local function render(resetScroll)
  if not window or not current then return end
  local scroll = resetScroll and 0 or window.entriesScroll:getValue()
  local completed, shown, nextByCategory, ordered = 0, 0, {}, {}
  readyCount = 0
  for index, entry in ipairs(current.entries) do
    if entry.completed then completed = completed + 1
    elseif entry.ready then readyCount = readyCount + 1 end
    if not entry.completed and not nextByCategory[entry.category] then nextByCategory[entry.category] = entry.id end
    ordered[#ordered+1] = {entry=entry, index=index,
      priority=entry.completed and 2 or (entry.ready and 0 or 1),
      ratio=(entry.ready or entry.completed) and 1 or entry.progress / entry.target}
  end
  -- Rank uses the entire accepted snapshot, before either objective filter.
  updateRank(completed, #current.entries)
  table.sort(ordered, function(a, b)
    if a.priority ~= b.priority then return a.priority < b.priority end
    if a.ratio ~= b.ratio then return a.ratio > b.ratio end
    return a.index < b.index
  end)
  window.entries:destroyChildren()
  for _, item in ipairs(ordered) do
    local entry = item.entry
    if (statusFilter == 'all' or (statusFilter == 'next' and nextByCategory[entry.category] == entry.id)
      or (statusFilter == 'completed' and entry.completed)
      or (statusFilter == 'active' and not entry.completed)
      or (statusFilter == 'ready' and entry.ready and not entry.completed))
      and (categoryFilter == 'all' or categoryFilter == entry.category) then
      shown = shown + 1
      local row = g_ui.createWidget('AchievementEntry', window.entries)
      fit(row.title, (entry.completed and '[DONE] ' or (entry.ready and '[READY] ' or '')) .. entry.title)
      row.title:setTooltip(entry.category .. ': ' .. entry.title)
      fit(row.reward, 'Reward: ' .. entry.reward)
      row.reward:setTooltip(entry.reward)
      local progress = (entry.completed or entry.ready) and entry.target or entry.progress
      local percent = math.min(100, 100 * progress / entry.target)
      local state = entry.completed and 'Completed' or (entry.ready and 'Reward pending' or 'In progress')
      fit(row.progress, string.format('%s  |  %d / %d  (%d%%)  |  %d remaining', state, progress, entry.target, math.floor(percent), entry.target-progress))
      row.progress:setColor(entry.ready and not entry.completed and '#BCA473' or (entry.completed and '#AAA99E' or '#C3C3BC'))
      row.bar:setPercent(percent)
      row.bar:setBackgroundColor(entry.ready and not entry.completed and '#BCA473' or (entry.completed and '#847A5F' or '#8E805E'))
      row:setBackgroundColor(entry.ready and not entry.completed and '#39362fbb' or (entry.completed and '#2e302b99' or '#28292799'))
      row.separator:setBackgroundColor(entry.ready and not entry.completed and '#BCA47366' or '#ffffff16')
      row:setHeight(row.title:getHeight() + row.reward:getHeight() + row.progress:getHeight() + 32)
    end
  end
  window.summary:setText(string.format('%d / %d completed  |  %d rewards pending  |  %d shown', completed, #current.entries, readyCount, shown))
  local b = current.bonuses or {}
  window.bonuses:setText(string.format('Speed +%d  |  Direct attack +%d%%  |  Direct PvP +%d%%  |  Death loss -%d%%',
    tonumber(b.speed) or 0, tonumber(b.attack) or 0, tonumber(b.pvp) or 0, tonumber(b.deathReduction) or 0))
  window.bonuses:setTooltip('Attack and PvP bonuses apply to direct physical and magic hits. Periodic damage is unchanged.')
  window.message:setText(shown == 0 and 'No achievements match these filters.'
    or (readyCount > 0 and 'Make room in your inventory, then use Claim rewards.' or 'Reach each objective to earn its reward automatically.'))
  window.entriesScroll:setValue(scroll)
  updateClaimButton()
end

local function validEntry(entry)
  if type(entry) ~= 'table' then return false end
  for _, key in ipairs({'id', 'title', 'category', 'reward'}) do
    if type(entry[key]) ~= 'string' or #entry[key] > 200 then return false end
  end
  return type(entry.completed) == 'boolean' and (entry.ready == nil or type(entry.ready) == 'boolean') and type(entry.progress) == 'number'
    and type(entry.target) == 'number' and entry.target > 0 and entry.target <= 2147483647
    and entry.progress >= 0 and entry.progress <= entry.target
    and entry.progress == math.floor(entry.progress) and entry.target == math.floor(entry.target)
end

local function acceptProgress(payload)
  if type(payload.entries) ~= 'table' or #payload.entries > 60 then return end
  for _, entry in ipairs(payload.entries) do if not validEntry(entry) then return end end
  local id, page, pages = payload.snapshotId, payload.page, payload.pages
  if type(id) ~= 'number' or id < 1 or id > 2147483647 or id ~= math.floor(id)
    or type(page) ~= 'number' or type(pages) ~= 'number' or pages < 1 or pages > 20
    or page < 1 or page > pages or page ~= math.floor(page) or pages ~= math.floor(pages) then return end
  if latestSnapshot and id < latestSnapshot then return end
  if not incoming or incoming.id ~= id then
    if latestSnapshot == id then return end
    latestSnapshot = id
    incoming = {id=id, total=pages, parts={}, received=0}
  end
  if incoming.total ~= pages or incoming.parts[page] then return end
  incoming.parts[page] = payload.entries
  incoming.received = incoming.received + 1
  if incoming.received < pages then return end

  local entries, ids = {}, {}
  for index = 1, pages do
    for _, entry in ipairs(incoming.parts[index]) do
      if ids[entry.id] or #entries >= 60 then incoming=nil; return end
      ids[entry.id] = true
      entries[#entries + 1] = entry
    end
  end
  current = {entries=entries, bonuses=payload.bonuses}
  incoming = nil
  cancel(timeoutEvent); timeoutEvent=nil
  for _, entry in ipairs(entries) do
    if not categories[entry.category] then
      categories[entry.category] = true
      window.category:addOption(entry.category, entry.category)
    end
  end
  render(false)
  if window:isVisible() then send('markSeen'); updateUnread(0)
  else updateUnread(tonumber(payload.unread) or 0) end
end

local function onOpcode(protocol, opcode, buffer)
  if not window or opcode ~= OPCODE or type(buffer) ~= 'string' or #buffer > 8192 then return end
  local ok, payload = pcall(json.decode, buffer)
  if not ok or type(payload) ~= 'table' then return end
  if payload.action == 'progress' then acceptProgress(payload)
  elseif payload.action == 'seen' then updateUnread(0) end
end

local function request(action)
  if not window or timeoutEvent or requestEvent then return end
  if action == 'claimRewards' and readyCount == 0 then return end
  local now = g_clock.millis()
  if lastRequest and now - lastRequest < 2100 then
    requestEvent = scheduleEvent(function() requestEvent=nil; request(action); updateClaimButton() end, 2100 - (now-lastRequest))
    updateClaimButton()
    return
  end
  if not send(action) then
    window.message:setText('Connect to the game to view your achievement progress.')
    return
  end
  lastRequest = now
  window.message:setText(action == 'claimRewards' and 'Claiming achievement rewards...' or 'Updating achievement progress...')
  timeoutEvent = scheduleEvent(function()
    timeoutEvent=nil; incoming=nil
    if window then
      window.message:setText(action == 'claimRewards' and 'Reward claim could not be confirmed. Please try Refresh.' or 'Progress could not be updated. Please try Refresh.')
      updateClaimButton()
    end
  end, 8000)
  updateClaimButton()
end

function refresh() request('getProgress') end

function claimRewards() request('claimRewards') end

function show()
  if not window then return end
  local size = g_ui.getRootWidget():getSize()
  window:setSize({width=660, height=math.min(580, size.height-16)})
  window:show(); window:raise(); window:focus()
  if current then render(false); send('markSeen'); updateUnread(0) end
  refresh()
  cancel(refreshEvent)
  local function poll()
    refreshEvent=nil
    if window and window:isVisible() and g_game.isOnline() then
      refresh()
      refreshEvent=scheduleEvent(poll, 10000)
    end
  end
  refreshEvent=scheduleEvent(poll, 10000)
end

function hide()
  cancel(refreshEvent); refreshEvent=nil
  if window then window:hide() end
end

function toggle()
  if window and window:isVisible() then hide() else show() end
end

local function onGameStart()
  cancel(startupEvent)
  -- onGameStart precedes the server's extended-opcode handshake.
  startupEvent=scheduleEvent(function() startupEvent=nil; refresh() end, 1000)
end

local function onGameEnd()
  hide()
  cancel(timeoutEvent); cancel(startupEvent); cancel(requestEvent)
  timeoutEvent,startupEvent,requestEvent=nil,nil,nil
  current,incoming,latestSnapshot,lastRequest=nil,nil,nil,nil
  readyCount=0
  if window then
    updateRank(0, 0)
    window.entries:destroyChildren()
    window.summary:setText('Achievement objectives')
    window.bonuses:setText('Progress and rewards are saved per character.')
    window.message:setText('Connect to the game to view your achievement progress.')
    updateClaimButton()
  end
  updateUnread(0)
end

function init()
  window=g_ui.displayUI('achievements'); window:hide()
  updateRank(0, 0)
  connect(window, {onVisibilityChange=syncPlayerBarSelection})
  syncPlayerBarSelection()
  for _,option in ipairs({{'Next objectives','next'},{'All objectives','all'},{'In progress','active'},{'Completed','completed'},{'Ready to claim','ready'}}) do
    window.filter:addOption(option[1],option[2])
  end
  window.category:addOption('All categories','all')
  window.filter.onOptionChange=function(widget,text,value) statusFilter=value; render(true) end
  window.category.onOptionChange=function(widget,text,value) categoryFilter=value; render(true) end
  updateClaimButton()
  connect(g_game,{onGameStart=onGameStart,onGameEnd=onGameEnd})
  ProtocolGame.registerExtendedOpcode(OPCODE,onOpcode,true)
  if g_game.isOnline() then onGameStart() end
end

function terminate()
  onGameEnd()
  disconnect(g_game,{onGameStart=onGameStart,onGameEnd=onGameEnd})
  if window then disconnect(window, {onVisibilityChange=syncPlayerBarSelection}) end
  ProtocolGame.unregisterExtendedOpcode(OPCODE)
  if window then window:destroy() end
  window=nil
end
