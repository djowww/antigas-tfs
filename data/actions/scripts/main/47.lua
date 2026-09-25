function onUse(player, item, fromPosition, target, toPosition)
	if item:getId() == 2772 then 
		item:transform(2773, 1)
		item:decay()
		Game.removeItemOnMap({x = 32623, y = 32188, z = 9}, 2536)
		Game.createItem(2536, 1, {x = 32623, y = 32189, z = 9})
	elseif item:getId() == 2773 then 
		item:transform(2772, 1)
		item:decay()
		Game.removeItemOnMap({x = 32623, y = 32189, z = 9}, 2536)
		Game.createItem(2536, 1, {x = 32623, y = 32188, z = 9})
	end
	return true
end