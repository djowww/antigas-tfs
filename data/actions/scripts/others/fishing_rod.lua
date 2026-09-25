local water = {
	4597, 4598, 4599, 4600, 4601, 4602,
	4609, 4610, 4611, 4612, 4613, 4614,
	4615, 4616, 4617, 4618, 4619, 4620,
	
}

local fishableWater = {
	4597, 4598, 4599, 4600, 4601, 4602,
	4609, 4610, 4611, 4612, 4613, 4614,
	4615, 4616, 4617, 4618, 4619, 4620,
}

local fakeWater = 622

function onUse(player, item, fromPosition, target, toPosition)
	if not target:isItem() then
		return false
	end
	
	if (target:getId() == fakeWater) then 
		target:getPosition():sendMagicEffect(CONST_ME_LOSEENERGY)
		return true
	end
	if not table.contains(water, target:getId()) then
		return false
	end
	
	if not Tile(player:getPosition()):hasFlag(TILESTATE_PROTECTIONZONE) then
	player:addSkillTries(SKILL_FISHING, 1)
			if math.random(1, 100) <= math.min(math.max(10 + (player:getEffectiveSkillLevel(SKILL_FISHING) - 10) * 0.597, 10), 50) then
				player:addItem(3578, 1)
			 end
		end

	target:getPosition():sendMagicEffect(2)
	return true
end