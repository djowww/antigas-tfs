local conf = {
   ["level"] = {
   -- [item_level] = {successPercent= CHANCE TO UPGRADE ITEM, downgradeLevel = ITEM GETS THIS LEVEL IF UPGRADE FAILS}
     [1] = {successPercent = 85, downgradeLevel = 0},
     [2] = {successPercent = 80, downgradeLevel = 1},
     [3] = {successPercent = 75, downgradeLevel = 2},
     [4] = {successPercent = 70, downgradeLevel = 3},
     [5] = {successPercent = 65, downgradeLevel = 4},
     [6] = {successPercent = 60, downgradeLevel = 5},
     [7] = {successPercent = 55, downgradeLevel = 0},
     [8] = {successPercent = 50, downgradeLevel = 0},
     [9] = {successPercent = 45, downgradeLevel = 0}
   },

   ["upgrade"] = { -- how many percent attributes are rised?
     attack = 5, -- attack %
     defense = 5, -- defense %
     armor = 5, -- armor %
     hitChance = 5, -- hit chance %
   }
}



local function upValue(value,level,percent)
    if value<0 then return 0 end
    for i=1,level do value=value+math.ceil(value*percent/100) end
    return value
end
function onUse(player,item,fromPosition,target,toPosition)
    if not Economy.owned(player,item) or not Economy.owned(player,target) or item==target then
        player:sendCancelMessage('Keep the scroll and equipment in your own inventory.');return true
    end
    local it=ItemType(target:getId())
    if it:isStackable() or (it:getWeaponType()==0 and it:getArmor()==0) then
        player:sendCancelMessage('You cannot upgrade this item.');return true
    end
    local name=target:getName()
    local level=0
    if name:find('+',1,true) then level=tonumber(name:match(' Refinado %+(%d+)$')) end
    if not level or level%1~=0 or level<0 or level>=#conf.level then
        player:sendCancelMessage('This item is already at maximum level or has an unsupported custom name.');return true
    end
    local nextLevel=conf.level[level+1].successPercent>=math.random(1,100) and level+1 or (conf.level[level] and conf.level[level].downgradeLevel or 0)
    local attributes={
        {ITEM_ATTRIBUTE_NAME,it:getName()..(nextLevel>0 and ' Refinado +'..nextLevel or '')},
        {ITEM_ATTRIBUTE_ATTACK,upValue(it:getAttack(),nextLevel,conf.upgrade.attack)},
        {ITEM_ATTRIBUTE_DEFENSE,upValue(it:getDefense(),nextLevel,conf.upgrade.defense)},
        {ITEM_ATTRIBUTE_ARMOR,upValue(it:getArmor(),nextLevel,conf.upgrade.armor)},
        {ITEM_ATTRIBUTE_HITCHANCE,upValue(it.getHitChance and it:getHitChance() or 0,nextLevel,conf.upgrade.hitChance)}
    }
    local ok=Economy.run(player,function(ctx)
        if not ctx:take(item,1) then return false end
        for _,a in ipairs(attributes) do if not ctx:setAttribute(target,a[1],a[2]) then return false end end
        return true
    end)
    if not ok then player:sendCancelMessage('Upgrade could not be saved. Item and scroll were preserved.');return true end
    player:getPosition():sendMagicEffect(nextLevel>level and CONST_ME_MAGIC_GREEN or CONST_ME_BLOCKHIT)
    player:sendTextMessage(MESSAGE_INFO_DESCR,(nextLevel>level and 'Upgrade successful. ' or 'Upgrade failed. ')..'Equipment level: '..nextLevel..'.')
    return true
end
