local SHOP_EXTENDED_OPCODE = 201
local SHOP_OFFERS = {}
local SHOP_CALLBACKS = {}
local SHOP_CATEGORIES = nil
local SHOP_BUY_URL = "https://tibia74.tech/coins.php"
local SHOP_AD = { -- can be nil
	image = "https://tibia74.tech/antigas-shop-banner.png",
	url = "https://tibia74.tech/coins.php",
	text = ""
}

function init()
	SHOP_CATEGORIES = {}
	
	local premiumCategory = addCategory({
		type="item",
		item=ItemType(5128):getId(),
		name="Premium Points"
	})
   --premiumCategory.addItem(10, 3043, 100, "Crystal Coins", "Enoy Test Server!.")
   --premiumCategory.addItem(1, 3057, 1, "Amulet of Loss", "Enoy Test Server!.")
   premiumCategory.addItem(11, 5128, 1, "Antigas Ticket", "The value of this ticket is 10 premium points.")
   premiumCategory.addItem(2, 5130, 1, "Antigas Coin", "Coin used to get premium points.")
   
   local regenerationCategory = addCategory({
		type="item",
		item=ItemType(5101):getId(),
		name="Regeneration Items"
	})
	regenerationCategory.addItem(80, 5102, 1, "Antigas Ring", "Eternal Light, + 1HP/2s + 2MP/3s.")
	regenerationCategory.addItem(50, 3549, 1, "Pair Of Soft Boots", "INFINITE Regen + 1 HP/MP per 2 second.")
   
	local scrollsCategory = addCategory({
		type="item",
		item=ItemType(5100):getId(),
		name="Scrolls"
	})
	scrollsCategory.addItem(25, 5291, 1, "Exp Scroll", "You receive 25% experience for 1 hours.")
	scrollsCategory.addItem(50, 5140, 1, "House Scroll", "Use this item to buy a house.")
	--scrollsCategory.addItem(30, 5098, 1, "Blue Djinn Scroll", "You can complete the Quest or use this Item to talk with the Djinns. (ATTENTION: Only 1 djinn per player).")
	--scrollsCategory.addItem(30, 5099, 1, "Green Djinn Scroll", "You can complete the Quest or use this Item to talk with the Djinns. (ATTENTION: Only 1 djinn per player).")
	scrollsCategory.addItem(30, 5226, 1, "Avar Tar Blessing", "Ability to buy all available blessings at once from Avar Tar.")
	scrollsCategory.addItem(30, 5100, 1, "Postman Scroll", "Access to use mailboxes in hazardous areas and negotiate with rashid.")
	scrollsCategory.addItem(25, 5131, 1, "Blessing Scroll", "Use this item to receive all regular blessings.")
	scrollsCategory.addItem(10, 5129, 1, "Teleport Scroll", "Using it will take you to your city of origin.")
	
	local trainingoffline = addCategory({
		type="item",
		item=ItemType(5282):getId(),
		name="Training Offline"
	})
	trainingoffline.addItem(50, 5285, 1, "Training Club", "ATTENTION: Place the furniture package in the position you want before using it, otherwise you will not be able to move it later.")
	trainingoffline.addItem(50, 5287, 1, "Training Sword", "ATTENTION: Place the furniture package in the position you want before using it, otherwise you will not be able to move it later.")
	trainingoffline.addItem(50, 5286, 1, "Training Axe", "ATTENTION: Place the furniture package in the position you want before using it, otherwise you will not be able to move it later.")
	trainingoffline.addItem(50, 5288, 1, "Training Distance", "ATTENTION: Place the furniture package in the position you want before using it, otherwise you will not be able to move it later.")
	trainingoffline.addItem(50, 5289, 1, "Training Magic", "ATTENTION: Place the furniture package in the position you want before using it, otherwise you will not be able to move it later.")
	
	local toolsCategory = addCategory({
		type="item",
		item=ItemType(3460):getId(),
		name="Utilities"
	})
	toolsCategory.addItem(40, 5247, 1, "Antigas Amulet", "+10 Speed.")
	toolsCategory.addItem(30, 5246, 1, "Magic Gold Converter", " (Infinite) Use to converter all gold in you inventory.")
	toolsCategory.addItem(10, 5171, 1, "Obsidian Knife", "Sharp and light, this is a useful tool for tanners, doctors and assassins.")
	toolsCategory.addItem(10, 5139, 1, "Light Shovel", "Same purpose as regular Shovels, but 20 oz lighter.")
	toolsCategory.addItem(10, 5138, 1, "Elvenhair Rope", "Light Rope 6.00 oz.")
	toolsCategory.addItem(10, 5154, 1, "Old Backpack", "Weighs 18.00 oz and 20 Slots.")
	toolsCategory.addItem(10, 5132, 1, "Check Blessing", "Click in this item to check your blessings.")
	toolsCategory.addItem(5, 3725, 100, "100 X Brown Mushroom", "So as not to be hungry.")
	toolsCategory.addItem(5, 5097, 1, "Dice", "Often used as a way of gambling, usually called casinos.")
	toolsCategory.addItem(40, 5336, 1, "universe scale mail", "armor defence.")
	
