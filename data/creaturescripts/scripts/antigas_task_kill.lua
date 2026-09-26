function onKill(killer, target)
	if not killer or not target or not killer:isPlayer() or not AntigasTasks.isAuthorized(killer) or not target:isMonster() then
		return true
	end

	local taskId = killer:getStorageValue(AntigasTasks.ACTIVE_STORAGE)
	local task = AntigasTasks.getTask(taskId)
	if not task or target:getName():lower() ~= task.monster:lower() then
		return true
	end

	local progress = math.max(0, killer:getStorageValue(AntigasTasks.PROGRESS_STORAGE))
	progress = math.min(task.count, progress + 1)
	killer:setStorageValue(AntigasTasks.PROGRESS_STORAGE, progress)

	if progress < task.count then
		killer:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, string.format("Task: %s (%d/%d).", task.monster, progress, task.count))
		return true
	end

	-- Clear state before granting rewards so the same completion cannot pay twice.
	killer:setStorageValue(AntigasTasks.ACTIVE_STORAGE, 0)
	killer:setStorageValue(AntigasTasks.PROGRESS_STORAGE, 0)
	killer:unregisterEvent("AntigasTaskKill")
	killer:addExperience(task.experience, true)
	killer:setBankBalance(killer:getBankBalance() + task.gold)
	killer:save()
	killer:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, string.format(
		"Tarefa concluída: %s. Recompensa: %d XP e %d gold depositados no banco. Use !task para escolher outra.",
		task.monster, task.experience, task.gold
	))
	return true
end
