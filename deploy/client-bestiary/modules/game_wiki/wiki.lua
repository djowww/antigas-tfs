local data = require "data/imperium_monster.lua"

local wikiItemsData = {}
local wikiWindow = nil
local creatureWindow = nil
local creatureFilter = nil
local clearFilterButton = nil
local BESTIARY_OPCODE = 124
local BESTIARY_MAX_KILLS = 1000
local bestiaryProgress = {}

local function normalizedName(name)
	return tostring(name or ""):lower():gsub("%s+", " ")
end

local function getKillCount(name)
	return math.max(0, math.min(BESTIARY_MAX_KILLS, tonumber(bestiaryProgress[normalizedName(name)]) or 0))
end

local function updateProgressWidget(widget, name)
	if not widget then return end
	local kills = getKillCount(name)
	local progressBar = widget:recursiveGetChildById("killProgressBar")
	local progressText = widget:recursiveGetChildById("killProgressText")
	if progressBar then
		progressBar:setPercent(kills * 100 / BESTIARY_MAX_KILLS)
	end
	if progressText then
		progressText:setText(string.format("%d / %d", kills, BESTIARY_MAX_KILLS))
	end
end

local function updateVisibleProgress()
	if not wikiWindow then return end
	local listPanel = wikiWindow:getChildById("listPanel")
	local list = listPanel and listPanel:getChildById("list")
	if list then
		for _, widget in ipairs(list:getChildren()) do
			local item = widget.creatureId and wikiItemsData[widget.creatureId]
			if item then updateProgressWidget(widget, item.name) end
		end
	end

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
	hide()
	updateVisibleProgress()
end

function init()
    wikiWindow = g_ui.displayUI('wiki')
    creatureFilter = wikiWindow:getChildById("creatureFilter")

	connect(g_game, {onGameEnd = onGameEnd})
    connect(creatureFilter, {onTextChange = filterCreature})
	ProtocolGame.registerExtendedOpcode(BESTIARY_OPCODE, onBestiaryOpcode, true)

	-- Anti-steal code
  if (REGISTRATION_KEY ~= "AbcDeFgH") then
	g_logger.fatal("Invalid serial ID for the server, please contact julianandresbernalv@gmail.com or JulianBernalV#7033")
  end

end

function terminate()
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
end

function show()
	filterCreature()
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

function filterCreature()
	local listPanel = wikiWindow:getChildById('listPanel')
	local list = listPanel:getChildById('list')
	local text = creatureFilter:getText():lower()

	list:destroyChildren()

	wikiItemsData = data
	for i=1, #wikiItemsData do

		local item = wikiItemsData[i]
		if text == "" or item.name:lower():find(text, 1, true) then
			local label = g_ui.createWidget("MonsterObject", list)
			label.creatureId = i

			local creature = label:recursiveGetChildById('creature')
			creature:setOutfit(item.look)

			local creatureLabel = label:recursiveGetChildById('creatureLabel')
			creatureLabel:setText(tr(item.name))
			updateProgressWidget(label, item.name)
		end
	end
	wikiWindow:show()

end

function selectCreature(creatureId)
	if nil ~= creatureWindow then
	creatureWindow:destroy()
    end

    if wikiItemsData ~= nil and #wikiItemsData > 0 then
		creatureWindow = g_ui.displayUI('creature')
		creatureWindow.creatureId = creatureId
		creatureWindow:setText(tr(wikiItemsData[creatureId].name))

		local creature = creatureWindow:getChildById('creature')
		creature:setOutfit(wikiItemsData[creatureId].look)

		local place = creatureWindow:getChildById('placeDesc')
		if #wikiItemsData[creatureId].place > 5 then
			place:setText(wikiItemsData[creatureId].place)
		else
			place:setText("Unknown")
		end

		local loot = creatureWindow:getChildById('lootDesc')
		local monsterLoot = wikiItemsData[creatureId].loot
		local lootText = ""
		for i=1, #monsterLoot do
			lootText = lootText .. wikiItemsData[creatureId].loot[i].itemName .. ', '
		end
		loot:setMaxLength(200)
		loot:setCursorVisible(false)
		lootText = lootText:sub(1, #lootText - 2)

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
	filterCreature()
end
