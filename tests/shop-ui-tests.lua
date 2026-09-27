-- Offline client fixture. Temporarily dofile() this after loadModules() in an
-- isolated client, then remove that boot hook before creating a public ZIP.
local function report(line)
  local file = assert(io.open('shop-ui-qa-report.txt', 'a'))
  file:write(line .. '\n')
  file:close()
end

local function checked(callback, delay)
  scheduleEvent(function()
    local ok, err = pcall(callback)
    if not ok then
      report('FAIL: ' .. tostring(err))
      g_app.exit()
    end
  end, delay)
end

local function offer(item, title, description, cost)
  return {type='item', item=item, count=1, id=cost, title=title,
    description=description, cost=cost}
end

local function category(item, name, offers)
  return {type='item', item=item, name=name, offers=offers}
end

local function run()
  report('START: Shop UI QA')
  assert(not g_game.isOnline(), 'QA must not connect or purchase')
  g_game.setClientVersion(772)
  local shopModule = modules.game_shop
  local root = g_ui.getRootWidget()
  local window = root:recursiveGetChildById('shopWindow')
  assert(window, 'Shop OTUI loads')
  assert(window:getWidth() == 750 and window:getHeight() == 500, 'Classic window size')
  shopModule.show()
  assert(window:isVisible(), 'Open Shop')
  shopModule.processStatus({points=123,
    buyUrl='https://tibia74.tech/coins.php',
    ad={image='https://tibia74.tech/antigas-shop-banner.png',
      url='https://tibia74.tech/coins.php', text=''}})
  assert(window.infoPanel:getWidth() == 210, 'Compact sidebar')
  assert(window.infoPanel:getHeight() == 68, 'Compact points block')
  assert(window.adPanel:getHeight() == 68, 'Local branded header')
  assert(window.adPanel.ad:getWidth() == 56 and
    window.adPanel.ad:getHeight() == 64, 'Fixed crest geometry')
  assert(type(window.adPanel.ad.onMouseRelease) == 'function', 'Existing crest link')
  assert(window.categories:getY() == window.offers:getY(), 'Aligned column tops')
  assert(window.infoPanel.buy:isVisible() and
    type(window.infoPanel.buy.onMouseRelease) == 'function', 'Buy Points callback')
  assert(window.infoPanel.points:getText() == 'Points: 123', 'Live points')

  local longDescription = 'ATTENTION: Place the furniture package in the position you want before using it, otherwise you will not be able to move it later.'
  local data = {
    category(5128, 'Premium Points', {
      offer(5128, 'Antigas Ticket', 'The value of this ticket is 10 premium points.', 11),
      offer(5130, 'Antigas Coin', 'Coin used to get premium points.', 2)}),
    category(5101, 'Regeneration Items', {
      offer(5102, 'Antigas Ring', 'Eternal Light, + 1HP/2s + 2MP/3s.', 80),
      offer(3549, 'Pair Of Soft Boots', 'INFINITE Regen + 1 HP/MP per 2 second.', 50)}),
    category(5100, 'Scrolls', {
      offer(5291, 'Exp Scroll', '+25% experience for 1 hour.', 25),
      offer(5140, 'House Scroll', 'Use this item to buy a house.', 50),
      offer(5226, 'Avar Tar Blessing', 'Ability to buy all available blessings at once from Avar Tar.', 30),
      offer(5100, 'Postman Scroll', 'Access to use mailboxes in hazardous areas and negotiate with rashid.', 30),
      offer(5131, 'Blessing Scroll', 'Use this item to receive all regular blessings.', 25),
      offer(5129, 'Teleport Scroll', 'Using it will take you to your city of origin.', 10)}),
    category(5282, 'Training Offline', {
      offer(5285, 'Training Club', longDescription, 50),
      offer(5287, 'Training Sword', longDescription, 50),
      offer(5286, 'Training Axe', longDescription, 50),
      offer(5288, 'Training Distance', longDescription, 50),
      offer(5289, 'Training Magic', longDescription, 50)}),
    category(3460, 'Utilities', {
      offer(5247, 'Antigas Amulet', '+10 Speed.', 40),
      offer(5246, 'Magic Gold Converter', 'Infinite gold converter.', 30),
      offer(5171, 'Obsidian Knife', 'Useful tool for tanners.', 10),
      offer(5139, 'Light Shovel', 'A lighter shovel.', 10),
      offer(5138, 'Elvenhair Rope', 'Light rope.', 10),
      offer(5154, 'Old Backpack', '18 oz and 20 slots.', 10),
      offer(5132, 'Check Blessing', 'Check your blessings.', 10),
      offer(3725, '100 X Brown Mushroom', 'Do not go hungry.', 5),
      offer(5097, 'Dice', 'A game item.', 5),
      offer(5336, 'universe scale mail', 'Armor defence.', 100)}),
    category(5128, 'Single item test', {
      offer(5128, 'A deliberately long product name for clipping',
        'This description should remain available in a tooltip.', 1)})
  }
  shopModule.processCategories(data)
  assert(window.categories:getChildCount() == #data, 'All categories loaded')

  local scrollCategory
  for index, entry in ipairs(data) do
    window.categories:getChildByIndex(index):focus()
    assert(window.offers:getChildCount() == #entry.offers,
      'Offer count for ' .. entry.name)
    assert(window.adPanel.heading:getText() == entry.name, 'Category heading')
    assert(window.adPanel.summary:getText():find(tostring(#entry.offers), 1, true),
      'Offer count in header')
    local previousPrice, previousBuy
    for _, row in ipairs(window.offers:getChildren()) do
      assert(row:getHeight() == 56, 'Consistent row height')
      assert(row.item:getWidth() == 32 and row.spriteArea:getWidth() == 44,
        'Original sprite in fixed area')
      assert(row.price:getText():find(' points', 1, true), 'Separate price')
      assert(row.buyButton:getWidth() == 48 and row.buyButton:getHeight() == 22,
        'Uniform BUY button')
      assert(row.title:getX() + row.title:getWidth() <= row.price:getX(),
        'Title cannot overlap price')
      assert(row.description:getX() + row.description:getWidth() <= row.price:getX(),
        'Description cannot overlap price')
      assert(row.buyButton:getX() + row.buyButton:getWidth() < window.offersScrollBar:getX(),
        'BUY clears scrollbar')
      if previousPrice then
        assert(row.price:getX() == previousPrice and
          row.buyButton:getX() == previousBuy, 'Aligned price and BUY columns')
      end
      previousPrice, previousBuy = row.price:getX(), row.buyButton:getX()
    end
    if entry.name == 'Training Offline' then
      assert(window.offers:getChildByIndex(1).description:getTooltip() == longDescription,
        'Full long description remains available')
    elseif entry.name == 'Scrolls' then
      scrollCategory = index
    end
  end
  report('PASS: categories 1/2/5/6/10, fixed sprite/price/BUY columns, long descriptions')

  window.categories:getChildByIndex(scrollCategory):focus()
  local scrollRow = window.offers:getChildByIndex(1)
  assert(scrollRow.price:getText() == '25 points', 'Two-digit price')
  signalcall(scrollRow.buyButton.onClick, scrollRow.buyButton)
  checked(function()
    shopModule.buyCanceled() -- Confirms BUY opens the existing confirmation only.
    report('PASS: BUY confirmation callback; purchase not submitted')
    shopModule.processStatus({points=98, buyUrl='https://tibia74.tech/coins.php'})
    assert(window.infoPanel.points:getText() == 'Points: 98', 'Points refresh')
    assert(window.adPanel.ad.onMouseRelease == nil, 'Missing ad clears old link')
    shopModule.processStatus({points=0})
    assert(not window.infoPanel.buy:isVisible(), 'No missing payment URL callback')
    assert(window.infoPanel:getHeight() == 68 and window.adPanel:getHeight() == 68,
      'Stable header without remote ad or payment URL')
    shopModule.processStatus({points=98, buyUrl='https://tibia74.tech/coins.php'})
    shopModule.processHistory({offer(5291, 'Exp Scroll', 'Bought on test date.', 25)})
    shopModule.showHistory()
    assert(window.offers:getChildCount() == 1, 'History lists purchases')
    assert(window.adPanel.heading:getText() == 'Transaction history', 'History heading')
    assert(not window.offers:getChildByIndex(1).buyButton:isVisible(),
      'History cannot be bought again')
    shopModule.hide()
    assert(not window:isVisible(), 'Close Shop')
    shopModule.show()
    assert(window:isVisible(), 'Reopen Shop')
    window.categories:getChildByIndex(5):focus()
    assert(window.offersScrollBar:getMaximum() > 0, 'Many items scroll')
    window.offersScrollBar:setValue(window.offersScrollBar:getMaximum())
    report('PASS: history, points refresh, close/reopen, scrollbar')
    local sizes = {{width=800,height=600}, {width=1024,height=768},
      {width=1366,height=768}}
    local function resizeCheck(index)
      local size = sizes[index]
      if not size then
        report('PASS: Shop OTUI and Lua runtime at all tested sizes')
        if SHOP_QA_PREVIEW then
          window.categories:getChildByIndex(1):focus()
          window.offersScrollBar:setValue(0)
          window.categories:getLastChild():destroy() -- Remove synthetic name test from preview.
          report('PREVIEW: ready for visual review')
          scheduleEvent(function() g_app.exit() end, 240000)
        else
          g_app.exit()
        end
        return
      end
      g_window.resize(size)
      checked(function()
        local screen, bounds = root:getRect(), window:getRect()
        assert(bounds.x >= screen.x and bounds.y >= screen.y and
          bounds.x + bounds.width <= screen.x + screen.width and
          bounds.y + bounds.height <= screen.y + screen.height,
          'Shop fits ' .. size.width .. 'x' .. size.height)
        assert(window.offers:getX() + window.offers:getWidth() <
          window.offersScrollBar:getX(), 'Scrollbar space after resize')
        window.offersScrollBar:setValue(window.offersScrollBar:getMaximum())
        checked(function()
          local last = window.offers:getLastChild()
          local lastBottom = last:getY() + last:getHeight()
          local listBottom = window.offers:getY() + window.offers:getHeight()
          assert(lastBottom <= listBottom + 1,
            'Last product visible after scrolling: ' ..
            tostring(lastBottom) .. ' > ' .. tostring(listBottom))
          report('PASS: geometry ' .. size.width .. 'x' .. size.height)
          resizeCheck(index + 1)
        end, 120)
      end, 250)
    end
    resizeCheck(1)
  end, 120)
end

checked(run, 1200)
