local statues = {
	[5282] = SKILL_SWORD,
	[5281] = SKILL_AXE,
	[5280] = SKILL_CLUB,
	[5283] = SKILL_DISTANCE,
	[5284] = SKILL_MAGLEVEL
}

function onUse(player, item, fromPosition, target, toPosition, isHotkey)
	local skill = statues[item:getId()]
	if not player:isPremium() then
		player:sendTextMessage(MESSAGE_STATUS_SMALL, Game.getReturnMessage(RETURNVALUE_YOUNEEDPREMIUMACCOUNT))
		return true
	end

	if player:isPzLocked() then
		return false
	end

	player:setOfflineTrainingSkill(skill)
	player:remove()
	return true
end