end

function addCategory(data)
  data['offers'] = {}
  table.insert(SHOP_CATEGORIES, data)
  table.insert(SHOP_CALLBACKS, {})
  local index = #SHOP_CATEGORIES
  return {
    addItem = function(cost, itemId, count, title, description, callback)      
      if not callback then
        callback = defaultItemBuyAction
      end
      table.insert(SHOP_CATEGORIES[index]['offers'], {
        cost=cost,
        type="item",
        item=ItemType(itemId):getId(), -- displayed
        itemId=itemId,
        count=count,
        title=title,
        description=description
      })
      table.insert(SHOP_CALLBACKS[index], callback)
    end,
    addOutfit = function(cost, outfit, title, description, callback)
      if not callback then
        callback = defaultOutfitBuyAction
      end
      table.insert(SHOP_CATEGORIES[index]['offers'], {
        cost=cost,
        type="outfit",
        outfit=outfit,
        title=title,
        description=description
      })    
      table.insert(SHOP_CALLBACKS[index], callback)
    end,
    addImage = function(cost, image, title, description, callback)
      if not callback then
        callback = defaultImageBuyAction
      end
      table.insert(SHOP_CATEGORIES[index]['offers'], {
        cost=cost,
        type="image",
        image=image,
        title=title,
        description=description
      })
      table.insert(SHOP_CALLBACKS[index], callback)
    end,
	addPremiumDays = function(cost, image, title, description, count, callback)
      if not callback then
        callback = defaultPremiumBuyAction
      end
      table.insert(SHOP_CATEGORIES[index]['offers'], {
        cost=cost,
        type="image",
        image=image,
        title=title,
        description=description,
		count=count,
      })
      table.insert(SHOP_CALLBACKS[index], callback)
    end
  }
end

function getPoints(player)
  local points = 0
  local resultId = db.storeQuery("SELECT `premium_points` FROM `accounts` WHERE `id` = " .. player:getAccountId())
  if resultId ~= false then
    points = result.getDataInt(resultId, "premium_points")
    result.free(resultId)
  end
  return points
end

function getStatus(player)
  local status = {
    ad = SHOP_AD,
    points = getPoints(player),
    buyUrl = SHOP_BUY_URL
  }
  return status
end

function sendJSON(player, action, data, forceStatus)
	local status = nil
	if not player:getStorageValue(1150001) or player:getStorageValue(1150001) + 10 < 	os.time() or forceStatus then
      status = getStatus(player)
	end
	player:setStorageValue(1150001, os.time())

	local msg = NetworkMessage()
	msg:addByte(50)
	msg:addByte(SHOP_EXTENDED_OPCODE)
	msg:addString(json.encode({action = action, data = data, status = status}))
	msg:sendToPlayer(player)
end

function sendMessage(player, title, msg, forceStatus)
  sendJSON(player, "message", {title=title, msg=msg}, forceStatus)
end

function onExtendedOpcode(player, opcode, buffer)
	if opcode ~= SHOP_EXTENDED_OPCODE then
		return false
	end
  
	if type(buffer) ~= 'string' or #buffer > 4096 then return false end
	local status, json_data = pcall(function() return json.decode(buffer) end)
	if not status or type(json_data) ~= 'table' then
		return false
	end

	local action = json_data['action']
	local data = json_data['data']
	local now,key=os.time(),json_data.action=='buy' and 1150004 or 1150003
	if player:getStorageValue(key)==now then return false end
	player:setStorageValue(key,now)
	if not action or not data then
		return false
	end

	if SHOP_CATEGORIES == nil then
		init()    
	end

	if action == 'init' then
		sendJSON(player, "categories", SHOP_CATEGORIES)
	elseif action == 'buy' then
		processBuy(player, data)
	elseif action == "history" then
		sendHistory(player)
	end
