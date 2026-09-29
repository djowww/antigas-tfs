local MARKET_OPCODE = 202

local window
local searchEvent
local categories = {}
local selectedCategory = "all"
local selectedItem
local currentView = "catalog"
local visibleItems
local pendingMessage
local pendingRequest
local requestSequence = 0
local page = 1
local serverVersion = 0
local formSide = 'sell'
local sideChosen = false
local mutations = {create=true,fill=true,cancel=true,collect=true}
local rightMode = 'overview'
local selectedFresh = false
local balanceData
local listState = 'idle'
local resetting = false
local activeRead, queuedRead, readDispatchEvent, readTimeoutEvent
local desiredRead = 0
local readBlocked = false
local recoverableReadError = false
local transactionTimer
local transactionRetry = false
local updateRetry, invalidateBalances, setListState, dispatchRead

local function numberText(value)
 local text = string.format('%.0f', value or 0)
 local result = text:reverse():gsub('(%d%d%d)', '%1,'):reverse():gsub('^,', '')
 return result
end

local function savePending(raw)
 local saved = g_settings.getNode('AntigasMarketPending') or {}
 saved[g_game.getCharacterName()] = raw
 g_settings.setNode('AntigasMarketPending', saved)
 g_settings.save()
end

local function syncPlayerBarSelection()
 local playerBars = modules.game_playerbars
 if playerBars and playerBars.setActionSelected then
  playerBars.setActionSelected('market', window and window:isVisible())
 end
end

local function transmitPending()
 local protocol = g_game.getProtocolGame()
 if protocol and g_game.isOnline() and pendingRequest then
  protocol:sendExtendedOpcode(MARKET_OPCODE, pendingRequest.raw)
 end
end

local function sendAction(action, data)
	local protocol = g_game.getProtocolGame()
	if not g_game.isOnline() or not protocol or not g_game.getFeature(GameExtendedOpcode) then return end
	if mutations[action] then
  if serverVersion < 2 then return displayInfoBox('Market', 'Please reopen Market after installing the updated client/server.') end
  if pendingRequest then return displayInfoBox('Market', 'A transaction is awaiting confirmation. Use Retry to check the same request safely.') end
  requestSequence = requestSequence + 1
  local request = {action=action,data=data or {},requestId=string.format('%d-%d-%d',os.time(),math.random(1,16777215),requestSequence)}
  pendingRequest = {raw=json.encode(request),id=request.requestId}
  selectedFresh=false
  savePending(pendingRequest.raw)
  transactionRetry = false
  if transactionTimer then removeEvent(transactionTimer) end
  transactionTimer = scheduleEvent(function()
   transactionTimer=nil
   if pendingRequest then transactionRetry=true;updateRetry();onFormChange() end
  end,10000)
  invalidateBalances()
  updateRetry()
  onFormChange()
  transmitPending()
  return
 end
	protocol:sendExtendedJSONOpcode(MARKET_OPCODE, { action = action, data = data or {} })
end

local function clearList()
	window.offerList:destroyChildren()
end

local function getWindowChild(id)
	-- Some controls (offerList, search, currencyFilter) are direct children;
	-- creation-form controls are nested inside createPanel.
	return window:recursiveGetChildById(id)
end

local function shortNumber(value)
 local divisor,suffix
 if value>=1000000000 then divisor,suffix=1000000000,'B'
 elseif value>=1000000 then divisor,suffix=1000000,'M'
 elseif value>=10000 then divisor,suffix=1000,'K' end
 if divisor then
  local scaled=math.floor(value/divisor*10+0.5)/10
  local text=string.format('%.1f',scaled):gsub('%.0$','')
  return (scaled*divisor~=value and '~' or '')..text..suffix
 end
 return numberText(value)
end

local function fitText(label, text)
 label:setText(text)
 if label:getWidth() < 1 then return end
 local shortened = text
 while #shortened > 1 and label:getTextSize().width > label:getWidth() do
  shortened=shortened:sub(1,-2);label:setText(shortened..'...')
 end
 label:setTooltip(text)
end

