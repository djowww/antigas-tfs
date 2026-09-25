local combat = Combat()
combat:setParameter(COMBAT_PARAM_DISTANCEEFFECT, 3)
combat:setParameter(COMBAT_PARAM_EFFECT, CONST_ME_POFF)


function onUseWeapon(player, variant)
	local skillRate = 2 -- same config.lua
	player:addSkillTries(SKILL_DISTANCE, 20*skillRate)	
    return combat:execute(player, variant)
end