local combat = Combat()
combat:setParameter(COMBAT_PARAM_EFFECT, CONST_ME_MAGIC_RED)

function onCastSpell(creature, variant)
    if creature:getMaster() then
        return true
    end
	
	local target = creature:getTarget()
	if target ~= nil then
		
		local creaturePos = creature:getPosition()
		local spectators = Game.getSpectators(creaturePos, false, false, 11, 11, 11, 11)
		local candidates = {}
		for _, spectator in ipairs(spectators) do
			if spectator ~= target and spectator ~= creature then candidates[#candidates+1] = spectator end
		end
		if #candidates == 0 then return false end
		local someoneInRoom = candidates[math.random(1,#candidates)]
		local someoneInRoomPos = someoneInRoom:getPosition()

		someoneInRoomPos:sendMagicEffect(CONST_ME_POFF)
		creaturePos:sendMagicEffect(CONST_ME_POFF)

		creature:teleportTo(Position(someoneInRoomPos.x,someoneInRoomPos.y,someoneInRoomPos.z))
		someoneInRoom:teleportTo(creaturePos)

		return combat:execute(creature, variant)
	end
	return false
end
