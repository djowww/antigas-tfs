local gameStart = 0

local function itemRarity()
  return modules.game_inventory and modules.game_inventory.AntigasItemRarity
end

function init()
  g_ui.importStyle('container')

  connect(Container, { onOpen = onContainerOpen,
                       onClose = onContainerClose,
                       onSizeChange = onContainerChangeSize,
                       onUpdateItem = onContainerUpdateItem })
  connect(g_game, { onGameEnd = clean })
  
  -- Anti-steal code
  if (REGISTRATION_KEY ~= "AbcDeFgH") then
	g_logger.fatal("Invalid serial ID for the server, please contact julianandresbernalv@gmail.com or JulianBernalV#7033")
  end

  reloadContainers()
end

function terminate()
  disconnect(Container, { onOpen = onContainerOpen,
                          onClose = onContainerClose,
                          onSizeChange = onContainerChangeSize,
                          onUpdateItem = onContainerUpdateItem })
  disconnect(g_game, { onGameEnd = clean })
  clean()
end

function reloadContainers()
  clean()
  for _,container in pairs(g_game.getContainers()) do
    onContainerOpen(container)
  end
end

function clean()
  for containerid,container in pairs(g_game.getContainers()) do
    destroy(container)
  end
end

function markStart()
  gameStart = g_clock.millis()
end

function destroy(container)
  local rarity = itemRarity()
  if rarity then rarity.forgetContainer(container) end
  if container.window then
    container.window:destroy()
    container.window = nil
    container.itemsPanel = nil
  end
end

function refreshContainerItems(container)
  local rarity = itemRarity()
  for slot=0,container:getCapacity()-1 do
    local itemWidget = container.itemsPanel:getChildById('item' .. slot)
    itemWidget:setItem(container:getItem(slot))
    if rarity then rarity.apply(itemWidget, 0, not container:isUnlocked()) end
  end

  if rarity then rarity.requestContainerPage(container) end

  if container:hasPages() then
    refreshContainerPages(container)
  end
end

function toggleContainerPages(containerWindow, pages)
  containerWindow:getChildById('miniwindowScrollBar'):setMarginTop(pages and 42 or 16)
  containerWindow:getChildById('contentsPanel'):setMarginTop(pages and 42 or 20)
  containerWindow:getChildById('pagePanel'):setVisible(pages)
end

function refreshContainerPages(container)
  local currentPage = 1 + math.floor(container:getFirstIndex() / container:getCapacity())
  local pages = 1 + math.floor(math.max(0, (container:getSize() - 1)) / container:getCapacity())
  container.window:recursiveGetChildById('pageLabel'):setText(string.format('Page %i of %i', currentPage, pages))

  local prevPageButton = container.window:recursiveGetChildById('prevPageButton')
  if currentPage == 1 then
    prevPageButton:setEnabled(false)
  else
    prevPageButton:setEnabled(true)
    prevPageButton.onClick = function() g_game.seekInContainer(container:getId(), container:getFirstIndex() - container:getCapacity()) end
  end

  local nextPageButton = container.window:recursiveGetChildById('nextPageButton')
  if currentPage >= pages then
    nextPageButton:setEnabled(false)
  else
    nextPageButton:setEnabled(true)
    nextPageButton.onClick = function() g_game.seekInContainer(container:getId(), container:getFirstIndex() + container:getCapacity()) end
  end
end

