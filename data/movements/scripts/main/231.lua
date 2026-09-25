function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() then
		doRelocate(item:getPosition(),{x = 32913, y = 32070, z = 12})
		Game.sendMagicEffect({x = 32913, y = 32070, z = 11}, 13)
	end
end


