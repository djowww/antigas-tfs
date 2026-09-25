function Creature.getClosestFreePosition(self, position, extended)
	local usePosition = Position(position)
	local tiles = { Tile(usePosition) }
	local length = extended and 2 or 1

	local tile
	for y = -length, length do
		for x = -length, length do
			if x ~= 0 or y ~= 0 then
				usePosition.x = position.x + x
				usePosition.y = position.y + y

				tile = Tile(usePosition)
				if tile then
					tiles[#tiles + 1] = tile
				end
			end
		end
	end

	for i = 1, #tiles do
		tile = tiles[i]
		if tile:getCreatureCount() == 0 and not tile:hasProperty(CONST_PROP_IMMOVABLEBLOCKSOLID) then
			return tile:getPosition()
		end
	end
	return Position()
end

function Creature:setMonsterOutfit(monster, time)
	local monsterType = MonsterType(monster)
	if not monsterType then
		return false
	end

	if self:isPlayer() and not (getPlayerFlagValue(self, PlayerFlag_CanIllusionAll) or monsterType:isIllusionable()) then
		return false
	end

	local condition = Condition(CONDITION_OUTFIT)
	condition:setOutfit(monsterType:getOutfit())
	condition:setTicks(time)
	self:addCondition(condition)

	return true
end

function Creature:setItemOutfit(item, time)
	local itemType = ItemType(item)
	if not itemType then
		return false
	end

	local condition = Condition(CONDITION_OUTFIT)
	condition:setOutfit({
		lookTypeEx = itemType:getId()
	})
	condition:setTicks(time)
	self:addCondition(condition)

	return true
end

function Creature:addSummon(monster)
	local summon = Monster(monster)
	if not summon then
		return false
	end

	summon:setTarget(nil)
	summon:setFollowCreature(nil)
	summon:setDropLoot(false)
	summon:setMaster(self)
	return true
end

function Creature:removeSummon(monster)
	local summon = Monster(monster)
	if not summon or summon:getMaster() ~= self then
		return false
	end

	summon:setTarget(nil)
	summon:setFollowCreature(nil)
	summon:setDropLoot(true)
	summon:setMaster(nil)
	return true
end

function Creature.getPlayer(self)
	return self:isPlayer() and self or nil
end

function Creature.isItem(self)
	return false
end

function Creature.isMonster(self)
	return false
end

function Creature.isNpc(self)
	return false
end

function Creature.isPlayer(self)
	return false
end

function Creature.isTile(self)
	return false
end

function Creature.isContainer(self)
	return false
end

DAMAGELIST_EXPONENTIAL_DAMAGE = 0
DAMAGELIST_LOGARITHMIC_DAMAGE = 1
DAMAGELIST_VARYING_PERIOD = 2
DAMAGELIST_CONSTANT_PERIOD = 3

function Creature:addDamageCondition(target, type, list, damage, period, rounds)
	if damage <= 0 or not target --[[or target:isImmune(type)--]] then
		return false
	end

	local condition = Condition(type)
	condition:setParameter(CONDITION_PARAM_OWNER, self:getId())
	condition:setParameter(CONDITION_PARAM_DELAYED, true)

	if list == DAMAGELIST_EXPONENTIAL_DAMAGE then
		local exponent, value = -10, 0
		while value < damage do
			value = math.floor(10 * math.pow(1.2, exponent) + 0.5)
			condition:addDamage(1, period or 4000, -value)

			if value >= damage then
				local permille = math.random(10, 1200) / 1000
				condition:addDamage(1, period or 4000, -math.max(1, math.floor(value * permille + 0.5)))
			else
				exponent = exponent + 1
			end
		end
	elseif list == DAMAGELIST_LOGARITHMIC_DAMAGE then
		local n, value = 0, damage
		while value > 0 do
			  value = math.floor(damage * math.pow(2.718281828459, -0.05 * n) + 0.5)
			if value ~= 0 then
				condition:addDamage(1, period or 4000, -value)
				n = n + 1
			end
		end
	elseif list == DAMAGELIST_VARYING_PERIOD then
		for _ = 1, rounds do
			condition:addDamage(1, math.random(period[1], period[2]) * 1000, -damage)
		end
	elseif list == DAMAGELIST_CONSTANT_PERIOD then
		condition:addDamage(rounds, period * 1000, -damage)
	end

	target:addCondition(condition)
	return true
end

--[[
    CLIENTOS_NONE = 0,

    CLIENTOS_LINUX = 1,
    CLIENTOS_WINDOWS = 2,
    CLIENTOS_FLASH = 3,

    CLIENTOS_OTCLIENT_LINUX = 10,
    CLIENTOS_OTCLIENT_WINDOWS = 11,
    CLIENTOS_OTCLIENT_MAC = 12,
]]

local function sendColorText(message, color, pos, send, cid)
    local player = Player(cid)
    if not player then
        return
    end
    -- this could also be handled inside of the calling function instead
    local clientid = player:getClient()['os']
    -- if the player is using otclient
    if clientid > 3 then
        local msg = NetworkMessage()
        msg:addByte(0x84)
        msg:addPosition(pos)
        msg:addByte(color)
        msg:addString(message)
        if send and next(send) then
            for i = 1, #send do
                if pos:getDistance(send[i]:getPosition()) <= 7 then
                    msg:sendToPlayer(send[i])
                end
            end
        end
    end
end

function Creature:sendColorText(message, pos, color, interval, canSee)
    -- Creature:sendColorText(message, position, color[, interval[, canSee]])
    if not self then
        return
    end
   
    local specs = Game.getSpectators(pos, false, true, 0, 8, 0, 6)
    local send = {}
    for i = 1, #specs do
        -- send to specific names
        if (canSee and next(canSee)) and isInArray(canSee, specs[i]:getName()) then
            send[#send+1] = specs[i]
        else
            -- or send it to everyone
            send[#send+1] = specs[i]
        end
    end
    send = (next(send) and send) or specs
    interval = type(color) == 'table' and #color or interval
    for x = 1, interval do
        if type(color) == 'table' then
            addEvent(sendColorText, 1000 * x, message, color[x], pos, send, self:getId())
        else
            addEvent(sendColorText, 1000 * x, message, color, pos, send, self:getId())
        end
    end
    return true
end