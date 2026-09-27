-- Test-only command, installed only in the disposable tiny-map world.
local rat, npc, dense
function onSay(player, words, param)
  if player:getName() ~= 'Viewport Tester' or not player:getGroup():getAccess() then return false end
  local p = {x=1000,y=1000,z=7}
  if param == 'setup' then
    for _,creature in ipairs(Game.getSpectators(Position(1000,1000,7),false,false,40,40,40,40)) do
      if not creature:isPlayer() then creature:remove() end
    end
    rat, npc = nil, nil
    rat = Game.createMonster('Rat',{x=1009,y=1000,z=7},false,true)
    npc = Game.createNpc('sam',{x=991,y=1000,z=7},false,true)
    player:setGhostMode(false)
    player:setOutfit({lookType=128,lookHead=78,lookBody=69,lookLegs=58,lookFeet=76})
    player:addItem(2854,1)
    print('VIEWPORT_FIXTURE setup rat='..tostring(rat~=nil)..' npc='..tostring(npc~=nil))
  elseif param == 'effects' then
    Position(1011,1001,7):sendMagicEffect(CONST_ME_MAGIC_BLUE)
    Position(1000,1000,7):sendDistanceEffect(Position(1011,1001,7),CONST_ANI_ARROW)
    local peer = Player('Viewport Peer')
    if peer then
      for _,creature in ipairs(Game.getSpectators(peer:getPosition(),false,false,40,40,40,40)) do
        if creature:isMonster() then creature:remove() end
      end
      peer:addHealth(peer:getMaxHealth())
      peer:addHealth(-30)
      peer:teleportTo(Position(1012,1001,7))
    end
  elseif param == 'floor8' then
    player:teleportTo(Position(1000,1000,8))
  elseif param == 'floor7' then
    player:teleportTo(Position(1000,1000,7))
  elseif param == 'border' then
    if rat and not rat:isRemoved() then
      rat:teleportTo(Position(1012,1000,7))
      rat:addHealth(-1)
    end
  elseif param == 'dense' and not dense then
    dense = true
    -- Away from the normal fixture; 8 occupied floors and 9 items per tile
    -- deliberately exceed a single legacy 64 KiB map packet.
    player:teleportTo(Position(1000,1000,7))
    for z=0,7 do
      for x=1015,1046 do
        for y=1017,1034 do
          local pos={x=x+(7-z),y=y+(7-z),z=z}
          local tile=Game.createTile(pos,true)
          if not tile:getGround() then Game.createItem(102,1,pos) end
          for i=1,9 do Game.createItem(3031,100,pos) end
        end
      end
    end
    player:teleportTo(Position(1030,1025,7))
    print('VIEWPORT_FIXTURE dense 8 floors / 4608 tiles')
  elseif param == 'reset' then
    player:teleportTo(Position(p))
  end
  return false
end
