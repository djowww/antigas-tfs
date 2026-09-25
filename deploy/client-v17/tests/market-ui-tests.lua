-- Offline fixture; no game connection is made.
local function run()
 g_game.setClientVersion(772)
 g_window.resize({width=1100,height=700})
 local sent={}
 local protocol={sendExtendedJSONOpcode=function(self,code,data) sent[#sent+1]=data end,
  sendExtendedOpcode=function(self,code,raw) sent[#sent+1]=json.decode(raw) end}
 g_game.isOnline=function() return true end
 g_game.getProtocolGame=function() return protocol end
 g_game.getCharacterName=function() return 'Market UI QA' end
 local feature=g_game.getFeature
 g_game.getFeature=function(id) return id==GameExtendedOpcode or feature(id) end
 local m=modules.game_market_antigas
 local w=g_ui.getRootWidget():recursiveGetChildById('marketWindow')
 local function child(id) return w:recursiveGetChildById(id) end
 local function packet(action,data) m.onExtendedJSONOpcode(nil,202,{action=action,data=data}) end
 m.onGameStart()
 m.show()
 assert(sent[#sent].action=='catalog','Market must open in catalog')
 local cats={}
 for _,pair in ipairs({{'all','All items'},{'weapons','Weapons'},{'shields','Shields'},{'armor','Armor'},
  {'helmets','Helmets'},{'legs','Legs'},{'boots','Boots'},{'jewelry','Jewelry'},
  {'runes','Runes'},{'ammunition','Ammunition'},{'supplies','Supplies'},{'other','Other'}}) do
  cats[#cats+1]={id=pair[1],name=pair[2]}
 end
 packet('init',{version=2,categories=cats})
 packet('balances',{bank=990000,wallet=999950,antigas=50,pending={count=3,gold=7500,antigas=5,items=2}})
 assert(child('collect'):getText()=='Collect (3)','Pending delivery counter')
 w.ownedOnly:setChecked(true)
 assert(sent[#sent].data.ownedOnly==true,'Owned filter sent to server')
 w.ownedOnly:setChecked(false)
 local items={{id=3264,name='sword',owned=2,category='weapons',subtype=-1,prices={['3031']={sell=150,buy=100},['5130']={sell=5,buy=3}}},
  {id=5312,name='wand of energy',owned=0,category='weapons',subtype=-1},
  {id=3309,name='thunder hammer',owned=1,category='weapons',subtype=-1},
  {id=9000,name='missing graphics',owned=0,category='other',subtype=-1}}
 packet('catalog',{items=items,page=1,hasNext=true})
 assert(w.offerList:getChildCount()==2,'Missing-sprite items must be filtered')
 assert(not w.sideFilter:isEnabled() and not w.currencyFilter:isEnabled(),'Offer filters disabled in catalog')
 m.selectCatalogItem(w.offerList:getChildren()[1])
 assert(not child('createOffer'):isEnabled() and child('price'):getText()=='','No accidental default price')
 assert(w.offerList:getChildren()[1].prices:getText():find('Antigas: Sell 5 | Buy 3',1,true),'Separate currency reference prices')
 child('quantity'):setText('2')
 child('price'):setText('150')
 assert(child('offerHelp'):getText():find('2 items',1,true),'Sell reserves items')
 child('side'):setCurrentOptionByData('buy')
 assert(child('offerHelp'):getText():find('300 gold',1,true),'Buy reserves currency total')
 child('quantity'):setText('1.5')
 assert(not child('createOffer'):isEnabled(),'Fractional quantity must be disabled')
 child('quantity'):setText('2')
 m.viewSelectedOffers()
 assert(sent[#sent].action=='browse' and sent[#sent].data.search=='sword','Selected item offer lookup')
 packet('offers',{offers={},page=1,hasNext=false})
 assert(w.offerList:getChildCount()==1,'Offers empty-state guidance')
 m.showMyOffers()
 packet('myOffers',{offers={{id=91,itemId=5312,name='wand of energy',side=0,amount=1,price=20,currency=3031}},page=1})
 assert(w.offerList:getChildCount()==1,'Old invisible offer remains cancellable')
 assert(w.offerList:getChildren()[1].action:getText()=='Cancel','Cancellation access retained')
 m.showHistory()
 packet('history',{entries={{event='Sold',itemId=3264,name='sword',quantity=2,total=300,currency=3031,pending=300,destination='gold to bank',date='2026-09-24 12:00 UTC'}},page=1})
 assert(w.offerList:getChildren()[1].details:getText():find('Pending: 300',1,true),'History pending destination')
 m.changePage(1)
 assert(sent[#sent].action=='history' and sent[#sent].data.page==2,'History pagination')
 m.searchCatalog()
 packet('catalog',{items=items,page=1,hasNext=true})
 packet('offers',{offers={},page=99})
 assert(w.offerList:getChildCount()==2 and child('pageLabel'):getText()=='Page 1','Stale view response ignored')
 m.changePage(1)
 assert(sent[#sent].action=='catalog' and sent[#sent].data.page==2,'Catalog pagination')
 m.refreshView()
 assert(sent[#sent].action=='catalog','Refresh keeps catalog view')
 packet('catalog',{items=items,page=1,hasNext=true})
 child('side'):setCurrentOptionByData('sell')
 scheduleEvent(function()
  local ok,err=pcall(function()
   local create,form=child('createOffer'):getRect(),child('createPanel'):getRect()
   assert(create.y+create.height<=form.y+form.height,'Form overflows panel')
   local balance,footer=child('balanceLabel'):getRect(),child('footer'):getRect()
   assert(balance.y+balance.height<=footer.y,'Balance text overlaps footer')
   print('MARKET_V15_QA_PASS: catalog, owned filter, reference prices, history, pending counter, blank price, legacy cancellation, geometry')
   g_app.doScreenshot('market-v15.png')
  end)
  if not ok then print('MARKET_V15_QA_FAIL '..tostring(err)) end
  g_game.isOnline=function() return false end
  scheduleEvent(function() g_app.exit() end,1000)
 end,1200)
end
local ok,err=pcall(run)
if not ok then
 print('MARKET_V15_QA_FAIL '..tostring(err))
 g_game.isOnline=function() return false end
 scheduleEvent(function() g_app.exit() end,1000)
end
