--[[Spider Egg
    --Classification:    Natural Products
    --Attributes: Summon a monster when broken.
    --Add: Unknow
    --Location: Spider and Tarantula caves, such as those found in Tiquanda.
    --Notes: Spider Eggs are very fragile and will break when attacked. They will either release nothing, a Spider, a Poison Spider, a Tarantula at rare times and very rarely a Giant Spider. Spiders that come from those eggs will not puff like normal spiders do when taken away too far from their spawn point.
    --To break the Spider Egg, simply use the egg.
    --Font: Tibia Wiki]]

function onUse(player, item, fromPosition, target, toPosition, isHotkey)

    local n = math.random(0, 1000)
    
    
    if n < 10 then
      Game.createMonster("Giant Spider", item:getPosition()) -- 10 / 1000 * 100 = ~1% chance to be born a GS.
    elseif n <= 60 then
      Game.createMonster("Tarantula", item:getPosition()) -- 60 - 10 = 50 / 1000 * 100 = ~5% chance to be born a Tarantula.
    elseif n <= 210 then
      Game.createMonster("Poison Spider", item:getPosition()) -- 210 - 60 = 150 / 1000 * 100 = ~15%  chance to be born a PS.
    elseif n <= 510 then
      Game.createMonster("Spider", item:getPosition()) -- 510 - 210 = 300 / 1000 * 100 = ~30% chance to be born a Spider.
    else
      fromPosition:sendMagicEffect(CONST_ME_POFF) -- 1000 - 510 = 490 / 1000 * 100 = ~49% chance of Fail.
    end
    
    item:transform(5251) -- Transform on remains of a spider egg.
    
    -- Native decay never retains unsafe item userdata in a delayed Lua callback.
    item:decay()
    return true
    
end
