-- Offline integration fixture. Run ONLY in an isolated client copy, after loadModules().
-- Uses the existing inbound callback; never connects or writes character data.
local function report(message)
  local file = assert(io.open(BESTIARY_QA_REPORT, 'a'))
  file:write(message .. '\n')
  file:close()
end
local function later(callback, delay)
  return scheduleEvent(function()
    local ok, err = pcall(callback)
    if not ok then report('FAIL: ' .. tostring(err)) end
  end, delay)
end
local function run()
  report('START Bestiary UI tests')
  assert(not g_game.isOnline(), 'Offline test only')
  g_window.setTitle('Antigas - Bestiary UI QA (offline)')
  g_window.setMinimumSize({width=480,height=360}) -- Fixture only; public minimum remains unchanged.
  g_window.resize({width = 900, height = 650})
  g_game.setClientVersion(772)
  local m = modules.game_wiki
  local root = g_ui.getRootWidget()
  local function window() return root:recursiveGetChildById('wikiWindow') end
  local function child(id) return window():recursiveGetChildById(id) end
  local function cards() return child('list'):getChildren() end
  local function packet(payload) ProtocolGame.onExtendedOpcode(nil, 124, json.encode(payload)) end
  m.show()
  assert(window():isVisible(), 'Open')
  packet({action = 'progress', data = {amazon = 347, ['ancient scarab'] = 1000, assassin = 99, badger = 500}})
  assert(#cards() == 138, 'Full catalog')
  local first = cards()[1]
  assert(first:recursiveGetChildById('killProgressBar'):getPercent() == 34.7, 'Proportional bar')
  assert(first.killProgressText:getText():find('34%%'), 'Percentage')
  assert(not cards()[5]:recursiveGetChildById('killProgressBar'):isVisible(), 'Zero progress has no fill')
  m.setProgressFilter('progress')
  assert(#cards() == 3, 'In progress excludes zero/completed')
  m.setProgressFilter('completed')
  assert(#cards() == 1, 'Completed only')
  child('creatureFilter'):setText('AMAZON')
  assert(#cards() == 0 and child('emptyState'):isVisible(), 'Search combines with filter')
  m.setProgressFilter('all')
  assert(#cards() == 1, 'Case insensitive search')
  m.clearFilter()
  assert(#cards() == 138, 'Clear search')
  first = cards()[1]
  signalcall(first.onClick, first)
  local detail = root:recursiveGetChildById('creatureWindow')
  assert(detail and detail:isVisible() and detail:getText() == 'Amazon', 'Click callback opens details')
  packet({action = 'update', monster = 'Amazon', kills = 348})
  assert(cards()[1] == first, 'Kill update does not rebuild matching grid')
  assert(detail:recursiveGetChildById('killProgressText'):getText():find('348 / 1000', 1, true), 'Live details update')
  m.closeCreature()
  assert(not detail:isVisible(), 'Close details')
  m.setProgressFilter('progress')
  packet({action = 'update', monster = 'Amazon', kills = 1000})
  assert(#cards() == 2, 'Completion leaves progress filter')
  m.setProgressFilter('completed')
  assert(#cards() == 2, 'Completion enters completed filter')
  m.hide()
  packet({action = 'update', monster = 'Badger', kills = 501})
  assert(not window():isVisible(), 'Incoming progress cannot reopen a closed window')
  m.toggle()
  assert(window():isVisible(), 'Toggle open')
  m.toggle()
  assert(not window():isVisible(), 'Toggle closed')
  m.setProgressFilter('all')
  child('creatureFilter'):setText('[')
  assert(#cards() == 0, 'Search is literal, not a Lua pattern')
  m.clearFilter()
  packet({action = 'progress', data = {amazon = 347, ['ancient scarab'] = 1000, assassin = 99, badger = 500}})
  m.show()
  local scroll = child('listScrollbar')
  scroll:setValue(200)
  local before = scroll:getValue()
  packet({action = 'update', monster = 'Amazon', kills = 348})
  assert(scroll:getValue() == before, 'Progress preserves scroll position')
  signalcall(g_game.onGameEnd)
  assert(not window():isVisible(), 'Logout closes Bestiary')
  m.show()
  assert(cards()[1].killProgressText:getText():find('0 / 1000', 1, true), 'No progress leaks to another session')
  m.terminate()
  assert(not root:recursiveGetChildById('wikiWindow'), 'Terminate destroys window')
  m.init()
  m.show()
  packet({action = 'progress', data = {amazon = 347, ['ancient scarab'] = 1000, assassin = 99, badger = 500}})
  assert(cards()[1].killProgressText:getText():find('347 / 1000', 1, true), 'Opcode re-registers after module reload')
  local catalog = dofile('/modules/game_wiki/data/antigas_monster.lua')
  local longLists = 0
  for id, monster in ipairs(catalog) do
    m.selectCreature(id)
    local text = root:recursiveGetChildById('creatureWindow'):getChildById('lootDesc'):getText()
    local seen = {}
    for _, entry in ipairs(type(monster.loot) == 'table' and monster.loot or {}) do
      assert(text:find(entry.itemName, 1, true), 'Missing loot name: ' .. monster.name .. '/' .. entry.itemName)
      if not seen[entry.itemName] then
        seen[entry.itemName] = true
        if entry.itemName == 'Gold Coin' then
          local _, copies = text:gsub('Gold Coin', '')
          assert(copies == 1, 'Repeated Gold Coin label: ' .. monster.name)
        end
      end
    end
    if #text > 200 then longLists = longLists + 1 end
    if type(monster.loot) ~= 'table' or #monster.loot == 0 then
      assert(text == 'This creature does not drop any loot.', 'Empty loot fallback')
    end
  end
  assert(longLists > 0, 'Long lists were exercised')
  m.closeCreature()
  report('PASS: all 138 detail lists; duplicate labels removed; ' .. longLists .. ' long lists untruncated')
  report('PASS: callbacks, filters, search, selection, live progress and open/close')

  local sizes = {{width=480,height=360}, {width=640,height=480}, {width=800,height=600}, {width=1100,height=700}}
  local function checkSize(index)
    local size = sizes[index]
    if not size then
      g_window.resize({width=900,height=650})
      later(function() m.resizeBestiary(); child('listScrollbar'):setValue(0); report('READY: offline visual review') end, 200)
      return
    end
    g_window.resize(size)
    later(function()
      local list, scrollbar = child('list'), child('listScrollbar')
      local w = window():getRect()
      local r = root:getRect()
      assert(r.width == size.width and r.height == size.height, 'Requested viewport applied')
      assert(w.width <= r.width and w.height <= r.height, 'Window within screen')
      local rows = cards()
      local columns = size.width < 640 and 2 or 4
      assert(rows[1]:getY() == rows[columns]:getY() and rows[columns+1]:getY() > rows[1]:getY(), 'Responsive columns')
      assert(rows[columns]:getX() + rows[columns]:getWidth() <= list:getX() + list:getWidth(), 'Grid width fits after resize callback')
      assert(list:getX() + list:getWidth() <= scrollbar:getX() - 4, 'Scrollbar clearance')
      assert(list:getY() + list:getHeight() <= child('creatureFilter'):getY() - 8, 'Footer clearance')
      scrollbar:setValue(scrollbar:getMaximum())
      later(function()
        local last = cards()[#cards()]
        assert(last:getY() >= list:getY(), 'Last row top visible')
        assert(last:getY() + last:getHeight() <= list:getY() + list:getHeight() + 1, 'Last row bottom visible')
        for _, card in ipairs(cards()) do
          local label = card.creatureLabel
          assert(label:getTextSize().height <= label:getHeight(), 'Long name fits: ' .. label:getText())
          assert(label:getTextSize().width <= label:getWidth(), 'Name width fits: ' .. label:getText())
          local creature = card:recursiveGetChildById('creature')
          assert(creature:getWidth() <= 64 and creature:getHeight() <= 64, 'Sprite fits fixed area')
          assert(card.killProgressText:getTextSize().width <= card.killProgressText:getWidth(), 'Progress text fits')
          assert(card.stage2:getY() + card.stage2:getHeight() <= card:getY() + card:getHeight(), 'Markers stay in card')
          assert(not card.rewardBadgeSlot:isVisible(), 'Future rewards remain hidden')
        end
        m.selectCreature(1)
        local details = root:recursiveGetChildById('creatureWindow')
        assert(details:getWidth() <= root:getWidth() and details:getHeight() <= root:getHeight(), 'Details fit viewport')
        local loot, close = details:getChildById('lootDesc'), details:getChildById('buttonCancel')
        assert(loot:getY() + loot:getHeight() < close:getY(), 'Details footer clear')
        m.closeCreature()
        report('PASS: geometry and last row ' .. r.width .. 'x' .. r.height)
        checkSize(index + 1)
      end, 100)
    end, 200)
  end
  checkSize(1)
end
later(run, 1000)
