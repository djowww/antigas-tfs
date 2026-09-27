-- Run: lua viewport-policy.lua /path/to/modules/game_interface/viewport.lua
dofile(assert(arg[1], 'viewport.lua path required'))
local count=0
for w=200,3440,19 do
  for h=200,1440,17 do
    local d=AntigasViewport.calculate(w,h,2)
    assert(d.width%2==1 and d.height%2==1)
    assert(d.width>=3 and d.width<=29 and d.height>=3 and d.height<=15)
    local x,y=AntigasViewport.requestSize(d)
    assert(x>=16 and x<=30 and y>=12 and y<=16)
    local c=AntigasViewport.calculate(w,h,1)
    assert(c.width==15 and c.height==11 and not c.wide)
    count=count+1
  end
end
local d=AntigasViewport.calculate(1172,590,2)
assert(d.width==21 and d.height==11 and d.wide)
d=AntigasViewport.calculate(1726,921,2)
assert(d.width==29 and d.height==15 and d.wide)
print('PASS: '..count..' viewport sizes, odd dimensions, caps and Classic fallback')
