-- Ground rarity snapshots are tied to native object identity, not sprite IDs.
local checks = 0
local function check(ok, reason) assert(ok, reason); checks = checks + 1 end
local function upvalue(fn, wanted)
  for i=1,100 do local name,value=debug.getupvalue(fn,i); if name==wanted then return value end end
end
dofile('../../Cliente/modules/corelib/json.lua')
local now, events, online, feature = 0, {}, true, true
local map, nativeTiles, requests = {}, {}, {}
local protocol = {sendExtendedOpcode=function(_, opcode, payload) requests[#requests+1]={opcode,payload} end}
local function key(pos) return pos.x..','..pos.y..','..pos.z end
local function item(id, pos)
  return {id=id,position=pos,isItem=function() return true end,
    getId=function(self) return self.id end,getPosition=function(self) return self.position end,
    setMarked=function(self,color) self.mark=color end}
end
local function tile(pos, things)
  local result = {things=things,getThings=function(self) return self.things end,
    getThing=function(self,index) return self.things[index+1] end}
  nativeTiles[key(pos)] = result; return result
end
local function step(ms)
  local target=now+ms
  while true do
    local nextEvent
    for _,e in ipairs(events) do
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
  getProtocolGame=function() return protocol end}
g_map={getTile=function(pos) return nativeTiles[key(pos)] end,
  colorizeThing=function(item,color) item.color=color end, removeThingColor=function(item) item.color='' end}
g_settings={getBoolean=function() return true end}
GameExtendedOpcode=1
local callback
ProtocolGame={registerExtendedOpcode=function(opcode, fn, raw)
  check(opcode==129 and raw, 'Dedicated raw opcode'); callback=fn
end,unregisterExtendedOpcode=function() callback=nil end}
local corpse
modules={game_interface={getMapPanel=function() return map end},game_loot={restoreMark=function(value)
  if value==corpse then value:setMarked('corpse glow'); return true end
end}}
dofile('../../Cliente/modules/corelib/networkdata.lua')
dofile('../../Cliente/modules/game_groundrarity/groundrarity.lua')
init(); step(250)
check(requests[1][1]==129 and requests[1][2]=='H|1', 'Versioned handshake')
local seq=0
local function receive(data)
  if data.event=='ready' or data.event=='reset' then seq=seq+1; data.seq=seq end
  callback(protocol,129,json.encode(data))
end
local function snapshot(pos, records)
  seq=seq+1; return {event='tile',position=pos,seq=seq,items=records}
end
local function record(stack,tier,id) return {itemId=id or 2376,stackpos=stack,tier=tier} end
local pos={x=100,y=100,z=7}
local rare,common=item(2376,pos),item(2376,pos)
local native=tile(pos,{rare,common})
receive(snapshot(pos,{record(0,1)}))
check(rare.color==nil, 'No unauthenticated pre-ready mark')
receive({event='ready',version=1})
local colors={'#42C96B','#3E8BFF','#A855F7','#F5C542','#EF4444'}
local pulseColors={'#4ACF72','#4B93FF','#AE63F9','#F7CD4B','#F04E4E'}
local function hasTierTint(target,tier)
  local bright=upvalue(updateMarks,'pulseBright')
  return target.color==(bright and pulseColors[tier] or colors[tier])
end
for tier=1,5 do
  receive(snapshot(pos,{record(0,tier)}))
  check(rare.color==colors[tier], 'Exact sprite rarity color '..tier)
  check(common.color==nil, 'Same-sprite common item is unchanged '..tier)
end
step(500)
check(rare.color==colors[5], 'Ground tint is steady')
native.things={common,rare}; step(1000)
check(rare.color=='#F04E4E', 'Ground rarity tint receives a subtle shared pulse')
step(1500)
check(rare.color==colors[5], 'Ground rarity pulse returns to the original rarity color')
step(500)
check(restoreMark(rare) and not restoreMark(common), 'Native identity survives shifted stack')
receive(snapshot(pos,{record(1,3)}))
check(hasTierTint(rare,3) and common.color==nil, 'Server stack refresh retains correct item')
map.markedThing=rare; rare:setMarked('yellow'); step(500)
check(rare.mark=='yellow' and hasTierTint(rare,3), 'Cursor mark and sprite tint coexist independently')
map.markedThing=nil; rare:setMarked('')
check(restoreMark(rare) and hasTierTint(rare,3), 'Hover departure restores tier tint')
local stale=snapshot(pos,{record(0,1)}); seq=seq+1
receive({event='tile',position=pos,seq=seq,items={record(1,5)}}); receive(stale)
check(hasTierTint(rare,5) and common.color==nil, 'Older sequence cannot recolor replacement')
native.things={common}; rare.position={x=65535,y=1,z=0}; step(500)
check(rare.color=='' and common.color==nil and not restoreMark(common), 'Pickup clears old object without tinting common duplicate')
rare.position=pos; native.things={rare,common}
receive(snapshot(pos,{record(0,2)}))
local replacement=item(2376,pos); native.things={replacement,common}; step(500)
check(rare.color=='' and replacement.color==nil, 'Recreated same-ID object cannot inherit old metadata')
receive(snapshot(pos,{record(0,4)}))
check(hasTierTint(replacement,4), 'Fresh ordered snapshot binds replacement')
receive(snapshot(pos,{}))
check(replacement.color=='', 'Empty authoritative snapshot clears tile')
native.things={}
receive(snapshot(pos,{record(0,1)})); native.things={replacement}; step(500)
check(not restoreMark(replacement), 'No deferred binding against stale stack reference')
receive(snapshot(pos,{record(0,1)}))
check(restoreMark(replacement), 'Server replay safely recovers missing native item')
nativeTiles[key(pos)]=nil; step(500)
check(replacement.color=='', 'Viewport tile removal clears retained object')

-- Walking map strips recreate Item objects even if the server item and its
-- rarity are unchanged. Re-entry must use the new authoritative snapshot in
-- the same turn, including a quick return before the 500 ms cleanup runs.
for _, cleanedBeforeReturn in ipairs({false, true}) do
  for tier=1,5 do
    local p={x=200+tier,y=cleanedBeforeReturn and 202 or 201,z=7}
    local departed=item(3264,p)
    tile(p,{departed})
    local previousSnapshot=snapshot(p,{record(0,tier,3264)})
    receive(previousSnapshot)
    nativeTiles[key(p)]=nil
    if cleanedBeforeReturn then step(500) end
    local returnedCommon,returnedRare=item(3264,p),item(3264,p)
    tile(p,{returnedCommon,returnedRare})
    local instant=now
    receive(snapshot(p,{record(1,tier,3264)}))
    check(now==instant and hasTierTint(returnedRare,tier),
      'Re-entered rare native item colors immediately, tier '..tier..', cleaned '..tostring(cleanedBeforeReturn))
    check(departed.color=='' and returnedCommon.color==nil,
      'Re-entry clears the departed instance and preserves common duplicate, tier '..tier)
    receive(previousSnapshot)
    check(returnedCommon.color==nil and hasTierTint(returnedRare,tier),
      'Old strip snapshot cannot transfer rarity to a common duplicate, tier '..tier)
    local secondReturn=item(3264,p)
    nativeTiles[key(p)]=nil
    tile(p,{secondReturn})
    receive(snapshot(p,{}))
    check(now==instant and returnedRare.color=='' and secondReturn.color==nil,
      'A common-only return clears old rarity immediately, tier '..tier)
  end
end

-- The corner of a diagonal move can occur in two serialized map strips.
-- Each fresh snapshot must color only the last native object at that corner.
local corner={x=212,y=212,z=7}
local cornerFirst=item(3264,corner)
tile(corner,{cornerFirst}); receive(snapshot(corner,{record(0,4,3264)}))
local cornerFinal,cornerCommon=item(3264,corner),item(3264,corner)
tile(corner,{cornerCommon,cornerFinal})
receive(snapshot(corner,{record(1,4,3264)}))
check(cornerFirst.color=='' and hasTierTint(cornerFinal,4) and cornerCommon.color==nil,
  'Diagonal corner reconstruction replaces its tint synchronously')
step(500)
check(hasTierTint(cornerFinal,4) and cornerCommon.color==nil,
  'Previous cleanup timer preserves the final diagonal corner binding')
local oldFloorSnapshot=snapshot(corner,{record(0,2,3264)})
receive({event='reset'})
receive(oldFloorSnapshot)
check(cornerFinal.color=='' and cornerCommon.color==nil,
  'A frame from the previous floor cannot survive a sequenced reset')
local newFloor={x=212,y=212,z=8}
local newFloorRare=item(3264,newFloor)
tile(newFloor,{newFloorRare}); receive(snapshot(newFloor,{record(0,2,3264)}))
check(hasTierTint(newFloorRare,2), 'New-floor native item colors immediately after map reset')

native=tile(pos,{replacement,common})
receive(snapshot(pos,{record(0,3)}))
for _,change in ipairs({
  function(d) d.seq=0 end,function(d) d.seq=1.5 end,function(d) d.seq=9007199254740992 end,
  function(d) d.position.x=65535 end,function(d) d.items[1].tier=0 end,
  function(d) d.items[1].tier=6 end,function(d) d.items[1].stackpos=10 end,
  function(d) d.items[1].itemId=0 end,function(d) d.items[2]=record(0,2) end,
  function(d) d.items={bad=record(1,2)} end,
  function(d) for i=1,11 do d.items[i]=record(i-1,2) end end
}) do
  local data=snapshot({x=100,y=100,z=7},{record(0,1)}); change(data); receive(data)
end
callback(protocol,129,string.rep(' ',4097))
callback(protocol,129,string.rep('[',20)..string.rep(']',20))
callback({},129,json.encode(snapshot(pos,{record(0,1)})))
check(hasTierTint(replacement,3), 'Invalid, excessive and foreign-connection packets ignored')
receive({event='reset'})
check(replacement.color=='' and not restoreMark(replacement), 'Map reset clears old viewport colors')
receive(snapshot(pos,{record(0,2)}))
check(restoreMark(replacement), 'Map reset preserves negotiation')

receive({event='reset'})
for n=1,270 do
  local p={x=1000+n,y=100,z=7}; local items,records={},{}
  for i=1,10 do items[i]=item(2376,p); records[i]=record(i-1,(i%5)+1) end
  tile(p,items); receive(snapshot(p,records))
end
local count,total=0,0
for _,entry in pairs(upvalue(updateMarks,'tiles')) do count=count+1; total=total+#entry.items end
check(count==256 and total==2560, 'Bounded tile and mark counts')
local pending=0; for _,e in ipairs(events) do if not e.done then pending=pending+1 end end
check(pending==1, 'One timer serves entire viewport')
receive({event='reset'})
corpse=item(3058,pos); corpse:setMarked('corpse glow'); native=tile(pos,{corpse})
receive(snapshot(pos,{record(0,2,3058)})); receive(snapshot(pos,{}))
check(corpse.mark=='corpse glow' and corpse.color=='', 'Removing tint preserves existing corpse glow')
corpse=nil
native.things={replacement}; receive(snapshot(pos,{record(0,5)}))
online=false; reset()
check(replacement.color=='' and not restoreMark(replacement), 'Logout clears native tint')
pending=0; for _,e in ipairs(events) do if not e.done then pending=pending+1 end end
check(pending==0, 'Logout cancels every timer')
online=true; _G.online(); step(250); seq=0
receive({event='ready',version=1})
receive(snapshot(pos,{record(0,1)}))
check(restoreMark(replacement), 'Reconnect negotiates afresh and restarts sequence safely')
terminate()
check(callback==nil, 'Unload unregisters callback')
print('ground-rarity-ui-tests: '..checks..' assertions passed')
