ITEM_ATTRIBUTE_CHESTQUESTNUMBER=28
MESSAGE_INFO_DESCR=1
local storageCalls=0
local player={getStorageValue=function(_,quest) storageCalls=storageCalls+1;return -1 end,
 getFreeCapacity=function() return 999999 end,sendTextMessage=function() end}
local item={getAttribute=function() return 0 end,getSize=function() error('decoration must decline the quest reward handler') end}
dofile('data/actions/scripts/others/chests.lua')
assert(onUse(player,item)==false,'unbound chest must decline the quest handler')
assert(storageCalls==0,'decoration must not read or create quest storage0')
item.getAttribute=function() return 110 end
item.getSize=function() return 0 end
assert(onUse(player,item)==true,'registered quest chest must retain the quest handler')
assert(storageCalls==1,'registered quest chest must still consult its quest storage')
print('PASS: decoration declines quest rewards and active quests retain their handler')
