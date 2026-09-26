function onSay(player, words, param)
	if not AntigasTasks.isAuthorized(player) then
		player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "Este comando é exclusivo da equipe.")
		return true
	end

	local activeTaskId = player:getStorageValue(AntigasTasks.ACTIVE_STORAGE)
	local modal = ModalWindow(AntigasTasks.MAIN_MODAL_ID, "Antigas Tasks", "")
	modal:setPriority(true)

	if activeTaskId > 0 then
		local task = AntigasTasks.getTask(activeTaskId)
		if not task then
			player:setStorageValue(AntigasTasks.ACTIVE_STORAGE, 0)
			player:setStorageValue(AntigasTasks.PROGRESS_STORAGE, 0)
			player:unregisterEvent("AntigasTaskKill")
			activeTaskId = 0
		else
			local progress = math.max(0, math.min(task.count, player:getStorageValue(AntigasTasks.PROGRESS_STORAGE)))
			modal:setMessage(string.format(
				"Tarefa atual: %s\nProgresso: %d/%d\n\nRecompensa: %d XP e %d gold no banco.",
				task.monster, progress, task.count, task.experience, task.gold
			))
			modal:addButton(1, "Abandonar")
			modal:addButton(2, "Fechar")
			modal:setDefaultEnterButton(2)
			modal:setDefaultEscapeButton(2)
			modal:sendToPlayer(player)
			return true
		end
	end

	modal:setMessage("Escolha uma tarefa. Cada personagem pode manter uma tarefa ativa por vez.\nApenas monstros mortos por você contam.")
	for taskId, task in ipairs(AntigasTasks.DEFINITIONS) do
		modal:addChoice(taskId, string.format("%s - %d mortes | %d XP + %d gold no banco", task.monster, task.count, task.experience, task.gold))
	end
	modal:addButton(1, "Aceitar")
	modal:addButton(2, "Fechar")
	modal:setDefaultEnterButton(1)
	modal:setDefaultEscapeButton(2)
	modal:sendToPlayer(player)
	return true
end
