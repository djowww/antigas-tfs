local denied = 0
local player = {
  sendCancelMessage = function(_, text)
    assert(text == 'O canal Loot e somente para leitura.')
    denied = denied + 1
  end
}
dofile('data/chatchannels/scripts/loot.lua')
for speakType = 1, 32 do
  assert(onSpeak(player, speakType, 'synthetic private test') == false)
end
assert(denied == 32)
local file = assert(io.open('data/chatchannels/chatchannels.xml', 'rb'))
local channels = file:read('*a')
file:close()
assert(channels:find('<channel id="10" name="Loot" script="loot.lua" />', 1, true))
file = assert(io.open('data/creaturescripts/scripts/login.lua', 'rb'))
local login = file:read('*a')
file:close()
assert(login:find('player:openChannel(10)', 1, true))
assert(login:find('Official client: v45', 1, true))
print('PASS: 68 loot channel checks (read-only denial, registration, automatic login channel)')
