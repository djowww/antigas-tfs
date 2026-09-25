function onRecord(current, old)
	addEvent(broadcastMessage, 150, "New server record: " .. current .. " players are logged in.", MESSAGE_STATUS_DEFAULT)
	return true
end