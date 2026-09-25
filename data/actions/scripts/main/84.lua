function onUse(player, item, fromPosition, target, toPosition)
	player:teleportTo({x = 32162, y = 32303, z = 8})
	Game.sendMagicEffect({x = 32162, y = 32303, z = 8}, 13)
	return true
end