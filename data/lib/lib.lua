-- Core API functions implemented in Lua
dofile('data/lib/core/core.lua')
dofile('data/lib/lamp_states.lua')

-- GM-only task window and kill-counter configuration.
dofile('data/lib/custom/antigasTasks.lua')

-- Compatibility library for our old Lua API
dofile('data/lib/compat/compat.lua')

dofile('data/lib/modalwindow.lua')

-- Crash-safe inventory/SQL changes for purchases and currency exchange.
dofile('data/lib/custom/economy.lua')

-- Online Time System
dofile('data/lib/custom/onlineTime.lua')

-- Persistent bonus earned for each uninterrupted hour online.
ONLINE_STAY_BONUS_STORAGE = 17592
ONLINE_STAY_BONUS_MAX = 24
