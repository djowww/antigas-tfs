local drunk = Condition(CONDITION_DRUNK)
drunk:setParameter(CONDITION_PARAM_TICKS, 60000)

local poison = Condition(CONDITION_POISON)
poison:addDamage(1, 4000, -0)
poison:addDamage(1, 4000, -10)
poison:addDamage(2, 4000, -9)
poison:addDamage(2, 4000, -8)
poison:addDamage(3, 4000, -7)
poison:addDamage(3, 4000, -6)
poison:addDamage(4, 4000, -5)
poison:addDamage(4, 4000, -4)
poison:addDamage(6, 4000, -3)
poison:addDamage(10, 4000, -2)
poison:addDamage(10, 4000, -1)
poison:addDamage(10, 4000, -1)
poison:addDamage(10, 4000, -1)
poison:addDamage(8, 3950, -1)
poison:addDamage(1, 3940, -1)

local messages = {
	[FLUID_WATER] = "Gulp.",
	[FLUID_WINE] = "Aah...",
	[FLUID_BEER] = "Aah...",
	[FLUID_MUD] = "Gulp.",
	[FLUID_BLOOD] = "Gulp.",
	[FLUID_SLIME] = "Urgh!",
	[FLUID_OIL] = "Gulp.",
	[FLUID_URINE] = "Urgh!",
	[FLUID_MILK] = "Mmmh.",
	[FLUID_MANAFLUID] = "Aaaah...",
	[FLUID_LIFEFLUID] = "Aaaah...",
	[FLUID_LEMONADE] = "Mmmh."
}

function onUse(player, item, fromPosition, target, toPosition)
	local targetItemType = ItemType(target:getId())
	if targetItemType and targetItemType:isFluidContainer() then
			if target:getFluidType() == 0 and item:getFluidType() ~= 0 then
			target:transform(target:getId(), item:getFluidType())
			item:transform(item:getId(), 0)
			return true
		elseif item:getFluidType() == 0 and target:getFluidType() ~= 0 then
			return false
		elseif target:getFluidType() ~= 0 and item:getFluidType() == 0 then
			target:transform(target:getId(), 0)
			item:transform(item:getId(), target:getFluidType())
			return true
		end
	end
	
	if target:isCreature() and target == player then
		if item:getFluidType() == FLUID_NONE then
			player:sendCancelMessage("It is empty.")
		else
			local self = target == player
			if self and item:getFluidType() == FLUID_BEER or item:getFluidType() == FLUID_WINE then
				player:addCondition(drunk)
			elseif self and item:getFluidType() == FLUID_SLIME then
				player:addCondition(poison)
			elseif item:getFluidType() == FLUID_MANAFLUID then
				target:addMana(math.random(50, 100))
				target:getPosition():sendMagicEffect(CONST_ME_MAGIC_BLUE)
			elseif item:getFluidType() == FLUID_LIFEFLUID then
				target:addHealth(math.random(50, 60))
				target:getPosition():sendMagicEffect(CONST_ME_MAGIC_BLUE)
			end
			
			if not self then
				if item:getFluidType() ~= FLUID_MANAFLUID and item:getFluidType() ~= FLUID_LIFEFLUID then
					if toPosition.x == CONTAINER_POSITION then
						toPosition = player:getPosition()
					end
					Game.createItem(2886, item:getFluidType(), toPosition):decay()
					return true
				end
			end
			
			local message = messages[item:getFluidType()]
			if message then
				target:say(message, TALKTYPE_SAY)
			else
				target:say("Gulp.", TALKTYPE_SAY)
			end
			item:transform(item:getId(), FLUID_NONE)
		end
	else
		if toPosition.x == CONTAINER_POSITION then
			toPosition = player:getPosition()
		end
		
		local tile = Tile(toPosition)
		if not tile then
			return false
		end
		
		if item:getFluidType() ~= FLUID_NONE and tile:hasFlag(TILESTATE_IMMOVABLEBLOCKSOLID) then
			return false
		end
		
		local fluidSource = targetItemType and targetItemType:getFluidSource() or FLUID_NONE
		if fluidSource ~= FLUID_NONE then
			item:transform(item:getId(), fluidSource)
		elseif item:getFluidType() == FLUID_NONE then
			player:sendTextMessage(MESSAGE_STATUS_SMALL, "It is empty.")
		else

			Game.createItem(2886, item.type, toPosition):decay()
				item:transform(item:getId(), FLUID_NONE)
		end
	end
	return true
end