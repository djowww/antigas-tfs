local data = require "data/imperium_monster.lua"

local wikiItemsData = {}
local wikiWindow = nil
local creatureWindow = nil
local creatureFilter = nil
local activeFilter = 'all'
local selectedCreatureId = nil
local refreshCreatureList
local BESTIARY_OPCODE = 124
local BESTIARY_MAX_KILLS = 1000
local bestiaryProgress = {}
local STAGES = {100, 500, 1000} -- Visual milestones only; no rewards or new storage.

local function matchesProgress(kills)
	return activeFilter == 'all' or (activeFilter == 'progress' and kills > 0 and kills < BESTIARY_MAX_KILLS)
		or (activeFilter == 'completed' and kills >= BESTIARY_MAX_KILLS)
end

local function normalizedName(name)
	return tostring(name or ""):lower():gsub("%s+", " ")
end

local function getKillCount(name)
	return math.max(0, math.min(BESTIARY_MAX_KILLS, tonumber(bestiaryProgress[normalizedName(name)]) or 0))
end

local function setCreaturePreview(widget, outfit)
	widget:setOutfit(outfit)
	-- Keep the original south-facing frame's pixel scale in a fixed 64px slot.
	local thing = g_things.getThingType(outfit.type, ThingCategoryCreature)
	local pixels = thing and thing:getExactSize(0, 2, 0, 0, 0) or 32
	pixels = math.max(1, math.min(64, pixels))
	widget:setSize({width = pixels, height = pixels})
end

