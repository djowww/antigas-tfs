function onKill(killer, target)
	return AntigasAchievements.onKill(killer, target)
end

function onDeath(player, corpse, killer, mostDamageKiller, unjustified, mostDamageUnjustified)
	return AntigasAchievements.onDeath(player, corpse, killer, mostDamageKiller, unjustified, mostDamageUnjustified)
end

function onAdvance(player, skill, oldLevel, newLevel)
	return AntigasAchievements.onAdvance(player, skill, oldLevel, newLevel)
end

function onExtendedOpcode(player, opcode, buffer)
	return AntigasAchievements.onExtendedOpcode(player, opcode, buffer)
end
