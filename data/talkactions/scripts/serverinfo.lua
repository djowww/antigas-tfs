function onSay(player, words, param)
	player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "Imperium Info:"
					.. "\nExp rate: " .. Game.getExperienceStage(player:getLevel())
					.. "\nSkill rate: " .. configManager.getNumber(configKeys.RATE_SKILL)
					.. "\nMagic rate: " .. configManager.getNumber(configKeys.RATE_MAGIC)
					.. "\nRunes rate: " .. configManager.getNumber(configKeys.RATE_MAGIC)
					.. "\nRegen rate: " .. configManager.getNumber(configKeys.RATE_MAGIC)
					.. "\nLoot rate: " .. configManager.getNumber(configKeys.RATE_LOOT))
	return false
end
