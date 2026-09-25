local ropeSpots = {
    386, 421
}
 
local holeSpots = {
    293, 294, 369, 370, 385, 394, 411, 412,
    421, 432, 433, 435, 482, 5081, 483, 594,
    595, 607, 609, 610, 615, 1066, 1067, 1080
}
 
function onUse(player, item, fromPosition, target, toPosition)
    local tile = Tile(toPosition)
    if not tile then
        return false
    end
   
    if not target:isItem() then
        return false
    end
   
    if target:getId() >= 2886 and target:getId() <= 2891 then
        target = tile:getGround()
    end
   
    if table.contains(ropeSpots, target:getId()) then
        player:teleportTo(target:getPosition():moveRel(0, 1, -1))
        return true
    elseif table.contains(holeSpots, target:getId()) or target:getId() == 435 then
        local tile = Tile(target:getPosition():moveRel(0, 0, 1))
        if not tile then
            return false
        end
       
        local thing = tile:getTopCreature()
        if not thing then
            thing = tile:getTopVisibleThing()
        end
       
        if thing:isCreature() then
            thing:teleportTo(target:getPosition():moveRel(0, 1, 0), false)
            return true
        end
        if thing:isItem() and thing:getType():isMovable() then
            thing:moveTo(target:getPosition():moveRel(0, 1, 0))
            return true
        end
        return true
    end
    return false
end