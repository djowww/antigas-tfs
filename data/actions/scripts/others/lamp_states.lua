function onUse(player, item, fromPosition, target, toPosition, isHotkey)
    local tile = Tile(toPosition)
    local house = tile and tile:getHouse()

    if house then
        if fromPosition ~= toPosition then
            player:sendCancelMessage(RETURNVALUE_CANNOTUSETHISOBJECT)
            return true
        end

        local onlyInvited = configManager.getBoolean(configKeys.ONLY_INVITED_CAN_MOVE_HOUSE_ITEMS)
        if onlyInvited and not house:isInvited(player) then
            player:sendCancelMessage(RETURNVALUE_PLAYERISNOTINVITED)
            return true
        end

        if not canStoreLampState(toPosition) then
            player:sendCancelMessage(RETURNVALUE_NOTPOSSIBLE)
            return true
        end
    end

    local transformId = lampTransformIds[item:getId()] or reverseLampTransformIds[item:getId()]
    item:transform(transformId)
    if house then
        storeLampState(toPosition, transformId)
    end
    return true
end
