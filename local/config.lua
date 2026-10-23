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
hotkeyAimbotEnabled = false

banLength = 3 * 24 * 60 * 60
whiteSkullTime = 15 * 60 * 1000
redSkullTime = 30 * 24 * 60 * 60
killsDayRedSkull = 3
killsWeekRedSkull = 5
killsMonthRedSkull = 10
killsDayBanishment = 6
killsWeekBanishment = 10
killsMonthBanishment = 20

ip = "127.0.0.1"
bindOnlyGlobalAddress = false
loginProtocolPort = 17173
gameProtocolPort = 17174
statusProtocolPort = 17173
maxPlayers = 2000
-- 0 selects maxPlayers + 256 (or 4096 when maxPlayers is unlimited).
maxConnections = 0
maxConnectionsPerIP = 128
motd = "Local test server. Account: 1 / local123"
onePlayerOnlinePerAccount = true
allowClones = false
serverName = "Tibia 7.4 - Local"
statusTimeout = 5000
replaceKickOnLogin = true
maxPacketsPerSecond = 50
autoStackCumulatives = true
uhTrap = true
moneyRate = 2

-- Custom Configs
blockLogin = false
blockLoginText = "Server launch: COMING SOON."

deathLosePercent = 10

-- The later bank-backed rent path stays disabled until a documented pre-bank
-- collection policy is available. Never remove owners to enforce a guessed rule.
houseRentPeriod = "never"
onlyInvitedCanMoveHouseItems = true

timeBetweenActions = 200
timeBetweenExActions = 1000

mapName = "map"
mapAuthor = "Tibia"

mysqlHost = "127.0.0.1"
mysqlUser = "localgame"
mysqlPass = "localgame"
mysqlDatabase = "tibia_local"
mysqlPort = 3306
mysqlSock = ""
passwordType = "sha1"

allowChangeOutfit = true
freePremium = false
kickIdlePlayerAfterMinutes = 15
-- Use the core's existing message limiter default; its numerical threshold is
-- an implementation setting, not a certified value from the 7.4 manual.
showMonsterLoot = true
queryPlayerContainers = true
emoteSpells = false

teleportNewbies = false
newbieTownId = 11
newbieLevelThreshold = 5


rateExp = 1
rateSkill = 1
rateLoot = 1
-- Rarity chance per eligible monster equipment drop, from 0 to 10000 (1000 = 10%).
itemRarityLootChance = 1000
rateMagic = 1
rateSpawn = 0

deSpawnRange = 0
deSpawnRadius = 0

warnUnsafeScripts = true
convertUnsafeScripts = true

defaultPriority = "high"
startupDatabaseOptimization = true

ownerName = "Local test"
ownerEmail = "admin@example.invalid"
url = "http://127.0.0.1"
location = "Sao Paulo"

-- Container-only database hostname; no database port is published.
mysqlHost = "db"
startupDatabaseOptimization = false
