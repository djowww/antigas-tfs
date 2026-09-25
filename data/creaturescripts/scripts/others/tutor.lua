function onModalWindow(cid, modalWindowId, buttonId, choiceId)
	cid:unregisterEvent("modalwindowhelper")
	local mensagem = { 
		[1] = "Automatic Tutor: Task NPCs are found in all Antiga cities, the common location is near the depot.", -- aqui é voce vai adicionar as respostas respeitando a sequencia
		[2] = "Automatic Tutor: The maximum number of tasks you can do per monster is 2.",
		[3] = "Automatic Tutor: The promotion is worth 10k",
		[4] = "Automatic Tutor: Yes, you can go alone, when you enter the level door you will find a teleport which will take you to the quest prizes.",
		[5] = "Automatic Tutor: The trainer area is only in the Thais temple",
		[6] = "Automatic Tutor: Yes, the bank system exists, you can deposit and withdraw money.",
		[7] = "Automatic Tutor: Paladin ammo is not infinite, but spears and small stones take longer than normal to deplete.",
		[8] = "Automatic Tutor: No, the spears do not fall.",
		[9] = "Automatic Tutor: You get 50% of what you would get from online training (eg 12 hours of offline training = 6 hours of online training).",

	}
	
	if modalWindowId == 1000 then
		if buttonId == 100 then
			for x = 1,#mensagem do
				if choiceId == x then
					cid:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, mensagem[x]) 			
				end
			end	
		end
	end
end
