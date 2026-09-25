function onLogin(cid)
	local player = Player(cid)
	if not player then
		return true
	end

	if player:getStorageValue(7895412) ~= 1 then
		player:setStorageValue(7895412, 1)
		player:popupFYI("Seja bem-vindo ao Das Antigas...")
	end
	return true
end
