-- Market v2: inventory, bank, offers and deliveries commit together.
local OPCODE, GOLD, PLATINUM, CRYSTAL, ANTIGAS = 202,3031,3035,3043,5130
local MAX_AMOUNT, MAX_TOTAL, MAX_SAFE, PAGE_SIZE = 10000,100000000,9007199254740991,40
local types, canonical, catalog, limits = {},{},nil,{}
local CATEGORIES = {
 {id="all",name="All items"},{id="weapons",name="Weapons"},
 {id="shields",name="Shields"},{id="armor",name="Armor"},
 {id="helmets",name="Helmets"},{id="legs",name="Legs"},
 {id="boots",name="Boots"},{id="jewelry",name="Jewelry"},
 {id="runes",name="Runes"},{id="ammunition",name="Ammunition"},
 {id="supplies",name="Supplies"},{id="other",name="Other"}
}
local validCategories={}
for _,c in ipairs(CATEGORIES) do validCategories[c.id]=true end
local function integer(value,low,high)
 local n=tonumber(value)
 if n and n==n and n>=low and n<=high and n==math.floor(n) then return n end
end
local function send(player,action,data)
 player:sendExtendedOpcode(OPCODE,json.encode({action=action,data=data or {}}))
end
local function message(player,text,requestId,ok)
 send(player,"message",{text=text,requestId=requestId,ok=ok or false})
end
local function category(t)
 if t:isRune() then return "runes" end
 local weapon=t:getWeaponType()
 if weapon==WEAPON_SHIELD then return "shields" end
 if weapon==WEAPON_AMMO then return "ammunition" end
 if weapon>0 then return "weapons" end
 local slot=t:getSlotPosition()
 local function has(mask) return math.floor(slot/mask)%2==1 end
 if has(SLOTP_HEAD) then return "helmets" end
 if has(SLOTP_LEGS) then return "legs" end
 if has(SLOTP_FEET) then return "boots" end
 if has(SLOTP_NECKLACE) or has(SLOTP_RING) then return "jewelry" end
 if has(SLOTP_ARMOR) or t:getArmor()>0 then return "armor" end
 return t:isStackable() and "supplies" or "other"
end
local function marketType(id)
 id=integer(id,100,6000)
 if not id or id==GOLD or id==PLATINUM or id==CRYSTAL or id==ANTIGAS then return nil end
 if types[id]~=nil then return types[id] or nil end
 local t=ItemType(id)
 local name=t:getName()
 if not name or name=="" or not t:isMovable() or t:isContainer() or t:isDoor()
  or t:isMagicField() or t:isSplash() or t:isFluidContainer() then types[id]=false;return nil end
 local subtype=not t:isStackable() and t:getCharges()>0 and t:getCharges() or -1
 types[id]={id=id,name=name,category=category(t),subtype=subtype,stackable=t:isStackable()}
 return types[id]
end

-- getUniqueId() in this engine is a script handle, not a quest attribute.
-- Match persistent attributes against an untouched item with the same count.
local function clean(item)
 if item:getActionId()~=0 or item:getMovementId()~=0 then return false end
 local id,t=item:getId(),ItemType(item:getId())
 if t:isContainer() then return false end
 local count=t:isStackable() and item:getCount() or (t:getCharges()>0 and t:getCharges() or 1)
 if t:getCharges()>0 and item:getCharges()~=t:getCharges() then return false end
 local key=id..":"..count
 if canonical[key]==nil then
  local sample=Game.createItem(id,count)
  if not sample then return false end
  canonical[key]=sample:serializeAttributes()
  sample:remove()
 end
 for _,attr in ipairs({ITEM_ATTRIBUTE_OWNER,ITEM_ATTRIBUTE_CORPSEOWNER,
  ITEM_ATTRIBUTE_KEYNUMBER,ITEM_ATTRIBUTE_KEYHOLENUMBER,ITEM_ATTRIBUTE_DOORQUESTNUMBER,
  ITEM_ATTRIBUTE_DOORQUESTVALUE,ITEM_ATTRIBUTE_DOORLEVEL,ITEM_ATTRIBUTE_CHESTQUESTNUMBER}) do
  if item:hasAttribute(attr) then return false end
 end
 return item:serializeAttributes()==canonical[key]
