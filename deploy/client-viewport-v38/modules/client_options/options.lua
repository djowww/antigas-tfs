local defaultOptions = {
	vsync = true,
	showFps = true,
	showPing = true,
	fullscreen = false,
	classicView = true,
	gameView = 2,
	cacheMap = false,
	classicControl = true,
	smartWalk = false,
	dash = false,
	autoChaseOverride = true,
	showStatusMessagesInConsole = true,
	showEventMessagesInConsole = true,
	showInfoMessagesInConsole = true,
	showTimestampsInConsole = true,
	showLevelsInConsole = true,
	showPrivateMessagesInConsole = true,
	showPrivateMessagesOnScreen = true,
	rightPanels = 1,
	leftPanels = 0,
	containerPanel = 8,
	backgroundFrameRate = 100,
	enableAudio = true,
	enableMusicSound = true,
	musicSoundVolume = 100,
	botSoundVolume = 100,
	enableLights = false,
	floorFading = 0,
	crosshair = 0,
	ambientLight = 100,
	optimizationLevel = 2,
	displayNames = true,
	displayHealth = true,
	displayMana = true,
	displayHealthOnTop = false,
	showHealthManaCircle = true,
	hidePlayerBars = true,
	highlightThingsUnderCursor = false,
	topHealtManaBar = false,
	displayText = true,
	dontStretchShrink = false,
	turnDelay = 30,
	hotkeyDelay = 30,
	blueNpc = true,

	ignoreServerDirection = true,
	realDirection = false,

	wsadWalking = false,
	walkFirstStepDelay = 200,
	walkTurnDelay = 100,
	walkStairsDelay = 50,
	walkTeleportDelay = 200,
	walkCtrlTurnDelay = 150,

	actionBar1 = false,
	actionBar2 = false
}

local optionsWindow
local optionsButton
local optionsTabBar
local options = {}
local extraOptions = {}
local generalPanel
local interfacePanel
local viewportPanel
local consolePanel
local graphicsPanel
local soundPanel
local extrasPanel
local audioButton

EXTRAS_PANEL_ENABLED = false
CLASIC_TIBIA = true

function openDiscord()
   g_platform.openUrl("https://discord.gg/N75HG8eW59")
end

