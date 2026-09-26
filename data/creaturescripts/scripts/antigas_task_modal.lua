function onModalWindow(player, modalWindowId, buttonId, choiceId)
	if not AntigasTasks.isAuthorized(player) then
		return true
	end

	if modalWindowId == AntigasTasks.ABANDON_MODAL_ID then
		if buttonId == 1 then
			player:setStorageValue(AntigasTasks.ACTIVE_STORAGE, 0)
			player:setStorageValue(AntigasTasks.PROGRESS_STORAGE, 0)
			player:unregisterEvent("AntigasTaskKill")
			player:save()
			player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "Tarefa abandonada.")
		end
		return true
	end

	if modalWindowId ~= AntigasTasks.MAIN_MODAL_ID then
		return true
	end

	local activeTaskId = player:getStorageValue(AntigasTasks.ACTIVE_STORAGE)
	if activeTaskId > 0 then
		if buttonId ~= 1 then
			return true
		end

		local confirm = ModalWindow(AntigasTasks.ABANDON_MODAL_ID, "Abandonar tarefa?", "Seu progresso atual será perdido. Deseja realmente abandonar?")
		confirm:addButton(1, "Sim")
		confirm:addButton(2, "Não")
		confirm:setDefaultEnterButton(2)
		confirm:setDefaultEscapeButton(2)
		confirm:setPriority(true)
		confirm:sendToPlayer(player)
		return true
	end

	if buttonId ~= 1 then
		return true
	end

	local task = AntigasTasks.getTask(choiceId)
	if not task then
		player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "Seleção inválida. Use !task para tentar novamente.")
		return true
	end

	-- Recheck state and authorization at acceptance; the modal response is client input.
	if not AntigasTasks.isAuthorized(player) or player:getStorageValue(AntigasTasks.ACTIVE_STORAGE) > 0 then
		return true
	end

	player:setStorageValue(AntigasTasks.ACTIVE_STORAGE, choiceId)
	player:setStorageValue(AntigasTasks.PROGRESS_STORAGE, 0)
	player:registerEvent("AntigasTaskKill")
	player:save()
	player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, string.format("Tarefa aceita: derrote %d %s. Use !task para acompanhar o progresso.", task.count, task.monster))
	return true
end