end
local function inventory(player)
 local entries,summary,seen={},{},{}
 local function visit(item,parent,slot)
  if not item then return end
  local id,t=item:getId(),ItemType(item:getId())
  if t:isContainer() then
   local uid=item:getUniqueId()
   if seen[uid] then return end
   seen[uid]=true
   for i=0,item:getSize()-1 do visit(item:getItem(i),item,nil) end
  elseif clean(item) then
   local subtype=not t:isStackable() and t:getCharges()>0 and item:getCharges() or -1
   local n=t:isStackable() and item:getCount() or 1
   entries[#entries+1]={item=item,parent=parent,slot=slot,id=id,subtype=subtype,count=n,stackable=t:isStackable()}
   local key=id..":"..subtype
   summary[key]=(summary[key] or 0)+n
  end
 end
 for slot=1,10 do visit(player:getSlotItem(slot),player,slot) end
 return entries,summary
end
local function balances(player,summary)
 return {bank=player:getBankBalance(),wallet=(summary[GOLD..":-1"] or 0)
  +100*(summary[PLATINUM..":-1"] or 0)+10000*(summary[CRYSTAL..":-1"] or 0),antigas=summary[ANTIGAS..":-1"] or 0}
end
local function sendBalances(player)
 local _,summary=inventory(player)
 send(player,"balances",balances(player,summary))
end
local function rows(sql,fields)
 local r=db.storeQuery(sql)
 local out={}
 if r then
  repeat
   local row={}
   for name,kind in pairs(fields) do row[name]=kind=="s" and result.getDataString(r,name) or result.getDataInt(r,name) end
   out[#out+1]=row
  until not result.next(r)
  result.free(r)
 end
 return out
end
local function changed(sql)
 if not db.query(sql) then return false end
 local r=rows("SELECT ROW_COUNT() AS n",{n="n"})
 return r[1] and r[1].n==1 or false
end
local function pageOf(data) return integer(data.page,1,250) or 1 end
local function sendCatalog(player,data)
 if not catalog then
  catalog={}
  for id=100,6000 do local t=marketType(id);if t then catalog[#catalog+1]=t end end
  table.sort(catalog,function(a,b) if a.name:lower()==b.name:lower() then return a.id<b.id end return a.name:lower()<b.name:lower() end)
 end
 local _,summary=inventory(player)
 local query=type(data.search)=="string" and data.search:sub(1,48):lower() or ""
 local cat=validCategories[data.category] and data.category or "all"
 local page,matched,items=pageOf(data),0,{}
 for _,item in ipairs(catalog) do
  if (cat=="all" or item.category==cat) and (query=="" or item.name:lower():find(query,1,true)) then
   matched=matched+1
   if matched>(page-1)*PAGE_SIZE and #items<PAGE_SIZE then
    items[#items+1]={id=item.id,name=item.name,category=item.category,subtype=item.subtype,owned=summary[item.id..":"..item.subtype] or 0}
   end
  end
 end
 send(player,"catalog",{items=items,page=page,hasNext=matched>page*PAGE_SIZE,total=matched})
end
local offerFields={id="n",owner="n",ownerName="s",side="n",itemId="n",subtype="n",name="s",category="s",amount="n",price="n",currency="n"}
local function sendOffers(player,data,mine)
 local clauses={"o.status=1"}
 if mine then clauses[#clauses+1]="o.owner_guid="..player:getGuid() end
 local cat=validCategories[data.category] and data.category or "all"
 if cat~="all" then clauses[#clauses+1]="o.category="..db.escapeString(cat) end
 local currency=integer(data.currency,0,6000)
 if currency==GOLD or currency==ANTIGAS then clauses[#clauses+1]="o.currency_id="..currency end
 local side=integer(data.side,0,1)
 if side then clauses[#clauses+1]="o.side="..side end
 local search=type(data.search)=="string" and data.search:sub(1,48) or ""
 if search~="" then clauses[#clauses+1]="LOCATE("..db.escapeString(search)..",o.item_name)>0" end
 local page=pageOf(data)
 local offers=rows("SELECT o.id,o.owner_guid AS owner,p.name AS ownerName,o.side,o.item_id AS itemId,o.item_subtype AS subtype,o.item_name AS name,o.category,o.remaining AS amount,o.unit_price AS price,o.currency_id AS currency FROM market_offers o JOIN players p ON p.id=o.owner_guid WHERE "..table.concat(clauses," AND ").." ORDER BY o.item_name,o.currency_id,o.side,o.unit_price,o.id LIMIT "..(PAGE_SIZE+1).." OFFSET "..((page-1)*PAGE_SIZE),offerFields)
 local hasNext=#offers>PAGE_SIZE
 if hasNext then table.remove(offers) end
 send(player,mine and "myOffers" or "offers",{offers=offers,page=page,hasNext=hasNext,playerGuid=player:getGuid()})
end

local function context(player)
 local ctx={player=player,bank=player:getBankBalance(),removed={},added={}}
 function ctx:fail(text) self.error=text;return false end
 function ctx:take(entry,n)
  local copy=entry.stackable and Game.createItem(entry.id,n) or entry.item:clone()
  if not copy then return false end
  local partial=n<entry.count and entry.item or nil
  if not entry.item:remove(n) then copy:remove();return false end
  self.removed[#self.removed+1]={item=copy,parent=entry.parent,slot=entry.slot,partial=partial,id=entry.id,count=entry.count}
  entry.count=entry.count-n
  return true
 end
 function ctx:takeItems(id,subtype,n)
  local entries,summary=inventory(self.player)
  if (summary[id..":"..subtype] or 0)<n then return false end
  for _,e in ipairs(entries) do
   if e.id==id and e.subtype==subtype and n>0 then
    local take=math.min(n,e.count)
    if not self:take(e,take) then return false end
    n=n-take
   end
  end
  return n==0
 end
 function ctx:pay(currency,amount)
  if currency==ANTIGAS then return self:takeItems(ANTIGAS,-1,amount) end
  if currency~=GOLD then return false end
  local entries,summary=inventory(self.player)
  local balance=balances(self.player,summary)
  if not integer(balance.bank,0,MAX_SAFE) or balance.bank+balance.wallet<amount then return false end
  -- Bank first, then physical denominations. Change is deposited into the bank.
  local fromBank=math.min(balance.bank,amount)
  self.player:setBankBalance(balance.bank-fromBank)
  local remaining=amount-fromBank
  for _,denom in ipairs({{GOLD,1},{PLATINUM,100},{CRYSTAL,10000}}) do
   for _,e in ipairs(entries) do
    if e.id==denom[1] and remaining>0 then
     local take=math.min(e.count,math.ceil(remaining/denom[2]))
     if not self:take(e,take) then return false end
     remaining=remaining-take*denom[2]
    end
   end
  end
  if remaining<0 then self.player:setBankBalance(self.player:getBankBalance()-remaining) end
  return remaining<=0
 end
 function ctx:deliver(id,subtype,count)
  if id==GOLD then
   local bank=self.player:getBankBalance()
   if not integer(bank,0,MAX_SAFE-count) then return 0 end
   self.player:setBankBalance(bank+count)
   return count
  end
  local town=self.player:getTown()
  local depot=town and self.player:getDepotChest(town:getId(),true)
  if not depot then return 0 end
  local delivered=0
  local stackable=ItemType(id):isStackable()
  local depotLimit=self.player:getGroup():getMaxDepotItems()
  if depotLimit==0 then depotLimit=self.player:isPremium() and 2000 or 1000 end
  while delivered<count and #self.added<100 do
   -- addItemEx has no actor, so enforce the player's total depot limit here.
   if depot:getItemHoldingCount()>=depotLimit then break end
   local n=stackable and math.min(100,count-delivered) or 1
   local item=Game.createItem(id,stackable and n or (subtype>=0 and subtype or 1))
   if not item then break end
   if depot:addItemEx(item,INDEX_WHEREEVER,FLAG_IGNOREAUTOSTACK)~=RETURNVALUE_NOERROR then item:remove();break end
   self.added[#self.added+1]=item
   delivered=delivered+n
  end
  return delivered
 end
 function ctx:undo()
  for i=#self.added,1,-1 do if not self.added[i]:remove() then return false end end
  self.player:setBankBalance(self.bank)
  for i=#self.removed,1,-1 do
   local e=self.removed[i]
   if e.partial then
    if not e.partial:transform(e.id,e.count) then return false end
   else
    local flags=FLAG_NOLIMIT+FLAG_IGNOREAUTOSTACK
    local ret
    if e.slot then ret=self.player:addItemEx(e.item,false,e.slot,flags)
    else ret=e.parent:addItemEx(e.item,INDEX_WHEREEVER,flags) end
    if ret~=RETURNVALUE_NOERROR then return false end
   end
  end
  return true
 end
 return ctx
end
local function claim(guid,kind,id,subtype,count,currency,amount)
 return db.query("INSERT INTO market_claims(player_guid,kind,item_id,item_subtype,item_count,currency_id,currency_amount) VALUES ("..guid..","..kind..","..id..","..subtype..","..count..","..currency..","..amount..")")
end
local function getOffer(id)
 return rows("SELECT id,owner_guid AS owner,side,item_id AS itemId,item_subtype AS subtype,remaining AS amount,unit_price AS price,currency_id AS currency FROM market_offers WHERE id="..id.." AND status=1 FOR UPDATE",{id="n",owner="n",side="n",itemId="n",subtype="n",amount="n",price="n",currency="n"})[1]
end
local function validOffer(o)
 return o and marketType(o.itemId) and marketType(o.itemId).subtype==o.subtype and (o.side==0 or o.side==1)
  and (o.currency==GOLD or o.currency==ANTIGAS) and integer(o.amount,1,MAX_AMOUNT)
  and integer(o.price,1,MAX_TOTAL) and o.amount*o.price<=(o.currency==ANTIGAS and 10000 or MAX_TOTAL)
end
local actions={}
function actions.create(ctx,data)
 local side=data.side=="buy" and 1 or (data.side=="sell" and 0 or nil)
 local item=marketType(data.itemId)
 local amount,price=integer(data.amount,1,MAX_AMOUNT),integer(data.price,1,MAX_TOTAL)
 local currency=integer(data.currency,1,6000)
 if not side or not item or not amount or not price or (currency~=GOLD and currency~=ANTIGAS)
  or data.subtype~=item.subtype or (not item.stackable and amount>1000)
  or amount*price>(currency==ANTIGAS and 10000 or MAX_TOTAL) then return ctx:fail("Invalid offer quantity, item or price.") end
 local counts=rows("SELECT COUNT(*) AS n FROM market_offers WHERE owner_guid="..ctx.player:getGuid().." AND status=1",{n="n"})
 if not counts[1] or counts[1].n>=15 then return ctx:fail("Maximum: 15 active offers per character.") end
 if side==0 then
  if not ctx:takeItems(item.id,item.subtype,amount) then return ctx:fail("Not enough unmodified items with full charges in your inventory.") end
 elseif not ctx:pay(currency,amount*price) then return ctx:fail("Not enough funds. Gold includes your bank and carried gold/platinum/crystal coins.") end
 if not db.query("INSERT INTO market_offers(owner_guid,side,item_id,item_subtype,item_name,category,remaining,unit_price,currency_id,status) VALUES ("..ctx.player:getGuid()..","..side..","..item.id..","..item.subtype..","..db.escapeString(item.name)..","..db.escapeString(item.category)..","..amount..","..price..","..currency..",1)") then return false end
 ctx.text="Offer created. Its items or money are reserved until traded or cancelled."
 return true
end
function actions.fill(ctx,data)
 local id,amount=integer(data.offerId,1,4294967295),integer(data.amount,1,MAX_AMOUNT)
 if not id or not amount then return ctx:fail("Invalid offer or quantity.") end
 local offer=getOffer(id)
 if not validOffer(offer) or offer.owner==ctx.player:getGuid() or amount>offer.amount then return ctx:fail("Offer changed, sold out or belongs to you. Refresh the list.") end
 local total=offer.price*amount
 local itemReceiver,moneyReceiver
 if offer.side==0 then
  if not ctx:pay(offer.currency,total) then return ctx:fail("Not enough funds in your inventory and bank.") end
  itemReceiver,moneyReceiver=ctx.player:getGuid(),offer.owner
 else
  if not ctx:takeItems(offer.itemId,offer.subtype,amount) then return ctx:fail("Not enough unmodified items with full charges in your inventory.") end
  itemReceiver,moneyReceiver=offer.owner,ctx.player:getGuid()
 end
 if not changed("UPDATE market_offers SET status=IF(remaining="..amount..",2,1),remaining=remaining-"..amount.." WHERE id="..id.." AND status=1 AND remaining>="..amount) then return false end
 if not claim(itemReceiver,0,offer.itemId,offer.subtype,amount,0,0) or not claim(moneyReceiver,1,0,-1,0,offer.currency,total) then return false end
 ctx.text="Trade completed. Use Collect: gold goes to your bank; items and Antigas Coins go to your depot."
 return true
end
function actions.cancel(ctx,data)
 local id=integer(data.offerId,1,4294967295)
 if not id then return ctx:fail("Invalid offer.") end
 local offer=getOffer(id)
 if not validOffer(offer) or offer.owner~=ctx.player:getGuid() then return ctx:fail("This is not an active offer owned by you.") end
 if not changed("UPDATE market_offers SET status=2 WHERE id="..id.." AND status=1") then return false end
 local ok
 if offer.side==0 then ok=claim(offer.owner,0,offer.itemId,offer.subtype,offer.amount,0,0)
 else ok=claim(offer.owner,1,0,-1,0,offer.currency,offer.amount*offer.price) end
 if not ok then return false end
 ctx.text="Offer cancelled. Use Collect to receive the remaining items or money."
 return true
end
function actions.collect(ctx)
 local claims=rows("SELECT id,kind,item_id AS itemId,item_subtype AS subtype,item_count AS itemCount,currency_id AS currency,currency_amount AS currencyAmount FROM market_claims WHERE player_guid="..ctx.player:getGuid().." ORDER BY id LIMIT 20 FOR UPDATE",{id="n",kind="n",itemId="n",subtype="n",itemCount="n",currency="n",currencyAmount="n"})
 if #claims==0 then return ctx:fail("No pending Market deliveries.") end
 local received=0
 for _,c in ipairs(claims) do
  local id=c.kind==1 and c.currency or c.itemId
  local count=c.kind==1 and c.currencyAmount or c.itemCount
  local t=marketType(id)
  if not integer(count,1,MAX_TOTAL) or (c.kind~=0 and c.kind~=1)
   or (c.kind==0 and (not t or t.subtype~=c.subtype))
   or (c.kind==1 and id~=GOLD and id~=ANTIGAS) then return ctx:fail("Invalid delivery detected. Contact support; no assets were transferred.") end
  local n=ctx:deliver(id,c.subtype,count)
  if n>0 then
   local sql
   if n==count then sql="DELETE FROM market_claims WHERE id="..c.id.." AND player_guid="..ctx.player:getGuid()
   else sql="UPDATE market_claims SET "..(c.kind==1 and "currency_amount" or "item_count").."="..(count-n).." WHERE id="..c.id.." AND player_guid="..ctx.player:getGuid() end
   if not changed(sql) then return false end
   received=received+n
  end
 end
 if received==0 then return ctx:fail("Your depot is full or your bank cannot receive more gold. Your deliveries remain reserved.") end
 ctx.text="Collected: gold to bank, items and Antigas Coins to depot. If deliveries remain, free depot space and collect again."
 return true
end
local function mutate(player,request,buffer)
 if not player.marketTransaction then return message(player,"Market requires the updated server. Trading is unavailable.",request.requestId) end
 local id=request.requestId
 if type(id)~="string" or #id<8 or #id>64 or not id:match("^[%w%-]+$") then return message(player,"Please install the updated Market client before trading.",id) end
 local ctx=context(player)
 local ok=player:marketTransaction(function()
  if not rows("SELECT id FROM players WHERE id="..player:getGuid().." FOR UPDATE",{id="n"})[1] then return false end
  local previous=rows("SELECT request_json,response FROM market_requests WHERE player_guid="..player:getGuid().." AND request_id="..db.escapeString(id),{request_json="s",response="s"})[1]
  if previous then
   if previous.request_json~=buffer then return ctx:fail("This request identifier was already used. Refresh and try again.") end
   ctx.text=previous.response
   return true
  end
  if not actions[request.action](ctx,request.data) then return false end
  return db.query("INSERT INTO market_requests(player_guid,request_id,action,request_json,response) VALUES ("..player:getGuid()..","..db.escapeString(id)..","..db.escapeString(request.action)..","..db.escapeString(buffer)..","..db.escapeString(ctx.text)..")")
 end,function() return ctx:undo() end)
 message(player,ok and ctx.text or ctx.error or "Market operation failed. No assets were transferred.",id,ok)
 sendBalances(player)
end
local function allowed(player,mutation)
 local now,guid=os.time(),player:getGuid()
 local limit=limits[guid]
 if not limit or limit.second~=now then limit={second=now,read=0,write=0};limits[guid]=limit end
 local key=mutation and "write" or "read"
 limit[key]=limit[key]+1
 if now%60==0 then for id,l in pairs(limits) do if l.second<now-60 then limits[id]=nil end end end
 return limit[key]<=(mutation and 3 or 8)
end
function onExtendedOpcode(player,opcode,buffer)
 if opcode~=OPCODE then return false end
 if type(buffer)~="string" or #buffer>2048 then return false end
 local ok,request=pcall(json.decode,buffer)
 if not ok or type(request)~="table" or type(request.action)~="string" or type(request.data)~="table" then return false end
 if not allowed(player,actions[request.action]~=nil) then
  if actions[request.action] then message(player,"Please wait a moment before another transaction.",request.requestId) end
  return false
 end
 if actions[request.action] then mutate(player,request,buffer)
 elseif request.action=="init" then
  send(player,"init",{categories=CATEGORIES,version=2,goldCoin=GOLD,antigasCoin=ANTIGAS})
  sendBalances(player)
 elseif request.action=="browse" then sendOffers(player,request.data,false)
 elseif request.action=="mine" then sendOffers(player,request.data,true)
 elseif request.action=="catalog" then sendCatalog(player,request.data)
 else return false end
 return true
end