function init()
	for k,v in pairs(defaultOptions) do
		g_settings.setDefault(k, v)
		options[k] = v
	end
	
	for _, v in ipairs(g_extras.getAll()) do
		extraOptions[v] = g_extras.get(v)
		g_settings.setDefault("extras_" .. v, extraOptions[v])
	end
	
	-- Anti-steal code
	if (REGISTRATION_KEY ~= "AbcDeFgH") then
		g_logger.fatal("Invalid serial ID for the server, please contact julianandresbernalv@gmail.com")
	end
	
	optionsWindow = g_ui.displayUI('options')
	optionsWindow:hide()

	optionsTabBar = optionsWindow:getChildById('optionsTabBar')
	optionsTabBar:setContentWidget(optionsWindow:getChildById('optionsTabContent'))

	g_keyboard.bindKeyDown('Ctrl+F', function() toggleOption('fullscreen') end)
	g_keyboard.bindKeyDown('Ctrl+N', toggleDisplays)

	generalPanel = g_ui.loadUI('game')
	optionsTabBar:addTab(tr('General'), generalPanel, '/images/optionstab/option_button')
	
	consolePanel = g_ui.loadUI('console')
	optionsTabBar:addTab(tr('Console'), consolePanel, '/images/optionstab/option_button')
	
	graphicsPanel = g_ui.loadUI('graphics')
	optionsTabBar:addTab(tr('Graphics'), graphicsPanel, '/images/optionstab/option_button')
	if CLASIC_TIBIA then
		graphicsPanel:recursiveGetChildById("ambientLight"):hide() 
		graphicsPanel:recursiveGetChildById("ambientLightLabel"):hide()
	end
	
	interfacePanel = g_ui.loadUI('interface')
	viewportPanel = g_ui.loadUI('viewport')
	viewportPanel.gameView:setCurrentIndex(g_settings.getNumber('gameView'))
	viewportPanel.gameView.onOptionChange = function(widget)
		setOption('gameView', widget.currentIndex)
	end
	optionsTabBar:addTab(tr('Interface'), viewportPanel, '/images/optionstab/option_button')
	-- optionsTabBar:addTab(tr('Interface'), interfacePanel, '/images/optionstab/option_button') 
	if CLASIC_TIBIA then
		interfacePanel:recursiveGetChildById("showHealthManaCircle"):setHeight(0) 
		interfacePanel:recursiveGetChildById("showHealthManaCircle"):hide()
		interfacePanel:recursiveGetChildById("highlightThingsUnderCursor"):setHeight(0) 
		interfacePanel:recursiveGetChildById("highlightThingsUnderCursor"):hide()
		interfacePanel:recursiveGetChildById("displayHealthOnTop"):setHeight(-8) 
		interfacePanel:recursiveGetChildById("displayHealthOnTop"):hide()
		interfacePanel:recursiveGetChildById("actionBar1"):setHeight(0) 
		interfacePanel:recursiveGetChildById("actionBar1"):hide()
		interfacePanel:recursiveGetChildById("actionBar2"):setHeight(0) 
		interfacePanel:recursiveGetChildById("actionBar2"):hide()
		interfacePanel:recursiveGetChildById("cacheMap"):setHeight(0) 
		interfacePanel:recursiveGetChildById("cacheMap"):hide()
		interfacePanel:recursiveGetChildById("classicView"):setHeight(-32) 
		interfacePanel:recursiveGetChildById("classicView"):hide()
		interfacePanel:recursiveGetChildById("floorFadingLabel"):hide()
		interfacePanel:recursiveGetChildById("floorFading"):hide()
		interfacePanel:recursiveGetChildById("floorFadingLabel2"):hide()
		interfacePanel:recursiveGetChildById("crosshairLabel"):hide()
		interfacePanel:recursiveGetChildById("crosshair"):hide()
		interfacePanel:recursiveGetChildById("topHealtManaBar"):setHeight(-25) 
		interfacePanel:recursiveGetChildById("topHealtManaBar"):hide()
	end
	
	keyboardPanel = g_ui.loadUI('keyboard')
	optionsTabBar:addTab(tr('Keyboard'), keyboardPanel, '/images/optionstab/option_button')
	
	audioPanel = g_ui.loadUI('audio')
	--optionsTabBar:addTab(tr('Audio'), audioPanel, '/images/optionstab/option_button')
	
	extrasPanel = g_ui.createWidget('Panel')
	for _, v in ipairs(g_extras.getAll()) do
		local extrasButton = g_ui.createWidget('OptionCheckBox')
		extrasButton:setId(v)
		extrasButton:setText(g_extras.getDescription(v))
		extrasPanel:addChild(extrasButton)
	end

	if not g_game.getFeature(GameNoDebug) and EXTRAS_PANEL_ENABLED then
		optionsTabBar:addTab(tr('Extras'), extrasPanel, '/images/optionstab/option_button')
	end

	optionsButton = modules.client_topmenu.addLeftButton('optionsButton', tr('Options'), '/images/topbuttons/options', toggle)
	audioButton = modules.client_topmenu.addLeftButton('audioButton', tr('Audio'), '/images/topbuttons/audio', function() toggleOption('enableAudio') end)

	addEvent(function() setup() end)
	connect(g_game, { onGameStart = online, onGameEnd = offline })                    
end

function terminate()
  disconnect(g_game, { onGameStart = online,
                     onGameEnd = offline })  

  g_keyboard.unbindKeyDown('Ctrl+Shift+F')
  g_keyboard.unbindKeyDown('Ctrl+N')
  optionsWindow:destroy()
  optionsButton:destroy()
  audioButton:destroy()
end

function setup()
	-- load options
	for k,v in pairs(defaultOptions) do
		if type(v) == 'boolean' then
			setOption(k, g_settings.getBoolean(k), true)
		elseif type(v) == 'number' then
			setOption(k, g_settings.getNumber(k), true)
		end
	end
  
	for _, v in ipairs(g_extras.getAll()) do
		g_extras.set(v, g_settings.getBoolean("extras_" .. v))
		local widget = extrasPanel:recursiveGetChildById(v)
		if widget then
			widget:setChecked(g_extras.get(v))
		end
	end  
  
	if g_game.isOnline() then
		online()
	end  