local function fitTitle(label,text)
 -- Two measured lines; do not silently clip long selected item names.
 label:setTextWrap(false)
 local first,rest='',text
 for word in text:gmatch('%S+') do
  local candidate=first=='' and word or first..' '..word
  label:setText(candidate)
  if label:getTextSize().width>label:getWidth() then break end
  first=candidate
 end
 if first=='' then fitText(label,text);return end
 rest=text:sub(#first+1):match('^%s*(.*)$')
 if rest=='' then label:setText(first) else
  fitText(label,rest)
  label:setText(first..'\n'..label:getText())
 end
 label:setTooltip(text)
end

updateRetry = function()
 if not window then return end
 local button=getWindowChild('retry')
 local visible=(pendingRequest and transactionRetry) or (recoverableReadError and not readBlocked)
 button:setVisible(not not visible)
 button:setEnabled(not not visible)
 button:setTooltip(pendingRequest and 'Check the SAME pending transaction using its original request ID; never create a second trade.' or 'Retry the failed query. No transaction is executed.')
end

invalidateBalances = function()
 balanceData=nil
 if not window then return end
 window.balanceLabel.goldBalance:setText('Bank: -- | Carried gold: --')
 window.balanceLabel.antigasBalance:setText('Antigas Coins: --')
 window.balanceLabel.goldBalance:setTooltip('Balances unavailable. Refresh to request current values.')
 window.balanceLabel.antigasBalance:setTooltip('Balance unavailable. Refresh to request current values.')
 getWindowChild('collect'):setText('Collect (--)')
 getWindowChild('collect'):setTooltip('Refresh to check pending deliveries. Gold goes to your bank; items and Antigas Coins go to your town depot.')
 getWindowChild('collect'):setEnabled(false)
end

local function stopReads()
 if searchEvent then removeEvent(searchEvent);searchEvent=nil end
 if readDispatchEvent then removeEvent(readDispatchEvent);readDispatchEvent=nil end
 if readTimeoutEvent then removeEvent(readTimeoutEvent);readTimeoutEvent=nil end
 activeRead,queuedRead=nil,nil
end

local function updateContext()
 if not window then return end
 local selected=selectedItem~=nil
 getWindowChild('emptySelection'):setVisible(not selected)
 getWindowChild('selectedItemPanel'):setVisible(selected)
 getWindowChild('contextActions'):setVisible(selected)
 getWindowChild('formPanel'):setVisible(selected and rightMode=='create')
 getWindowChild('contextHelp'):setVisible(selected and rightMode~='create')
 getWindowChild('showCreate'):setOn(rightMode=='create')
 local itemOffers=selected and currentView=='offers' and selectedCategory=='all' and window.search:getText()==selectedItem.name
 getWindowChild('selectedOffers'):setOn(not not itemOffers)
 getWindowChild('contextHelp'):setText(itemOffers and
  'Offers for this item are shown in the list. Buy or sell only after reviewing and confirming the trade.' or
  'View offers to trade with another player, or create a listing for others to fill.')
 if selected then
  fitTitle(getWindowChild('selectedName'),selectedItem.name)
  getWindowChild('selectedName'):setTooltip(selectedItem.name..' | '..(selectedItem.category or ''))
  getWindowChild('selectedOwned'):setText(selectedFresh and ('You own: '..numberText(selectedItem.owned or 0)) or 'You own: -- (refresh catalog)')
 end
end

local function hasSprite(id)
 if not visibleItems then
  if not g_things.isDatLoaded() then return false end
  visibleItems = {}
  -- Enumerate valid types instead of querying nonexistent IDs (which logs errors).
  for _, thing in pairs(g_things.getThingTypes(ThingCategoryItem)) do
   local thingId = thing:getId()
   if thingId >= 100 then
    for _, sprite in ipairs(thing:getSprites()) do
     if sprite > 0 and sprite <= g_sprites.getSpritesCount() then
      visibleItems[thingId] = true
      break
     end
    end
   end
  end
 end
 return visibleItems[tonumber(id)] == true
end

local function setView(view)
 if currentView ~= view then clearList() end
 currentView = view
 local catalogView = view == 'catalog'
 local mine = view == 'mine'
 local historyView = view == 'history'
 window.currencyFilter:setEnabled(view == 'offers')
 window.sideFilter:setEnabled(view == 'offers')
 window.search:setEnabled(not mine and not historyView)
 window.categoryPanel:setEnabled(not mine and not historyView)
 window.ownedOnly:setEnabled(catalogView)
 getWindowChild('history'):setOn(historyView)
 for _, pair in ipairs({{'catalogTab','catalog'},{'offersTab','offers'},{'mineTab','mine'}}) do
  getWindowChild(pair[1]):setOn(pair[2] == view)
 end
 for _, button in ipairs(window.categoryPanel:getChildren()) do
  button:setOn(button.categoryId == selectedCategory)
 end
 updateContext()
end

local function emptyList(text)
 local label = g_ui.createWidget('Label', window.offerList)
 label:setWidth(math.max(180,window.offerList:getWidth()-18))
 label:setHeight(64)
 label:setTextWrap(true)
 label:setText(text)
 label:setColor('#bfbfbf')
end

setListState = function(state, text)
 listState=state
 if not window then return end
 getWindowChild('listStatus'):setText(state=='loading' and 'Loading...' or state=='error' and 'Query failed' or '')
 if state~='ready' then
  clearList()
  emptyList(text or 'Loading...')
  getWindowChild('prevPage'):setEnabled(false)
  getWindowChild('nextPage'):setEnabled(false)
  getWindowChild('pageLabel'):setText(state=='loading' and 'Page ...' or 'Page --')
 end
 updateContext()
 onFormChange()
end

-- List responses have no query ID in the existing protocol. Only one query
-- may be in flight; coalesce newer input and never paint a superseded reply.
-- A timeout is NOT treated as cancellation: a late response still owns its
-- slot. Reconnect is required if it never arrives, rather than mislabel data.
dispatchRead = function()
 if activeRead or readDispatchEvent or not queuedRead or readBlocked then return end
 readDispatchEvent=scheduleEvent(function()
  readDispatchEvent=nil
  if activeRead or not queuedRead or readBlocked then return end
  activeRead=queuedRead;queuedRead=nil
  local request=activeRead
  readTimeoutEvent=scheduleEvent(function()
   readTimeoutEvent=nil
   if activeRead~=request then return end
   readBlocked=true;selectedFresh=false
   invalidateBalances()
   setListState('error','No response. Reconnect to the game before retrying safely.')
   updateRetry()
  end,15000)
  sendAction(request.action,request.data)
 end,180)
end

local function beginRead(view,action,data)
 if resetting or readBlocked then
  if readBlocked then setListState('error','No response. Reconnect to the game before retrying safely.') end
  return
 end
 if searchEvent then removeEvent(searchEvent);searchEvent=nil end
 desiredRead=desiredRead+1
 local key=table.concat({action,tostring(data.page),tostring(data.side),tostring(data.category),
  tostring(data.currency),tostring(data.search),tostring(data.ownedOnly)},'|')
 recoverableReadError=false
 if view=='catalog' then selectedFresh=false end
 setListState('loading')
 if activeRead and activeRead.key==key then
  activeRead.generation=desiredRead;queuedRead=nil
 else queuedRead={view=view,action=action,data=data,key=key,generation=desiredRead} end
 updateRetry()
 dispatchRead()
end

local function finishRead(view,payload)
 if not activeRead or activeRead.view~=view then return false end
 if payload.page and tonumber(payload.page)~=activeRead.data.page then return false end
 local request=activeRead
 if readTimeoutEvent then removeEvent(readTimeoutEvent);readTimeoutEvent=nil end
 activeRead=nil;readBlocked=false
 local current=request.generation==desiredRead and view==currentView
 if not current then dispatchRead();return false end
 listState='ready';recoverableReadError=false
 getWindowChild('listStatus'):setText('')
 updateRetry()
 return true
end

local function currencyLabel(id)
	if id == 5130 then return "Antigas Coin" end
	return "gold"
end

local function paymentSource(currency)
 return currency == 5130 and 'Antigas Coins from your inventory.' or 'Gold: bank first, then gold/platinum/crystal coins.'
end

local function deliveryDestination(selling, currency)
 if not selling then return 'Bought items: Collect to your town depot.' end
 return currency == 5130 and 'Payment: Collect Antigas Coins to your town depot.' or 'Payment: Collect gold to your bank.'
end

local function goldBreakdown(total)
 local crystal = math.floor(total / 10000)
 local platinum = math.floor(total % 10000 / 100)
 local gold = total % 100
 local parts = {}
 if crystal > 0 then parts[#parts+1] = numberText(crystal)..' crystal' end
 if platinum > 0 then parts[#parts+1] = numberText(platinum)..' platinum' end
 if gold > 0 then parts[#parts+1] = numberText(gold)..' gold' end
 return table.concat(parts, ' + ')
end

local function getCurrencyFilter()
	local option = window.currencyFilter:getCurrentOption()
	return option and tonumber(option.data) or 0
end

local function getFormCurrency()
	local option = getWindowChild("currency"):getCurrentOption()
	return option and tonumber(option.data) or 3031
end

local function setCoin(widget, currency)
 widget:setItemId(hasSprite(currency) and currency or 0)
 -- A full pile is legible at 16px; this is a symbol, never a quantity label.
 widget:setItemCount(100)
 widget:setShowCount(false)
end

local function updateCurrencyCombo(combo)
 local option = combo:getCurrentOption()
 local currency = option and tonumber(option.data) or 0
 setCoin(combo.coin, currency == 0 and 3031 or currency)
 setCoin(combo.secondCoin, 5130)
 combo.secondCoin:setVisible(currency == 0)
 combo:setTextOffset({x=currency == 0 and 41 or 25,y=0})
end

local function currencyMenu(combo)
 local menu = g_ui.createWidget('ComboBoxPopupMenu')
 menu:setId(combo:getId()..'PopupMenu')
 menu:setGameMenu(true)
 for _, option in ipairs(combo.options) do
  local text, currency = option.text, tonumber(option.data)
  menu:addOption(text, function() combo:setCurrentOption(text) end)
  local button = menu:getLastChild()
  button:setTextOffset({x=currency == 0 and 41 or 25,y=0})
  local icon = g_ui.createWidget('AntigasMarketCoin',button)
  icon:addAnchor(AnchorLeft,'parent',AnchorLeft)
  icon:addAnchor(AnchorVerticalCenter,'parent',AnchorVerticalCenter)
  icon:setMarginLeft(4)
  setCoin(icon,currency == 0 and 3031 or currency)
  if currency == 0 then
   local second = g_ui.createWidget('AntigasMarketCoin',button)
   second:addAnchor(AnchorLeft,'parent',AnchorLeft)
   second:addAnchor(AnchorVerticalCenter,'parent',AnchorVerticalCenter)
   second:setMarginLeft(20)
   setCoin(second,5130)
  end
 end
 menu:setWidth(math.max(combo:getWidth(),169))
 menu:display({x=combo:getX(),y=combo:getY()+combo:getHeight()})
 connect(menu,{onDestroy=function() combo:setOn(false) end})
 combo:setOn(true)
 return true
end

local function referencePrice()
 if not selectedItem or not selectedFresh or listState=='error' then return end
 local prices = (selectedItem.prices or {})[tostring(getFormCurrency())] or {}
 -- Reference is from the player's perspective: highest buyer / cheapest seller.
 local price
 if formSide == 'sell' then price = tonumber(prices.buy) else price = tonumber(prices.sell) end
 if price and price >= 1 and price <= 100000000 and price == math.floor(price) then return price end
end

function useBestPrice()
 if pendingRequest then return end
 local price = referencePrice()
 if price then getWindowChild('price'):setText(string.format('%.0f',price)) end
end

local function selectedAmount(row)
	local amount = tonumber(row.amount:getText())
 if not amount or amount < 1 or amount ~= math.floor(amount) or not row.offerData or amount > row.offerData.amount then return nil end
 return amount
end

local function renderOffer(offer, mine)
 if not mine and not hasSprite(offer.itemId) then return false end
	local row = g_ui.createWidget("AntigasMarketOfferRow", window.offerList)
	row:setWidth(math.max(180, window.offerList:getWidth() - 18))
	row.offerData = offer
	if hasSprite(offer.itemId) then row.item:setItemId(offer.itemId) else row.item:hide() end
	row.item:setItemCount(1)
	row.title:setText(offer.name .. "  x" .. numberText(offer.amount))
 row.title.onGeometryChange=function() fitText(row.title,offer.name..'  x'..numberText(offer.amount)) end
 row.title:setTooltip(offer.name..'  x'..numberText(offer.amount))
	local sideText = offer.side == 0 and "Seller" or "Buyer"
 local details = string.format('%s: %s', sideText, offer.ownerName or '?')
	row.details:setText(details)
 row.details:setTooltip(details)
 row.priceDetails:setText('Unit: '..numberText(offer.price)..' '..currencyLabel(offer.currency))
 row.priceDetails:setTooltip(row.priceDetails:getText())
 setCoin(row.unitCoin,offer.currency)
 setCoin(row.totalCoin,offer.currency)
	if mine then
		row.amount:hide()
		row.action:setText("Cancel")
  row.totalDetails:setText('Remaining: '..numberText(offer.amount*offer.price)..' '..currencyLabel(offer.currency))
		row.action.onClick = function() confirmAction('Cancel this offer and return its remaining assets?',function() sendAction("cancel", { offerId = offer.id }) end) end
	else
		row.amount:show()
		row.action:setText(offer.side == 0 and "Buy" or "Sell")
		row.action.onClick = function() modules.game_market_antigas.onOfferAction(row) end
  row.amount:setTooltip('Whole items to trade, from 1 to '..numberText(offer.amount)..'.')
  row.amount.onTextChange = function()
   local amount = selectedAmount(row)
   row.action:setEnabled(amount ~= nil)
   row.totalDetails:setText(amount and ('Total: '..numberText(amount*offer.price)..' '..currencyLabel(offer.currency)) or ('Enter 1 to '..numberText(offer.amount)..' items.'))
   row.totalCoin:setVisible(amount ~= nil)
  end
  row.amount.onTextChange()
	end
 return true
end

local function showCatalog(data)
	setView('catalog')
	clearList()
	local items = data.items or {}
	local visible = 0
	for _, item in ipairs(items) do
   if hasSprite(item.id) then
		visible = visible + 1
		local row = g_ui.createWidget("AntigasMarketCatalogRow", window.offerList)
		row:setWidth(math.max(180, window.offerList:getWidth() - 18))
		row.itemData = item
		row.icon:setItemId(item.id)
  setCoin(row.goldCoin,3031)
  setCoin(row.antigasCoin,5130)
  row.itemName.onGeometryChange=function() fitText(row.itemName,item.name) end
  fitText(row.itemName,item.name)
  row.owned:setText('Own: '..shortNumber(item.owned or 0))
  local function prices(id,label)
   local p=(item.prices or {})[tostring(id)] or {}
   local hasSeller = p.sell and p.sell > 0
   local hasBuyer = p.buy and p.buy > 0
   local tip=label..': '..(hasSeller and 'buy from '..numberText(p.sell) or 'no sellers')..
    ' | '..(hasBuyer and 'sell for '..numberText(p.buy) or 'no buyers')
   if not hasSeller and not hasBuyer then return label..': --',tip,false end
   return label..': buy '..(hasSeller and shortNumber(p.sell) or '--')..
    ' / sell '..(hasBuyer and shortNumber(p.buy) or '--'),tip,true
  end
  local gold,goldTip,goldAvailable=prices(3031,'Gold')
  local antigas,antigasTip,antigasAvailable=prices(5130,'Antigas')
  row.goldPrice:setText(gold)
  row.antigasPrice:setText(antigas)
  row.goldPrice:setColor(goldAvailable and '#d0d0d0' or '#ababab')
  row.antigasPrice:setColor(antigasAvailable and '#d0d0d0' or '#ababab')
  row:setTooltip(item.name..' | '..(item.category or '')..'\nYou own: '..numberText(item.owned or 0)..
   ' tradable items in equipment/backpacks.\n'..goldTip..'\n'..antigasTip..
   '\nBuy: cheapest seller. Sell: highest buyer. Per item; availability may change.\n-- means no matching offers, not zero price.')
  if selectedItem and selectedItem.id == item.id and selectedItem.subtype == item.subtype then
   selectedItem = item
   selectedFresh=true
   row:setOn(true)
  end
	 end
	end
	if visible == 0 then
   emptyList(#items > 0 and 'No items available on this page. Try another page or search.' or 'No items found. Try another name or select All items.')
	end
 getWindowChild('listStatus'):setText(visible==0 and 'No results' or visible..' items on this page')
 setView(currentView)
 onFormChange()
end

local function populateCategories(data)
	window.categoryPanel:destroyChildren()
	categories = data or {}
	for _, category in ipairs(categories) do
		local button = g_ui.createWidget("AntigasMarketTab", window.categoryPanel)
		button:setHeight(25)
		button:setWidth(window.categoryPanel:getWidth())
		button:setText(category.name)
		button.categoryId = category.id
		button.onClick = function(widget)
			if resetting or readBlocked then return end
			selectedCategory = widget.categoryId
			if currentView == "catalog" then
				modules.game_market_antigas.searchCatalog()
			else
				modules.game_market_antigas.browse()
			end
		end
	end
end

local function createWindow()
	if window then return end
	window = g_ui.displayUI("market")
	window:hide()
 connect(window,{onVisibilityChange=syncPlayerBarSelection})
 syncPlayerBarSelection()
	window.currencyFilter:addOption("All currencies", "0")
	window.currencyFilter:addOption("Gold Coin", "3031")
	window.currencyFilter:addOption("Antigas Coin", "5130")
	window.currencyFilter:setCurrentOptionByData("0")
	window.currencyFilter.onOptionChange = function()
  updateCurrencyCombo(window.currencyFilter)
  if not resetting and currentView == 'offers' then modules.game_market_antigas.browse() end
 end
 window.currencyFilter.onMousePress = currencyMenu
 window.sideFilter:addOption('All offers', '-1')
 window.sideFilter:addOption('Buy items', '0')
 window.sideFilter:addOption('Sell items', '1')
 window.sideFilter:setCurrentOptionByData('-1')
 window.sideFilter.onOptionChange = function() if not resetting and currentView == 'offers' then modules.game_market_antigas.browse() end end
	local currency = getWindowChild("currency")
	currency:addOption("Gold Coin", "3031")
	currency:addOption("Antigas Coin", "5130")
	currency:setCurrentOptionByData("3031")
	getWindowChild("quantity"):setText("1")
 getWindowChild("price"):setText("")
 currency.onOptionChange = onFormChange
 currency.onMousePress = currencyMenu
 updateCurrencyCombo(window.currencyFilter)
 setView('catalog')
 onFormChange()
end

function init()
	ProtocolGame.registerExtendedJSONOpcode(MARKET_OPCODE, onExtendedJSONOpcode)
	connect(g_game, { onGameStart = onGameStart, onGameEnd = onGameEnd })
	createWindow()
	if g_game.isOnline() then onGameStart() end
end

function terminate()
 stopReads()
 if transactionTimer then removeEvent(transactionTimer);transactionTimer=nil end
 if pendingMessage then pendingMessage:destroy();pendingMessage=nil end
	disconnect(g_game, { onGameStart = onGameStart, onGameEnd = onGameEnd })
	ProtocolGame.unregisterExtendedJSONOpcode(MARKET_OPCODE, onExtendedJSONOpcode)
	if window then
  disconnect(window,{onVisibilityChange=syncPlayerBarSelection})
  window:destroy(); window=nil
 end
end

function onGameStart()
	createWindow()
 resetting=true
 stopReads()
 if transactionTimer then removeEvent(transactionTimer);transactionTimer=nil end
 activeRead,queuedRead=nil,nil
 readBlocked,recoverableReadError,transactionRetry=false,false,false
 desiredRead=0
 listState='idle'
 rightMode='overview'
 selectedFresh=false
 serverVersion = 0
 selectedItem = nil
 formSide = 'sell'
 sideChosen = false
 selectedCategory = 'all'
 window.ownedOnly:setChecked(false)
 getWindowChild('price'):setText('')
 currentView = 'catalog'
 visibleItems = nil
 updateCurrencyCombo(window.currencyFilter)
 setCoin(window.balanceLabel.goldCoin,3031)
 setCoin(window.balanceLabel.antigasCoin,5130)
 invalidateBalances()
 window.search:setText('')
 if searchEvent then removeEvent(searchEvent);searchEvent=nil end
 window.sideFilter:setCurrentOptionByData('-1')
 window.currencyFilter:setCurrentOptionByData('0')
 clearList()
 page = 1
 pendingRequest = nil
 local saved = g_settings.getNode('AntigasMarketPending') or {}
 local raw = saved[g_game.getCharacterName()]
 if type(raw)=='string' then
  local ok,request=pcall(json.decode,raw)
  if ok and type(request)=='table' and request.requestId then pendingRequest={raw=raw,id=request.requestId} end
 end
 transactionRetry=pendingRequest~=nil
 updateRetry()
 getWindowChild('selectedItemPanel').selectedIcon:setItemId(0)
 getWindowChild('selectedItemPanel').selectedName:setText('')
 getWindowChild('quantity'):setText('1')
 resetting=false
 updateContext()
 onFormChange()
end

function onGameEnd()
 stopReads()
 if transactionTimer then removeEvent(transactionTimer);transactionTimer=nil end
 if pendingMessage then pendingMessage:destroy();pendingMessage=nil end
	if window then window:hide() end
end

function show()
	if not g_game.isOnline() then return end
	createWindow()
	window:show()
	window:raise()
	window:focus()
 invalidateBalances()
	sendAction('init')
	searchCatalog()
end

function hide()
	if window then window:hide() end
end

function toggle()
	-- The sidebar button is an "open/bring to front" action. Closing is handled
	-- by the window's Close button or Escape, so clicking it must raise it even
	-- when another game window currently covers it.
	show()
end

function browse(keepPage)
	if not window then return end
	setView('offers')
 if not keepPage then page=1 end
	local side=window.sideFilter:getCurrentOption()
	beginRead('offers',"browse", {
		page=page,
		side=side and tonumber(side.data) or -1,
		category = selectedCategory,
		currency = getCurrencyFilter(),
		search = window.search:getText()
	})
end

function onSearchTextChange()
 if resetting or readBlocked or not window then return end
	if searchEvent then removeEvent(searchEvent) end
 desiredRead=desiredRead+1
 queuedRead=nil
 if currentView=='catalog' then selectedFresh=false end
 setListState('loading')
	searchEvent = scheduleEvent(function()
		searchEvent = nil
		if currentView == 'catalog' then searchCatalog() elseif currentView == 'offers' then browse() end
	end, 350)
end

function searchCatalog(keepPage)
	if not window or resetting then return end
	setView('catalog')
 if not keepPage then page=1 end
 beginRead('catalog',"catalog", {page=page,category = selectedCategory, search = window.search:getText(),ownedOnly=window.ownedOnly:isChecked() })
end

function onOwnedFilterChange()
 if not resetting and currentView=='catalog' then searchCatalog() end
end

function refreshView()
 if readBlocked then return setListState('error','No response. Reconnect to the game before retrying safely.') end
 invalidateBalances()
 sendAction('init')
 if currentView == 'catalog' then searchCatalog() elseif currentView == 'mine' then showMyOffers() elseif currentView=='history' then showHistory() else browse() end
end

function viewSelectedOffers()
 if not selectedItem then return end
 rightMode='offers'
 resetting=true
 window.search:setText(selectedItem.name)
 resetting=false
 if searchEvent then removeEvent(searchEvent);searchEvent=nil end
 selectedCategory = 'all'
 browse()
end

function showCreateOffer()
 if not selectedItem then return end
 rightMode='create'
 updateContext()
 onFormChange()
end

function setOfferSide(side)
 if side ~= 'buy' and side ~= 'sell' then return end
 formSide = side
 sideChosen = true
 onFormChange()
end

function onFormChange()
 if not window then return end
 local amount = tonumber(getWindowChild('quantity'):getText())
 local price = tonumber(getWindowChild('price'):getText())
 local currency = getFormCurrency()
 local selling = formSide == 'sell'
 updateCurrencyCombo(getWindowChild('currency'))
 setCoin(getWindowChild('createPanel'):recursiveGetChildById('totalCoin'),currency)
 local best = referencePrice()
 getWindowChild('bestPrice'):setEnabled(best ~= nil and not pendingRequest)
 getWindowChild('bestPrice'):setText(selling and 'Use best buyer' or 'Use best seller')
 getWindowChild('bestPrice'):setTooltip(best and
  ('Use '..numberText(best)..' '..currencyLabel(currency)..' per item from the '..(selling and 'highest buyer' or 'cheapest seller')..'. Reference only; availability may change. Review before creating your offer.') or
  'No matching offers in this currency. Enter your own price, or refresh the catalog.')
 getWindowChild('sellMode'):setOn(selling)
 getWindowChild('buyMode'):setOn(not selling)
 getWindowChild('unitPriceLabel'):setTooltip('Price of ONE item in '..currencyLabel(currency)..'.')
 local currencyTip=currency == 5130 and 'Antigas Coin is separate from gold. Uses physical coins in your inventory.' or
  '100 gold = 1 platinum; 10,000 gold = 1 crystal. Gold uses bank first, then carried coins.'
 getWindowChild('currencyHelp'):setTooltip(currencyTip)
 getWindowChild('currency'):setTooltip(currencyTip)
 local reason
 if pendingRequest then reason = transactionRetry and 'No response yet. Retry checks the same transaction safely.' or 'Waiting for transaction confirmation...'
 elseif not selectedItem then reason = 'Select an item in the catalog to begin.'
 elseif not selectedFresh then reason = 'Refresh the catalog and select this item again.'
 elseif listState=='error' then reason = 'Resolve the query error before creating an offer.'
 elseif not balanceData or serverVersion<2 then reason = 'Refresh to load current balances and Market status.'
 elseif not amount or amount < 1 or amount > 10000 or amount ~= math.floor(amount) then reason = 'Quantity: enter a whole number from 1 to 10,000.'
 elseif not price or price < 1 or price > 100000000 or price ~= math.floor(price) then reason = 'Enter a whole unit price, starting at 1.'
 elseif amount*price > (currency == 5130 and 10000 or 100000000) then reason = 'Total exceeds the limit: '..numberText(currency == 5130 and 10000 or 100000000)..' '..currencyLabel(currency)..'.'
 elseif selling and amount>(selectedItem.owned or 0) then reason = 'You own only '..numberText(selectedItem.owned or 0)..' tradable items. Refresh if this changed.'
 elseif not selling and amount*price>(currency==5130 and balanceData.antigas or balanceData.bank+balanceData.wallet) then
  reason='Not enough '..currencyLabel(currency)..' for this offer. Refresh if your balance changed.'
 end
 getWindowChild('createOffer'):setEnabled(reason == nil and rightMode=='create')
 getWindowChild('createOffer'):setTooltip(reason or 'Review quantity, total, reserved assets and delivery before confirming.')
 getWindowChild('createOffer'):setText(selling and 'Create sell offer' or 'Create buy offer')
 local validNumbers=amount and amount>=1 and amount<=10000 and amount==math.floor(amount) and
  price and price>=1 and price<=100000000 and price==math.floor(price)
 getWindowChild('totalLabel'):setText(selling and 'Total to receive when sold' or 'Total payment reserved')
 getWindowChild('totalAmount'):setText((validNumbers and numberText(amount*price) or '--')..' '..currencyLabel(currency))
 getWindowChild('totalAmount'):setTooltip(validNumbers and
  ('Total: '..numberText(amount*price)..' '..currencyLabel(currency)..'. '..(selling and deliveryDestination(true,currency) or paymentSource(currency))) or 'Enter a valid quantity and unit price.')
 getWindowChild('offerHelp'):setText(reason or (selling and
  ('Reserve '..numberText(amount)..' items until sold or cancelled. Review before confirming.') or
  'Payment is reserved until filled or cancelled. This is a listing, not an instant purchase.'))
 updateContext()
 return reason == nil and rightMode=='create'
end

function selectCatalogItem(row)
	local item = row.itemData
	if not item or not hasSprite(item.id) then return end
	selectedItem = item
 selectedFresh=true
 rightMode='overview'
 resetting=true
 getWindowChild('quantity'):setText('1')
 getWindowChild('price'):setText('')
 resetting=false
 for _, entry in ipairs(window.offerList:getChildren()) do
  if entry.itemData then entry:setOn(entry==row) end
 end
	local selectedItemPanel = getWindowChild("selectedItemPanel")
	selectedItemPanel.selectedIcon:setItemId(item.id)
	selectedItemPanel.selectedIcon:setItemCount(1)
	local owned = item.owned or 0
	selectedItemPanel.selectedName:setText(item.name)
 if not sideChosen then formSide = owned > 0 and 'sell' or 'buy' end
 getWindowChild('selectedOffers'):setEnabled(true)
 onFormChange()
end

function createOffer()
 if not onFormChange() then return end
	if not selectedItem then
		return displayInfoBox(tr("Market"), tr("Search the item catalog and select an item first."))
	end
	local amount = tonumber(getWindowChild("quantity"):getText())
	local price = tonumber(getWindowChild("price"):getText())
	if not amount or not price or amount < 1 or price < 1 then
		return displayInfoBox(tr("Market"), tr("Enter a valid quantity and unit price."))
	end
 local data={
		side = formSide,
		itemId = selectedItem.id,
		subtype = selectedItem.subtype,
		amount = math.floor(amount),
		price = math.floor(price),
		currency = getFormCurrency()
	}
 local reservation = data.side == 'sell' and numberText(data.amount)..' items' or numberText(data.amount*data.price)..' '..currencyLabel(data.currency)
 local total = data.amount * data.price
 local summary = string.format('Create %s offer: %s x %s\nUnit price: %s %s\nTotal: %s %s\nReserved now: %s',data.side,selectedItem.name,numberText(data.amount),numberText(data.price),currencyLabel(data.currency),numberText(total),currencyLabel(data.currency),reservation)
 if data.currency == 3031 then summary = summary..'\nGold equivalent: '..goldBreakdown(total) end
 if data.side == 'buy' then summary = summary..'\n'..paymentSource(data.currency) end
 summary = summary..'\n'..deliveryDestination(data.side == 'sell',data.currency)..'\nAn offer waits for another player; it is not an instant trade.'
 confirmAction(summary,function() sendAction('create',data) end,data.currency)
end

function showMyOffers(keepPage)
	if not window then return end
	setView('mine')
 if not keepPage then page=1 end
	beginRead('mine',"mine", {page=page})
end

function changePage(delta)
 if listState~='ready' then return end
 if delta<0 and not getWindowChild('prevPage'):isEnabled() then return end
 if delta>0 and not getWindowChild('nextPage'):isEnabled() then return end
 page=math.max(1,math.min(250,page+delta))
 if currentView=='catalog' then searchCatalog(true)
 elseif currentView=='mine' then showMyOffers(true)
 elseif currentView=='history' then showHistory(true)
 else browse(true) end
end

function showHistory(keepPage)
 if not window then return end
 setView('history')
 if not keepPage then page=1 end
 beginRead('history','history',{page=page})
end

local function renderHistory(payload)
 clearList()
 for _,entry in ipairs(payload.entries or {}) do
  local row=g_ui.createWidget('AntigasMarketHistoryRow',window.offerList)
  row:setWidth(math.max(180,window.offerList:getWidth()-18))
  if hasSprite(entry.itemId) then row.icon:setItemId(entry.itemId) else row.icon:hide() end
  row.itemName:setText(entry.event..': '..entry.name..' x'..numberText(entry.quantity))
  local title=entry.event..': '..entry.name..' x'..numberText(entry.quantity)
  row.itemName.onGeometryChange=function() fitText(row.itemName,title) end
  row.itemName:setTooltip(title)
  local status=(entry.pending or 0)>0 and 'Pending: '..numberText(entry.pending) or 'Collected'
  row.details:setText(numberText(entry.total)..' '..currencyLabel(entry.currency)..' total\n'..status..' | '..entry.destination..'\n'..entry.date)
  row.details:setColor((entry.pending or 0)>0 and '#e6ce92' or '#c0c0c0')
 end
 if #(payload.entries or {})==0 then emptyList('No transactions recorded yet. History begins with this update; older deliveries are still available through Collect.') end
end

function retry()
 if pendingRequest then transmitPending()
 elseif recoverableReadError and not readBlocked then refreshView() end
end

function confirmAction(text, callback, currency)
 if pendingMessage then pendingMessage:destroy() end
 local box
 local function cancel() if box then box:destroy();box=nil end end
 local function accept() cancel();callback() end
 box=displayGeneralBox('Confirm Market transaction',text,{{text='Confirm',callback=accept},{text='Cancel',callback=cancel}},accept,cancel)
 if currency then
  box:setPaddingLeft(box:getPaddingLeft()+28)
  box:setWidth(box:getWidth()+28)
  local icon = g_ui.createWidget('AntigasMarketCoin',box)
  icon:setId('transactionCurrency')
  icon:addAnchor(AnchorRight,'messageBoxLabel',AnchorLeft)
  icon:addAnchor(AnchorTop,'messageBoxLabel',AnchorTop)
  icon:setMarginRight(8)
  setCoin(icon,currency)
 end
 pendingMessage=box
 box.onDestroy=function(widget) if pendingMessage==widget then pendingMessage=nil end end
end

function collect()
 if not balanceData or pendingRequest then return end
	sendAction("collect", {})
end

local function validResponse(data)
 local p=data.data
 if type(data.action)~='string' or type(p)~='table' then return false end
 local function integer(v,lo,hi) return type(v)=='number' and v==math.floor(v) and v>=lo and v<=hi end
 local function text(v,n) return type(v)=='string' and #v<=n end
 local function optional(v,fn) return v==nil or fn(v) end
 local function amount(v) return integer(v,0,9007199254740991) end
 local function money(v) return integer(v,0,100000000) end
 local function list(v,max,check)
  if type(v)~='table' or #v>max then return false end
  local n=0
  for k,row in pairs(v) do
   if not integer(k,1,#v) or type(row)~='table' or not check(row) then return false end
   n=n+1
  end
  return n==#v
 end
 if not optional(p.page,function(v) return integer(v,1,250) end) or
    not optional(p.hasNext,function(v) return type(v)=='boolean' end) then return false end
 if data.action=='init' then
  return integer(p.version,2,1000) and list(p.categories,32,function(v) return text(v.id,32) and text(v.name,80) end)
 elseif data.action=='balances' then
  if not amount(p.bank) or not amount(p.wallet) or not amount(p.antigas) then return false end
  if p.pending==nil then return true end
  if type(p.pending)~='table' then return false end
  for _,key in ipairs({'count','gold','antigas','items'}) do if not optional(p.pending[key],amount) then return false end end
  return true
 elseif data.action=='catalog' then
  return list(p.items,100,function(v)
   if not integer(v.id,1,65535) or not text(v.name,96) or not optional(v.owned,amount) or
      not optional(v.category,function(x) return text(x,32) end) or
      not optional(v.subtype,function(x) return integer(x,-1,65535) end) then return false end
   if v.prices~=nil then
    if type(v.prices)~='table' then return false end
    for _,price in pairs(v.prices) do
     if type(price)~='table' or not optional(price.sell,money) or not optional(price.buy,money) then return false end
    end
   end
   return true
  end)
 elseif data.action=='offers' or data.action=='myOffers' then
  return list(p.offers,100,function(v)
   return integer(v.id,1,9007199254740991) and integer(v.itemId,1,65535) and text(v.name,96) and
    integer(v.side,0,1) and (v.currency==3031 or v.currency==5130) and
    integer(v.amount,1,10000) and integer(v.price,1,100000000) and optional(v.ownerName,function(x) return text(x,96) end)
  end)
 elseif data.action=='history' then
  return list(p.entries,100,function(v)
   return integer(v.itemId,0,65535) and text(v.name,96) and text(v.event,80) and text(v.destination,256) and
    text(v.date,80) and amount(v.quantity) and amount(v.total) and optional(v.pending,amount) and
    (v.currency==3031 or v.currency==5130)
  end)
 elseif data.action=='message' then
  return type(p.ok)=='boolean' and text(p.text,2048) and optional(p.requestId,function(v) return text(v,96) end)
 end
 return false
end

function onExtendedJSONOpcode(protocol, code, data)
	if code ~= MARKET_OPCODE or type(data) ~= 'table' or not window then return end
 if not validResponse(data) then NetworkData.warn();return end
	local action = data.action
	local payload = data.data or {}
 local responseView = ({offers='offers',myOffers='mine',catalog='catalog',history='history'})[action]
 if responseView and not finishRead(responseView,payload) then return end
 if payload.page then
  page=payload.page
  getWindowChild('pageLabel'):setText('Page '..page)
  getWindowChild('prevPage'):setEnabled(page>1)
  getWindowChild('nextPage'):setEnabled(payload.hasNext and page<250)
 end
	if action == "init" then
  serverVersion=payload.version or 0
		populateCategories(payload.categories)
  setView(currentView)
  onFormChange()
 elseif action == 'balances' then
  balanceData={bank=tonumber(payload.bank) or 0,wallet=tonumber(payload.wallet) or 0,antigas=tonumber(payload.antigas) or 0}
  local pending=payload.pending or {}
  local button=getWindowChild('collect')
  button:setText('Collect ('..numberText(pending.count)..')')
  button:setColor((pending.count or 0)>0 and '#dfcf9f' or '#c5c5c5')
  button:setEnabled(not pendingRequest and (pending.count or 0)>0)
  button:setTooltip('Pending: '..numberText(pending.gold)..' gold to bank; '..numberText(pending.antigas)..' Antigas Coins and '..numberText(pending.items)..' items to your town depot. Refresh to check for new deliveries.')
  local goldText='Bank: '..numberText(payload.bank)..' | Carried gold: '..numberText(payload.wallet)
  fitText(window.balanceLabel.goldBalance,goldText)
  window.balanceLabel.goldBalance:setTooltip(goldText..'\nGold uses bank first, then carried gold/platinum/crystal coins.')
  fitText(window.balanceLabel.antigasBalance,'Antigas Coins: '..numberText(payload.antigas))
  onFormChange()
	elseif action == "offers" then
		setView('offers')
		clearList()
		local count = 0
		for _, offer in ipairs(payload.offers or {}) do if renderOffer(offer, false) then count=count+1 end end
  getWindowChild('listStatus'):setText(count==0 and 'No offers' or count..' offers on this page')
  if count == 0 then emptyList('No matching player offers. Select an item in Catalog to create a listing.') end
  onFormChange()
	elseif action == "myOffers" then
		setView('mine')
		clearList()
		for _, offer in ipairs(payload.offers or {}) do renderOffer(offer, true) end
  if #(payload.offers or {}) == 0 then emptyList('You have no active offers. Select an item in Catalog to create one.') end
  onFormChange()
	elseif action == "catalog" then
		showCatalog(payload)
 elseif action == 'history' then
  renderHistory(payload)
  onFormChange()
	elseif action == "message" then
  if pendingRequest and payload.requestId==pendingRequest.id then
   if transactionTimer then removeEvent(transactionTimer);transactionTimer=nil end
   transactionRetry=false
   pendingRequest=nil
   savePending(nil)
   updateRetry()
   onFormChange()
  end
  if not payload.ok and not payload.requestId then
   stopReads()
   readBlocked=false
   recoverableReadError=true
   selectedFresh=false
   invalidateBalances()
   setListState('error',payload.text or 'Query failed. Use Retry to request fresh data.')
   updateRetry()
  end
		if pendingMessage then pendingMessage:destroy() end
		pendingMessage = displayInfoBox(tr("Market"), payload.text or "")
		pendingMessage.onDestroy = function(widget)
			if widget == pendingMessage then pendingMessage = nil end
		end
  if payload.ok then
   if currentView=='mine' then showMyOffers() elseif currentView=='catalog' then searchCatalog() elseif currentView=='history' then showHistory() else browse() end
  end
	end
end

function onOfferAction(row)
	local offer = row.offerData
	if not offer then return end
	local amount = selectedAmount(row)
 if not amount then return end
 local buying = offer.side == 0
 local summary = string.format('%s now: %s x %s\nUnit price: %s %s\nTotal: %s %s',buying and 'Buy' or 'Sell',offer.name,numberText(amount),numberText(offer.price),currencyLabel(offer.currency),numberText(amount*offer.price),currencyLabel(offer.currency))
 if buying then summary = summary..'\n'..paymentSource(offer.currency) end
 summary = summary..'\n'..deliveryDestination(not buying,offer.currency)
 confirmAction(summary,function() sendAction('fill',{offerId=offer.id,amount=amount}) end,offer.currency)
end
