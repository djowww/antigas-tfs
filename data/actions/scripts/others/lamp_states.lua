function onUse(player, item, fromPosition, target, toPosition, isHotkey)
    local tile = Tile(toPosition)
    local transformId = lampTransformIds[item:getId()] or reverseLampTransformIds[item:getId()]
    item:transform(transformId)
    if tile and tile:getHouse() then
        wallLamps[serializePos(toPosition)] = transformId -- update lamp state
        dumpLampStates()
    end
    return true
end