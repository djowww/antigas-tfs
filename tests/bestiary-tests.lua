-- Run against the real library and event handlers with isolated player doubles.
dofile('data/lib/custom/antigasBestiary.lua')
local now = 1000
os.time = function() return now end
json = {
  encode = function(value) return value end,
  decode = function(value)
    if value == 'invalid' then error('invalid JSON') end
    return _G.request
  end
}
MonsterType = function(name) return name == 'rat' or name == 'dragon' end
dofile('data/creaturescripts/scripts/bestiary.lua')
local function player(guid)
  return {
    storage = {}, sent = {},
    isPlayer = function() return true end,
    getGuid = function() return guid end,
    getStorageValue = function(self, key) return self.storage[key] or -1 end,
    setStorageValue = function(self, key, value) self.storage[key] = value end,
    sendExtendedOpcode = function(self, opcode, value)
      assert(opcode == 124)
      self.sent[#self.sent + 1] = value
    end
  }
end
local function monster(name, master)
  return {
    isMonster = function() return true end,
    getMaster = function() return master end,
    getName = function() return name end
  }
end
local first, second = player(1), player(2)
local key = AntigasBestiary.storageKey('Rat')
assert(key == AntigasBestiary.storageKey('  RAT  '))
onKill(first, monster('Rat'))
assert(first.storage[key] == 1 and second:getStorageValue(key) == -1)
onKill(first, monster('Rat', second))
assert(first.storage[key] == 1, 'Player summons must not grant progress')
for i = 1, 1100 do onKill(first, monster('Rat')) end
assert(first.storage[key] == 1000 and #first.sent == 1000, 'Counter must stop at the cap')
onKill(second, monster('Rat'))
assert(second.storage[key] == 1, 'Characters must remain independent')
request = {action = 'getProgress', monsters = {'Rat', 'DRAGON', 'unknown'}}
onExtendedOpcode(first, 124, '{}')
local response = first.sent[#first.sent]
assert(response.action == 'progress' and response.data.Rat == 1000)
assert(response.data.DRAGON == 0 and response.data.unknown == nil)
local sent = #first.sent
onExtendedOpcode(first, 124, '{}')
assert(#first.sent == sent, 'Repeated requests must be throttled')
onExtendedOpcode(second, 124, '{}')
assert(second.sent[#second.sent].data.Rat == 1, 'Throttle must not block another player')
now = now + 3
onExtendedOpcode(first, 124, 'invalid')
onExtendedOpcode(first, 124, string.rep('x', 8193))
onExtendedOpcode(first, 123, '{}')
assert(#first.sent == sent, 'Invalid messages must not emit a reply')
request.monsters = {}
for i = 1, 201 do request.monsters[i] = 'rat' end
onExtendedOpcode(first, 124, '{}')
assert(#first.sent == sent, 'Oversized catalogs must be rejected')
print('PASS Bestiary: isolation, summons, cap, queries, throttling and malformed requests')
