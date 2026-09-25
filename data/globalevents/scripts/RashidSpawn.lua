local config = {
	['Monday'] = Position(32047, 31572, 7),  -- Folda
	['Tuesday'] = Position(32936, 32076, 7), -- Venore
	['Wednesday'] = Position(32363, 32205, 7), --Thais
	['Thursday'] = Position(33066, 32880, 6),
	['Friday'] = Position(33239, 32483, 7),
	['Saturday'] = Position(33171, 31810, 6),
	['Sunday'] = Position(32335, 31782, 6)
}

-- Should Rashid spawn as in real tibia?
local spawnByDay = true

function onStartup()
	if spawnByDay then
		local npc = Game.createNpc('rashid', config[os.date('%A')], false, true)
		if npc then
			npc:setMasterPos(config[os.date('%A')])
		end
	else
		local npc
		for k, position in pairs(config) do
			npc = Game.createNpc('rashid', position, false, true)
			if npc then
				npc:setMasterPos(position)
			end
		end
	end

	return true
end
