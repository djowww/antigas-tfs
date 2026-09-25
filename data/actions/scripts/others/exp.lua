function onUse(cid, item, fromPosition, itemEx, toPosition)
    local player = Player(cid)
    if player:getStorageValue(1234) >= os.time() then
         player:sendTextMessage(MESSAGE_EVENT_ADVANCE, 'You already 25% exp! expire '..os.date ("%d %B %Y %X ",player:getStorageValue(1234)))
        return true
    end

    player:setStorageValue(1234, os.time() + 3600)
    Item(item.uid):remove(1)
      player:sendTextMessage(MESSAGE_EVENT_ADVANCE, 'Your 1 hours of 25% XP has started!')
	  player:getPosition():sendMagicEffect(13)
    return true
end

-- The experience callback is defined only in data/events/scripts/player.lua.
