local dead_human = {
    4240, 4241, 4242, 4247, 4248
}

local fields_blocked = {
    2118, 2122, 2121, 2119, 2120, 2123, 2124, 2125, 2126, 2127, 2131, 2132, 2133, 2134, 2135, 2138, 2139
}

local removalLimit = 50

function onCastSpell(creature, variant)
    local position = variant:getPosition()
    local tile = Tile(position)
    if tile then
        local items = tile:getItems()
        if items then
            for i, item in ipairs(items) do
                if item:getType():isMovable() and item:getActionId() == 0 and not table.contains(dead_human, item:getId()) then
                    item:remove()
                end

                if table.contains(fields_blocked, item:getId()) then
                    position:sendMagicEffect(CONST_ME_POFF)
                    return false
                end

                if i == removalLimit then
                    break
                end
            end
        end
    end

    position:sendMagicEffect(CONST_ME_POFF)
    return true
end