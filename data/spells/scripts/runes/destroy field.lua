local fieldIds = {
	2118, 2119, 2120, 2121, 2122, 2123, 2124, 2125,
	2126, 2127, 2131, 2132, 2133, 2134, 2135
}

function onCastSpell(creature, variant, isHotkey)
	local position = Variant.getPosition(variant)
	local tile = Tile(position)
	local field = tile and tile:getItemByType(ITEM_TYPE_MAGICFIELD)

	local blockedPositions = {
    Position(32615, 32221, 10),
    Position(32613, 32220, 10),
	Position(32615, 32223, 10)
	}

    if table.contains(blockedPositions, variant:getPosition()) then
        creature:sendCancelMessage(RETURNVALUE_NOTPOSSIBLE)
        variant:getPosition():sendMagicEffect(CONST_ME_POFF)
        return false
    end

	if field and table.contains(fieldIds, field:getId()) then
		field:remove()
		position:sendMagicEffect(CONST_ME_POFF)
		return true
	end

	creature:sendCancelMessage(RETURNVALUE_NOTPOSSIBLE)
	creature:getPosition():sendMagicEffect(CONST_ME_POFF)
	return false
end