function onContainerOpen(container, previousContainer)
  local rarity = itemRarity()
  local containerWindow
  if previousContainer then
    if rarity then rarity.forgetContainer(previousContainer) end
    containerWindow = previousContainer.window
    previousContainer.window = nil
    previousContainer.itemsPanel = nil
  else
    containerWindow = g_ui.createWidget('ContainerWindow', modules.game_interface.getRightPanel())
  
  -- white border flash effect
    containerWindow:setBorderWidth(1)
    containerWindow:setBorderColor("#ffffff")
    scheduleEvent(function() 
      if containerWindow then
        containerWindow:setBorderWidth(0)
      end
    end, 500)
  end
  
  containerWindow:setId('container' .. container:getId())
  if gameStart + 1000 < g_clock.millis() then
    --containerWindow:clearSettings()
  end
  
  containerWindow:setId('container' .. container:getId())
  local containerPanel = containerWindow:getChildById('contentsPanel')
  local containerItemWidget = containerWindow:getChildById('containerItemWidget')
  containerWindow.onClose = function()
    g_game.close(container)
    containerWindow:hide()
  end
  containerWindow.onDrop = function(container, widget, mousePos)
    if containerPanel:getChildByPos(mousePos) then
      return false
    end
    local child = containerPanel:getChildByIndex(-1)
    if child then
      child:onDrop(widget, mousePos, true)        
    end
  end

  -- this disables scrollbar auto hiding
  local scrollbar = containerWindow:getChildById('miniwindowScrollBar')
  scrollbar:mergeStyle({ ['$!on'] = { }})

  local upButton = containerWindow:getChildById('upButton')
  upButton.onClick = function()
    g_game.openParent(container)
  end
  upButton:setVisible(container:hasParent())

  local name = container:getName()
  name = name:sub(1,1):upper() .. name:sub(2)
  containerWindow:setText(name)

  containerItemWidget:setItem(container:getContainerItem())

  containerPanel:destroyChildren()
  for slot=0,container:getCapacity()-1 do
    local itemWidget = g_ui.createWidget('Item', containerPanel)
    itemWidget:setId('item' .. slot)
    itemWidget:setItem(container:getItem(slot))
    itemWidget:setMargin(0)
    itemWidget.position = container:getSlotPosition(slot)

    if rarity then
      rarity.apply(itemWidget, 0, not container:isUnlocked())
    elseif not container:isUnlocked() then
      itemWidget:setBorderColor('red')
      itemWidget:setBorderWidth(1)
    end
  end

  container.window = containerWindow
  container.itemsPanel = containerPanel

  if rarity then rarity.requestContainerPage(container) end

  toggleContainerPages(containerWindow, container:hasPages())
  refreshContainerPages(container)

  local layout = containerPanel:getLayout()
  local cellSize = layout:getCellSize()
  containerWindow:setContentMinimumHeight(cellSize.height + 3)
  containerWindow:setContentMaximumHeight(cellSize.height*layout:getNumLines()+layout:getNumLines()*3 + 4)
  
  if container:hasPages() then
    local height = containerWindow.miniwindowScrollBar:getMarginTop() + containerWindow.pagePanel:getHeight()+17
    if containerWindow:getHeight() < height then
      containerWindow:setHeight(height)
    end
  end
  
  if not previousContainer then
    local filledLines = math.max(math.ceil(container:getItemsCount() / layout:getNumColumns()), 1)
    containerWindow:setContentHeight((cellSize.height+3)*filledLines)
  end

  containerWindow:setup()
end

function onContainerClose(container)
  destroy(container)
end

function onContainerChangeSize(container, size)
  if not container.window then return end
  refreshContainerItems(container)
end

function onContainerUpdateItem(container, slot, item, oldItem)
  if not container.window then return end
  local itemWidget = container.itemsPanel:getChildById('item' .. slot)
  if not itemWidget then return end
  itemWidget:setItem(item)
  local rarity = itemRarity()
  if rarity then
    rarity.apply(itemWidget, 0, not container:isUnlocked())
    rarity.requestContainerItem(container, slot)
  end
end

function onContainerMousePress(widget, mousePos, mouseButton)
 if mouseButton ~= MouseRightButton then return end
 
   local getLeftTopSlot = rootWidget:recursiveGetChildByPos({x = mousePos.x-2, y = mousePos.y+2})
   local getLeftDownSlot = rootWidget:recursiveGetChildByPos({x = mousePos.x-2, y = mousePos.y-2})
   local getRightDownSlot = rootWidget:recursiveGetChildByPos({x = mousePos.x+2, y = mousePos.y-2})
   local getRightTopSlot = rootWidget:recursiveGetChildByPos({x = mousePos.x+2, y = mousePos.y+2})
   local WindowContents = rootWidget:recursiveGetChildByPos(mousePos)
   
   if WindowContents:getStyleName() == "ContainerWindow" then
      if getLeftTopSlot:getStyleName() == "Item" then
	     local item = getLeftTopSlot:getItem()
	     if item then
			modules.game_interface.processMouseAction(getLeftTopSlot:getPosition(), mouseButton, nil, item, item, nil, nil)
		 end
	  elseif getLeftDownSlot:getStyleName() == "Item" then
	     local item = getLeftDownSlot:getItem()
	     if item then
			modules.game_interface.processMouseAction(getLeftDownSlot:getPosition(), mouseButton, nil, item, item, nil, nil)
		 end
	  elseif getRightDownSlot:getStyleName() == "Item" then
	     local item = getRightDownSlot:getItem()
	     if item then
			modules.game_interface.processMouseAction(getRightDownSlot:getPosition(), mouseButton, nil, item, item, nil, nil)
		 end
	  elseif getRightTopSlot:getStyleName() == "Item" then
	     local item = getRightTopSlot:getItem()
	     if item then
			modules.game_interface.processMouseAction(getRightTopSlot:getPosition(), mouseButton, nil, item, item, nil, nil)
		 end
	  end
   end
end
