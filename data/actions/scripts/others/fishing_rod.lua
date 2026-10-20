function onUse(player, item, fromPosition, target, toPosition)
 if not target:isItem() then return false end
 local id = target:getId()
 if (id < 4597 or id > 4602) and (id < 4609 or id > 4614) then return false end
 target:getPosition():sendMagicEffect(CONST_ME_LOSEENERGY)
 if id > 4602 or item:getId() ~= 3483 then return true end
 if Tile(player:getPosition()):hasFlag(TILESTATE_PROTECTIONZONE) or player:getItemCount(3492) == 0 then return true end
 -- TestSkill credits before both inclusive tests, including failed attempts.
 player:addSkillTries(SKILL_FISHING, 1)
 if math.random(0, 79) <= player:getEffectiveSkillLevel(SKILL_FISHING) and math.random(0, 99) <= 50 then
  player:addItem(3578, 1)
  target:transform(id + 12)
  player:removeItem(3492, 1)
 end
 return true
end
