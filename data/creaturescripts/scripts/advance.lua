local config = {
    heal = true,
    save = false,
    effect = true
}

function onAdvance(player, skill, oldLevel, newLevel)
    if skill ~= SKILL_LEVEL or newLevel <= oldLevel then
        return true
    end

    if config.effect then
        player:getPosition():sendMagicEffect(13, isInGhostMode and player)
    end

    if config.heal then
        player:addHealth(player:getMaxHealth())
        player:addMana(player:getMaxMana())
    end

    if config.save then
        player:save()
    end
    return true
end