end

function toggle()
	if optionsWindow:isVisible() then
		hide()
	else
		show()
	end
end

function show()
	optionsWindow:show()
	optionsWindow:raise()
	optionsWindow:focus()
end

function hide()
	optionsWindow:hide()
end

function toggleDisplays()
	if options['displayNames'] and options['displayHealth'] and options['displayMana'] then
		setOption('displayNames', false)
	elseif options['displayHealth'] then
		setOption('displayHealth', false)
		setOption('displayMana', false)
	else
		if not options['displayNames'] and not options['displayHealth'] then
			setOption('displayNames', true)
		else
			setOption('displayHealth', true)
			setOption('displayMana', true)
		end
	end
end

function toggleOption(key) 
	setOption(key, not getOption(key))
end

function setOption(key, value, force)
	if extraOptions[key] ~= nil then
		g_extras.set(key, value)
		g_settings.set("extras_" .. key, value)
		if key == "debugProxy" and modules.game_proxy then
			if value then
				modules.game_proxy.show()
			else
				modules.game_proxy.hide()      
			end
		end
	return
	end
  
	if modules.game_interface == nil then
		return
	end
   
	if not force and options[key] == value then return end
	local gameMapPanel = modules.game_interface.getMapPanel()

	if key == 'vsync' then
		g_window.setVerticalSync(value)
	elseif key == 'showFps' then
		modules.game_interface.setFpsVisible(value)
	elseif key == 'showPing' then
		modules.game_interface.setPingVisible(value)
	elseif key == 'fullscreen' then
		g_window.setFullscreen(value)
	elseif key == 'enableAudio' then
		if g_sounds ~= nil then
			g_sounds.setAudioEnabled(value)
		end
		if value then
			audioButton:setIcon('/images/topbuttons/audio')
		else
			audioButton:setIcon('/images/topbuttons/audio_mute')
		end
	elseif key == 'enableMusicSound' then
		if g_sounds ~= nil then
			g_sounds.getChannel(SoundChannels.Music):setEnabled(true)
		end
	elseif key == 'musicSoundVolume' then
		if g_sounds ~= nil then
			g_sounds.getChannel(SoundChannels.Music):setGain(value/100)
		end
		
		audioPanel:getChildById('musicSoundVolumeLabel'):setText(tr('Music volume: %d', value))
	elseif key == 'botSoundVolume' then
		if g_sounds ~= nil then
			g_sounds.getChannel(SoundChannels.Bot):setGain(value/100)
		end
		
		audioPanel:getChildById('botSoundVolumeLabel'):setText(tr('Bot sound volume: %d', value)) 		
	elseif key == 'backgroundFrameRate' then
		local text, v = value, value
		if value <= 0 or value >= 201 then text = 'max' v = 0 end
		graphicsPanel:getChildById('backgroundFrameRateLabel'):setText(tr('Game framerate limit: %s', text))
		g_app.setMaxFps(v)
	elseif key == 'enableLights' then
		gameMapPanel:setDrawLights(value and options['ambientLight'] < 100)
		graphicsPanel:getChildById('ambientLight'):setEnabled(value)
		graphicsPanel:getChildById('ambientLightLabel'):setEnabled(value)
	elseif key == 'floorFading' then
		gameMapPanel:setFloorFading(value)
		interfacePanel:getChildById('floorFadingLabel'):setText(tr('Floor fading: %s ms', value))
	elseif key == 'crosshair' then
		if value == 1 then
			gameMapPanel:setCrosshair("")    
		elseif value == 2 then
			gameMapPanel:setCrosshair("/data/images/crosshair/default.png")        
		elseif value == 3 then
			gameMapPanel:setCrosshair("/data/images/crosshair/full.png")    
		end
	elseif key == 'ambientLight' then
		graphicsPanel:getChildById('ambientLightLabel'):setText(tr('Ambient light: %s%%', value))
		gameMapPanel:setMinimumAmbientLight(value/100)
		gameMapPanel:setDrawLights(options['enableLights'] and value < 100)
	elseif key == 'optimizationLevel' then
		g_adaptiveRenderer.setLevel(0)
	elseif key == 'displayNames' then
		gameMapPanel:setDrawNames(value)
	elseif key == 'displayHealth' then
		gameMapPanel:setDrawHealthBars(value)
	elseif key == 'blueNpc' then
    if value then
  	   g_game.enableFeature(GameBlueNpcNameColor)
    else
	   g_game.disableFeature(GameBlueNpcNameColor)
    end	
	elseif key == 'displayMana' then
		gameMapPanel:setDrawManaBar(value)
	elseif key == 'displayHealthOnTop' then
		gameMapPanel:setDrawHealthBarsOnTop(value)
	elseif key == 'hidePlayerBars' then
		gameMapPanel:setDrawPlayerBars(value)
	elseif key == 'displayText' then
		gameMapPanel:setDrawTexts(value)
	elseif key == 'dontStretchShrink' then
		addEvent(function()
			modules.game_interface.updateStretchShrink()
		end)
	elseif key == 'dash' then
		if value then
			g_game.setMaxPreWalkingSteps(2)
		else 
			g_game.setMaxPreWalkingSteps(1)    
		end
	elseif key == 'wsadWalking' then
		if modules.game_console and modules.game_console.consoleToggleChat:isChecked() ~= value then
			modules.game_console.consoleToggleChat:setChecked(value)
		end
	elseif key == 'hotkeyDelay' then
		keyboardPanel:getChildById('hotkeyDelayLabel'):setText(tr('Hotkey delay: %s ms', value))  
	elseif key == 'walkFirstStepDelay' then
		keyboardPanel:getChildById('walkFirstStepDelayLabel'):setText(tr('Walk delay after first step: %s ms', value))  
	elseif key == 'walkTurnDelay' then
		keyboardPanel:getChildById('walkTurnDelayLabel'):setText(tr('Walk delay after turn: %s ms', value))  
	elseif key == 'walkStairsDelay' then
		keyboardPanel:getChildById('walkStairsDelayLabel'):setText(tr('Walk delay after floor change: %s ms', value))  
	elseif key == 'walkTeleportDelay' then
		keyboardPanel:getChildById('walkTeleportDelayLabel'):setText(tr('Walk delay after teleport: %s ms', value))  
	elseif key == 'walkCtrlTurnDelay' then
		keyboardPanel:getChildById('walkCtrlTurnDelayLabel'):setText(tr('Walk delay after ctrl turn: %s ms', value))  
	end  

  -- change value for keybind updates
	for _,panel in pairs(optionsTabBar:getTabsPanel()) do
		local widget = panel:recursiveGetChildById(key)
		if widget then
			if widget:getStyle().__class == 'UICheckBox' then
				widget:setChecked(value)
			elseif widget:getStyle().__class == 'UIScrollBar' then
				widget:setValue(value)
			elseif widget:getStyle().__class == 'UIComboBox' then
				if valur ~= nil or value < 1 then 
					value = 1
				end
			
				if widget.currentIndex ~= value then
					widget:setCurrentIndex(value)
				end
			end      
		break
		end
	end
  
	g_settings.set(key, value)
	options[key] = value
  
	if key == 'gameView' then
		modules.game_interface.updateMapViewport()
	elseif key == 'classicView' or key == 'rightPanels' or key == 'leftPanels' or key == 'cacheMap' then
		modules.game_interface.refreshViewMode()    
	elseif key == 'actionBar1' or key == 'actionBar2' then
	end
end

function getOption(key)
	return options[key]
end

function addTab(name, panel, icon)
	optionsTabBar:addTab(name, panel, icon)
end

function addButton(name, func, icon)
	optionsTabBar:addButton(name, func, icon)
end

function online()
	setLightOptionsVisibility(not g_game.getFeature(GameForceLight))
end

function offline()
	setLightOptionsVisibility(true)
end

-- graphics
function setLightOptionsVisibility(value)
	graphicsPanel:getChildById('enableLights'):setEnabled(value)
	graphicsPanel:getChildById('ambientLightLabel'):setEnabled(value)
	graphicsPanel:getChildById('ambientLight'):setEnabled(value)  
	interfacePanel:getChildById('floorFading'):setEnabled(value)
	interfacePanel:getChildById('floorFadingLabel'):setEnabled(value)
	interfacePanel:getChildById('floorFadingLabel2'):setEnabled(value)  
end
