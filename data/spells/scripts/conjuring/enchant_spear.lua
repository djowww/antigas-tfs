function onCastSpell(creature, variant)
	if ItemType(5290):isRetired() then
		creature:sendCancelMessage(RETURNVALUE_NOTPOSSIBLE)
		return false
	end
	return creature:conjureItem(3277, 5290, 1, CONST_ME_MAGIC_GREEN)
end
