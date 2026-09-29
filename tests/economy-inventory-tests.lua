-- Run from the TFS root with Lua 5.1/LuaJIT. No server or database is used.
assert(loadfile('data/lib/custom/economy.lua'))()

local function item(uid, children, size)
    local value={uid=uid,children=children,size=size}
    function value:getUniqueId() return self.uid end
    function value:isContainer() return self.children~=nil end
    function value:getSize() return self.size end
    function value:getItem(index) return self.children[index] end
    return value
end

local function playerWithBackpack(backpack)
    return {getSlotItem=function(_,slot) return slot==3 and backpack or nil end}
end

-- Empty slots must be ignored instead of queued as nil inventory records.
local nestedItem=item(4)
local inner=item(3,{[1]=nestedItem},2)
local backpack=item(1,{[0]=item(2),[2]=inner},4)
local inventory=Economy.inventory(playerWithBackpack(backpack))
assert(inventory and #inventory==4,'sparse nested containers must be traversed safely')
for _,entry in ipairs(inventory) do
    assert(entry.item~=nil,'inventory traversal must never return an empty slot')
end

local function backpackWithChildren(count)
    local children={}
    for index=0,count-1 do children[index]=item(index+2) end
    return item(1,children,count)
end

-- The root counts toward the bounded scan: exactly 10,000 nodes are allowed.
assert(#Economy.inventory(playerWithBackpack(backpackWithChildren(9999)))==10000,
    'the maximum supported inventory size must remain valid')
assert(Economy.inventory(playerWithBackpack(backpackWithChildren(10000)))==nil,
    'inventories larger than the configured scan limit must fail closed')

print('Economy inventory regression tests passed')
