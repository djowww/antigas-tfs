LOOT_ANALYZER_OPCODE = 120
DROP_ANALYZER_OPCODE = 122
SUPPLY_ANALYZER_OPCODE = 123
EXP_ANALYZER_OPCODE = 121

-- Table setup for the item prices
itemWorth = {
    [3031] = {value = 1}, --gold coin
	[3577] = {value = 5}, --meat
	[3607] = {value = 1}, --cheese
	[3582] = {value = 8}, --ham
	[3725] = {value = 10}, --brown mushroom
	[3358] = {value = 70}, --chain armor
	[3264] = {value = 25}, --sword
	[3410] = {value = 45}, --plata shield
	[3286] = {value = 30}, --mace
	[3352] = {value = 12}, --chain helmet
	[3357] = {value = 400}, --plate armor
    [3557] = {value = 115}, --plate legs
	[3351] = {value = 190}, --steel helmet
	[3269] = {value = 400}, --halberd
	[3409] = {value = 80}, --steel shield
	[3359] = {value = 150}, --brass armor
	[3265] = {value = 450}, --two handed sword
	[3447] = {value = 2}, --arrow
	[3446] = {value = 3}, --bolt
	[3305] = {value = 350}, --battle hammer
	[3413] = {value = 95}, --battle shield
	[3155] = {value = 0}, --SD
	[3160] = {value = 0}, --UH
	[3200] = {value = 0}, --EXPLO
	[3198] = {value = 0}, --Adori gRAn
	[3152] = {value = 0}, --Adura gran
	[3191] = {value = 0}, --GFB
	[3174] = {value = 0}, --Adori
	[3192] = {value = 0}, --EXPLO
	[3161] = {value = 0}, --avalanche
	[3158] = {value = 0}, --icicle
	[3148] = {value = 0}, --adito grav
	[5125] = {value = 55}, --mana fluid
	[3416] = {value = 4000}, --dragon shield
	[3079] = {value = 30000}, --boots of haste
	
}

function Player.addAnalyzerExp(self, value, expH)
	if expH < 0 then expH = 0 end
	self:sendOpcode(EXP_ANALYZER_OPCODE, {value, expH})
return true
end

function Player.checkAnalyzerLootItem(self, itemId, amount, type)
	if itemWorth[itemId] then
		if (type == 2) then
			self:addAnalyzerSupplies(itemWorth[itemId].value * amount)
		else
			self:addAnalyzerLoot(itemWorth[itemId].value * amount)
		end
	else
		-- Item not registrered on the loot table
	end
end

function Player.addAnalyzerLoot(self, value)
	local lTable = {}
	table.insert(lTable, 1) -- Type
	table.insert(lTable, value) -- Worth
	
	self:sendOpcode(LOOT_ANALYZER_OPCODE, lTable)
	self:addAnalyzerProfit(value)
return true
end

function Player.addAnalyzerSupplies(self, value)
	self:sendOpcode(LOOT_ANALYZER_OPCODE, {2, value})
	self:addAnalyzerProfit(-value)
return true
end

function Player.addAnalyzerProfit(self, value)
	self:sendOpcode(LOOT_ANALYZER_OPCODE, {3, value})
return true
end

function Player.addAnalyzerDrop(self, value)
	self:sendOpcode(DROP_ANALYZER_OPCODE, value)
return true
end

function Player.addAnalyzerSupply(self, value)
	self:sendOpcode(SUPPLY_ANALYZER_OPCODE, value)
return true
end

function Player.sendOpcode(self, code, ...)
	local res = {...}
	if #res > 0 then
		if #res == 1 then
			res = res[1]
		else
			res = {['@'] = res}
		end
		
		local msg = NetworkMessage()
		msg:addByte(50)
		msg:addByte(code)
		msg:addString(serialize(res))
		msg:sendToPlayer(self)
	end
end

local function checkVar(v)
	if v==nil then
		return 'nil'
	end
	local  t = type(v)
	if t=="number"   then return tostring(v)
	elseif t=="string"   then return string.format("%q", v)
	elseif t=="boolean"  then return v and "true" or "false"
	elseif t=="function" then
		return string.format ("loadstring(%q,'@serialized')", string.dump (v))
	elseif t=="userdata" then
		return checkVar(getmetatable(t))
	elseif t=="table" then
		local res = '{'
		local lastIndex = 1
		local first = true

		for i, o in pairs(v) do
			if first then
				first = false
			else
				res = res..','
			end
			if lastIndex ~= i then
				local t = type(i)
				if t ~= 'number' and (string.find(i, "%s") ~= nil or string.match(i, '^[A-Za-z]+[%w]+') ~= i) then
					res = res.."['"..i.."']"
				elseif t == 'number' then
					res = res..'['..i..']'
				else
					res = res..i
				end
				res = res..'='
			else
				lastIndex = lastIndex + 1
			end
			res = res..checkVar(o)
		end
		return res..'}'
	end
end

function serialize(o)
	return checkVar(o)
end

function unserialize(o)
	if o == nil then
		return nil
	end

	if o == 'true' then
		return true
	elseif o == 'false' then
		return false
	end

	local v = tonumber(o)
	if v ~= nil then
		return v
	end

	v = loadstring('return ' .. o)()
	if v ~= nil then
		return v
	end

	return o
end
