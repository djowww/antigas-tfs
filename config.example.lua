-- Example only. Set real values in config.lua on your own server.
-- Never commit database credentials or the private RSA key.
worldType = "pvp"
protectionLevel = 1
pzLocked = 60000
removeChargesFromRunes = true
timeToDecreaseFrags = 6 * 60 * 60 * 1000
stairJumpExhaustion = 0
experienceByKillingPlayers = false
expFromPlayersLevelRange = 75
hotkeyAimbotEnabled = true

banLength = 3 * 24 * 60 * 60
whiteSkullTime = 15 * 60 * 1000
redSkullTime = 3 * 24 * 60 * 60
killsDayRedSkull = 3
killsWeekRedSkull = 5
killsMonthRedSkull = 10
killsDayBanishment = 6
killsWeekBanishment = 10
killsMonthBanishment = 20

ip = "127.0.0.1"
bindOnlyGlobalAddress = false
loginProtocolPort = 7173
gameProtocolPort = 7174
statusProtocolPort = 7173
maxPlayers = 2000
motd = "Bem-vindo ao Antigas 7.4! Crie sua conta em tibia74.tech"
onePlayerOnlinePerAccount = true
allowClones = false
serverName = "Antigas 7.4"
statusTimeout = 5000
replaceKickOnLogin = true
maxPacketsPerSecond = 50
autoStackCumulatives = true
uhTrap = true
moneyRate = 2

-- Custom Configs
blockLogin = false
blockLoginText = "Server launch: COMING SOON."

deathLosePercent = -1

houseRentPeriod = "monthly"
onlyInvitedCanMoveHouseItems = true

timeBetweenActions = 200
timeBetweenExActions = 1000

mapName = "map"
mapAuthor = "Tibia"

mysqlHost = "127.0.0.1"
mysqlUser = "CHANGE_ME"
mysqlPass = ""
mysqlDatabase = "DATABASE_NAME"
mysqlPort = 3306
mysqlSock = ""
passwordType = "sha1"

allowChangeOutfit = true
freePremium = true
kickIdlePlayerAfterMinutes = 15
maxMessageBuffer = 0
showMonsterLoot = true
queryPlayerContainers = true
emoteSpells = false

teleportNewbies = true
newbieTownId = 11
newbieLevelThreshold = 5


rateExp = 1
rateSkill = 1
rateLoot = 1
rateMagic = 1
rateSpawn = 0

deSpawnRange = 0
deSpawnRadius = 0

warnUnsafeScripts = true
convertUnsafeScripts = true

defaultPriority = "high"
startupDatabaseOptimization = true

ownerName = "Antigas 7.4"
ownerEmail = "admin@example.invalid"
url = "https://tibia74.tech"
location = "Sao Paulo"
