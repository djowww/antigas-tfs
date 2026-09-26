AntigasTasks = {
	ACTIVE_STORAGE = 20740001,
	PROGRESS_STORAGE = 20740002,
	MAIN_MODAL_ID = 20740101,
	ABANDON_MODAL_ID = 20740102,

	DEFINITIONS = {
		{monster = "Rat", count = 25, experience = 250, gold = 100},
		{monster = "Rotworm", count = 50, experience = 1000, gold = 500},
		{monster = "Minotaur", count = 50, experience = 2500, gold = 1500},
		{monster = "Dragon", count = 25, experience = 7500, gold = 4000}
	}
}

function AntigasTasks.isAuthorized(player)
	return player ~= nil and player:getGroup() ~= nil and player:getGroup():getAccess()
end

function AntigasTasks.getTask(taskId)
	if type(taskId) ~= "number" or taskId < 1 or taskId > #AntigasTasks.DEFINITIONS then
		return nil
	end
	return AntigasTasks.DEFINITIONS[taskId]
end
