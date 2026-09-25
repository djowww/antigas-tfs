local config = {
    level = 2	
}

local SKINS = {
    -- Minotaurs
    [4011] = {25, 5172},
	[4057] = {25, 5172},
	[4052] = {25, 5172},
	[4047] = {25, 5172},
	
	--Dragons
	[4025] = {25, 5198},
	[4062] = {25, 5197},
	
	--Behemoth
	[4112] = {25, 5193},
}

function onUse(cid, item, fromPosition, itemEx, toPosition)
    if(getPlayerLevel(cid) < config.level) then
        doPlayerSendCancel(cid, "You have to be at least Level " .. config.level .. " to use this tool.")
        return true
    end

    local skin = SKINS[itemEx.itemid]
    if(not skin) then
        doPlayerSendDefaultCancel(cid, RETURNVALUE_NOTPOSSIBLE)
        return true
    end

    local random, effect = math.random(1, 100), CONST_ME_BLOCKHIT
    if(random <= skin[1]) then
        doPlayerAddItem(cid, skin[2], 1)
    elseif(skin[3] and random >= skin[3]) then
        doPlayerAddItem(cid, skin[4], 1)
    else
        effect = CONST_ME_POFF
    end

    doSendMagicEffect(toPosition, effect)
    doTransformItem(itemEx.uid, itemEx.itemid + 1)
    return true
end