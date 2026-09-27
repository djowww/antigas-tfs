local OPCODE = 125
local window, button, pollEvent, searchEvent, timeoutEvent, layoutEvent
local selected, detailData, rows, pending = nil, nil, {}, {}
local page, pages, serial, filter = 1, 1, 0, 'all'
local resetting = false
local statusText = {unstarted='Not recorded',active='In progress',completed='Completed'}

local function cancel(event) if event then removeEvent(event) end end
local function int(value,low,high)
  return type(value)=='number' and value==math.floor(value) and value>=low and value<=high
end
local function str(value,limit) return type(value)=='string' and #value<=limit end

local function fit(label,text)
  label:setTooltip(text)
  local lines, current = {}, ''
  local width = math.max(40,label:getWidth()-2)
  for word in text:gmatch('%S+') do
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
  window.detail.title:setText('Select a quest')
  window.detail.state:setText('')
  window.detail.description:setText('Choose a quest on the left to view your recorded progress.')
  window.detail.reward:setText('')
  window.detail.steps:destroyChildren()
end

local function renderDetail()
  if not window or not detailData then return end
  local q=detailData
  fit(window.detail.title,q.name)
  fit(window.detail.state,statusText[q.status]..'  |  '..q.region)
  fit(window.detail.description,q.description)
  fit(window.detail.reward,q.rewards~='' and ('Map reward: '..q.rewards) or
    'Rewards and permissions remain with the original quest NPCs and scripts.')
  window.detail.steps:destroyChildren()
  for _,s in ipairs(q.steps) do
    local row=g_ui.createWidget('QuestStep',window.detail.steps)
    fit(row.title,s.name)
    row.progress:setText((s.completed and 'Done' or 'Recorded')..': '..s.current..' / '..s.target)
    row.progress:setColor(s.completed and '#c6b785' or '#bababa')
    row:setHeight(row.title:getHeight()+25)
  end
end

local function send(action,data)
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
      window.message:setText('No reply yet. Reconnect after a server update, or use Refresh.')
    end
  end,8000) end
  return true
end

function selectQuest(id)
  if selected~=id then clearDetail(); window.detailScroll:setValue(0) end
  selected=id
  for _,row in ipairs(window.quests:getChildren()) do
    local active=row.questId==selected
    row:setBorderColor(active and '#aaa28c' or '#505050')
    row:setBackgroundColor(active and '#42423e' or '#343434')
  end
  send('detail',{id=id})
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
      row.status:setText(statusText[q.status]..'  |  '..q.done..' / '..q.total..' stages')
      row:setTooltip(q.name..'\n'..q.region)
      row.onClick=function() selectQuest(q.id) end
      local active=q.id==selected
      row:setBorderColor(active and '#aaa28c' or '#505050')
      row:setBackgroundColor(active and '#42423e' or '#343434')
      found=found or active
    end
    window.questScroll:setValue(scroll)
    window.count:setText(data.completed..' / '..data.total..' completed  |  '..data.matched..' matched')
    window.page:setText('Page '..page..' / '..pages)
    window.previous:setEnabled(page>1); window.next:setEnabled(page<pages)
    if not found then
      selected=nil; pending.detail=nil; clearDetail()
      if rows[1] then selectQuest(rows[1].id) end
    end
    if #rows==0 then window.detail.title:setText('No matching quests') end
  elseif data.action=='detail' then
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
  window.message:setText('Read-only progress. Updates every 6 seconds while open; claim rewards in the world.')
end

function refresh()
  if not window or not window:isVisible() then return end
  local query=window.search:getText():sub(1,48):gsub('[%c]','')
  if not send('list',{page=page,filter=filter,query=query}) then
    window.message:setText('Connect to Antigas to load your quest progress.')
    return
  end
  if selected then send('detail',{id=selected}) end
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
  pending={}; selected=nil; page=1; clearDetail()
  window.questScroll:setValue(0)
  searchEvent=scheduleEvent(function() searchEvent=nil; refresh() end,350)
end

function changePage(delta)
  local target=math.max(1,math.min(pages,page+delta))
  if target==page then return end
  page=target; selected=nil; pending={}; clearDetail()
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
    renderDetail()
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
  window.search:setText(''); window.filter:setCurrentOption('All',true)
  window.quests:destroyChildren(); clearDetail()
  window.count:setText("Your character's quest journal")
  window.page:setText('Page 1 / 1')
  resetting=false
end

function init()
  window=g_ui.displayUI('questlog'); window:hide()
  button=modules.client_topmenu.addRightGameToggleButton('questLogButton','Quest Log (Ctrl+J)',
    '/images/topbuttons/questlog',toggle,false)
  for _,entry in ipairs({{'All','all'},{'In progress','active'},{'Completed','completed'},{'Not recorded','unstarted'}}) do
    window.filter:addOption(entry[1],entry[2])
  end
  window.filter.onOptionChange=function(widget,text,value) filter=value; changedSearch() end
  connect(window.search,{onTextChange=changedSearch})
  connect(g_game,{onGameEnd=offline})
  connect(g_ui.getRootWidget(),{onGeometryChange=resize})
  ProtocolGame.registerExtendedOpcode(OPCODE,onQuestOpcode,true)
  g_keyboard.bindKeyDown('Ctrl+J',toggle)
end

function terminate()
  hide(); cancel(layoutEvent); layoutEvent=nil
  disconnect(g_game,{onGameEnd=offline})
  disconnect(g_ui.getRootWidget(),{onGeometryChange=resize})
  disconnect(window.search,{onTextChange=changedSearch})
  g_keyboard.unbindKeyDown('Ctrl+J')
  ProtocolGame.unregisterExtendedOpcode(OPCODE)
  button:destroy(); window:destroy()
  window,button=nil,nil
end
