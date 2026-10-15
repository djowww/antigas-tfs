-- Run from the TFS root with Lua 5.2 or LuaJIT. No database/server is used.
local manifest = assert(io.open('data/items/retired-items.json', 'rb'))
local retired = {}
for id in manifest:read('*a'):gmatch('"id"%s*:%s*(%d+)') do retired[tonumber(id)] = true end
manifest:close()
local known = {[3031]='gold coin',[3035]='platinum coin',[3043]='crystal coin',
 [3157]='cranial basher',[3270]='club',[3460]='shovel',[3549]='boots',
 [3725]='brown mushroom',[5130]='Antigas Coin'}
ItemType = function(id)
 local item = {id=id}
 function item:isRetired() return retired[self.id] == true end
 function item:getId() return self.id end
 function item:getName() return known[self.id] or (retired[self.id] and 'retired item '..self.id or '') end
 function item:isMovable() return true end
 function item:isStackable() return self.id==3031 or self.id==3035 or self.id==3043 or self.id==3725 or self.id==5130 end
 function item:getCharges() return 0 end
 function item:getWeaponType() return 0 end
 function item:getSlotPosition() return 0 end
 function item:getArmor() return 0 end
 for _,method in ipairs({'isContainer','isDoor','isMagicField','isSplash','isFluidContainer','isRune','isCorpse','isReadable','isWritable'}) do item[method]=function() return false end end
 return item
end
local function upvalue(fn, name)
 for index=1,100 do local key,value=debug.getupvalue(fn,index);if key==name then return value end;if not key then break end end
 error('missing upvalue '..name)
end
local function replaceUpvalue(fn, name, value)
 for index=1,100 do local key=debug.getupvalue(fn,index);if key==name then debug.setupvalue(fn,index,value);return end;if not key then break end end
 error('missing upvalue '..name)
end
local function check(name, fn)
 local ok,err=pcall(fn)
 if not ok then error(name..': '..tostring(err)) end
 print('PASS: '..name)
end
dofile('data/lib/core/json.lua')
local requests,storage={},{}
local player={getAccountId=function() return 1 end,getGuid=function() return 1 end,
 getStorageValue=function(_,k) return storage[k] or -1 end,setStorageValue=function(_,k,v) storage[k]=v end}
