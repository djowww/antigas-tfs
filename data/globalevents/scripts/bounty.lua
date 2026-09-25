function onThink(interval)
    local resultId = db.storeQuery([[SELECT p.name, b.prize, b.currencyType
        FROM bounty_hunter_system b
        INNER JOIN players p ON p.id = b.target_id
        WHERE b.killed = 0 ORDER BY b.prize DESC, b.id ASC LIMIT 3]])
    if not resultId then
        return true
    end
    local lines = {"MOST WANTED:"}
    local number = 1
    repeat
        lines[#lines + 1] = string.format("%d. %s - %d %s", number,
            result.getDataString(resultId, "name"),
            result.getDataInt(resultId, "prize"),
            result.getDataString(resultId, "currencyType"))
        number = number + 1
    until not result.next(resultId)
    result.free(resultId)
    Game.broadcastMessage(table.concat(lines, "\n"))
    return true
end