local function fitCreatureName(label, name)
	-- This client's automatic wrapping is not recomputed reliably on resize.
	-- Use two measured lines, as in the existing Market title component.
	label:setText(name)
	if label:getWidth() < 1 or label:getTextSize().width <= label:getWidth() then return end
	local first = ''
	for word in name:gmatch('%S+') do
		local candidate = first == '' and word or first .. ' ' .. word
		label:setText(candidate)
		if label:getTextSize().width > label:getWidth() then break end
		first = candidate
	end
	if first == '' then label:setText(name) return end
	local rest = name:sub(#first + 1):match('^%s*(.*)$')
	label:setText(first .. (rest ~= '' and '\n' .. rest or ''))
end

local function updateProgressWidget(widget, name)
	if not widget then return end
	local kills = getKillCount(name)
	local progressBar = widget:recursiveGetChildById("killProgressBar")
	local progressText = widget:recursiveGetChildById("killProgressText")
	if progressBar then
		progressBar:setPercent(kills * 100 / BESTIARY_MAX_KILLS)
		progressBar:setVisible(kills > 0)
	end
	if progressText then
		progressText:setText(string.format("%d / %d %s %d%%", kills, BESTIARY_MAX_KILLS, string.char(183), math.floor(kills * 100 / BESTIARY_MAX_KILLS)))
	end
	for index, threshold in ipairs(STAGES) do
		local marker = widget:recursiveGetChildById('stage' .. index)
		if marker then marker:setBackgroundColor(kills >= threshold and '#958358' or '#262626') end
	end
	if widget.isBestiaryCard then
		local selected = widget.creatureId == selectedCreatureId
		widget:setBorderColor(selected and '#B5B0A1' or (kills >= BESTIARY_MAX_KILLS and '#8F7D4C' or '#555555'))
		widget:setBackgroundColor(selected and '#41413E' or '#343434')
		widget:setTooltip(name .. '\n' .. kills .. ' / ' .. BESTIARY_MAX_KILLS .. ' kills\nMilestones: 100 / 500 / 1000 kills')
	end
end

local function updateVisibleProgress()
	if not wikiWindow then return end
	refreshCreatureList(false)

	if creatureWindow and creatureWindow.creatureId then
		local item = wikiItemsData[creatureWindow.creatureId]
		if item then updateProgressWidget(creatureWindow, item.name) end
	end
end

local function requestProgress()
	if not g_game.isOnline() or not g_game.getFeature(GameExtendedOpcode) then return end
	local protocol = g_game.getProtocolGame()
	if not protocol then return end

	local names = {}
	for _, item in ipairs(data) do
		names[#names + 1] = item.name
	end
	protocol:sendExtendedOpcode(BESTIARY_OPCODE, json.encode({action = "getProgress", monsters = names}))
end

local function onBestiaryOpcode(protocol, opcode, buffer)
	if opcode ~= BESTIARY_OPCODE or type(buffer) ~= "string" or #buffer > 16384 then return end
	local decoded, payload = pcall(function() return json.decode(buffer) end)
	if not decoded or type(payload) ~= "table" then return end

	if payload.action == "progress" then
		if type(payload.data) ~= "table" then return end
		bestiaryProgress = {}
		for name, kills in pairs(payload.data) do
			if type(name) == "string" then
				bestiaryProgress[normalizedName(name)] = math.max(0, math.min(BESTIARY_MAX_KILLS, tonumber(kills) or 0))
			end
		end
	elseif payload.action == "update" and type(payload.monster) == "string" then
		bestiaryProgress[normalizedName(payload.monster)] = math.max(0, math.min(BESTIARY_MAX_KILLS, tonumber(payload.kills) or 0))
	else
		return
	end
	updateVisibleProgress()
end

local function onGameEnd()
	bestiaryProgress = {}
	selectedCreatureId = nil
	activeFilter = 'all'
	hide()
	updateVisibleProgress()
end

function resizeBestiary()
	if not wikiWindow then return end
	local rootSize = rootWidget:getSize()
	wikiWindow:setSize({width = math.min(700, rootSize.width - 16), height = math.min(450, rootSize.height - 16)})
	local list = wikiWindow:recursiveGetChildById('list')
	local width = list:getWidth()
	local columns = math.max(1, math.min(4, math.floor((width + 4) / 140)))
	local layout = list:getLayout()
	layout:setNumColumns(columns)
	layout:setCellSize({width = math.floor((width - (columns - 1) * 4) / columns), height = 132})
	if creatureWindow then
		creatureWindow:setSize({width = math.min(570, rootSize.width - 24), height = math.min(330, rootSize.height - 24)})
	end
end

function init()
    wikiWindow = g_ui.displayUI('wiki')
    creatureFilter = wikiWindow:getChildById("creatureFilter")
	wikiItemsData = data

	connect(g_game, {onGameEnd = onGameEnd})
    connect(creatureFilter, {onTextChange = filterCreature})
	connect(rootWidget, {onGeometryChange = resizeBestiary})
	ProtocolGame.registerExtendedOpcode(BESTIARY_OPCODE, onBestiaryOpcode, true)

	-- Anti-steal code
  if (REGISTRATION_KEY ~= "AbcDeFgH") then
	g_logger.fatal("Invalid serial ID for the server, please contact julianandresbernalv@gmail.com or JulianBernalV#7033")
  end

end

function terminate()
	disconnect(rootWidget, {onGeometryChange = resizeBestiary})
	if creatureFilter then disconnect(creatureFilter, {onTextChange = filterCreature}) end
    if creatureWindow ~= nil then
	creatureWindow:destroy()
    end
    if wikiWindow ~= nil then
	wikiWindow:destroy()
    end

	disconnect(g_game, {
	    onGameEnd = onGameEnd,
	  })
	ProtocolGame.unregisterExtendedOpcode(BESTIARY_OPCODE)
	wikiWindow, creatureWindow, creatureFilter = nil, nil, nil
end

function show()
	if not wikiWindow then return end
	resizeBestiary()
	refreshCreatureList(false)
	wikiWindow:show()
	wikiWindow:raise()
	requestProgress()
end

function hide()
	if creatureWindow ~= nil then
	creatureWindow:hide()
    end
	if wikiWindow ~= nil then
	wikiWindow:hide()
    end

end

function toggle()
	if wikiWindow ~= nil and wikiWindow:isVisible() then
		if creatureWindow ~= nil then
		creatureWindow:hide()
	    end
	wikiWindow:hide()
	else
		show()
	end
end

refreshCreatureList = function(resetScroll)
	if not wikiWindow then return end
	local listPanel = wikiWindow:getChildById('listPanel')
	local list = listPanel:getChildById('list')
	local scrollbar = listPanel:getChildById('listScrollbar')
	local text = creatureFilter:getText():lower()

	local visible = {}
	for i = 1, #wikiItemsData do
		local item = wikiItemsData[i]
		if matchesProgress(getKillCount(item.name)) and (text == '' or item.name:lower():find(text, 1, true)) then
			visible[#visible + 1] = i
		end
	end
	local children = list:getChildren()
	local rebuild = #children ~= #visible
	for index, id in ipairs(visible) do
		if not children[index] or children[index].creatureId ~= id then rebuild = true break end
	end
	local oldScroll = scrollbar:getValue()
	if rebuild then
		local layout = list:getLayout()
		layout:disableUpdates()
		list:destroyChildren()
		for _, id in ipairs(visible) do
			local item = wikiItemsData[id]
			local card = g_ui.createWidget('MonsterObject', list)
			card.creatureId, card.isBestiaryCard = id, true
			setCreaturePreview(card:recursiveGetChildById('creature'), item.look)
			local title = card:recursiveGetChildById('creatureLabel')
			title.onGeometryChange = function() fitCreatureName(title, item.name) end
			fitCreatureName(title, item.name)
		end
		layout:enableUpdates()
		layout:update()
	end
	for _, card in ipairs(list:getChildren()) do updateProgressWidget(card, wikiItemsData[card.creatureId].name) end
	listPanel:getChildById('emptyState'):setVisible(#visible == 0)
	wikiWindow:getChildById('resultCount'):setText(string.format('%d / %d', #visible, #wikiItemsData))
	for _, filter in ipairs({'all', 'progress', 'completed'}) do
		wikiWindow:getChildById('filter_' .. filter):setOn(activeFilter == filter)
	end
	if resetScroll then scrollbar:setValue(0) elseif rebuild then scrollbar:setValue(oldScroll) end
end

function filterCreature()
	refreshCreatureList(true)
end

function setProgressFilter(value)
	if value ~= 'all' and value ~= 'progress' and value ~= 'completed' then return end
	activeFilter = value
	refreshCreatureList(true)
end

function selectCreature(creatureId)
	if not wikiItemsData[creatureId] then return end
	selectedCreatureId = creatureId
	refreshCreatureList(false)
	if nil ~= creatureWindow then
	creatureWindow:destroy()
    end

    if wikiItemsData ~= nil and #wikiItemsData > 0 then
		creatureWindow = g_ui.displayUI('creature')
		creatureWindow.creatureId = creatureId
		creatureWindow:setText(tr(wikiItemsData[creatureId].name))

		resizeBestiary()
		local creature = creatureWindow:recursiveGetChildById('creature')
		setCreaturePreview(creature, wikiItemsData[creatureId].look)

		local place = creatureWindow:getChildById('placeDesc')
		if #wikiItemsData[creatureId].place > 5 then
			place:setText(wikiItemsData[creatureId].place)
		else
			place:setText("Unknown")
		end

		local loot = creatureWindow:getChildById('lootDesc')
		local monsterLoot = wikiItemsData[creatureId].loot
		if type(monsterLoot) ~= 'table' then monsterLoot = {} end
		local names, seen = {}, {}
		for _, entry in ipairs(monsterLoot) do
			local name = entry.itemName
			if type(name) == 'string' and name ~= '' and not seen[name] then
				names[#names + 1], seen[name] = name, true
			end
		end
		local lootText = table.concat(names, ', ')
		-- Read-only catalog text: keep all names, including long loot lists.
		loot:setMaxLength(math.max(#lootText, 200))
		loot:setCursorVisible(false)

		if #lootText > 1 then
			loot:setText(lootText)
		else
			loot:setText("This creature does not drop any loot.")
		end

		local health = creatureWindow:getChildById('healthInfo')
		health:setText(wikiItemsData[creatureId].health)

		local manacost = creatureWindow:getChildById('summonInfo')
		manacost:setText(wikiItemsData[creatureId].manacost)

		local exp = creatureWindow:getChildById('expInfo')
		exp:setText(wikiItemsData[creatureId].experience)
		updateProgressWidget(creatureWindow, wikiItemsData[creatureId].name)
	end
end

function closeCreature()
	if creatureWindow ~= nil then
	creatureWindow:hide()
    end
end

function clearFilter()
	creatureFilter:setText('')
end
