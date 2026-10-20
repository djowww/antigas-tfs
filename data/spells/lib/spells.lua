function healingFormula(level, maglevel, base, variation)
	local value = 2 * level + (3 * maglevel)
	local min = value - math.random(variation) + base / 100
	local max = value + math.random(variation) + base / 100
	return min, max
end

-- One integer roll precedes both factor scaling and integer truncation.
function legacySpellForce(level, magicLevel, base, variation, clamp)
 local factor = 2 * level + 3 * magicLevel
 if clamp == "minimum" then factor = math.max(factor, 100)
 elseif clamp == "maximum" then factor = math.min(factor, 100) end
 return math.floor((base + math.random(-variation, variation)) * factor / 100)
end

function damageFormula(level, magicLevel, base, variation, clamp)
 local amount = -legacySpellForce(level, magicLevel, base, variation, clamp)
 return amount, amount
end

---------------------------------------------------------------------------------------

AREA_WAVE3 = {
{1, 1, 1},
{1, 1, 1},
{0, 3, 0}
}

AREA_WAVE4 = {
{1, 1, 1, 1, 1},
{0, 1, 1, 1, 0},
{0, 1, 1, 1, 0},
{0, 0, 3, 0, 0}
}

AREA_WAVE6 = {
{0, 0, 0, 0, 0},
{0, 1, 3, 1, 0},
{0, 0, 0, 0, 0}
}

AREA_SQUAREWAVE5 = {
{1, 1, 1},
{1, 1, 1},
{1, 1, 1},
{0, 1, 0},
{0, 3, 0}
}

AREA_SQUAREWAVE6 = {
{0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0},
{0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0},
{0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0},
{0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0},
{0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0},
{0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0},
{0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0},
{0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0},
{0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0},
{0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0},
{0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0},
{0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0}
}

AREA_SQUAREWAVE7 = {
{0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0},
{0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0},
{0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0},
{0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0},
{0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0},
{0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0},
{0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0},
{0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0},
{0, 0, 0, 0, 1, 1, 1, 0, 0, 0, 0},
{0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0},
{0, 0, 0, 0, 0, 3, 0, 0, 0, 0, 0}
}

--Diagonal waves
AREADIAGONAL_WAVE4 = {
{0, 0, 0, 0, 1, 0},
{0, 0, 0, 1, 1, 0},
{0, 0, 1, 1, 1, 0},
{0, 1, 1, 1, 1, 0},
{1, 1, 1, 1, 1, 0},
{0, 0, 0, 0, 0, 3}
}

AREADIAGONAL_SQUAREWAVE5 = {
{1, 1, 1, 0, 0},
{1, 1, 1, 0, 0},
{1, 1, 1, 0, 0},
{0, 0, 0, 1, 0},
{0, 0, 0, 0, 3}
}

AREADIAGONAL_WAVE6 = {
{0, 0, 1},
{0, 3, 0},
{1, 0, 0}
}

--Beams
AREA_BEAM1 = {
{3}
}

AREA_BEAM5 = {
{1},
{1},
{1},
{1},
{3}
}

AREA_BEAM7 = {
{1},
{1},
{1},
{1},
{1},
{1},
{3}
}

AREA_BEAM8 = {
{1},
{1},
{1},
{1},
{1},
{1},
{1},
{3}
}

--Diagonal Beams
AREADIAGONAL_BEAM5 = {
{1, 0, 0, 0, 0},
{0, 1, 0, 0, 0},
{0, 0, 1, 0, 0},
{0, 0, 0, 1, 0},
{0, 0, 0, 0, 3}
}

AREADIAGONAL_BEAM7 = {
{1, 0, 0, 0, 0, 0, 0},
{0, 1, 0, 0, 0, 0, 0},
{0, 0, 1, 0, 0, 0, 0},
{0, 0, 0, 1, 0, 0, 0},
{0, 0, 0, 0, 1, 0, 0},
{0, 0, 0, 0, 0, 1, 0},
{0, 0, 0, 0, 0, 0, 3}
}

--Circles
AREA_CIRCLE2X2 = {
{0, 1, 1, 1, 0},
{1, 1, 1, 1, 1},
{1, 1, 3, 1, 1},
{1, 1, 1, 1, 1},
{0, 1, 1, 1, 0}
}

AREA_CIRCLE3X3 = {
{0, 0, 1, 1, 1, 0, 0},
{0, 1, 1, 1, 1, 1, 0},
{1, 1, 1, 1, 1, 1, 1},
{1, 1, 1, 3, 1, 1, 1},
{1, 1, 1, 1, 1, 1, 1},
{0, 1, 1, 1, 1, 1, 0},
{0, 0, 1, 1, 1, 0, 0}
}

-- Crosses
AREA_CROSS1X1 = {
{0, 1, 0},
{1, 3, 1},
{0, 1, 0}
}

AREA_CIRCLE5X5 = {
{0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0},
{0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0},
{0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0},
{0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0},
{0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0},
{1, 1, 1, 1, 1, 3, 1, 1, 1, 1, 1},
{0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0},
{0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0},
{0, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0},
{0, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0},
{0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0}
}

--Squares
AREA_SQUARE1X1 = {
{1, 1, 1},
{1, 3, 1},
{1, 1, 1}
}

-- Walls
AREA_WALLFIELD = {
{1, 1, 3, 1, 1}
}

AREADIAGONAL_WALLFIELD = {
{0, 0, 0, 0, 1},
{0, 0, 0, 1, 1},
{0, 1, 3, 1, 0},
{1, 1, 0, 0, 0},
{1, 0, 0, 0, 0},
}

function Player:conjureItem(reagentId, conjureId, conjureCount, effect)
	if ItemType(conjureId):isRetired() then
		self:sendCancelMessage(RETURNVALUE_NOTPOSSIBLE)
		return false
	end
	if not conjureCount and conjureId ~= 0 then
		local itemType = ItemType(conjureId)
		if itemType:getId() == 0 then
			return false
		end

		local charges = itemType:getCharges()
		if charges ~= 0 then
			conjureCount = charges
		end
	end

	if reagentId ~= 0 and not self:removeItem(reagentId, 1, -1) then
		self:sendCancelMessage(RETURNVALUE_YOUNEEDAMAGICITEMTOCASTSPELL)
		self:getPosition():sendMagicEffect(CONST_ME_POFF)
		return false
	end

	local item = self:addItem(conjureId, conjureCount)
	if not item then
		self:sendCancelMessage(RETURNVALUE_NOTPOSSIBLE)
		self:getPosition():sendMagicEffect(CONST_ME_POFF)
		return false
	end

	if item:hasAttribute(ITEM_ATTRIBUTE_DURATION) then
		item:decay()
	end

	self:getPosition():sendMagicEffect(item:getType():isRune() and CONST_ME_MAGIC_RED or effect)
	return true
end
