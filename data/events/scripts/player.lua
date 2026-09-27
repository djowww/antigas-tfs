DISABLE_CONTAINER_WEIGHT = 0 -- 0 = ENABLE CONTAINER WEIGHT CHECK | 1 = DISABLE CONTAINER WEIGHT CHECK
CONTAINER_WEIGHT = 1000000 -- 1000000 = 10k = 10000.00 oz | this function is only for containers, item below the weight determined here can be moved inside the container, for others items look game.cpp at the src

function Player:onLook(thing, position, distance)
	local description = "You see " .. thing:getDescription(distance)
	if self:getGroup():getAccess() then
		if thing:isItem() then
			description = string.format("%s\nItem ID: %d", description, thing:getId())

			local actionId = thing:getActionId()
			if actionId ~= 0 then
				description = string.format("%s, Action ID: %d", description, actionId)
			end

			local uniqueId = thing:getAttribute(ITEM_ATTRIBUTE_MOVEMENTID)
			if uniqueId > 0 and uniqueId < 65536 then
				description = string.format("%s, Movement ID: %d", description, uniqueId)
			end

			local itemType = thing:getType()

			local transformEquipId = itemType:getTransformEquipId()
			local transformDeEquipId = itemType:getTransformDeEquipId()
			if transformEquipId ~= 0 then
				description = string.format("%s\nTransforms to: %d (onEquip)", description, transformEquipId)
			elseif transformDeEquipId ~= 0 then
				description = string.format("%s\nTransforms to: %d (onDeEquip)", description, transformDeEquipId)
			end

			local decayId = itemType:getDecayId()
			if decayId ~= -1 then
				description = string.format("%s\nDecays to: %d", description, decayId)
			end
			if thing:getAttribute(ITEM_ATTRIBUTE_DECAYSTATE) == 1 then
				description = string.format("%s\nDecaying in %d minutes (%d seconds).", description, thing:getAttribute(ITEM_ATTRIBUTE_DURATION) / 1000 / 60, thing:getAttribute(ITEM_ATTRIBUTE_DURATION) / 1000)
			end
		elseif thing:isCreature() then
			local str = "%s\nHealth: %d / %d"
			if thing:isPlayer() and thing:getMaxMana() > 0 then
				str = string.format("%s, Mana: %d / %d", str, thing:getMana(), thing:getMaxMana())
			end
			description = string.format(str, description, thing:getHealth(), thing:getMaxHealth()) .. "."
		end

		local position = thing:getPosition()
		description = string.format(
			"%s\nPosition: %d, %d, %d",
			description, position.x, position.y, position.z
		)

		if thing:isCreature() then
			if thing:isPlayer() then
				description = string.format("%s\nIP: %s.", description, Game.convertIpToString(thing:getIp()))
			end
		end
	end
	
	self:sendTextMessage(MESSAGE_INFO_DESCR, description)
end

function Player:onLookInBattleList(creature, distance)
	local description = "You see " .. creature:getDescription(distance)
	if self:getGroup():getAccess() then
		local str = "%s\nHealth: %d / %d"
		if creature:isPlayer() and creature:getMaxMana() > 0 then
			str = string.format("%s, Mana: %d / %d", str, creature:getMana(), creature:getMaxMana())
		end
		description = string.format(str, description, creature:getHealth(), creature:getMaxHealth()) .. "."

		local position = creature:getPosition()
		description = string.format(
			"%s\nPosition: %d, %d, %d",
			description, position.x, position.y, position.z
		)

		if creature:isPlayer() then
			description = string.format("%s\nIP: %s", description, Game.convertIpToString(creature:getIp()))
		end
	end
	self:sendTextMessage(MESSAGE_INFO_DESCR, description)
end

function Player:onLookInTrade(partner, item, distance)
	self:sendTextMessage(MESSAGE_INFO_DESCR, "You see " .. item:getDescription(distance))
end

function Player:onMoveItem(item, count, fromPosition, toPosition, fromCylinder, toCylinder)
	local t = fromCylinder and Tile(fromCylinder:getPosition())
	local corpse = t and t:getTopDownItem()
	
	if corpse then
		local itemType = corpse:getType()
		if itemType:isCorpse() and toPosition.x == CONTAINER_POSITION then
			self:checkAnalyzerLootItem(item:getId(), count)
			
			local dropAnalyzer = {}
				table.insert(dropAnalyzer, item:getName())
			table.insert(dropAnalyzer, count)
				table.insert(dropAnalyzer, item:getId())
			self:addAnalyzerDrop(dropAnalyzer)
		end
	end
	
	-- No move parcel very heavy
	if DISABLE_CONTAINER_WEIGHT == 0 and ItemType(item:getId()):isContainer() and item:getWeight() > CONTAINER_WEIGHT then
		self:sendCancelMessage("Your cannot move this item too heavy.")
		return false
	end
	
	return true
end

function Player:onItemMoved(item, count, fromPosition, toPosition, fromCylinder, toCylinder)
end

function Player:onMoveCreature(creature, fromPosition, toPosition)
	if creature and creature:getId() == self:getId() then
		local position = self:getPosition()
		-- The movement callback is also used before a pushed creature moves.
		-- Count only the post-move callback emitted by the walk path.
		if position.x == toPosition.x and position.y == toPosition.y and position.z == toPosition.z then
			AntigasAchievements.onWalk(self, fromPosition, toPosition)
		end
	end
	return true
