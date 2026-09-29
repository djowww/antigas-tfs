-- CONFIG
APP_NAME = "Antigas 7.4"
g_app.setName("Antigas 7.4")
APP_VERSION = 49        -- client release (independent of protocol 772)
SERVER_VERSION = 772
-- Keep mount fields enabled for protocol compatibility, but hide mount UI/actions.
MOUNTS_ENABLED = false
-- Keep addon fields enabled for protocol compatibility, but hide addon UI/actions.
ADDONS_ENABLED = false
STICK_MODULES = true
OLD_SCHOOL = true
PRODUCTION_MODE = false
REGISTRATION_KEY = "AbcDeFgH"
-- Public compatibility marker, never an authentication secret.
CLIENT_LOGIN_TAG = "Antigas-26"
-- Only the public half is distributed. The private key stays on the game host.
ANTIGAS_RSA_PUBLIC_KEY = "151443125323504204375382354287356003701006971573041073445496555415478359019135764120268216214793438872432577466463500772267222035885123566964906884006462345636524667036973926875446320056229710429874630771165351493794880179782407166548292481542252089147741100986631791473955222848947024386813939016739023607339"
AUTO_RECONNECT = false

-- If you don't use updater or other service, set it to updater = ""
Services = {
	website = "https://tibia74.tech",
	createAccountWebsite = "https://tibia74.tech/#criar-conta",
	accessAccountWebsite = "https://tibia74.tech/account.php",
	loginInfo = "",
	updater = "",
	releaseInfo = "https://tibia74.tech/client-release.json",
	-- stats = "",
	-- crash reporting and feedback are not configured
}

-- Servers accept http login url, websocket login url or ip:port:version
Servers = {
--  OTClientV8 = "http://otclient.ovh/api/login.php",
--  OTClientV8Websocket = "wss://otclient.ovh:3000/",
--  OTClientV8proxy = "http://otclient.ovh/api/login.php?proxy=1",
--  OTClientV8ClassicWithFeatures = "otclient.ovh:7171:1099:25:30:80:90",
 OTClientV8Classic = "187.77.238.51:7173:772"
}

USE_NEW_ENERGAME = false -- uses entergamev2 based on websockets instead of entergame
ALLOW_CUSTOM_SERVERS = false -- if true it shows option ANOTHER on server list
-- CONFIG END

-- print first terminal message
-- g_logger.info(os.date("== application started at %b %d %Y %X"))
-- g_logger.info(g_app.getName() .. ' ' .. g_app.getVersion() .. ' rev ' .. g_app.getBuildRevision() .. ' (' .. g_app.getBuildCommit() .. ') made by ' .. g_app.getAuthor() .. ' built on ' .. g_app.getBuildDate() .. ' for arch ' .. g_app.getBuildArch())

if not g_resources.directoryExists("/data") then
  g_logger.fatal("Data dir doesn't exist.")
end

if not g_resources.directoryExists("/modules") then
  g_logger.fatal("Modules dir doesn't exist.")
end

-- settings
g_configs.loadSettings("/config.otml")

-- set layout
local settings = g_configs.getSettings()
local layout = DEFAULT_LAYOUT
if g_app.isMobile() then
  layout = "mobile"
elseif settings:exists('layout') then
  layout = settings:getValue('layout')
end
g_resources.setLayout(layout)

-- load mods
g_modules.discoverModules()
g_modules.ensureModuleLoaded("corelib")

local function loadModules()
  -- libraries modules 0-99
  g_modules.autoLoadModules(99)
  g_modules.ensureModuleLoaded("gamelib")

  -- client modules 100-499
  g_modules.autoLoadModules(499)
  g_modules.ensureModuleLoaded("client")

  -- game modules 500-999
  g_modules.autoLoadModules(999)
  g_modules.ensureModuleLoaded("game_interface")

  -- mods 1000-9999
  g_modules.autoLoadModules(9999)
end

-- report crash
--if type(Services.crash) == 'string' and Services.crash:len() > 4 and g_modules.getModule("crash_reporter") then
  --g_modules.ensureModuleLoaded("crash_reporter")
--end

-- run updater, must use data.zip
if type(Services.updater) == 'string' and Services.updater:len() > 4
  and g_resources.isLoadedFromArchive() and g_modules.getModule("updater") then
  g_modules.ensureModuleLoaded("updater")
  return Updater.init(loadModules)
end
loadModules()