return true
end

function processBuy(player, data)
  if type(data) ~= 'table' then
    return sendMessage(player, "Error!", "Invalid offer")
  end
  local categoryId = tonumber(data["category"])
  local offerId = tonumber(data["offer"])
  local category = categoryId and SHOP_CATEGORIES[categoryId]
  local callbacks = categoryId and SHOP_CALLBACKS[categoryId]
  local offer = category and offerId and category.offers[offerId]
  local callback = callbacks and offerId and callbacks[offerId]
  if not offer or not callback or data["title"] ~= offer["title"] or data["cost"] ~= offer["cost"] then
    sendJSON(player, "categories", SHOP_CATEGORIES) -- refresh categories, maybe invalid
    return sendMessage(player, "Error!", "Invalid offer")      
  end
  local points = getPoints(player)
  if not offer['cost'] or offer['cost'] > points or points < 1 then
    return sendMessage(player, "Error!", "You don't have enough points to buy " .. offer['title'] .."!", true)    
  end
  -- All currently registered offers are ordinary items. Do not run arbitrary
  -- callbacks inside a transaction without a matching memory rollback.
  if offer.type ~= 'item' or callback ~= defaultItemBuyAction then
    return sendMessage(player,'Error!','This offer is unavailable.',true)
  end
  local ok=Economy.run(player,function(ctx)
    if not Economy.changed('UPDATE accounts SET premium_points=premium_points-'..offer.cost..' WHERE id='..player:getAccountId()..' AND premium_points>='..offer.cost) then return false end
    if not ctx:give(offer.itemId,offer.count) then return false end
    return db.query('INSERT INTO shop_history (account,player,date,title,cost,details) VALUES ('..player:getAccountId()..','..player:getGuid()..',NOW(),'..db.escapeString(offer.title)..','..offer.cost..','..db.escapeString(json.encode(offer))..')')
  end)
  if ok then return sendMessage(player,'Success!','You bought '..offer.title..'!',true) end
  return sendMessage(player,'Error!','Purchase not completed. Check inventory space; your points were not charged.',true)
end

function sendHistory(player)
  if player:getStorageValue(1150002) and player:getStorageValue(1150002) + 10 > os.time() then
    return -- min 10s delay
  end
  player:setStorageValue(1150002, os.time())

  local history = {}
	local resultId = db.storeQuery("SELECT `details`, `title`, `cost`, `date` FROM `shop_history` WHERE `account` = " .. player:getAccountId() .. " order by `id` DESC LIMIT 50")

	if resultId ~= false then
    repeat
      local details = result.getDataString(resultId, "details")
      local status, json_data = pcall(function() return json.decode(details) end)
      if not status or type(json_data) ~= 'table' then
        json_data = {
          type = "image",
          title = result.getDataString(resultId, "title"),
          cost = result.getDataInt(resultId, "cost")
        }
      end
      table.insert(history, json_data)
      history[#history]["description"] = "Bought on " .. result.getDataString(resultId, "date") .. " for " .. result.getDataInt(resultId, "cost") .. " points."
    until not result.next(resultId)
    result.free(resultId)
	end

  sendJSON(player, "history", history)
end

-- BUY CALLBACKS
-- May be useful: print(json.encode(offer))

function defaultItemBuyAction(player, offer)
  -- todo: check if has capacity
  if player:addItem(offer["itemId"], offer["count"], false) then
    return true
  end
  return "Can't add item! Do you have enough space?"
end

function defaultPremiumBuyAction(player, offer)
	if player:getPremiumDays() + offer["count"] > 360 then
		return "You can't buy more than 1 premium year"
	else
		player:addPremiumDays(offer["count"])
	return true
	end
return true
end

function defaultOutfitBuyAction(player, offer)
 if player:addOutfit(offer["outfit"], false) then
    return true
  end
  return "Can't add the outfit!"
end

function defaultImageBuyAction(player, offer)
  return "default image buy action is not implemented"
end

function customImageBuyAction(player, offer)
  return "custom image buy action is not implemented. Offer: " .. offer['title']
end
