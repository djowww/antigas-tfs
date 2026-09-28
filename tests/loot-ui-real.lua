-- Execute with the isolated fixture prepared by loot-ui-prepare.py.
local checks = 0
local function report(message)
  local f = assert(io.open(LOOT_REAL_REPORT, 'a'))
  f:write(message .. '\n'); f:close()
end
local function check(value, message)
  assert(value, message); checks = checks + 1
end
local function run()
  check(not g_game.isOnline(), 'Native client starts offline')
  g_game.setClientVersion(772)
  check(modules.game_things.isLoaded(), 'Native item definitions loaded')
  check(modules.game_loot ~= nil, 'Loot module autoloaded')
  local label = g_ui.createWidget('ConsoleLabel', g_ui.getRootWidget())
  label:setColoredText({'common', '#C8CED8', ', rare', '#3E8BFF'})
  check(label:getText() == 'common, rare', 'Native colored text retains plaintext')
  label:selectAll()
  check(label:getSelection() == 'common, rare', 'Native colored text can be copied')
  report('CAPABILITY: setColoredText on native ConsoleLabel and selection work')
  local corpse = Item.create(3058)
  corpse:setMarked('#C8CED8'); corpse:setMarked('')
  check(corpse:isItem(), 'Native corpse mark API works')
  label:destroy()

  local loot, console = modules.game_loot, modules.game_console
  local outgoing = {}
  local protocol = {sendExtendedOpcode=function(_, opcode, payload) outgoing[#outgoing+1]={opcode,payload} end}
  local previous={online=g_game.isOnline,protocol=g_game.getProtocolGame,localPlayer=g_game.getLocalPlayer,
    name=g_game.getCharacterName,feature=g_game.getFeature,talk=g_game.talkChannel}
  local pos={x=100,y=100,z=7}
  g_game.isOnline=function() return true end
  g_game.getProtocolGame=function() return protocol end
  g_game.getLocalPlayer=function() return {getPosition=function() return pos end} end
  g_game.getCharacterName=function() return 'Offline Loot QA' end
  g_game.getFeature=function(id) return id==GameExtendedOpcode or previous.feature(id) end
  g_game.talkChannel=function() error('Read-only Loot must never send a chat message') end
  console.addChannel('Loot',10)
  local tab=console.getChannelTab(10)
  check(tab and tab.channelId==10, 'Native personal Loot channel')
  loot.reset()
  local function receive(data) ProtocolGame.onExtendedOpcode(protocol,128,json.encode(data)) end
  receive({event='ready',version=1})
  g_map.addThing(corpse,pos,-1)
  local second=Item.create(3058)
  g_map.addThing(second,pos,-1)
  local tile=g_map.getTile(pos)
  check(tile and #tile:getThings()==2, 'Native map tile has two identical corpse items')
  local function stackOf(item)
    for i, thing in ipairs(tile:getThings()) do if thing==item then return i-1 end end
  end
  local firstStack,secondStack=stackOf(corpse),stackOf(second)
  local colors={'#42C96B','#3E8BFF','#A855F7','#F5C542','#EF4444'}
  for tier=0,5 do
    receive({event='loot',id=tostring(tier+1),name='a black knight',position=pos,corpseId=3058,
      stackpos=firstStack,tier=tier,unopened=tier==0,
      items={{id=2148,name='63 gold coins',count=63,tier=0},{id=2376,name='a sword',count=1,tier=tier}}})
  end
  local buffer=tab.tabPanel:getChildById('consoleBuffer')
  check(buffer:getChildCount()==6, 'Native channel shows six loot records')
  for _, entry in ipairs(buffer:getChildren()) do
    check(entry:getText():find('Loot of a black knight: 63 gold coins, a sword',1,true), 'Native console plaintext')
    entry:selectAll()
    check(entry:getSelection()==entry:getText(), 'Rich loot line supports exact full selection')
  end
  console.selectAll(buffer)
  check(buffer.selectionText:find('63 gold coins, a sword',1,true), 'Channel-wide copy includes loot')
  console.clearSelection(buffer)
  console.sendMessage('This must never be spoken',tab)
  check(#outgoing==0, 'Loot text input cannot send game chat')
  check(loot.restoreMark(corpse), 'Native corpse identity is tracked')
  receive({event='marker',id='20',position=pos,corpseId=3058,stackpos=secondStack,tier=5})
  loot.updateMarkers()
  check(loot.restoreMark(second), 'Native second same-sprite corpse independently tracked')
  receive({event='opened',id='1'})
  check(not loot.restoreMark(corpse) and loot.restoreMark(second), 'Opening only clears server-selected corpse')
  receive({event='removed',id='20'})
  check(not loot.restoreMark(second), 'Removal clears native marker')
  for _, effectId in ipairs({13,14,15}) do
    local effect=Effect.create(); effect:setId(effectId)
    check(effect:getId()==effectId, 'Native drop effect '..effectId..' is available')
  end
  local recycled=buffer:getFirstChild()
  console.MAX_LINES=0
  console.addTabText('Plain channel fallback after rich loot', {color='#C8CED8'},tab)
  check(buffer:getLastChild()==recycled and recycled:getText():find('Plain channel fallback after rich loot',1,true), 'Recycled rich label accepts plain fallback')
  console.MAX_LINES=100
  local panel=console.consolePanel
  local frame=g_ui.createWidget('UIWidget',g_ui.getRootWidget())
  frame:setPosition({x=10,y=250}); frame:setSize({width=780,height=330})
  panel:setParent(frame); panel:fill('parent'); panel:show()
  console.consoleTabBar:selectTab(tab)
  loot.reset()
  g_game.isOnline,g_game.getProtocolGame,g_game.getLocalPlayer=previous.online,previous.protocol,previous.localPlayer
  g_game.getCharacterName,g_game.getFeature,g_game.talkChannel=previous.name,previous.feature,previous.talk
  check(not g_game.isOnline(), 'Native fixture remains disconnected')
  report('PASS: native loot UI, '..checks..' assertions, no connection')
  scheduleEvent(function() g_app.doScreenshot('loot-ui-native.png') end,350)
end
scheduleEvent(function()
  report('START: native loot UI')
  local ok, err = pcall(run)
  if not ok then report('FAIL: ' .. tostring(err)) end
  scheduleEvent(function() g_app.exit() end, 1000)
end, 100)
