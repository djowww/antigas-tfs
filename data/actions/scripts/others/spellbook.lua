function onUse(player, item, fromPosition, target, toPosition, isHotkey)
	local count = getPlayerInstantSpellCount(player)
	local text = ""
	local spells = {}
	for i = 0, count - 1 do
		local spell = getPlayerInstantSpellInfo(player, i)
		if spell.level >= 0 then
			if spell.manapercent > 0 then
				spell.mana = spell.manapercent .. "%"
			end
			spells[#spells + 1] = spell
		end
	end

	table.sort(spells, function(a, b) return a.level < b.level end)

	local prevLevel = -1
	for i, spell in ipairs(spells) do
		local line = ""
		if prevLevel ~= spell.level then
			if i ~= 1 then
				line = "\n"
			end
			line = line .. "Spells for Magic Level " .. spell.level .. "\n"
			prevLevel = spell.level
		end
		if not string.match(spell.name, "House") then -- check for `House` in name
    text = text .. line .. "  " .. spell.words .. " - " .. spell.name .. " : " .. spell.mana .. "\n"
end
	end
	player:showTextDialog(item:getId(), text)
	return true
end