-- Native rendering with a silent localhost stub; no real account or server.
local checks = 0
local function report(message)
  local f = assert(io.open(GROUND_REAL_REPORT, 'a'))
  f:write(message .. '\n'); f:close()
end
local function check(value, message) assert(value, message); checks=checks+1 end
local function run()
  check(not g_game.isOnline(), 'Native client remains disconnected')
  g_game.setClientVersion(772)
  g_game.setProtocolVersion(772)
  check(modules.game_things.isLoaded(), 'Native item definitions loaded')
  GROUND_BOOT_NATIVE_PLAYER()
  local nativePlayer=g_game.getLocalPlayer()
  check(nativePlayer~=nil, 'Loopback boot initializes the native LocalPlayer')
  nativePlayer:setHealth(150,150)
  local rarity=modules.game_groundrarity
  check(rarity~=nil, 'Ground rarity module autoloaded')
  local outgoing={}
  local protocol={sendExtendedOpcode=function(_,opcode,payload) outgoing[#outgoing+1]={opcode,payload} end}
  local previous={online=g_game.isOnline,protocol=g_game.getProtocolGame,feature=g_game.getFeature,
    player=g_game.getLocalPlayer}
  g_game.isOnline=function() return true end
  g_game.getProtocolGame=function() return protocol end
  g_game.getFeature=function(id) return id==GameExtendedOpcode or previous.feature(id) end
  g_game.getLocalPlayer=function() return {getPosition=function() return {x=100,y=100,z=7} end} end
  local sequence=0
  local function receive(data)
    if data.event=='ready' or data.event=='reset' then sequence=sequence+1; data.seq=sequence end
    ProtocolGame.onExtendedOpcode(protocol,129,json.encode(data))
  end
  local function stackOf(item)
    for i,thing in ipairs(g_map.getTile(item:getPosition()):getThings()) do if thing==item then return i-1 end end
  end
  local function snapshot(pos,records)
    sequence=sequence+1; receive({event='tile',position=pos,seq=sequence,items=records})
  end
  rarity.reset(); receive({event='ready',version=1})
  local pos={x=100,y=100,z=7}
  local first,second=Item.create(3264),Item.create(3264)
  g_map.addThing(first,pos,-1); g_map.addThing(second,pos,-1)
  snapshot(pos,{{itemId=3264,stackpos=stackOf(first),tier=2}})
  check(rarity.restoreMark(first) and not rarity.restoreMark(second), 'Native identical sprites retain distinct rarity')
  local third=Item.create(3264); g_map.addThing(third,pos,-1); rarity.updateMarks()
  check(rarity.restoreMark(first) and not rarity.restoreMark(third), 'Stack shift cannot tint common native item')
  local panel=modules.game_interface.getMapPanel()
  g_settings.set('highlightThingsUnderCursor',true)
  panel:markThing(first,'yellow'); panel:markThing(nil)
  check(rarity.restoreMark(first), 'Native hover departure restores rarity mark')
  g_map.removeThing(first); rarity.updateMarks()
  check(not rarity.restoreMark(first) and not rarity.restoreMark(second), 'Native pickup does not transfer rarity')
  g_map.addThing(first,pos,-1)
  snapshot(pos,{{itemId=3264,stackpos=stackOf(first),tier=5}})
  g_map.removeThing(first)
  local replacement=Item.create(3264); g_map.addThing(replacement,pos,-1); rarity.updateMarks()
  check(not rarity.restoreMark(replacement), 'Replacement native object never inherits stale tint')
  snapshot(pos,{{itemId=3264,stackpos=stackOf(replacement),tier=4}})
  check(rarity.restoreMark(replacement), 'Authoritative native snapshot rebinds replacement')
  receive({event='reset'})
  check(not rarity.restoreMark(replacement), 'Server map reset clears native state')
  g_map.removeThing(second); g_map.removeThing(third); g_map.removeThing(replacement)

  -- Real map, six columns: common then the five rarity colors. A UIItem row
  -- separately verifies whether native inventory rendering honors setMarked.
  local root=g_ui.getRootWidget()
  local frame=g_ui.createWidget('UIWidget',root)
  frame:setBackgroundColor('#20242C'); frame:setPosition({x=12,y=40}); frame:setSize({width=780,height=530})
  local title=g_ui.createWidget('UILabel',frame)
  title:setPosition({x=24,y=52}); title:setSize({width=744,height=25})
  title:setText('RARIDADE NO PROPRIO ITEM  |  cliente nativo, QA local'); title:setColor('#ECF0F6')
  modules.client_options.setOption('ambientLight',100)
  modules.client_options.setOption('enableLights',false)
  local map=modules.game_interface.getMapPanel()
  map:setParent(frame); map:breakAnchors(); map:show()
  map:setPosition({x=35,y=110}); map:setSize({width=720,height=330})
  map:setKeepAspectRatio(false); map:setVisibleDimension({width=13,height=7})
  map:setMinimumAmbientLight(1); map:setDrawLights(false); map:setDrawNames(false); map:setDrawHealthBars(false)
  g_map.setCentralPosition({x=100,y=100,z=7})
  map:setCameraPosition({x=100,y=100,z=7})
  for x=93,107 do for y=95,105 do g_map.addThing(Item.create(416),{x=x,y=y,z=7},-1) end end
  local names={'Comum','Incomum','Raro','Epico','Lendario','Mitico'}
  local colors={'#C8CED8','#42C96B','#3E8BFF','#A855F7','#F5C542','#EF4444'}
  for tier=0,5 do
    local label=g_ui.createWidget('UILabel',frame)
    label:setPosition({x=35+tier*120,y=84}); label:setSize({width=120,height=24})
    label:setText(names[tier+1]); label:setColor(colors[tier+1])
    for row,itemId in ipairs({3264,3357,3552}) do
      local p={x=95+tier*2,y=97+row,z=7}
      local item=Item.create(itemId); g_map.addThing(item,p,-1)
      if tier>0 then snapshot(p,{{itemId=itemId,stackpos=stackOf(item),tier=tier}}) end
      check(rarity.restoreMark(item)==(tier>0), 'Native map sample '..tier..'/'..row)
    end
    local widget=g_ui.createWidget('UIItem',frame)
    widget:setPosition({x=69+tier*120,y=466}); widget:setSize({width=52,height=52})
    local held=Item.create(3264); widget:setItem(held)
    local uiRarity=modules.game_inventory.AntigasItemRarity
    uiRarity.apply(widget,tier,false,6,tier,0)
    local reference=g_ui.createWidget('UIWidget',frame)
    reference:setColor(tier>0 and colors[tier+1] or '#FFFFFF')
    check(json.encode(widget:getColor())==json.encode(reference:getColor()), 'Native UIItem sprite color '..tier)
    check(widget:getBorderTopWidth()==(tier>0 and 1 or 0), 'Existing rarity border remains '..tier)
    reference:destroy()
  end
  local note=g_ui.createWidget('UILabel',frame)
  note:setPosition({x=35,y=442}); note:setSize({width=720,height=24})
  note:setText('Mapa acima / sprite em UIItem abaixo'); note:setColor('#C8CED8')
  check(#outgoing==0, 'Fixture does not send custom messages through the fake transport')
  scheduleEvent(function()
    map:setMinimumAmbientLight(1); map:setDrawLights(false); map:setDrawNames(false); map:setDrawHealthBars(false)
    map:setKeepAspectRatio(false); map:setVisibleDimension({width=13,height=7})
    scheduleEvent(function() g_app.doScreenshot('ground-rarity-ui-native.png') end,150)
    scheduleEvent(function()
      rarity.reset()
      g_game.isOnline,g_game.getProtocolGame,g_game.getFeature,g_game.getLocalPlayer=previous.online,previous.protocol,previous.feature,previous.player
      report('PASS: native ground rarity, '..checks..' assertions, rendered frame, localhost stub only')
    end,300)
  end,800)
end
scheduleEvent(function()
  report('START: native ground rarity')
  local ok,err=pcall(run)
  if not ok then report('FAIL: '..tostring(err)) end
  scheduleEvent(function() g_app.exit() end,1500)
end,100)
