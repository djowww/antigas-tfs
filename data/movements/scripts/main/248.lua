local event_duration = 1 * 60
local event_interval = 1
local wand_pos = {x = 32509, y = 31589, z = 15}
local runningUntil = 0
local positions = {
    {x = 32511, y = 31593, z = 15},
    {x = 32510, y = 31593, z = 15},
    {x = 32509, y = 31593, z = 15},
 	{x = 32508, y = 31593, z = 15},
 	{x = 32507, y = 31593, z = 15},
	{x = 32512, y = 31592, z = 15},
	{x = 32511, y = 31592, z = 15},
	{x = 32510, y = 31592, z = 15},
	{x = 32508, y = 31592, z = 15},
	{x = 32507, y = 31592, z = 15},
	{x = 32506, y = 31592, z = 15},
	{x = 32513, y = 31591, z = 15},
	{x = 32512, y = 31591, z = 15},
	{x = 32511, y = 31591, z = 15},
	{x = 32509, y = 31591, z = 15},
	{x = 32507, y = 31591, z = 15},
	{x = 32506, y = 31591, z = 15},
	{x = 32505, y = 31591, z = 15},
	{x = 32513, y = 31590, z = 15},
	{x = 32512, y = 31590, z = 15},
	{x = 32510, y = 31590, z = 15},
	{x = 32509, y = 31590, z = 15},
	{x = 32508, y = 31590, z = 15},
	{x = 32506, y = 31590, z = 15},
	{x = 32505, y = 31590, z = 15},
	{x = 32513, y = 31589, z = 15},
	{x = 32513, y = 31589, z = 15},
	{x = 32512, y = 31589, z = 15},
	{x = 32511, y = 31589, z = 15},
	{x = 32510, y = 31589, z = 15},
	{x = 32508, y = 31589, z = 15},
	{x = 32507, y = 31589, z = 15},
	{x = 32506, y = 31589, z = 15},
	{x = 32505, y = 31589, z = 15},
	{x = 32513, y = 31588, z = 15},
	{x = 32512, y = 31588, z = 15},
	{x = 32510, y = 31588, z = 15},
	{x = 32509, y = 31588, z = 15},
	{x = 32508, y = 31588, z = 15},
	{x = 32506, y = 31588, z = 15},
	{x = 32505, y = 31588, z = 15},
	{x = 32513, y = 31587, z = 15},
	{x = 32512, y = 31587, z = 15},
	{x = 32511, y = 31587, z = 15},
	{x = 32509, y = 31587, z = 15},
	{x = 32507, y = 31587, z = 15},
	{x = 32506, y = 31587, z = 15},
	{x = 32505, y = 31587, z = 15},
	{x = 32512, y = 31586, z = 15},
	{x = 32511, y = 31586, z = 15},
	{x = 32510, y = 31586, z = 15},
	{x = 32508, y = 31586, z = 15},
	{x = 32507, y = 31586, z = 15},
	{x = 32506, y = 31586, z = 15},
	{x = 32511, y = 31585, z = 15},
	{x = 32510, y = 31585, z = 15},
	{x = 32509, y = 31585, z = 15},
	{x = 32508, y = 31585, z = 15},
	{x = 32507, y = 31585, z = 15},
}

local function repeatEffect(position, effect, interval, end_time)
    if os.time() >= end_time then
        return
    end

    Game.sendMagicEffect(position, effect)
    addEvent(repeatEffect, interval * 1000, position, effect, interval, end_time)
end

function onAddItem(item, tileitem, position)
    if item.itemid ~= 3034 then
    	Game.sendMagicEffect(position, 16)
    	item:remove()
    else
        Game.sendMagicEffect(position, 16)
        Game.removeItemOnMap(position, 3034)
        if os.time() >= runningUntil then
            for key, pos in pairs(positions) do
                if pos.x == position.x and pos.y == position.y then
                    repeatEffect(wand_pos, 15, event_interval, os.time() + event_duration)
                    runningUntil = os.time() + event_duration
                    break
                end
            end
        end
    end
    return true
end

