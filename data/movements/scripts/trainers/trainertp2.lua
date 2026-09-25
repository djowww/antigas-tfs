local storage = 5845
	
function onStepIn(creature, item, position, fromPosition)
	if not creature:isPlayer() then
		return false
	end
	doRelocate(item:getPosition(),{x = 32369, y = 32241, z = 07})
	Game.sendMagicEffect({x = 32369, y = 32241, z = 07}, CONST_ME_TELEPORT)
	creature:setStorageValue(storage, os.time() + 5)

	return true
end