local ropeSpots = {
 386, 421
}

function onCastSpell(creature, variant)
 local position = creature:getPosition()
 
 local tile = Tile(position)
 if isInArray(ropeSpots, tile:getGround():getId()) then
  position:sendMagicEffect(CONST_ME_TELEPORT)
  tile = Tile(position:moveUpstairs())
  if tile then
   creature:teleportTo(position)
  else
   creature:sendCancelMessage(RETURNVALUE_NOTENOUGHROOM)
   position:sendMagicEffect(CONST_ME_POFF)
  end
 else
  creature:sendCancelMessage(RETURNVALUE_NOTPOSSIBLE)
  position:sendMagicEffect(CONST_ME_POFF)
  return false
 end
 return true
end