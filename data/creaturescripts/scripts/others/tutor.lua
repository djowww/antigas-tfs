function onModalWindow(cid, modalWindowId, buttonId, choiceId)
	if modalWindowId ~= 1000 then
		return true
	end
	cid:unregisterEvent("modalwindowhelper")
	local mensagem = { 
		[3] = "Automatic Tutor: The promotion is worth 10k",
		[4] = "Automatic Tutor: Yes, you can go alone, when you enter the level door you will find a teleport which will take you to the quest prizes.",
		[5] = "Automatic Tutor: The trainer area is only in the Thais temple",
		[6] = "Automatic Tutor: Yes, the bank system exists, you can deposit and withdraw money.",
		[7] = "Automatic Tutor: Paladin ammo is not infinite, but spears and small stones take longer than normal to deplete.",
		[8] = "Automatic Tutor: No, the spears do not fall.",
		[9] = "Automatic Tutor: You get 50% of what you would get from online training (eg 12 hours of offline training = 6 hours of online training).",

	}
	
	if buttonId == 100 and mensagem[choiceId] then
		cid:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, mensagem[choiceId])
	end
	return true
end
