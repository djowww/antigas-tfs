-- Offline validation of the shipped loot module and real JSON decoder.
local checks = 0
local function check(ok, reason) assert(ok, reason); checks = checks + 1 end
local function count(t) local n=0; for _ in pairs(t) do n=n+1 end; return n end
local function upvalue(fn, wanted)
  for i=1,100 do local name,value=debug.getupvalue(fn,i); if name==wanted then return value end end
end
dofile('../../Cliente/modules/corelib/json.lua')
local now, events, active, online, feature = 0, {}, true, true, true
local tiles, requests, lines = {}, {}, {}
local playerPos = {x=100,y=100,z=7}
local map = {}
local protocol = {sendExtendedOpcode=function(_, opcode, payload) requests[#requests+1]={opcode,payload} end}
local function posKey(pos) return pos.x..','..pos.y..','..pos.z end
local function item(id, pos)
  return {id=id,position=pos,marks={},isItem=function() return true end,
    getId=function(self) return self.id end,getPosition=function(self) return self.position end,
    setMarked=function(self,color) self.mark=color; self.marks[#self.marks+1]=color end}
end
local function tile(pos, things)
  local result = {things=things,getThings=function(self) return self.things end,
    getThing=function(self,index) return self.things[index+1] end}
  tiles[posKey(pos)] = result; return result
end
local function step(ms)
  local target = now+ms
  while true do
    local nextEvent
    for _, e in ipairs(events) do
      if not e.done and e.time<=target and (not nextEvent or e.time<nextEvent.time) then nextEvent=e end
    end
    if not nextEvent then break end
    now=nextEvent.time; nextEvent.done=true; nextEvent.callback()
  end
  now=target
end
function scheduleEvent(callback, delay)
  local e={callback=callback,time=now+delay}; events[#events+1]=e; return e
end
function removeEvent(e) e.done=true end
function connect() end
function disconnect() end
g_clock={millis=function() return now end}
g_logger={warning=function() end}
g_game={isOnline=function() return online end,getFeature=function() return feature end,
  getProtocolGame=function() return protocol end,getLocalPlayer=function() return {getPosition=function() return playerPos end} end}
g_map={getTile=function(pos) return tiles[posKey(pos)] end}
g_settings={getBoolean=function() return true end}
GameExtendedOpcode=1
local callback
ProtocolGame={registerExtendedOpcode=function(opcode, fn, raw)
  check(opcode==128 and raw, 'Raw dedicated opcode'); callback=fn
end,unregisterExtendedOpcode=function() callback=nil end}
modules={game_interface={getMapPanel=function() return map end},game_console={
  getChannelTab=function(id) if active and id==10 then return {} end end,
  addTabText=function(text, settings, tab, name, rich) lines[#lines+1]={text=text,rich=rich} end}}
dofile('../../Cliente/modules/corelib/networkdata.lua')
dofile('../../Cliente/modules/game_loot/loot.lua')
init()
step(250)
check(requests[1][1]==128 and requests[1][2]=='H|1', 'Versioned capability handshake')
local function receive(data) callback(protocol,128,json.encode(data)) end
local pos={x=101,y=100,z=7}
local first, second = item(3058,pos), item(3058,pos)
local corpseTile = tile(pos,{first,second})
local function loot(id, stack, tier)
  return {event='loot',id=tostring(id),name='a black knight',position=pos,corpseId=3058,
    stackpos=stack,tier=tier,unopened=true,items={{id=2376,name='a sword',count=1,tier=tier}}}
end
receive(loot(1,0,2))
check(#lines==0 and first.mark==nil, 'Packets before handshake are ignored')
receive({event='ready',version=1})
receive(loot(1,0,2))
check(#lines==1 and first.mark and first.mark~='', 'Rare loot is logged and unopened corpse marked')
check(lines[1].rich[4]=='#3E8BFF' and lines[1].text=='Loot of a black knight: a sword', 'Exact item rarity color and copy text')
local prior=first.mark
step(450)
check(first.mark~=prior, 'Unopened marker pulses')
receive(loot(1,0,2))
check(#lines==1, 'Duplicate token cannot duplicate loot notice')
receive(loot(2,1,5)); step(150)
check(second.mark and second.mark~='', 'Second identical corpse on same tile has own mark')
receive({event='opened',id='1'})
check(first.mark=='' and second.mark~='', 'Opening one identical corpse preserves the other')
corpseTile.things={second}
step(150)
check(second.mark~='', 'Changing stack index preserves native corpse identity')
map.markedThing=second
second:setMarked('yellow'); step(150)
check(second.mark=='yellow', 'Cursor hover temporarily owns highlight')
map.markedThing=nil; second:setMarked('')
check(restoreMark(second) and second.mark~='', 'Hover departure restores unopened marker')
receive({event='removed',id='2'})
check(second.mark=='', 'Server removal clears mark')

local common = loot(3,0,0); common.items={}
common.unopened=false
receive(common)
check(lines[#lines].text:find('nothing',1,true), 'Empty loot is visible')
common.id='4'; receive(common)
check(#lines==4 and second.mark=='', 'Each empty kill has a unique log and no unopened marker')
common.id='5'; common.items={{id=2376,name='a sword',count=1,tier=0}}; common.unopened=true
receive(common)
step(150)
check(second.mark and second.mark~='', 'Common unopened corpses are also highlighted')
local replacement=item(3058,pos); corpseTile.things={replacement}
step(150)
check(second.mark=='' and replacement.mark==nil, 'Replacement sprite never inherits stale marker')
receive({event='marker',id='5',position=pos,corpseId=3058,stackpos=0,tier=0})
check(restoreMark(replacement), 'Fresh server marker can bind the recreated corpse')
receive({event='opened',id='5'})

local burst1,burst2,burst3=item(3058,pos),item(3058,pos),item(3058,pos)
corpseTile.things={burst1}
receive(loot(6,0,1))
corpseTile.things={burst2,burst1}
receive(loot(7,0,2))
corpseTile.things={burst3,burst2,burst1}
receive(loot(8,0,3))
step(150)
receive({event='opened',id='7'})
check(restoreMark(burst1) and not restoreMark(burst2) and restoreMark(burst3), 'Burst corpses bind synchronously before stack index shifts')
receive({event='opened',id='6'}); receive({event='opened',id='8'})
corpseTile.things={}
receive({event='marker',id='9',position=pos,corpseId=3058,stackpos=0,tier=1})
corpseTile.things={replacement}; step(150)
check(not restoreMark(replacement), 'Missing item is never rebound against a delayed stale stack')
receive({event='marker',id='9',position=pos,corpseId=3058,stackpos=0,tier=1})
check(restoreMark(replacement), 'Server replay resolves initially missing corpse safely')
receive({event='opened',id='9'})

for tier=1,5 do
  local data=loot(10+tier,0,tier)
  data.items={{id=2376,name='a sword',count=1,tier=0},{id=2376,name='a sword',count=1,tier=tier}}
  receive(data)
  local rich=lines[#lines].rich
  check(rich[4]=='#C8CED8' and rich[8]==({'#42C96B','#3E8BFF','#A855F7','#F5C542','#EF4444'})[tier], 'Identical names keep independent tier color '..tier)
end
local visible=#lines
local data=loot(30,-1,3); data.unopened=false
receive(data)
check(#lines==visible+1, 'Offscreen party loot still logs')
data=loot(31,0,1); data.omitted=7; receive(data)
check(lines[#lines].text:find('+7 itens',1,true), 'Bounded overflow summary is displayed')
active=false; receive(loot(32,0,0)); check(#lines==visible+2, 'Player-closed Loot channel stays closed'); active=true
data=loot(33,-1,0); data.unopened=false; data.name=string.rep('á',80); data.items[1].name=string.rep('á',160)
receive(data)
check(#lines==visible+3, 'Legacy accented names fit character limits after UTF-8 JSON decoding')

visible=#lines
for _, change in ipairs({
  function(d) d.id='bad' end,function(d) d.tier=6 end,function(d) d.stackpos=-1 end,
  function(d) d.name='bad\nname' end,function(d) d.items[1].tier=1.5 end,
  function(d) d.position={x=65535,y=100,z=7} end,function(d) d.items[1].count=0 end,
  function(d) d.items[1].name=string.rep('x',161) end,function(d) d.omitted=-1 end,
  function(d) d.items[1].id=0 end,function(d) d.unopened='yes' end
}) do local invalid=loot(100,0,1); change(invalid); receive(invalid) end
callback(protocol,128,string.rep(' ',8193))
callback(protocol,128,string.rep('[',20)..string.rep(']',20))
callback({},128,json.encode(loot(101,0,1)))
check(#lines==visible, 'Invalid/excessive/stale-protocol inputs are rejected')

reset(); receive({event='ready',version=1})
for i=1,300 do
  local p={x=1000+i,y=100,z=7}
  tile(p,{item(3058,p)})
  receive({event='marker',id=tostring(1000+i),position=p,corpseId=3058,stackpos=0,tier=0})
end
check(count(upvalue(updateMarkers,'markers'))==256, 'Marker count is bounded')
local pending=0
for _,event in ipairs(events) do if not event.done then pending=pending+1 end end
check(pending==1, 'All markers share one bounded pulse timer')
for i=1,600 do local d=loot(2000+i,-1,0); d.unopened=false; receive(d) end
check(count(upvalue(upvalue(onOpcode,'remember'),'seen'))==512, 'Duplicate history is bounded')
playerPos={x=100,y=100,z=8}; step(150)
check(count(upvalue(updateMarkers,'markers'))==0, 'Floor change removes stale corpse markers')
reset(); receive({event='ready',version=1})
receive({event='marker',id='99999',position=pos,corpseId=3058,stackpos=99,tier=1})
step(2200)
check(count(upvalue(updateMarkers,'markers'))==0, 'Unresolvable stack reference expires')
receive({event='marker',id='99998',position=pos,corpseId=3058,stackpos=0,tier=1})
online=false; reset()
pending=0; for _,event in ipairs(events) do if not event.done then pending=pending+1 end end
check(pending==0 and count(upvalue(updateMarkers,'markers'))==0, 'Logout cancels all timers and clears state')
terminate()
check(callback==nil, 'Unload unregisters callback')
print('loot-ui-tests: '..checks..' assertions passed')