check('shop catalogs omit retired offers and empty categories; original offers remain',function()
 dofile('data/creaturescripts/scripts/shop.lua')
 sendJSON=function(_,action,data) requests[action]=data end
 sendMessage=function(_,_,text) requests.message=text end
 init()
 assert(onExtendedOpcode(player,201,json.encode({action='init',data={}})))
 local categories=requests.categories
 assert(#categories==3,'Premium Points, Regeneration Items and Utilities must have offers')
 local found={}
 local premium
 for _,cat in ipairs(categories) do
  assert(#cat.offers>0,'empty category must not be advertised')
  assert(not ItemType(cat.item):isRetired(),'category icon must be an existing classic item')
  if cat.name=='Premium Points' then premium=cat end
  for _,offer in ipairs(cat.offers) do assert(not retired[offer.itemId],'retired shop offer leaked');found[offer.itemId]=offer end
 end
 assert(not retired[5130] and retired[5128],'only the Antigas Coin may leave the retirement catalog')
 assert(premium and premium.item==5130,'Premium Points category must use the active Coin icon')
 assert(found[5130] and found[5130].cost==2,'Antigas Coin Store offer must remain at 2 Shop points')
 assert(not found[5128],'retired Antigas Ticket offer must stay hidden')
 assert(found[3549] and found[3549].cost==50,'existing original boots offer/cost must stay')
 assert(found[3725] and found[3725].count==100 and found[3725].cost==5,'existing original mushroom offer/count/cost must stay')
end)
check('shop direct retired purchase never reads or debits points',function()
 local categories=requests.categories
 categories[1].offers[1].itemId=3157 -- simulate an old cached offer.
 getPoints=function() error('retired purchases must reject before reading/debiting funds') end
 processBuy(player,{category=1,offer=1,title=categories[1].offers[1].title,cost=categories[1].offers[1].cost})
 assert(requests.message and requests.message:lower():find('unavailable',1,true))
end)
WEAPON_SHIELD,WEAPON_AMMO,WEAPON_WAND=4,7,6
SLOTP_HEAD,SLOTP_LEGS,SLOTP_FEET,SLOTP_NECKLACE,SLOTP_RING,SLOTP_ARMOR=1,2,4,8,16,32
check('market filters retired types and rejects direct buy/sell requests',function()
 dofile('data/creaturescripts/scripts/market.lua')
 local mutate=upvalue(onExtendedOpcode,'mutate')
 local actions=upvalue(mutate,'actions')
 local marketType=upvalue(actions.create,'marketType')
 assert(marketType(3157)==nil,'retired type must not enter catalog even with valid equipment metadata')
 for id in pairs(retired) do assert(marketType(id)==nil,'retired manifest type leaked into market: '..id) end
 assert(marketType(3270) and marketType(3270).id==3270,'ordinary classic item must remain available')
 assert(marketType(5130)==nil,'Antigas Coin must remain a currency, not a tradable product item')
 db={storeQuery=function() error('rejected item must not query or mutate the economy') end,query=function() error('must not mutate') end}
 local ctx={player=player,fail=function(self,text) self.error=text;return false end,pay=function() error('must not debit') end,takeItems=function() error('must not remove items') end}
 for _,side in ipairs({'buy','sell'}) do assert(actions.create(ctx,{side=side,itemId=3157,subtype=-1,amount=1,price=1,currency=3031})==false) end
end)
check('market creates and fills Coin offers while preserving Gold currency behavior',function()
 local actions=upvalue(upvalue(onExtendedOpcode,'mutate'),'actions')
 local createQueries,paid={},{}
 local oldRows=upvalue(actions.create,'rows')
 local oldGetOffer,oldChanged,oldClaim,oldHistory=upvalue(actions.fill,'getOffer'),upvalue(actions.fill,'changed'),
  upvalue(actions.fill,'claim'),upvalue(actions.fill,'history')
 replaceUpvalue(actions.create,'rows',function(sql)
  createQueries[#createQueries+1]=sql
  return {{n=0}}
 end)
 db={query=function(sql) createQueries[#createQueries+1]=sql;return true end,
  escapeString=function(s) return "'"..s.."'" end}
 local ctx={player=player,fail=function(self,text) self.error=text;return false end,
  pay=function(_,currency,amount) paid[#paid+1]={currency=currency,amount=amount};return true end,
  takeItems=function() return true end}
 for _,currency in ipairs({5130,3031}) do
  assert(actions.create(ctx,{side='buy',itemId=3270,subtype=-1,amount=2,price=3,currency=currency}),
   'valid currency-denominated offers must be created')
 end
 assert(paid[1].currency==5130 and paid[1].amount==6,'Coin balance must pay Coin offers')
 assert(paid[2].currency==3031 and paid[2].amount==6,'Gold balance must keep its existing payment path')
 assert(createQueries[2]:find(',5130,1)',1,true),'Coin currency must be stored on the Market offer')
 assert(createQueries[4]:find(',3031,1)',1,true),'Gold currency must remain stored on the Market offer')
 local offer={id=71,owner=2,side=0,itemId=3270,subtype=-1,amount=2,price=3,currency=5130}
 local claims,paidDuringFill={},{}
 replaceUpvalue(actions.fill,'getOffer',function() return offer end)
 replaceUpvalue(actions.fill,'changed',function() return true end)
 replaceUpvalue(actions.fill,'claim',function(guid,kind,id,subtype,count,currency,amount)
  claims[#claims+1]={guid=guid,kind=kind,id=id,subtype=subtype,count=count,currency=currency,amount=amount}
  return #claims
 end)
 replaceUpvalue(actions.fill,'history',function() return true end)
 ctx.pay=function(_,currency,amount) paidDuringFill[#paidDuringFill+1]={currency=currency,amount=amount};return true end
 assert(actions.fill(ctx,{offerId=71,amount=2}),'valid Coin-denominated offer must fill')
 assert(paidDuringFill[1].currency==5130 and paidDuringFill[1].amount==6,'filling a Coin offer must charge Coins')
 assert(claims[2].kind==1 and claims[2].currency==5130 and claims[2].amount==6,
  'seller must receive the Coin claim without changing a player balance directly')
 offer.currency=3031
 claims={}
 assert(actions.fill(ctx,{offerId=71,amount=2}),'Gold-denominated offer must still fill')
 assert(paidDuringFill[2].currency==3031 and paidDuringFill[2].amount==6,'Gold fills must retain the existing path')
 assert(claims[2].kind==1 and claims[2].currency==3031 and claims[2].amount==6,'Gold claim behavior must remain unchanged')
 replaceUpvalue(actions.fill,'getOffer',oldGetOffer);replaceUpvalue(actions.fill,'changed',oldChanged)
 replaceUpvalue(actions.fill,'claim',oldClaim);replaceUpvalue(actions.fill,'history',oldHistory)
 replaceUpvalue(actions.create,'rows',oldRows)
end)
check('market cancels a Coin buy offer into one reserved Coin claim',function()
 local actions=upvalue(upvalue(onExtendedOpcode,'mutate'),'actions')
 local offer={id=72,owner=1,side=1,itemId=3270,subtype=-1,amount=4,price=3,currency=5130}
 local changedSql,claimArgs
 local oldGetOffer,oldChanged,oldClaim,oldHistory=upvalue(actions.cancel,'getOffer'),upvalue(actions.cancel,'changed'),
  upvalue(actions.cancel,'claim'),upvalue(actions.cancel,'history')
 replaceUpvalue(actions.cancel,'getOffer',function() return offer end)
 replaceUpvalue(actions.cancel,'changed',function(sql) changedSql=sql;return true end)
 replaceUpvalue(actions.cancel,'claim',function(...) claimArgs={...};return 81 end)
 replaceUpvalue(actions.cancel,'history',function() return true end)
 local ctx={player=player,fail=function(_,text) error(text) end}
 assert(actions.cancel(ctx,{offerId=72}),'active Coin offer must cancel')
 assert(changedSql:find('UPDATE market_offers SET status=2',1,true),'cancellation must close the original offer')
 assert(claimArgs[1]==1 and claimArgs[2]==1 and claimArgs[5]==0 and claimArgs[6]==5130 and claimArgs[7]==12,
  'cancellation must reserve the full remaining Coin amount for its owner')
 replaceUpvalue(actions.cancel,'getOffer',oldGetOffer);replaceUpvalue(actions.cancel,'changed',oldChanged)
 replaceUpvalue(actions.cancel,'claim',oldClaim);replaceUpvalue(actions.cancel,'history',oldHistory)
end)
check('market public and own listings filter retired item and currency IDs',function()
 local sendOffers=upvalue(onExtendedOpcode,'sendOffers')
 local sqls={}
 db={storeQuery=function(sql) sqls[#sqls+1]=sql;return false end,escapeString=function(s) return "'"..s.."'" end}
 player.sendExtendedOpcode=function(_,_,payload) requests.market=json.decode(payload) end
 for _,mine in ipairs({false,true}) do
  sendOffers(player,{},mine)
  local sql=sqls[#sqls]
  assert(sql:find('o.item_id NOT IN',1,true),'all listings must exclude retired IDs')
  assert(sql:find('o.currency_id NOT IN',1,true),'retired currencies must be excluded')
  assert(requests.market.data.offers and #requests.market.data.offers==0)
 end
end)
check('market fills reject stale retired goods and currency before payment',function()
 local actions=upvalue(upvalue(onExtendedOpcode,'mutate'),'actions')
 local offer={id=1,owner=2,side=0,itemId=3157,subtype=-1,amount=1,price=1,currency=3031}
 replaceUpvalue(actions.fill,'getOffer',function() return offer end)
 local ctx={player=player,fail=function() return false end,pay=function() error('retired offer must not debit') end,takeItems=function() error('must not remove inventory') end}
 assert(actions.fill(ctx,{offerId=1,amount=1})==false)
 offer.itemId,offer.currency=3270,5128
 assert(actions.fill(ctx,{offerId=1,amount=1})==false)
 assert(actions.create(ctx,{side='buy',itemId=3270,subtype=-1,amount=1,price=1,currency=5128})==false)
end)
check('market collect skips retired claims and still delivers classic claims',function()
 local actions=upvalue(upvalue(onExtendedOpcode,'mutate'),'actions')
 replaceUpvalue(actions.collect,'rows',function() return {{id=1,kind=0,itemId=3157,subtype=-1,itemCount=1,currency=0,currencyAmount=0},
  {id=2,kind=0,itemId=3270,subtype=-1,itemCount=1,currency=0,currencyAmount=0}} end)
 replaceUpvalue(actions.collect,'changed',function(sql) assert(sql:find('id=2',1,true),'retired claim must remain for canonical migration');return true end)
 local ctx={player=player,fail=function(_,text) error(text) end,deliver=function(_,id,_,count) assert(id==3270,'retired claim must not be recreated');return count end}
 assert(actions.collect(ctx))
end)
check('market keeps a Coin claim reserved when the depot is full, then collects it',function()
 local actions=upvalue(upvalue(onExtendedOpcode,'mutate'),'actions')
 local pending={{id=91,kind=1,itemId=0,subtype=-1,itemCount=0,currency=5130,currencyAmount=25}}
 local changes,delivered={},{}
 local oldRows,oldChanged=upvalue(actions.collect,'rows'),upvalue(actions.collect,'changed')
 replaceUpvalue(actions.collect,'rows',function() return pending end)
 replaceUpvalue(actions.collect,'changed',function(sql) changes[#changes+1]=sql;return true end)
 local ctx={player=player,fail=function(_,text) return false end,
  deliver=function(_,id,subtype,count) delivered[#delivered+1]={id=id,subtype=subtype,count=count};return 0 end}
 assert(actions.collect(ctx)==false,'a full depot must not report a Coin claim as collected')
 assert(#changes==0 and pending[1].currencyAmount==25,'a failed delivery must leave the complete Coin claim reserved')
 ctx.fail=function(_,text) error(text) end
 ctx.deliver=function(_,id,subtype,count) delivered[#delivered+1]={id=id,subtype=subtype,count=count};return count end
 assert(actions.collect(ctx),'Coin claim must collect when depot capacity returns')
 assert(delivered[#delivered].id==5130 and delivered[#delivered].count==25,'Market must deliver the Coin item to the depot')
 assert(changes[#changes]:find('DELETE FROM market_claims WHERE id=91',1,true),'successful delivery must clear only the collected claim')
 replaceUpvalue(actions.collect,'rows',oldRows);replaceUpvalue(actions.collect,'changed',oldChanged)
end)
check('retired loot is skipped without aborting classic sibling loot',function()
 Container={}
 dofile('data/lib/core/container.lua')
 local creations=0
 Game={createItem=function(id) creations=creations+1;assert(id==3270,'retired loot creation attempted');return {isContainer=function() return false end,remove=function() end} end}
 getLootRandom=function() return 0 end
 RETURNVALUE_NOERROR=0
 local corpse={getEmptySlots=function() return 10 end,addItemEx=function() return 0 end}
 assert(Container.createLootItem(corpse,{itemId=3157,chance=100000,maxCount=1,childLoot={},subType=-1,actionId=-1}))
 assert(creations==0,'retired loot must be skipped before native creation')
 assert(Container.createLootItem(corpse,{itemId=3270,chance=100000,maxCount=1,childLoot={},subType=-1,actionId=-1}))
 assert(creations==1,'classic sibling must still be delivered')
end)
check('economy rejects retired grants before creating inventory objects',function()
 dofile('data/lib/custom/economy.lua')
 local calls=0
 local subject={getBankBalance=function() return 100 end,marketTransaction=function(_,work) return work() end}
 Game={createItem=function() calls=calls+1;error('retired grant must stop before native creation') end}
 assert(Economy.run(subject,function(ctx) return ctx:give(3157,1) end)==false)
 assert(calls==0)
end)
check('retired arena reward neither consumes chest entitlement nor dereferences nil',function()
 dofile('data/actions/scripts/arena/arenachest.lua')
 local subject={getStorageValue=function() return -1 end,getVocation=function() return {getId=function() return 1 end} end,
  addItem=function() error('retired reward must never attempt grant') end,setStorageValue=function() error('chest entitlement must remain untouched') end,
  sendTextMessage=function() end}
 MESSAGE_INFO_DESCR=1
 assert(onUse(subject,{getMovementId=function() return 7100 end,getPosition=function() return {sendMagicEffect=function() end} end}))
end)
check('retired achievement reward preserves qualification, skills and bonuses',function()
 SKILL_FIST,SKILL_CLUB,SKILL_SWORD,SKILL_AXE,SKILL_DISTANCE,SKILL_SHIELD,SKILL_MAGLEVEL,SKILL_LEVEL=0,1,2,3,4,5,7,8
 MESSAGE_EVENT_ADVANCE=19
 dofile('data/lib/custom/antigasAchievements.lua')
 local saved={[17821]=2,[17804]=7}
 local subject={getStorageValue=function(_,id) return saved[id] or -1 end,
  setStorageValue=function() error('retired item rewards must not alter progress storage') end,
  getLevel=function() return 200 end,getMagicLevel=function() return 120 end,getSkillLevel=function() return 120 end,
  addItem=function() error('retired achievement must not create item') end}
 assert(AntigasAchievements.grantPendingRewards(subject)==false)
 assert(saved[17821]==2 and saved[17804]==7)
 subject.isPlayer=function() return true end
 local entries={}
 subject.sendExtendedOpcode=function(_,_,payload) for _,entry in ipairs(json.decode(payload).entries) do entries[entry.id]=entry end end
 assert(AntigasAchievements.sendProgress(subject))
 assert(entries.level_1.ready==false and entries.level_1.reward=='Item reward retired','catalog must not advertise an unavailable claim')
 assert(saved[17821]==2 and saved[17804]==7,'progress reads must preserve historical qualification and bonuses')
end)
check('retired conjure target cannot consume a classic reagent or mana',function()
 dofile('data/spells/scripts/conjuring/enchant_spear.lua')
 local subject={conjureItem=function() error('retired conjure must reject before reagent or mana mutation') end,sendCancelMessage=function() end}
 RETURNVALUE_NOTPOSSIBLE=1
 assert(onCastSpell(subject,{})==false)
 Player={}
 dofile('data/spells/lib/spells.lua')
 subject.removeItem=function() error('central conjure helper must not consume a classic reagent') end
 subject.addItem=function() error('central conjure helper must not create retired target') end
 assert(Player.conjureItem(subject,3277,5290,1,0)==false)
end)
check('retired saved request status uses only an owned read and never replays a mutation',function()
 local oldRows,oldBalances,oldAllowed=upvalue(onExtendedOpcode,'rows'),upvalue(onExtendedOpcode,'sendBalances'),upvalue(onExtendedOpcode,'allowed')
 local found,queries,refreshes=false,0,0
 replaceUpvalue(onExtendedOpcode,'rows',function(sql)
  assert(sql:find('SELECT response FROM market_requests WHERE player_guid=1 AND request_id=',1,true)==1,'status must read only the authenticated character request')
  assert(not sql:find('INSERT',1,true) and not sql:find('UPDATE',1,true),'status must never mutate history or finances')
  queries=queries+1
  return found and {{response='Original committed response'}} or {}
 end)
 replaceUpvalue(onExtendedOpcode,'sendBalances',function() refreshes=refreshes+1 end)
 replaceUpvalue(onExtendedOpcode,'allowed',function(_,mutation) assert(not mutation,'status must be a read');return true end)
 db={query=function() error('status must never mutate') end,escapeString=function(s) return "'"..s.."'" end}
 player.marketTransaction=function() error('status must never start a mutation') end
 for _,committed in ipairs({false,true}) do
  found=committed
  assert(onExtendedOpcode(player,202,json.encode({action='requestStatus',data={requestId='old-request'}})))
  local result=requests.market.data
  assert(requests.market.action=='message' and result.retiredPendingStatus and result.requestId=='old-request')
  assert(result.previouslyCommitted==committed,'status must reflect committed history without replay')
 end
 assert(queries==2 and refreshes==2,'both resolutions must refresh authoritative balances')
 assert(onExtendedOpcode(player,202,json.encode({action='requestStatus',data={requestId="bad'identifier"}})))
 assert(queries==2,'invalid identifiers must not query history')
 replaceUpvalue(onExtendedOpcode,'rows',oldRows);replaceUpvalue(onExtendedOpcode,'sendBalances',oldBalances);replaceUpvalue(onExtendedOpcode,'allowed',oldAllowed)
end)
print('Retired provider regression tests passed')
