function doDestroyItem(target)
	-- A simple use/no target can pass a position table rather than an Item.
	if not target or type(target.isItem) ~= 'function' or not target:isItem() then
		return false
	end

	local itemType = ItemType(target:getId())
	if not itemType:isDestroyable() then
		return false
	end
	
	if math.random(1,10) <= 3 then
		target:transform(itemType:getDestroyTarget())
		target:decay()
		target:getPosition():sendMagicEffect(CONST_ME_BLOCKHIT)
	else
		target:getPosition():sendMagicEffect(CONST_ME_POFF)
	end
	
	return true
end
