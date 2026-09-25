local count = 0
local function check(value, label)
  assert(value, label)
  count = count + 1
  print('LOOT_V17_PASS ' .. label)
end
local ok, err = pcall(function()
  g_game.setClientVersion(772)
  modules.client_release.terminate()
  local online = true
  g_game.isOnline = function() return online end
  local loot = modules.game_lootstatistics
  local root = g_ui.getRootWidget()
  local w = root:recursiveGetChildById('lootStatisticsWindow')
  loot.reset()
  local originalUnserialize = unserialize
  local calls = 0
  unserialize = function(raw) calls = calls + 1; return originalUnserialize(raw) end
  -- Dispatch wire strings exactly as the native protocol does. Direct calls to
  -- onLoot bypassed this boundary in v16 and missed the regression.
  local function packet(opcode, raw) ProtocolGame.onExtendedOpcode({}, opcode, raw) end
  packet(122, '{"gold coin",12,3031}')
  packet(122, '{"gold coin",8,3031}')
  check(not w:isVisible(), 'hidden receipt does not open the window')
  loot.toggle()
  check(w:isVisible(), 'Loot button opens the window')
  check(w.lootList:getChildCount() == 1, 'hidden pickups merge into one row')
  check(w.lootList:getFirstChild().description:getText() == '20 x gold coin', 'dispatcher accumulates 12 + 8 gold')
  packet(122, '{"gold coin",3,3031}')
  check(w.lootList:getFirstChild().description:getText() == '23 x gold coin', 'visible pickup updates immediately')
  packet(123, '{"mana fluid",2,5125}')
  check(w.supplyList:getFirstChild().description:getText() == '2 x mana fluid', 'supply uses same raw dispatch path')
  check(calls == 0, 'loot and supply never call Lua unserialize')
  packet(122, '{[1] = "gold coin", [2] = 4, [3] = 3031}')
  check(w.lootList:getFirstChild().description:getText()=='27 x gold coin','live serializer explicit keys accepted')
  for _,raw in ipairs({
    '{"bad",-1,3031}', '{"bad",0,3031}', '{"bad",1.5,3031}',
    '{"bad",2000000001,3031}', '{"bad",1,99999}', '{"bad",1,0}',
    '{"bad",1,3031}; LOOT_CODE_EXECUTED = true',
    '{[1]="bad",[2]=1,[3]=3031}; LOOT_CODE_EXECUTED = true',
    '{[1]="bad",[2]=1,[4]=3031}', '{[1]="bad",[2]=1,[3]=3031,[4]=5}',
    '{[1]="bad",[2]=1,[3]=3031+1}', '{[1]="bad",[2]=0,[3]=3031}',
    '(function() LOOT_CODE_EXECUTED = true; return {"bad",1,3031} end)()',
    '{"' .. string.rep('a',81) .. '",1,3031}', string.rep('x',513)
  }) do packet(122,raw) end
  check(w.lootList:getChildCount()==1 and w.lootList:getFirstChild().description:getText()=='27 x gold coin','malformed/oversized entries do not change counters')
  check(calls==0 and not LOOT_CODE_EXECUTED,'code-like payload is never evaluated')
  loot.hide()
  check(not w:isVisible() and not modules.game_playerbars.lootButton:isChecked(), 'hide does not reopen through checkbox callback')
  loot.toggle()
  loot.reset()
  check(w.lootList:getChildCount()==0 and w.supplyList:getChildCount()==0,'Reset clears both lists')
  packet(122,'{"unknown sprite",1,65535}')
  check(w.lootList:getChildCount()==1 and not w.lootList:getFirstChild().icon:isVisible(),'unknown sprite keeps text without renderer error')
  loot.offline()
  check(not w:isVisible() and w.lootList:getChildCount()==0,'logout clears and closes the session')
  online=false;loot.toggle()
  check(not w:isVisible(),'cannot open Loot offline')
  online=true
  local legacy
  ProtocolGame.registerExtendedOpcode(240,function(p,op,a,b) legacy={a,b} end)
  packet(240,'{["@"]= {7,9}}')
  check(legacy[1]==7 and legacy[2]==9,'legacy callback argument unpacking preserved')
  ProtocolGame.unregisterExtendedOpcode(240)
  local rawValue, jsonValue
  ProtocolGame.registerExtendedOpcode(240,function(p,op,v) rawValue=v end,true)
  ProtocolGame.registerExtendedJSONOpcode(240,function(p,op,v) jsonValue=v end)
  packet(240,'{"count":4}')
  check(rawValue=='{"count":4}' and jsonValue.count==4,'raw and JSON consumers receive original wire data')
  ProtocolGame.unregisterExtendedOpcode(240)
  ProtocolGame.unregisterExtendedJSONOpcode(240)
  ProtocolGame.registerExtendedOpcode(240,function(p,op,v) legacy=v end)
  packet(240,'{5,6}')
  check(type(legacy)=='table' and legacy[1]==5,'unregister removes raw mode before opcode reuse')
  ProtocolGame.unregisterExtendedOpcode(240)
  local before=calls
  loot.terminate();loot.init();loot.toggle()
  w=root:recursiveGetChildById('lootStatisticsWindow')
  packet(122,'{"gold coin",1,3031}')
  check(w.lootList:getChildCount()==1 and calls==before,'module reload retains raw mode without duplicate registration')
  loot.reset()
  packet(122,'{"gold coin",2000000000,3031}');packet(122,'{"gold coin",1,3031}')
  check(w.lootList:getFirstChild().description:getText()=='2000000000 x gold coin','aggregate count capped')
  loot.hide();loot.reset()
  for id=40000,40255 do packet(122,'{"test",1,'..id..'}') end
  loot.toggle()
  check(w.lootList:getChildCount()==250,'unique rows capped at 250')
  loot.offline()
  unserialize=originalUnserialize
  -- If present, replay captured packets from actual corpse pickups and supply
  -- use in the isolated server, through this same client dispatcher/UI.
  if g_resources.fileExists('/wire-results.json') then
    local captured=json.decode(g_resources.readFileContents('/wire-results.json'))
    loot.toggle()
    for _,v in ipairs(captured.wire) do packet(v.opcode,v.buffer) end
    check(w.lootList:getChildCount()==1 and w.lootList:getFirstChild().description:getText()=='20 x gold coin','real server pickup packets render exact UI total')
    check(w.supplyList:getChildCount()>0,'real server use packet renders supply UI')
    loot.offline()
  end
  print('LOOT_V17_CLIENT_PASS checks='..count)
end)
if not ok then print('LOOT_V17_CLIENT_FAIL '..tostring(err)) end
g_game.isOnline=function() return false end
if ok then scheduleEvent(function() dofile('/market-ui-tests.lua') end,200)
else scheduleEvent(function() g_app.exit() end,500) end
