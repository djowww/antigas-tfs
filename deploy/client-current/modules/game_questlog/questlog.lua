local OPCODE = 125
local window, button, pollEvent, searchEvent, timeoutEvent, layoutEvent, selectionEvent, scrollEvent
local selected, detailData, rows, pending = nil, nil, {}, {}
local page, pages, serial, filter = 1, 1, 0, 'all'
local resetting = false
local statusText = {active='In progress',completed='Completed'}
local journalHint = 'Your journal grows with the paths you discover. Seek answers in the world.'

local function cancel(event) if event then removeEvent(event) end end

local function syncPlayerBarSelection()
  local playerBars = modules.game_playerbars
  if playerBars and playerBars.setActionSelected then
    playerBars.setActionSelected('quest', window and window:isVisible())
  end
end
local function int(value,low,high)
  return type(value)=='number' and value==math.floor(value) and value>=low and value<=high
end
local function str(value,limit) return type(value)=='string' and #value<=limit end

local function fit(label,text)
  label:setTooltip(text)
  local lines, current = {}, ''
  local width = math.max(40,label:getWidth()-2)
  for word in text:gmatch('%S+') do
    -- Also wrap a single long name; whitespace-only wrapping can overflow.
    label:setText(word)
    if label:getTextSize().width>width then
      if current~='' then lines[#lines+1]=current; current='' end
      local part=''
      for char in word:gmatch('.') do
        label:setText(part..char)
        if part~='' and label:getTextSize().width>width then lines[#lines+1]=part; part=char
        else part=part..char end
      end
      word=part
    end
    local candidate = current=='' and word or current..' '..word
    label:setText(candidate)
    if current~='' and label:getTextSize().width>width then
      lines[#lines+1]=current; current=word
    else current=candidate end
  end
  if current~='' then lines[#lines+1]=current end
  label:setText(table.concat(lines,'\n'))
  label:setHeight(math.max(14,#lines*14+2))
end

local function clearDetail()
  detailData=nil
  fit(window.detail.title,'Unwritten pages')
  fit(window.detail.state,'A personal journal')
  window.detail.state:setColor('#bcbcbc')
  fit(window.detail.description,'Your next adventure is still out there. Speak with the people you meet, explore forgotten places and keep their stories in mind. New entries appear as your discoveries are recorded.')
  window.detail.reward:setText(''); window.detail.reward:hide()
  window.detail.entriesTitle:hide()
  window.detail.steps:destroyChildren()
end

local function renderDetail()
  if not window or not detailData then return end
  local q=detailData
  local scroll=window.detailScroll:getValue()
  fit(window.detail.title,q.name)
  fit(window.detail.state,statusText[q.status]..'  |  '..q.region)
  fit(window.detail.description,q.description)
  window.detail.state:setColor(q.status=='completed' and '#bdb08b' or '#bcbcbc')
  fit(window.detail.reward,q.rewards~='' and ('Recorded find: '..q.rewards) or '')
  window.detail.reward:setVisible(q.rewards~='')
  window.detail.entriesTitle:show()
  window.detail.steps:destroyChildren()
  for _,s in ipairs(q.steps) do
    local row=g_ui.createWidget('QuestStep',window.detail.steps)
    fit(row.title,s.name)
    row.progress:setText(s.completed and 'Remembered' or 'Unfinished')
    row.progress:setColor(s.completed and '#c6b785' or '#bababa')
    row:setHeight(row.title:getHeight()+25)
  end
  cancel(scrollEvent)
  scrollEvent=scheduleEvent(function()
    scrollEvent=nil
    if window and detailData==q then window.detailScroll:setValue(scroll) end
  end,30)
end

local function send(action,data)
  if pending[action] then return false end
  if not g_game.isOnline() or not g_game.getFeature(GameExtendedOpcode) then return false end
  local protocol=g_game.getProtocolGame()
  if not protocol then return false end
  serial=serial%1000000000+1
  data.action,data.requestId=action,serial
  pending[action]=serial
  protocol:sendExtendedOpcode(OPCODE,json.encode(data))
  if not timeoutEvent then timeoutEvent=scheduleEvent(function()
    timeoutEvent=nil
    if window and window:isVisible() and next(pending) then
      pending={}
      window.message:setText('Your journal could not be updated. Try Refresh.')
    end
  end,8000) end
  return true
end

function selectQuest(id)
  if not window or not window:isVisible() then return end
  cancel(selectionEvent)
  pending.detail=nil
  if not next(pending) then cancel(timeoutEvent); timeoutEvent=nil end
  if selected~=id then clearDetail(); window.detailScroll:setValue(0) end
  selected=id
  for _,row in ipairs(window.quests:getChildren()) do
    local active=row.questId==selected
    row:setBorderColor(active and '#aaa28c' or '#505050')
    row:setBackgroundColor(active and '#42423e' or '#343434')
  end
  selectionEvent=scheduleEvent(function()
    selectionEvent=nil
    if selected==id and window and window:isVisible() then send('detail',{id=id}) end
  end,180)
end

local function validSummary(q)
  return type(q)=='table' and str(q.id,64) and str(q.name,100) and str(q.region,100)
    and statusText[q.status] and int(q.total,1,30) and int(q.done,0,q.total)
end

function onQuestOpcode(protocol,opcode,buffer)
  if opcode~=OPCODE or not window or not window:isVisible() or type(buffer)~='string' or #buffer>48000 then return end
  local ok,data=pcall(json.decode,buffer)
  if not ok or type(data)~='table' or not int(data.requestId,1,1000000000) or
    pending[data.action]~=data.requestId then return end
  if data.journal~=2 then
    window.message:setText('The journal is not available in this world yet.')
    pending={}; cancel(timeoutEvent); timeoutEvent=nil
    return
  end
  if data.action=='list' then
    if type(data.entries)~='table' or #data.entries>35 or not int(data.pages,1,1000) or
      not int(data.page,1,data.pages) or not int(data.total,0,10000) or
      not int(data.completed,0,data.total) or not int(data.matched,0,data.total) then return end
    for _,q in ipairs(data.entries) do if not validSummary(q) then return end end
    page,pages,rows=data.page,data.pages,data.entries
    local scroll=window.questScroll:getValue()
    window.quests:destroyChildren()
    local found=false
    for _,q in ipairs(rows) do
      local row=g_ui.createWidget('QuestRow',window.quests)
      row.questId=q.id
      fit(row.title,q.name)
      row:setHeight(row.title:getHeight()+27)
      row.status:setText(statusText[q.status]..'  |  '..q.total..(q.total==1 and ' note' or ' notes'))
      row:setTooltip(q.name..'\n'..q.region)
      row.onClick=function() selectQuest(q.id) end
      local active=q.id==selected
      row:setBorderColor(active and '#aaa28c' or '#505050')
      row:setBackgroundColor(active and '#42423e' or '#343434')
      found=found or active
    end
    window.questScroll:setValue(scroll)
    window.count:setText(data.total..' discovered  |  '..data.completed..' completed')
    window.page:setText('Page '..page..' / '..pages)
    window.previous:setEnabled(page>1); window.next:setEnabled(page<pages)
    pending.list=nil
    if not found then
      selected=nil; pending.detail=nil; clearDetail()
      if rows[1] then selectQuest(rows[1].id) end
    elseif selected then
      -- Refresh details after the list, preventing mixed generations of replies.
      selectQuest(selected)
    end
    if #rows==0 and data.total>0 then
      fit(window.detail.title,'No matching entries')
      fit(window.detail.description,'Try another search or return to All entries to read your journal.')
    end
  elseif data.action=='detail' then
    if data.unavailable==true then
      selected=nil; clearDetail(); pending.detail=nil
      window.message:setText(journalHint)
      if not next(pending) then cancel(timeoutEvent); timeoutEvent=nil end
      return
    end
    local q=data.quest
    if not validSummary(q) or q.id~=selected or not str(q.description,1800) or
      not str(q.rewards,3000) or type(q.steps)~='table' or #q.steps~=q.total then return end
    for _,s in ipairs(q.steps) do
      if type(s)~='table' or not str(s.name,150) or not int(s.target,1,1000000) or
        not int(s.current,0,s.target) or type(s.completed)~='boolean' then return end
    end
    detailData=q; renderDetail()
  else return end
  pending[data.action]=nil
  if not next(pending) then cancel(timeoutEvent); timeoutEvent=nil end
  window.message:setText(journalHint)
end

function refresh()
  if not window or not window:isVisible() then return end
  if pending.list or pending.detail or searchEvent or selectionEvent then return end
  local query=window.search:getText():sub(1,48):gsub('[%c]','')
  if not send('list',{page=page,filter=filter,query=query}) then
    window.message:setText('Enter the world to open your journal.')
    return
  end
end

local function poll()
  pollEvent=nil
  if window and window:isVisible() then
    refresh(); pollEvent=scheduleEvent(poll,6000)
  end
end

function changedSearch()
  if resetting then return end
  cancel(searchEvent)
  cancel(selectionEvent); selectionEvent=nil
  cancel(timeoutEvent); timeoutEvent=nil
  pending={}; selected=nil; page=1; clearDetail()
  rows={}; window.quests:destroyChildren()
  window.questScroll:setValue(0)
  searchEvent=scheduleEvent(function() searchEvent=nil; refresh() end,350)
end

function changePage(delta)
  local target=math.max(1,math.min(pages,page+delta))
  if target==page then return end
  cancel(searchEvent); searchEvent=nil
  cancel(selectionEvent); selectionEvent=nil
  cancel(timeoutEvent); timeoutEvent=nil
  page=target; selected=nil; pending={}; clearDetail()
  rows={}; window.quests:destroyChildren()
  window.questScroll:setValue(0); refresh()
end

function resize()
  if not window then return end
  local size=g_ui.getRootWidget():getSize()
  window:setSize({width=math.min(720,size.width-16),height=math.min(480,size.height-16)})
  window.quests:setWidth(math.floor(window:getWidth()*0.40))
  cancel(layoutEvent)
  layoutEvent=scheduleEvent(function()
    layoutEvent=nil
    if not window then return end
    for i,row in ipairs(window.quests:getChildren()) do
      if rows[i] then fit(row.title,rows[i].name); row:setHeight(row.title:getHeight()+27) end
    end
    if detailData then renderDetail() else clearDetail() end
  end,30)
end

function show()
  if not window then return end
  resize(); window:show(); window:raise(); window:focus()
  button:setOn(true)
  cancel(pollEvent); refresh(); pollEvent=scheduleEvent(poll,6000)
end

function hide()
  cancel(pollEvent); cancel(searchEvent); cancel(timeoutEvent)
  cancel(selectionEvent); cancel(scrollEvent)
  selectionEvent,scrollEvent=nil,nil
  pollEvent,searchEvent,timeoutEvent=nil,nil,nil
  pending={}
  if window then window:hide() end
  if button then button:setOn(false) end
end

function toggle()
  if window and window:isVisible() then hide() else show() end
end

function offline()
  hide(); selected,detailData,rows=nil,nil,{}
  page,pages,filter=1,1,'all'
  resetting=true
  window.search:setText(''); window.filter:setCurrentOption('All entries',true)
  window.quests:destroyChildren(); clearDetail()
  window.count:setText('A personal journal')
  window.page:setText('Page 1 / 1')
  resetting=false
end

function init()
  window=g_ui.displayUI('questlog'); window:hide()
  connect(window, {onVisibilityChange=syncPlayerBarSelection})
  syncPlayerBarSelection()
  button=modules.client_topmenu.addRightGameToggleButton('questLogButton','Quest Log (Ctrl+J)',
    '/images/topbuttons/questlog',toggle,false)
  for _,entry in ipairs({{'All entries','all'},{'In progress','active'},{'Completed','completed'}}) do
    window.filter:addOption(entry[1],entry[2])
  end
  window.filter.onOptionChange=function(widget,text,value) filter=value; changedSearch() end
  connect(window.search,{onTextChange=changedSearch})
  connect(g_game,{onGameEnd=offline})
  connect(g_ui.getRootWidget(),{onGeometryChange=resize})
  ProtocolGame.registerExtendedOpcode(OPCODE,onQuestOpcode,true)
  g_keyboard.bindKeyDown('Ctrl+J',toggle)
  clearDetail()
end

function terminate()
  hide(); cancel(layoutEvent); layoutEvent=nil
  if window then disconnect(window, {onVisibilityChange=syncPlayerBarSelection}) end
  disconnect(g_game,{onGameEnd=offline})
  disconnect(g_ui.getRootWidget(),{onGeometryChange=resize})
  disconnect(window.search,{onTextChange=changedSearch})
  g_keyboard.unbindKeyDown('Ctrl+J')
  ProtocolGame.unregisterExtendedOpcode(OPCODE)
  button:destroy(); window:destroy()
  window,button=nil,nil
end
