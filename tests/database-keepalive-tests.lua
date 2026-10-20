local sync, async, freed = 0, 0, 0
local available = true
db = {
    storeQuery = function(sql)
        assert(sql == 'SELECT 1 AS alive', 'heartbeat must be read-only')
        sync = sync + 1
        return available and 41 or false
    end,
    asyncQuery = function(sql)
        assert(sql == 'DO 1', 'worker heartbeat must have no persistent effects')
        async = async + 1
        return available
    end
}
result = {free = function(id) assert(id == 41); freed = freed + 1 end}
dofile('data/globalevents/scripts/database_keepalive.lua')
assert(onThink(60000))
assert(sync == 1 and async == 1 and freed == 1, 'both sessions must be kept alive and result freed')
available = false
assert(onThink(60000), 'an outage must not disable subsequent heartbeats')
assert(sync == 2 and async == 2 and freed == 1, 'failed reads must not free invalid handles')
available = true
assert(onThink(60000))
assert(sync == 3 and async == 3 and freed == 2, 'heartbeat must resume after recovery')
print('Database heartbeat tests passed: both sessions, outage, recovery, result cleanup')
