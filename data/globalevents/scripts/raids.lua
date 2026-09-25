local raids = {
	-- Weekly
	--Segunda-Feira
	['Monday'] = {
		['06:00'] = {raidName = 'thaiscaverats'},
		['18:00'] = {raidName = 'horses'},
		['21:00'] = {raidName = 'darashiawaspplague'}
	},

	--Terça-Feira
	['Tuesday'] = {
		['16:00'] = {raidName = 'panther'},
		['18:00'] = {raidName = 'horses'}
	},

	--Quarta-Feira
	['Wednesday'] = {
		['12:00'] = {raidName = 'orcbp'},
		['18:00'] = {raidName = 'horses'}
	},

	--Quinta-Feira
	['Thursday'] = {
		['22:00'] = {raidName = 'kazordoonhornedfox'},
		['18:00'] = {raidName = 'horses'},
		['21:00'] = {raidName = 'darashiawaspplague'}
	},

	--Sexta-feira
	['Friday'] = {
		['06:00'] = {raidName = 'foldayetis'},
		['18:00'] = {raidName = 'horses'},
		['20:00'] = {raidName = 'cavesgrorlam0'}
	},

	--Sábado
	['Saturday'] = {
		['20:00'] = {raidName = 'pohdemodras'},
		['18:00'] = {raidName = 'horses'},
		['14:00'] = {raidName = 'mintwalinminogeneral'},
		['02:00'] = {raidName = 'drefianecromancer'}
	},

	--Domingo
	['Sunday'] = {
		['23:00'] = {raidName = 'panther'},
		['18:00'] = {raidName = 'horses'}
	},

	-- By date (Day/Month)
	['31/10'] = {
		['16:00'] = {raidName = 'halloweenhare'}
	}
}

function onThink(interval, lastExecution, thinkInterval)
	local now = os.time()
	local day, date = os.date('%A', now), os.date('%d/%m', now)
	local today, clock = os.date('%Y-%m-%d', now), os.date('%H:%M', now)

	local raidDays = {}
	if raids[day] then
		raidDays[#raidDays + 1] = raids[day]
	end
	if raids[date] then
		raidDays[#raidDays + 1] = raids[date]
	end

	if #raidDays == 0 then
		return true
	end

	for i = 1, #raidDays do
		local settings = raidDays[i][clock]
		if settings and settings.lastExecutedDate ~= today then
			if Game.startRaid(settings.raidName) then
				settings.lastExecutedDate = today
			end
		end
	end

	return true
end
