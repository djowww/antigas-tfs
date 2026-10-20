-- The dispatcher and DatabaseTasks have separate MySQL sessions. Keep both
-- active while the world is empty so wait_timeout cannot break the first save.
-- These statements have no persistent effects and never replay a player write.
function onThink(interval)
    local resultId = db.storeQuery('SELECT 1 AS alive')
    if resultId then result.free(resultId) end
    db.asyncQuery('DO 1')
    -- Keep scheduling during an outage; the database layer handles reconnection.
    return true
end
