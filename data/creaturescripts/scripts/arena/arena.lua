function onDeath(creature, corpse, killer, mostDamageKiller, unjustified, mostDamageUnjustified)
    if creature:isPlayer() or creature:getMaster() then
        return true
    end

	local monsterName = creature:getName():lower()
	local creatures = {
						['medusa'] = {next='Kratos',nextPos=Position(6219,5930,7)},
						['kratos'] = {next='reaper',nextPos=Position(6238,5930,7)},
						['reaper'] = {next='Shadow',nextPos=Position(6257,5930,7)},
						['shadow'] = {next='GOD',nextPos=Position(6276,5930,7),message='There is only one way to kill GOD'},
						['gaia'] = {nextPos=Position(6156,5955,7),storage=7300},


						['drasilla'] = {next='Grimgor Guteater',nextPos=Position(31941,31451,7)},
						['grimgor guteater'] = {next='Spirit of Fire',nextPos=Position(31960,31451,7)},
						['spirit of fire'] = {next='The Dark Dancer',nextPos=Position(31979,31451,7)},
						['the dark dancer'] = {next='Tentacles',nextPos=Position(31998,31451,7)},
						['tentacles'] = {nextPos=Position(31883,31458,7),storage=7200},

						['achad'] = {next='Colerian the Barbarian',nextPos=Position(31941,31466,7)},
						['colerian the barbarian'] = {next='Orcus the Cruel',nextPos=Position(31960,31466,7)},
						['orcus the cruel'] = {next='Rocky',nextPos=Position(31979,31466,7)},
						['rocky'] = {next='The Hairy One',nextPos=Position(31998,31466,7)},
						['the hairy one'] = {nextPos=Position(31874,31457,7),storage=7100},
					}
	if creatures[monsterName] then
		local arenaPos = creatures[monsterName]
		if arenaPos.nextPos then
			killer:teleportTo(arenaPos.nextPos)
			arenaPos.nextPos:sendMagicEffect(CONST_ME_MAGIC_RED)
		end
		if arenaPos.storage then
			killer:setStorageValue(arenaPos.storage,2)
		end
		if arenaPos.next then
			Game.createMonster(arenaPos.next,Position(arenaPos.nextPos.x+8,arenaPos.nextPos.y,arenaPos.nextPos.z))
		end
		if arenaPos.message then
			killer:sendTextMessage(MESSAGE_EVENT_ADVANCE , arenaPos.message)
		end
	end
	return true
end