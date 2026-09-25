function onStepIn(creature, item, position, fromPosition)
	if creature:isPlayer() then 
		doRelocate(item:getPosition(),{x = 32098, y = 32318, z = 09})
		Game.sendMagicEffect({x = 32169, y = 32302, z = 07}, 13)
	end
end