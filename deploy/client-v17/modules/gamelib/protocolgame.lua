local opcodeCallbacks = {}
local extendedCallbacks = {}
local extendedRawCallbacks = {}
local extendedJSONCallbacks = {}
local extendedJSONData = {}
local maxPacketSize = 65000

function ProtocolGame:onOpcode(opcode, msg)
  for i, callback in pairs(opcodeCallbacks) do
    if i == opcode then
      callback(self, msg)
      return true
    end
  end
  return false
end

function ProtocolGame:onExtendedOpcode(opcode, buffer)
  local callback = extendedCallbacks[opcode]
  if callback then
    -- Raw consumers validate the wire data themselves, without evaluating Lua.
    -- Keep the original buffer intact for JSON consumers of the same opcode.
    if extendedRawCallbacks[opcode] then
      callback(self, opcode, buffer)
    else
      local decoded = unserialize(buffer)
      if decoded and type(decoded) == 'table' and decoded['@'] then
        callback(self, opcode, unpack(decoded['@']))
      else
        callback(self, opcode, decoded)
      end
    end
  end
  
  callback = extendedJSONCallbacks[opcode]
  if callback then
    local status = buffer:sub(1,1) -- O - just one message, S - start, P - part, E - end
    local data = buffer:sub(2)
    if status ~= "E" and status ~= "P" then
      extendedJSONData[opcode] = ""
    end
    if status ~= "S" and status ~= "P" and status ~= "E" then
      extendedJSONData[opcode] = buffer
    else
      extendedJSONData[opcode] = extendedJSONData[opcode] .. data
    end
    if status ~= "S" and status ~= "P" then
      local json_status, json_data = pcall(function() return json.decode(extendedJSONData[opcode]) end)
      extendedJSONData[opcode] = nil
      if not json_status then
        error("Invalid data in extended JSON opcode (" .. json_status .. "): " .. json_data)
        return
      end
      callback(self, opcode, json_data)
    end
  end
end

function ProtocolGame.registerOpcode(opcode, callback)
  if opcodeCallbacks[opcode] then
    error('opcode ' .. opcode .. ' already registered will be overriden')
  end

  opcodeCallbacks[opcode] = callback
end

function ProtocolGame.unregisterOpcode(opcode)
  opcodeCallbacks[opcode] = nil
end

function ProtocolGame.registerExtendedOpcode(opcode, callback, raw)
  if not callback or type(callback) ~= 'function' then
    error('Invalid callback.')
  end

  if opcode < 0 or opcode > 255 then
    error('Invalid opcode. Range: 0-255')
  end

  if extendedCallbacks[opcode] then
    error('Opcode is already taken.')
  end

  extendedCallbacks[opcode] = callback
  extendedRawCallbacks[opcode] = raw == true
end

function ProtocolGame.unregisterExtendedOpcode(opcode)
  if opcode < 0 or opcode > 255 then
    error('Invalid opcode. Range: 0-255')
  end

  if not extendedCallbacks[opcode] then
    error('Opcode is not registered.')
  end

  extendedCallbacks[opcode] = nil
  extendedRawCallbacks[opcode] = nil
end

function ProtocolGame.registerExtendedJSONOpcode(opcode, callback)
  if not callback or type(callback) ~= 'function' then
    error('Invalid callback.')
  end

  if opcode < 0 or opcode > 255 then
    error('Invalid opcode. Range: 0-255')
  end

  if extendedJSONCallbacks[opcode] then
    error('Opcode is already taken.')
  end

  extendedJSONCallbacks[opcode] = callback
end

function ProtocolGame.unregisterExtendedJSONOpcode(opcode)
  if opcode < 0 or opcode > 255 then
    error('Invalid opcode. Range: 0-255')
  end

  if not extendedJSONCallbacks[opcode] then
    error('Opcode is not registered.')
  end

  extendedJSONCallbacks[opcode] = nil
end

function sendSpecialOpcode(code, ...)
	local res = {...}
	if #res > 0 then
		if #res == 1 then
			res = res[1]
		else
			res = {['@'] = res}
		end
	
		local protocolGame = g_game.getProtocolGame()
		if protocolGame then
			protocolGame:sendExtendedOpcode(code, serialize(res))
		end
	end
end

function ProtocolGame:sendExtendedJSONOpcode(opcode, data)
  if opcode < 0 or opcode > 255 then
    error('Invalid opcode. Range: 0-255')
  end

  if type(data) ~= "table" then
    error('Invalid data type, should be table')
  end
  
  local buffer = json.encode(data)  
  local s = {}
  for i=1, #buffer, maxPacketSize do
     s[#s+1] = buffer:sub(i,i+maxPacketSize - 1)
  end
  if #s == 1 then
    self:sendExtendedOpcode(opcode, s[1])
    return
  end
  self:sendExtendedOpcode(opcode, "S" .. s[1])
  for i=2,#s - 1 do
    self:sendExtendedOpcode(opcode, "P" .. s[i])
  end
  self:sendExtendedOpcode(opcode, "E" .. s[#s])
end
