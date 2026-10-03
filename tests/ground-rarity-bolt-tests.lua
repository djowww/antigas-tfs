-- Exercise the real controller with native-shaped userdata identities.
-- Missing ownership checks, reused sprite ids, and uncapped bursts must fail.
local checks, now, sequence, packet = 0, 0, 0
local function check(ok, why) assert(ok, why); checks = checks + 1 end
local states, nativeTiles, events, widgets = {}, {}, {}, {}
local function key(pos) return pos.x .. ',' .. pos.y .. ',' .. pos.z end
local function native(state, methods)
  local value = newproxy(true)
  states[value] = state
  getmetatable(value).__index = methods
  return value
end
local widgetMethods = {
  isDestroyed=function(self) return states[self].destroyed end,
  destroy=function(self)
    assert(not states[self].destroyed, 'No second call on destroyed native widget')
    states[self].destroyed = true
  end
}
local function widget()
  local result = native({opacity=0}, widgetMethods)
  widgets[#widgets+1] = result
  return result
end
local itemMethods = {
  isItem=function() return true end,
  getId=function(self) return states[self].id end,
  getPosition=function(self) return states[self].position end,
  isLyingCorpse=function(self) return states[self].corpse or false end
}
local tileMethods = {
  getThings=function(self) return states[self].items end,
  getThing=function(self, stack) return states[self].items[stack+1] end,
  getWidget=function(self) return states[self].widget end,
  setWidget=function(self, value) states[self].widget = value end,
  removeWidget=function(self)
    local state = states[self]
    if state.widget then state.widget:destroy(); state.widget=nil end
  end
}
local function put(x, options)
  local position = {x=x,y=100,z=7}
  local item = native({id=options and options.id or 3264,position=position,corpse=options and options.corpse}, itemMethods)
  local tile = native({items={item}}, tileMethods)
  nativeTiles[key(position)] = tile
  return position, item, tile
end
local protocol = {sendExtendedOpcode=function() end}
g_game={isOnline=function() return true end, getProtocolGame=function() return protocol end,
  getFeature=function() return true end}
g_clock={millis=function() return now end}
g_map={getTile=function(pos) return nativeTiles[key(pos)] end,
  colorizeThing=function(item, color) states[item].color=color end,
  removeThingColor=function(item) states[item].color=nil end}
GameExtendedOpcode=1
function scheduleEvent(callback, delay)
  local result = {callback=callback, delay=delay}; events[#events+1]=result; return result
end
function removeEvent(event) event.removed=true end
function connect() end
function disconnect() end
local callback
ProtocolGame={registerExtendedOpcode=function(_, fn) callback=fn end,
  unregisterExtendedOpcode=function() callback=nil end}
NetworkData={decode=function() return true, packet end}
modules={game_rarityvisuals={createGroundBolt=widget,
  paintGroundBolt=function(value, tier, time, seed, opacity)
    assert(not value:isDestroyed(), 'Painting never uses destroyed userdata')
    local state=states[value]; state.opacity=opacity; state.tier=tier; state.seed=seed
  end}}
dofile('deploy/client-current/modules/game_groundrarity/groundrarity.lua')
init()
local function receive(data)
  sequence=sequence+1; data.seq=sequence; packet=data; callback(protocol,129,'packet')
end
receive({event='ready',version=1})
local function snapshot(pos, records) receive({event='tile',position=pos,items=records}) end
local function rare(pos, tier) snapshot(pos, {{itemId=3264,stackpos=0,tier=tier or 3}}) end
local function owned()
  local count, active, attached = 0, 0, {}
  for _, tile in pairs(nativeTiles) do
    local value=tile:getWidget()
    if value and states[value].seed then
      count=count+1; attached[value]=true
      if states[value].opacity>0 then active=active+1 end
    end
  end
  return count, active, attached
end
local pos, item, tile=put(100)
rare(pos); updateMarks()
check(tile:getWidget()~=nil, 'A valid native rare item receives an owned bolt')
local first=tile:getWidget()
check(states[first].tier==3, 'Bolt receives the item rarity tier')
now=100; updateMarks()
check(tile:getWidget()==first, 'Controller reuses its existing tile decoration')

local common=native({id=3264,position=pos}, itemMethods)
states[tile].items={common}; updateMarks()
check(first:isDestroyed() and tile:getWidget()==nil, 'Same-sprite replacement clears stale item decoration')
check(states[common].color==nil, 'A common replacement does not inherit sprite rarity')

local foreign=widget(); states[tile].widget=foreign; rare(pos); updateMarks()
check(tile:getWidget()==foreign and not foreign:isDestroyed(), 'Foreign widget ownership is respected')
snapshot(pos,{})
check(tile:getWidget()==foreign, 'Empty snapshot never removes foreign widget')
states[tile].widget=nil; rare(pos); updateMarks()
local own=tile:getWidget()
states[tile].widget=foreign; updateMarks()
check(own:isDestroyed() and not foreign:isDestroyed(), 'Foreign replacement releases only the orphan owned decoration')
states[tile].widget=nil; updateMarks()
own=tile:getWidget()
tile:removeWidget(); updateMarks()
check(own:isDestroyed() and tile:getWidget()~=own, 'Native tile clean handles an already destroyed widget')
own=tile:getWidget()
own:destroy(); updateMarks()
check(own:isDestroyed() and tile:getWidget()~=own, 'Externally destroyed decoration releases the tile slot without double destruction')
own=tile:getWidget()
local replacementTile=native({items={common}}, tileMethods)
nativeTiles[key(pos)]=replacementTile; updateMarks()
check(own:isDestroyed() and tile:getWidget()==nil, 'Tile replacement detaches its old tile owner')
check(replacementTile:getWidget()~=nil, 'Same tracked native item can attach to its current tile')

receive({event='reset'})
check(replacementTile:getWidget()==nil, 'Map reset releases every owned decoration')
local stackPos, topRare, stackTile=put(102)
local bottomRare=native({id=3264,position=stackPos}, itemMethods)
states[stackTile].items={topRare,bottomRare}
snapshot(stackPos,{{itemId=3264,stackpos=1,tier=5},{itemId=3264,stackpos=0,tier=2}})
updateMarks()
check(states[stackTile:getWidget()].tier==2, 'Native top-to-bottom order chooses the upper rare item tier')
local topBolt=stackTile:getWidget()
states[stackTile].items={bottomRare}; updateMarks()
check(topBolt:isDestroyed() and states[stackTile:getWidget()].tier==5, 'Picking up the top item transfers the bolt to the remaining rare item')
receive({event='reset'})
local corpsePos,_,corpseTile=put(101,{corpse=true})
rare(corpsePos); updateMarks()
check(corpseTile:getWidget()==nil, 'Corpse marks do not add the item lightning decoration')
receive({event='reset'})
nativeTiles={}
local seen={}
for index=1,40 do
  local densePos, denseItem=put(1000+index)
  rare(densePos, (index%5)+1); seen[denseItem]=false
end
local maxOwned, maxActive, positive, dark=0,0,false,false
for time=0,4200*8,150 do
  now=time; updateMarks()
  local count,active=owned()
  maxOwned=math.max(maxOwned,count); maxActive=math.max(maxActive,active)
  check(count<=24 and active<=6, 'Dense viewport respects owned/visible decoration caps')
  for _,denseTile in pairs(nativeTiles) do
    local value=denseTile:getWidget()
    if value then
      if states[value].opacity>0 then positive=true; seen[states[denseTile].items[1]]=true
      else dark=true end
    end
  end
end
check(maxOwned>0 and maxActive>0 and positive and dark, 'Lightning has both a visible burst and a quiet interval')
for _,shown in pairs(seen) do check(shown, 'Deterministic rotation reaches every dense rare item') end
receive({event='reset'})
nativeTiles={}; seen={}
-- x increases by 7 and id falls by 31: 31*x + 7*id stays constant.
-- These native items deliberately share a seed, stressing burst fairness.
for index=1,24 do
  local alignedId=3264-index*31
  local alignedPos,alignedItem=put(2000+index*7,{id=alignedId})
  snapshot(alignedPos,{{itemId=alignedId,stackpos=0,tier=3}})
  seen[alignedItem]=false
end
for time=0,4200*8,150 do
  now=time; updateMarks()
  local count,active=owned()
  check(count<=24 and active<=6, 'Synchronized burst still respects decoration caps')
  for _,alignedTile in pairs(nativeTiles) do
    local value=alignedTile:getWidget()
    if value and states[value].opacity>0 then seen[states[alignedTile].items[1]]=true end
  end
end
for _,shown in pairs(seen) do check(shown, 'Every synchronized rare item eventually receives a burst') end
local pending=0
for _,event in ipairs(events) do if not event.removed then pending=pending+1 end end
check(pending==1, 'Existing controller timer serves all ground decorations')
reset()
local count=owned(); check(count==0, 'Logout reset detaches all owned ground widgets')
pending=0
for _,event in ipairs(events) do if not event.removed then pending=pending+1 end end
check(pending==0, 'Reset cancels controller and handshake timers')
terminate()
check(callback==nil, 'Terminate unregisters opcode ownership')
print('ground-rarity-bolt-tests: '..checks..' assertions passed')
