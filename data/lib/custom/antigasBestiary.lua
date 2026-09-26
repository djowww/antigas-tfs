AntigasBestiary = {
	OPCODE = 124,
	STORAGE_BASE = 1500000000,
	STORAGE_HASH_RANGE = 600000000,
	MAX_KILLS = 1000
}

function AntigasBestiary.normalizeName(name)
	if type(name) ~= "string" or #name == 0 or #name > 40 then
		return nil
	end
	return name:lower():gsub("%s+", " "):match("^%s*(.-)%s*$")
end

-- Stable per-monster storage key. The range was collision-checked against the
-- current server roster and the complete 7.4 Bestiary catalog.
function AntigasBestiary.storageKey(name)
	local normalized = AntigasBestiary.normalizeName(name)
	if not normalized then
		return nil
	end

	local hash = 5381
	for index = 1, #normalized do
		hash = (hash * 33 + string.byte(normalized, index)) % AntigasBestiary.STORAGE_HASH_RANGE
	end
	return AntigasBestiary.STORAGE_BASE + hash
end
