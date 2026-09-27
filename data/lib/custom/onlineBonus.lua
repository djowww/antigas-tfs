-- The storage value is offset-encoded so existing whole-percent values can be
-- migrated in place without another storage key: 1000 + tenths of a percent.
ONLINE_STAY_BONUS_STORAGE = 17592
ONLINE_STAY_BONUS_MAX = 5
ONLINE_STAY_BONUS_SCALE = 10
ONLINE_STAY_BONUS_STEP = 2 -- 0.2 percentage points per uninterrupted hour.
ONLINE_STAY_BONUS_STORAGE_OFFSET = 1000
ONLINE_STAY_BONUS_XP_REMAINDER_STORAGE = 17600
ONLINE_STAY_BONUS_SKILL_REMAINDER_BASE = 17601
ONLINE_STAY_BONUS_DENOMINATOR = 100 * ONLINE_STAY_BONUS_SCALE

function Player:getOnlineStayBonusUnits()
	local stored = math.max(0, self:getStorageValue(ONLINE_STAY_BONUS_STORAGE))
	local maxUnits = ONLINE_STAY_BONUS_MAX * ONLINE_STAY_BONUS_SCALE
	local encodedMax = ONLINE_STAY_BONUS_STORAGE_OFFSET + maxUnits

	if stored < ONLINE_STAY_BONUS_STORAGE_OFFSET then
		-- Before the fractional system, the same key held 0..24 whole percent.
		local legacyPercent = math.min(ONLINE_STAY_BONUS_MAX, stored)
		stored = ONLINE_STAY_BONUS_STORAGE_OFFSET + legacyPercent * ONLINE_STAY_BONUS_SCALE
		self:setStorageValue(ONLINE_STAY_BONUS_STORAGE, stored)
	elseif stored > encodedMax then
		stored = encodedMax
		self:setStorageValue(ONLINE_STAY_BONUS_STORAGE, stored)
	end

	return stored - ONLINE_STAY_BONUS_STORAGE_OFFSET
end

function Player:setOnlineStayBonusUnits(units)
	local maxUnits = ONLINE_STAY_BONUS_MAX * ONLINE_STAY_BONUS_SCALE
	units = math.floor(tonumber(units) or 0)
	units = math.max(0, math.min(maxUnits, units))
	self:setStorageValue(ONLINE_STAY_BONUS_STORAGE, ONLINE_STAY_BONUS_STORAGE_OFFSET + units)
	return units
end

-- Carry fractional bonus gains between events so small XP/skill awards still
-- receive the advertised percentage instead of being rounded away each time.
function Player:applyOnlineStayBonus(amount, remainderStorage)
	local bonusUnits = self:getOnlineStayBonusUnits()
	if bonusUnits == 0 then
		return 0
	end

	local denominator = ONLINE_STAY_BONUS_DENOMINATOR
	local remainder = math.max(0, math.min(denominator - 1, self:getStorageValue(remainderStorage)))
	local numerator = math.floor(math.max(0, amount) * bonusUnits + remainder + 1e-9)
	local extra = math.floor(numerator / denominator)
	self:setStorageValue(remainderStorage, numerator - extra * denominator)
	return extra
end
