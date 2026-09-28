-- Loot is delivered individually by the server; players cannot broadcast here.
function onSpeak(player, type, message)
	player:sendCancelMessage("O canal Loot e somente para leitura.")
	return false
end
