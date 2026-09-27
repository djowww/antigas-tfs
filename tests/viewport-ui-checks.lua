-- Development-only measurements using the real UIMap and server tiles.
function ViewportQA.geometry(label)
  local d=ViewportQA.snapshot(label)
  local panel=modules.game_interface.getMapPanel()
  local r=panel:getPaddingRect()
  local center={x=math.floor(r.x+r.width/2),y=math.floor(r.y+r.height/2)}
  local hits={}
  for _,axis in ipairs({'x','y'}) do
    local changes,last={},nil
    for delta=-160,160 do
      local pt={x=center.x,y=center.y}; pt[axis]=pt[axis]+delta
      local tile=panel:getTile(pt); local p=tile and tile:getPosition()
      if p and last and p[axis]~=last then table.insert(changes,delta) end
      last=p and p[axis]
    end
    hits[axis]=changes
  end
  local px,py=hits.x[3]-hits.x[2],hits.y[3]-hits.y[2]
  assert(math.abs(px-py)<=1,'non-square projection')
  local tile=panel:getTile(center)
  assert(tile and tile:getPosition().x==d.position.x and tile:getPosition().y==d.position.y,'camera off center')
  local corners={}
  for _,v in ipairs({{2,2},{r.width-3,2},{2,r.height-3},{r.width-3,r.height-3}}) do
    tile=panel:getTile({x=r.x+math.floor(v[1]),y=r.y+math.floor(v[2])})
    assert(tile and tile:getGround(),'missing real edge tile')
    table.insert(corners,tile:getPosition())
  end
  ViewportQA.log(label..'-PASS',{tilePitchX=px,tilePitchY=py,corners=corners})
end
function ViewportQA.creatures()
  local names={}
  for _,c in ipairs(g_map.getSpectatorsInRangeEx(g_game.getLocalPlayer():getPosition(),false,14,14,7,7)) do names[c:getName()]=c end
  return names
end
function ViewportQA.dimension(x,y)
  local d=modules.game_interface.getMapPanel():getVisibleDimension()
  assert(d.width==x and d.height==y,'unexpected dimension '..d.width..'x'..d.height)
end
