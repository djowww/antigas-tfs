function onSay(cid, words, param)
    local player = Player(cid)
    if param == "emote" and player:getStorageValue(30019) < 1 then
        player:setStorageValue(30019, 1)
        player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "You have enabled emoted spells.")
    elseif param == "normal" and player:getStorageValue(30019) == 1 then
        player:setStorageValue(30019, 0)
        player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "You have disabled emoted spells.")
    end
    return false
end