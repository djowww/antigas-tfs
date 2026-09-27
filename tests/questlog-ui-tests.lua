-- Offline OTClient fixture. Never connect or submit purchases.
local function report(s)
  local f=assert(io.open('questlog-ui-report.txt','a')); f:write(s..'\n'); f:close()
end
local function checked(fn,delay)
  scheduleEvent(function()
    local ok,err=pcall(fn)
    if not ok then report('FAIL: '..tostring(err)); g_app.exit() end
  end,delay)
end
local function run()
  assert(not g_game.isOnline(),'Offline test only')
  local sent={}
  local oldOnline,oldFeature,oldProtocol=g_game.isOnline,g_game.getFeature,g_game.getProtocolGame
  g_game.isOnline=function() return true end
  g_game.getFeature=function() return true end
  g_game.getProtocolGame=function() return {sendExtendedOpcode=function(self,op,buffer)
    assert(op==125); sent[#sent+1]=json.decode(buffer)
  end} end
  local module=modules.game_questlog
  local window=g_ui.getRootWidget():recursiveGetChildById('questLogWindow')
  assert(window,'Module loads OTUI')
  module.show()
  assert(window:isVisible() and sent[#sent].action=='list')
  local function response(data,request)
    data.requestId=request.requestId
    module.onQuestOpcode(nil,125,json.encode(data))
  end
  local entries={}
  for i=1,35 do entries[i]={id='quest-'..i,name=i==1 and 'The Explorer Society' or
    'A long quest title with multiple words - Mainland '..i,region='Port Hope',kind='story',status='active',done=2,total=13} end
  local function listing()
    response({action='list',entries=entries,page=1,pages=7,total=242,matched=242,completed=3},sent[#sent])
  end
  listing()
  assert(window.quests:getChildCount()==35,'Full page renders')
  assert(sent[#sent].action=='detail','Selection requests detail')
  local quest={id='quest-1',name='The Explorer Society',region='Port Hope / Northport',
    status='active',done=2,total=13,description=string.rep('Existing mission progress is read from your character. ',5),
    rewards=string.rep('Gold coins and original quest rewards. ',8),steps={}}
  for i=1,13 do quest.steps[i]={name='Research mission '..i..' with a longer objective name',current=i<3 and 2 or 0,target=2,completed=i<3} end
  response({action='detail',quest=quest},sent[#sent])
  assert(window.detail.steps:getChildCount()==13,'All mission steps render')
  local pending=sent[#sent]
  module.onQuestOpcode(nil,125,'{bad')
  response({action='detail',quest=quest},{requestId=pending.requestId-1})
  assert(window.detail.steps:getChildCount()==13,'Malformed and stale packets ignored')
  report('PASS: module, open, list, automatic selection, details, long descriptions, malformed/stale replies')
  local sizes={{width=800,height=600},{width=1024,height=768},{width=1366,height=768}}
  local function nextSize(i)
    if not sizes[i] then
      window.search:setText('Explorer')
      checked(function()
        assert(sent[#sent].query=='Explorer','Debounced search')
        window.filter:setCurrentOption('Completed')
        checked(function()
          assert(sent[#sent].filter=='completed','Filter callback')
          local oldCount=#sent
          module.hide(); assert(not window:isVisible())
          module.show(); assert(window:isVisible() and #sent>oldCount,'Reopen refreshes')
          module.offline()
          assert(window.quests:getChildCount()==0 and window.search:getText()=='','Clear character data on logout')
          g_game.isOnline,g_game.getFeature,g_game.getProtocolGame=oldOnline,oldFeature,oldProtocol
          report('PASS: search, filters, close/reopen, logout clears private progress')
          if QUESTLOG_QA_PREVIEW then
            g_game.isOnline=function() return true end
            g_game.getFeature=function() return true end
            g_game.getProtocolGame=function() return {sendExtendedOpcode=function(self,op,b) sent[#sent+1]=json.decode(b) end} end
            module.show(); listing(); response({action='detail',quest=quest},sent[#sent])
            checked(function()
              assert(window.detail.title:getText()=='The Explorer Society','Preview detail survives layout')
            end,120)
            report('PREVIEW: ready')
            scheduleEvent(function() g_app.exit() end,240000)
          else g_app.exit() end
        end,420)
      end,420)
      return
    end
    g_window.resize(sizes[i])
    checked(function()
      local r,b=g_ui.getRootWidget():getRect(),window:getRect()
      assert(b.x>=r.x and b.y>=r.y and b.x+b.width<=r.x+r.width and b.y+b.height<=r.y+r.height,'Window fits')
      local bar=modules.game_playerbars.playerBarsWindow
      local market=bar:recursiveGetChildById('marketButton')
      local quests=bar:recursiveGetChildById('questButton')
      assert(market:getY()==quests:getY() and market:getX()+market:getWidth()<quests:getX(),'Service row aligns')
      assert(quests:getX()+quests:getWidth()<=bar:getX()+bar:getWidth(),'Quests button fits horizontally')
      assert(quests:getY()+quests:getHeight()<=bar:getY()+bar:getHeight(),'Quests button fits vertically')
      assert(window.quests:getX()+window.quests:getWidth()<window.questScroll:getX(),'Quest scrollbar clear')
      assert(window.detail:getX()+window.detail:getWidth()<window.detailScroll:getX(),'Detail scrollbar clear')
      for _,label in ipairs({window.detail.title,window.detail.state,window.detail.description,window.detail.reward}) do
        assert(label:getTextSize().height<=label:getHeight(),'Full text height fits: '..label:getId())
        assert(label:getTextSize().width<=label:getWidth(),'Full text width fits: '..label:getId())
      end
      assert(window.detail.description:getText():gsub('%s+',' ')==quest.description:gsub('%s+$',''),'No description text lost')
      window.detailScroll:setValue(window.detailScroll:getMaximum())
      window.questScroll:setValue(window.questScroll:getMaximum())
      checked(function()
        local row=window.quests:getLastChild()
        assert(row:getY()+row:getHeight()<=window.quests:getY()+window.quests:getHeight()+1,'Last quest fully visible')
        local last=window.detail.steps:getLastChild()
        assert(last:getY()+last:getHeight()<=window.detail:getY()+window.detail:getHeight()+1,'Last stage fully visible')
        assert(window.search:getY()>window.detail:getY()+window.detail:getHeight(),'Footer unobstructed')
        report('PASS: layout, wrapping and both scrollbars '..sizes[i].width..'x'..sizes[i].height)
        nextSize(i+1)
      end,150)
    end,280)
  end
  nextSize(1)
end
checked(run,1200)
