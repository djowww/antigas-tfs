-- Run from the TFS root with Lua 5.1/5.2 or LuaJIT. No database is used.
-- Exercise the actual Market/refine/Economy Lua scripts with an inventory fixture.
CONST_SLOT_BACKPACK, RETURNVALUE_NOERROR = 3, 0
INDEX_WHEREEVER, FLAG_NOLIMIT, FLAG_IGNOREAUTOSTACK = -1, 1, 2
ITEM_ATTRIBUTE_NAME, ITEM_ATTRIBUTE_ATTACK, ITEM_ATTRIBUTE_DEFENSE = 1, 2, 3
ITEM_ATTRIBUTE_ARMOR, ITEM_ATTRIBUTE_HITCHANCE = 4, 5
ITEM_ATTRIBUTE_OWNER, ITEM_ATTRIBUTE_CORPSEOWNER = 6, 7
ITEM_ATTRIBUTE_KEYNUMBER, ITEM_ATTRIBUTE_KEYHOLENUMBER = 8, 9
ITEM_ATTRIBUTE_DOORQUESTNUMBER, ITEM_ATTRIBUTE_DOORQUESTVALUE = 10, 11
ITEM_ATTRIBUTE_DOORLEVEL, ITEM_ATTRIBUTE_CHESTQUESTNUMBER = 12, 13
MESSAGE_INFO_DESCR, CONST_ME_MAGIC_GREEN, CONST_ME_BLOCKHIT = 22, 18, 3

local SWORD, SCROLL, BAG = 2376, 9000, 1988
local definitions = {
    [SWORD] = {name = 'sword', attack = 20, defense = 10, weapon = 1},
    [SCROLL] = {name = 'upgrade scroll', stackable = true},
    [BAG] = {name = 'backpack', container = true}
}
function ItemType(id)
    local d = assert(definitions[id], 'Unknown fixture item')
    return {
        getName = function() return d.name end,
        isStackable = function() return d.stackable or false end,
        isContainer = function() return d.container or false end,
        getCharges = function() return 0 end,
        getWeaponType = function() return d.weapon or 0 end,
        getAttack = function() return d.attack or 0 end,
        getDefense = function() return d.defense or 0 end,
        getArmor = function() return 0 end,
        getHitChance = function() return 0 end
    }
end

