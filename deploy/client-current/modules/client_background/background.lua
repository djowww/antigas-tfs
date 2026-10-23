-- private variables
local background
local infoWindow

local accesAccountLink = ""
local websiteLink = ""
downloadClient = ""

local infoTexts = {
 [1] = "Tibia 7.4 Local",
 [2] = "Classic 7.4 visuals",
 [3] = "Account: 1 / local123",
 [4] = "Retro client",
 [5] = "",
 [6] = "Local test",
 [7] = "127.0.0.1",
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
   if accesAccountLink ~= "" then g_platform.openUrl(accesAccountLink) end
end

function openWebsite()
   if websiteLink ~= "" then g_platform.openUrl(websiteLink) end
end

function setClientInfo()
  for label, text in pairs(infoTexts) do
    local label = infoWindow:getChildById('infoLabel' .. label)
    label:setText(text)
  end
end
