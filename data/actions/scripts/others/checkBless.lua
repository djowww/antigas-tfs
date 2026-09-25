local blessings = {
	{id = 1, name = 'The Spiritual Shielding'},
	{id = 2, name = 'The Embrace of Tibia'},
	{id = 3, name = 'The Fire of the Suns'},
	{id = 4, name = 'The Spark of the Phoenix'},
	{id = 5, name = 'The Wisdom of Solitude'}
}

function onUse(player, item, fromPosition, target, toPosition, isHotkey)

	local result, bless = 'Received blessings:'
	for i = 1, #blessings do
		bless = blessings[i]
		result = player:hasBlessing(bless.id) and result .. '\n' .. bless.name or result
	end
	player:sendTextMessage(MESSAGE_EVENT_ADVANCE, 20 > result:len() and 'No blessings received.' or result)
	return true
end
