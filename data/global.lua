math.randomseed(os.mtime())
dofile('data/lib/lib.lua')

function getDistanceBetween(firstPosition, secondPosition)
	local xDif = math.abs(firstPosition.x - secondPosition.x)
	local yDif = math.abs(firstPosition.y - secondPosition.y)
	local posDif = math.max(xDif, yDif)
	if firstPosition.z ~= secondPosition.z then
		posDif = posDif + 15
	end
	return posDif
end

function getFormattedWorldTime()
	local worldTime = getWorldTime()
	local hours = math.floor(worldTime / 60)

	local minutes = worldTime % 60
	if minutes < 10 then
		minutes = '0' .. minutes
	end
	return hours .. ':' .. minutes
end

string.split = function(str, sep)
	local res = {}
	for v in str:gmatch("([^" .. sep .. "]+)") do
		res[#res + 1] = v
	end
	return res
end

string.trim = function(str)
	return str:match'^()%s*$' and '' or str:match'^%s*(.*%S)'
end

table.contains = function(array, value)
	for _, targetColumn in pairs(array) do
		if targetColumn == value then
			return true
		end
	end
	return false
end

function getRealTime()
	local hours = tonumber(os.date("%H", os.time()))
	local minutes = tonumber(os.date("%M", os.time()))

	if hours < 10 then
		hours = '0' .. hours
	end
	if minutes < 10 then
		minutes = '0' .. minutes
	end
	return hours .. ':' .. minutes
end

function getRealDate()
	local month = tonumber(os.date("%m", os.time()))
	local day = tonumber(os.date("%d", os.time()))

	if month < 10 then
		month = '0' .. month
	end
	if day < 10 then
		day = '0' .. day
	end
	return day .. '/' .. month
end

function firstToUpper(str)
    return (str:gsub("^%l", string.upper))
end

function isInArray(array, value, isCaseSensitive)
    local compareLowerCase = false
    if value ~= nil and type(value) == "string" and not isCaseSensitive then
        value = string.lower(value)
        compareLowerCase = true
    end
    if array == nil or value == nil then
        return (array == value), nil
    end
    local t = type(array)
    if t ~= "table" then
        if compareLowerCase and t == "string" then
            return (string.lower(array) == string.lower(value)), nil
        else
            return (array == value), nil
        end
    end
    for k,v in pairs(array) do
        local newV
        if compareLowerCase and type(v) == "string" then
            newV = string.lower(v)
        else
            newV = v
        end
        if newV == value then
            return true, k
        end
    end
    return false
end

function capAll(str)
    local newStr = ""; wordSeparate = string.gmatch(str, "([^%s]+)")
    for v in wordSeparate do
        v = v:gsub("^%l", string.upper)
        if newStr ~= "" then
            newStr = newStr.." "..v
        else
            newStr = v
        end
    end
    return newStr
end

weatherConfig = {

    groundEffect = 32,

    fallEffect = 18,

    thunderEffect = false,

    minDMG = 0,

    maxDMG = 0

}

 

function Player.sendWeatherEffect(self, groundEffect, fallEffect, thunderEffect)

    local position, random = self:getPosition(), math.random

    position.x = position.x + random(-4, 4)

      position.y = position.y + random(-4, 4)

 

    local fromPosition = Position(position.x + 1, position.y, position.z)

       fromPosition.x = position.x - 7

       fromPosition.y = position.y - 5

 

    local tile, getGround

    for Z = 1, 7 do

        fromPosition.z = Z

        position.z = Z

 

        tile = Tile(position)

        if tile then -- If there is a tile, stop checking floors

            fromPosition:sendDistanceEffect(position, fallEffect)

            position:sendMagicEffect(groundEffect, self)

 

            getGround = tile:getGround()

            if getGround and ItemType(getGround:getId()):getFluidSource() == 1 then

                position:sendMagicEffect(32, self)

            end

            break

        end

    end

 

    if thunderEffect and tile then

        if random(2) == 1 then

            local topCreature = tile:getTopCreature()

 

            if topCreature and topCreature:isPlayer() then

                position:sendMagicEffect(21, self)

                doTargetCombatHealth(0, self, COMBAT_ENERGYDAMAGE, -weatherConfig.minDMG, -weatherConfig.maxDMG, CONST_ME_NONE)

                self:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "You were hit by lightning and lost some health.")

            end

        end

    end

end

function Player.setExhaustion(self, value, time)
    self:setStorageValue(value, time + os.time())
end

function Player.getExhaustion(self, value)
    local storage = self:getStorageValue(value)
    if not storage or storage <= os.time() then
        return 0
    end

    return storage - os.time()
end

function Player:hasExhaustion(value)
    return self:getExhaustion(value) > 0
end

string.splitTrimmed = function(str, sep)
	local res = {}
	for v in str:gmatch("([^" .. sep .. "]+)") do
		res[#res + 1] = v:trim()
	end
	return res
end

-- refinamiento de espadas

function getItemAttribute(uid, key)
   local i = ItemType(Item(uid):getId())
   local string_attributes = {
     [ITEM_ATTRIBUTE_NAME] = i:getName(),
     [ITEM_ATTRIBUTE_ARTICLE] = i:getArticle(),
     [ITEM_ATTRIBUTE_PLURALNAME] = i:getPluralName(),
     ["name"] = i:getName(),
     ["article"] = i:getArticle(),
     ["pluralname"] = i:getPluralName()
   }

   local numeric_attributes = {
     [ITEM_ATTRIBUTE_WEIGHT] = i:getWeight(),
     [ITEM_ATTRIBUTE_ATTACK] = i:getAttack(),
     [ITEM_ATTRIBUTE_DEFENSE] = i:getDefense(),
     [ITEM_ATTRIBUTE_EXTRADEFENSE] = i:getExtraDefense(),
     [ITEM_ATTRIBUTE_ARMOR] = i:getArmor(),
     [ITEM_ATTRIBUTE_HITCHANCE] = i:getHitChance(),
     [ITEM_ATTRIBUTE_SHOOTRANGE] = i:getShootRange(),
     ["weight"] = i:getWeight(),
     ["attack"] = i:getAttack(),
     ["defense"] = i:getDefense(),
     ["extradefense"] = i:getExtraDefense(),
     ["armor"] = i:getArmor(),
     ["hitchance"] = i:getHitChance(),
     ["shootrange"] = i:getShootRange()
   }
   
   local attr = Item(uid):getAttribute(key)
   if tonumber(attr) then
     if numeric_attributes[key] then
       return attr ~= 0 and attr or numeric_attributes[key]
     end
   else
     if string_attributes[key] then
       if attr == "" then
         return string_attributes[key]
       end
     end
   end
return attr
end

function doItemSetAttribute(uid, key, value)
   return Item(uid):setAttribute(key, value)
end

function doItemEraseAttribute(uid, key)
   return Item(uid):removeAttribute(key)
end
