local function restoreItemBorder(widget)
  local rarity = modules.game_inventory and modules.game_inventory.AntigasItemRarity
  if rarity then
    rarity.restoreBorder(widget)
  else
    widget:setBorderWidth(0)
  end
end

function UIItem:onDragEnter(mousePos)
  if self:isVirtual() then return false end

  local item = self:getItem()
  if not item then return false end

  self:setBorderWidth(1)
  self.currentDragThing = item
  g_mouse.pushCursor('target')
  return true
end

function UIItem:onDragLeave(droppedWidget, mousePos)
  if self:isVirtual() then return false end
  self.currentDragThing = nil
  g_mouse.popCursor('target')
  restoreItemBorder(self)
  self.hoveredWho = nil
  return true
end

function UIItem:onDrop(widget, mousePos, forced)
  if not self:canAcceptDrop(widget, mousePos) and not forced then return false end

  local item = widget.currentDragThing
  if not item or not item:isItem() then return false end
  
  if self.selectable then
    self:setItemId(item:getId())
    self:setItemCount(item:getCount())
    if item:getSubType() > 1 then
      self:setItemSubType(item:getSubType())
    end
    return
  end

  local toPos = self.position

  local itemPos = item:getPosition()
  if itemPos.x == toPos.x and itemPos.y == toPos.y and itemPos.z == toPos.z then return false end

  if item:getCount() > 1 then
    modules.game_interface.moveStackableItem(item, toPos)
  else
    g_game.move(item, toPos, 1)
  end

  restoreItemBorder(self)
  return true
end

function UIItem:onDestroy()
  if self == g_ui.getDraggingWidget() and self.hoveredWho then
    restoreItemBorder(self.hoveredWho)
  end

  if self.hoveredWho then
    self.hoveredWho = nil
  end

  local visuals = modules.game_rarityvisuals
  if visuals and visuals.clearSlot then visuals.clearSlot(self) end
end

function UIItem:onHoverChange(hovered)
  UIWidget.onHoverChange(self, hovered)

  if self:isVirtual() or not self:isDraggable() then return end

  local draggingWidget = g_ui.getDraggingWidget()
  if draggingWidget and self ~= draggingWidget then
    local gotMap = draggingWidget:getClassName() == 'UIGameMap'
    local gotItem = draggingWidget:getClassName() == 'UIItem' and not draggingWidget:isVirtual()
    if hovered and (gotItem or gotMap) then
      self:setBorderWidth(1)
      draggingWidget.hoveredWho = self
    else
      restoreItemBorder(self)
      draggingWidget.hoveredWho = nil
    end
  end
end

function UIItem:onMouseRelease(mousePosition, mouseButton)
  if self.cancelNextRelease then
    self.cancelNextRelease = false
    return true
  end

  if self:isVirtual() then return false end

  local item = self:getItem()
  if not item or not self:containsPoint(mousePosition) then return false end

  if modules.client_options.getOption('classicControl') and
     ((g_mouse.isPressed(MouseLeftButton) and mouseButton == MouseRightButton) or
      (g_mouse.isPressed(MouseRightButton) and mouseButton == MouseLeftButton)) then
    g_game.look(item)
    self.cancelNextRelease = true
    return true
  elseif modules.game_interface.processMouseAction(mousePosition, mouseButton, nil, item, item, nil, nil) then
    return true
  end
  return false
end

function UIItem:canAcceptDrop(widget, mousePos)
  if not self.selectable and (self:isVirtual() or not self:isDraggable()) then return false end
  if not widget or not widget.currentDragThing then return false end

  local children = rootWidget:recursiveGetChildrenByPos(mousePos)
  for i=1,#children do
    local child = children[i]
    if child == self then
      return true
    elseif not child:isPhantom() then
      return false
    end
  end

  error('Widget ' .. self:getId() .. ' not in drop list.')
  return false
end

function UIItem:onClick(mousePos)
  if not self.selectable or not self.editable then
    return
  end

  if modules.game_itemselector then
    modules.game_itemselector.show(self)
  end
end

function UIItem:onItemChange()
  local rarity = modules.game_inventory and modules.game_inventory.AntigasItemRarity
  if rarity and (self.rarityTier or self.rarityTooltip or self.rarityLocked) then
    rarity.apply(self, 0, self.rarityLocked)
  else
    local visuals = modules.game_rarityvisuals
    if visuals and visuals.clearSlot then visuals.clearSlot(self) end
  end
  local tooltip = nil
  if self:getItem() and self:getItem():getTooltip():len() > 0 then
    tooltip = self:getItem():getTooltip()
  end
  self:setTooltip(tooltip)
end
