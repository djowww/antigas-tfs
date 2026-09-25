function onUse(player, item, fromPosition, target, toPosition)
	if item:getId() == 2772 then 
		item:transform(2773, 1)
		item:decay()
		Game.removeItemOnMap({x = 32824, y = 32229, z = 12}, 1791)
	elseif item:getId() == 2773 then 
		item:transform(2772, 1)
		item:decay()
		doRelocate({x = 32824, y = 32229, z = 12},{x = 32824, y = 32229, z = 12})
		Game.createItem(1791, 1, {x = 32824, y = 32229, z = 12})
	end
	return true
end