end

function Player:onReportBug(message, position, category)
	if self:getAccountType() == ACCOUNT_TYPE_NORMAL then
		return false
	end

	local name = self:getName()
	local file = io.open("data/reports/bugs/" .. name .. " report.txt", "a")

	if not file then
		self:sendTextMessage(MESSAGE_EVENT_DEFAULT, "There was an error when processing your report, please contact a gamemaster.")
		return true
	end

	file:write("------------------------------\n")
	file:write("Name: " .. name)
	if category == BUG_CATEGORY_MAP then
		file:write(" [Map position: " .. position.x .. ", " .. position.y .. ", " .. position.z .. "]")
	end
	local playerPosition = self:getPosition()
	file:write(" [Player Position: " .. playerPosition.x .. ", " .. playerPosition.y .. ", " .. playerPosition.z .. "]\n")
	file:write("Comment: " .. message:sub(1,4096) .. "\n")
	file:close()

	self:sendTextMessage(MESSAGE_EVENT_DEFAULT, "Your report has been sent to " .. configManager.getString(configKeys.SERVER_NAME) .. ".")
	return true
end

function Player:onTurn(direction)
    if self:getGroup():getAccess() and self:getDirection() == direction then
        local nextPosition = self:getPosition()
        nextPosition:getNextPosition(direction)

        self:teleportTo(nextPosition, true)
    end

    return true
end

function Player:onTradeAccept(target, item, targetItem)
	return true
end

local soulCondition = Condition(CONDITION_SOUL, CONDITIONID_DEFAULT)
soulCondition:setTicks(4 * 60 * 1000)
soulCondition:setParameter(CONDITION_PARAM_SOULGAIN, 1)

local function getExpForLevel(level)
	level = level - 1
	return ((50 * level * level * level) - (150 * level * level) + (400 * level)) / 3
end

function Player:onGainExperience(source, exp, rawExp)
	if not source or source:isPlayer() then
		return exp
	end
	
	-- Premium
	--local xpPremium = 0
	--if self:isPremium() then
		--xpPremium = exp * 0.2 -- +20% XP
	--end
	
	-- Soul regeneration
	local vocation = self:getVocation()
	if self:getSoul() < vocation:getMaxSoul() and exp >= self:getLevel() then
		soulCondition:setParameter(CONDITION_PARAM_SOULTICKS, vocation:getSoulGainTicks() * 1000)
		self:addCondition(soulCondition)
	end

	-- Apply experience stage multiplier
	exp = exp * Game.getExperienceStage(self:getLevel())
	
	local multiplier = 1.1
    if self:getStorageValue(17754) == 1 then
        exp = exp * multiplier
    end
	
	if self:getStorageValue(1234) >= os.time() then
    exp = exp * 1.25
    end

	local onlineBonusExtra = self:applyOnlineStayBonus(exp, ONLINE_STAY_BONUS_XP_REMAINDER_STORAGE)
	local bestiaryBonusExtra = self:applyBestiaryExperienceBonus(exp)
	exp = exp + onlineBonusExtra + bestiaryBonusExtra
	
	-- Custom Lines
    if getGlobalStorageValue(17589) > os.time() then
        exp = exp * (1 + getGlobalStorageValue(17585) / 100)
    end
    -- Custom Lines
	
	-- Report final gained experience and a non-negative amount to the next level.
	local expForLevel = getExpForLevel(self:getLevel() + 1)
	if expForLevel >= 1 then
		self:addAnalyzerExp(exp, math.max(0, expForLevel - self:getExperience() - exp))
	end
	return exp
end

function Player:onLoseExperience(exp)
	return exp
end

function Player:onGainSkillTries(skill, tries)
    local remainderStorage = ONLINE_STAY_BONUS_SKILL_REMAINDER_BASE + skill
    if APPLY_SKILL_MULTIPLIER == false then
        local onlineBonusExtra = self:applyOnlineStayBonus(tries, remainderStorage)
        return tries + onlineBonusExtra
    end

    if skill == SKILL_MAGLEVEL then
        tries = tries * configManager.getNumber(configKeys.RATE_MAGIC)
        -- Custom Lines
        if getGlobalStorageValue(17591) > os.time() then
            tries = tries * (1 + getGlobalStorageValue(17587) / 100)
        end
        -- Custom Lines
        local onlineBonusExtra = self:applyOnlineStayBonus(tries, remainderStorage)
        return tries + onlineBonusExtra
    end
    
    tries = tries * configManager.getNumber(configKeys.RATE_SKILL)
    -- Custom Lines
    if getGlobalStorageValue(17590) > os.time() then
        tries = tries * (1 + getGlobalStorageValue(17586) / 100)
    end
    -- Custom Lines
    local onlineBonusExtra = self:applyOnlineStayBonus(tries, remainderStorage)
    return tries + onlineBonusExtra
end

function Player:onUseItem(item, target)
    -- Consumption is reported by the engine after the actual item/charge change.
    -- This hook remains available for permission checks, never for counting clicks.
    return true
end

function Player:onRemoveCount(item, count)
    return true
end
