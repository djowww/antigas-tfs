local combat = createCombatObject()
setCombatParam(combat, COMBAT_PARAM_EFFECT, CONST_ME_MAGIC_BLUE)
 
local area = createCombatArea(AREA_CIRCLE3X3)
setCombatArea(combat, area)
 
function onTargetCorpse(cid, pos)
    local getPos = pos
    getPos.stackpos = 255
    corpse = getThingfromPos(getPos)
    if(corpse.uid > 0 and isCorpse(corpse.uid) and isMoveable(corpse.uid) and getPlayerSkullType(cid) ~= 5) then
       
 
    local summon = Game.createMonster("Skeleton", pos, true)
        if summon then
            doRemoveItem(corpse.uid)
            cid:addSummon(summon)
            pos:sendMagicEffect(CONST_ME_MAGIC_BLUE)
        end
        return false
    end
end
setCombatCallback(combat, CALLBACK_PARAM_TARGETTILE, "onTargetCorpse")
 
function onCastSpell(cid, var)
    return doCombat(cid, combat, var)
end