local nextId = 0
local function makeItem(id, count, rarity)
    nextId = nextId + 1
    local item = {id = id, uid = nextId, count = count or 1, rarity = rarity, attributes = {}, children = {}}
    function item:isItem() return true end
    function item:isPlayer() return false end
    function item:isContainer() return ItemType(self.id):isContainer() end
    function item:getId() return self.id end
    function item:getUniqueId() return self.uid end
    function item:getCount() return self.count end
    function item:getCharges() return 0 end
    function item:getActionId() return 0 end
    function item:getMovementId() return 0 end
    function item:getName() return self.attributes[ITEM_ATTRIBUTE_NAME] or ItemType(self.id):getName() end
    function item:getRarityInfo()
        if self.rarity then return self.rarity.tier, self.rarity.kind, self.rarity.value, self.rarity.subtype end
    end
    function item:hasAttribute(key) return self.attributes[key] ~= nil end
    function item:getAttribute(key) return self.attributes[key] end
    function item:setAttribute(key, value) self.attributes[key] = value; return true end
    function item:removeAttribute(key) self.attributes[key] = nil; return true end
    function item:serializeAttributes()
        local out = {tostring(self.count)}
        for key = 1, 13 do out[#out + 1] = tostring(self.attributes[key]) end
        if self.rarity then out[#out + 1] = 'rarity:' .. self.rarity.tier end
        return table.concat(out, '|')
    end
    function item:getTopParent()
        local parent = self
        while parent.parent do parent = parent.parent end
        return parent
    end
    function item:getSize() return #self.children end
    function item:getItem(index) return self.children[index + 1] end
    function item:addItemEx(child)
        self.children[#self.children + 1] = child
        child.parent, child.removed = self, false
        return RETURNVALUE_NOERROR
    end
    function item:clone()
        local copy = makeItem(self.id, self.count, self.rarity)
        for key, value in pairs(self.attributes) do copy.attributes[key] = value end
        return copy
    end
    function item:remove(amount)
        amount = amount or self.count
        if amount < self.count then self.count = self.count - amount; return true end
        if self.parent then
            for index, child in ipairs(self.parent.children) do
                if child == self then table.remove(self.parent.children, index); break end
            end
        end
        self.parent, self.removed = nil, true
        return true
    end
    function item:transform(id, count) self.id, self.count = id, count; return true end
    return item
end
Game = {createItem = makeItem}

local function makePlayer(items)
    local player = {bank = 100, messages = {}, children = {}, rollback = false}
    local bag = makeItem(BAG)
    bag.parent = player
    player.bag = bag
    for _, item in ipairs(items) do bag:addItemEx(item) end
    function player:isPlayer() return true end
    function player:getId() return 1 end
    function player:getSlotItem(slot) return slot == CONST_SLOT_BACKPACK and self.bag or nil end
    function player:getBankBalance() return self.bank end
    function player:setBankBalance(value) self.bank = value end
    function player:marketTransaction(work, undo)
        local ok = work()
        if ok and not self.failCommit then return true end
        self.rollback = true
        assert(undo(), 'transaction rollback must restore inventory')
        return false
    end
    function player:sendCancelMessage(message) self.messages[#self.messages + 1] = message end
    function player:sendTextMessage(_, message) self.messages[#self.messages + 1] = message end
    function player:getPosition() return {sendMagicEffect = function() end} end
    return player
end

local function upvalue(fn, expected)
    for index = 1, 100 do
        local name, value = debug.getupvalue(fn, index)
        if name == expected then return value end
        if not name then break end
    end
    error('Missing upvalue: ' .. expected)
end

dofile('data/creaturescripts/scripts/market.lua')
local inventory = upvalue(upvalue(onExtendedOpcode, 'sendBalances'), 'inventory')
local clean = upvalue(inventory, 'clean')
local rarity = {tier = 5, kind = 6, value = 5, subtype = 0}
local plain, rare = makeItem(SWORD), makeItem(SWORD, 1, rarity)
assert(clean(plain), 'ordinary unmodified equipment must remain tradable')
assert(not clean(rare), 'rarity items must never enter id-only Market offers')
local refined = makeItem(SWORD)
refined:setAttribute(ITEM_ATTRIBUTE_ATTACK, 21)
assert(not clean(refined), 'refined items must remain excluded from id-only offers')
local owner = makePlayer({rare, plain, refined})
local entries, summary = inventory(owner)
assert(#entries == 1 and entries[1].item == plain, 'Market inventory must select only the ordinary instance')
assert(summary[SWORD .. ':-1'] == 1, 'Market sell count must exclude rare and refined copies')
assert(not rare.removed and rare.parent == owner.bag, 'Market reads must preserve rare inventory')

dofile('data/lib/custom/economy.lua')
dofile('data/actions/scripts/refine.lua')
local originalRandom = math.random
math.random = function() return 1 end
local scroll = makeItem(SCROLL, 2)
owner = makePlayer({rare, scroll})
assert(onUse(owner, scroll, nil, rare, nil))
assert(rare:getName() == 'sword Refinado +1')
assert(rare:getAttribute(ITEM_ATTRIBUTE_ATTACK) == 21,
    'refine must calculate from base attack 20, without compounding rarity +5')
assert(rare:getRarityInfo() == 5 and rare.rarity.value == 5, 'refining must preserve the rarity bonus')
assert(scroll:getCount() == 1, 'successful refine consumes exactly one scroll')
assert(onUse(owner, scroll, nil, rare, nil))
assert(rare:getAttribute(ITEM_ATTRIBUTE_ATTACK) == 23, 'second refine still derives its value from base stats')
assert(rare.rarity == rarity and rare.rarity.value == 5, 'second refine must not duplicate the rarity bonus')
assert(scroll.removed, 'last scroll must be consumed once')

math.random = function() return 100 end
scroll = makeItem(SCROLL)
owner.bag:addItemEx(scroll)
assert(onUse(owner, scroll, nil, rare, nil))
assert(rare:getName() == 'sword Refinado +1' and rare:getAttribute(ITEM_ATTRIBUTE_ATTACK) == 21)
assert(rare.rarity == rarity, 'failed refinement/downgrade must preserve rarity')

math.random = function() return 1 end
scroll = makeItem(SCROLL, 2)
owner.bag:addItemEx(scroll)
owner.failCommit = true
local before = rare:serializeAttributes()
assert(onUse(owner, scroll, nil, rare, nil))
assert(owner.rollback and scroll:getCount() == 2, 'failed commit must restore the partial scroll stack')
assert(rare:serializeAttributes() == before, 'failed commit must restore all refined attributes and rarity')

owner = makePlayer({makeItem(SWORD, 1, rarity), makeItem(SCROLL)})
rare, scroll = owner.bag.children[1], owner.bag.children[2]
owner.failCommit = true
assert(onUse(owner, scroll, nil, rare, nil))
assert(#owner.bag.children == 2 and owner.bag.children[2]:getId() == SCROLL,
    'failed commit must restore a fully removed scroll')
assert(not rare:hasAttribute(ITEM_ATTRIBUTE_ATTACK) and not rare:hasAttribute(ITEM_ATTRIBUTE_NAME),
    'rollback must remove newly introduced attributes')
assert(rare.rarity == rarity, 'rollback must leave the original rarity metadata intact')

owner = makePlayer({makeItem(SWORD, 1, rarity)})
rare = owner.bag.children[1]
assert(not Economy.run(owner, function(ctx) return ctx:take(rare, 1) and false end))
assert(#owner.bag.children == 1 and owner.bag.children[1]:getRarityInfo() == 5,
    'rollback of a removed rarity item must restore its clone with instance metadata')
math.random = originalRandom
print('PASS: rarity Market exclusion, repeated refinement, downgrade, partial/full rollback and metadata preservation')
