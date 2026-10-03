-- private variables
local background
local infoWindow

local accesAccountLink = "https://tibia74.tech/"
local websiteLink = "https://tibia74.tech/"
downloadClient = "https://tibia74.tech/"

local infoTexts = {
 [1] = "Antigas 7.4",
 [2] = "Classic 7.4 visuals",
 [3] = "Antigas server",
 [4] = "Retro client",
 [5] = "",
 [6] = "Official site",
 [7] = "tibia74.tech",
}

-- public functions
function init()
  background = g_ui.displayUI('background')
  background:lower()

  infoWindow = background:getChildById('infoBox')
  infoWindow:hide()
  
  connect(g_game, { onGameStart = hide })
  connect(g_game, { onGameEnd = show })
  
  setClientInfo()
end

function terminate()
  disconnect(g_game, { onGameStart = hide })
  disconnect(g_game, { onGameEnd = show })

  infoWindow:destroy()
  background:destroy()
  Background = nil
end

function hide()
  background:hide()
end

function show()
  background:show()
end

function infoShow()
  if not infoWindow:isVisible() then
     infoWindow:setVisible(true)
  end
end

function infoHide()
  if infoWindow:isVisible() then
    infoWindow:setVisible(false)
  end
end

function accesAccount()
   g_platform.openUrl(accesAccountLink)
end

function openWebsite()
   g_platform.openUrl(websiteLink)
end

function setClientInfo()
  for label, text in pairs(infoTexts) do 
    local label = infoWindow:getChildById('infoLabel' .. label)
    label:setText(text)
  end
end
