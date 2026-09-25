function onLogin(player)
	local loginStr = "Welcome to Antigas 7.4"
	if player:getLastLoginSaved() <= 0 then
		player:sendOutfitWindow()
	else
		player:openChannel(4)
		player:openChannel(6)
		player:openChannel(7)
	end
	player:sendTextMessage(MESSAGE_STATUS_DEFAULT, loginStr)
	
	-- Maintenance mode
    --if (player:getGroup():getId() < 2) then
      --  return false
    --else
    --end

	-- Promotion
	if player:isPremium() then
		if player:getVocation():getId() ~= 0 and player:getVocation():getId() < 5 and player:getStorageValue(30018) == 1 then
			player:setVocation(player:getVocation():getId() + 4)
		end
	else
		if player:getVocation():getId() ~= 0 and player:getVocation():getId() > 4 then
			player:setVocation(player:getVocation():getId() - 4)
		end
	end

	-- 7.4 Premium System
    local premiumTowns = {'Edron', 'Ankrahmun', 'Darashia'}
 
    if player:isPremium() then
        player:setStorageValue(43434, 1)
    elseif player:getStorageValue(43434) == 1 then
        player:setStorageValue(43434, 0)
        local town = player:getTown()
        if isInArray(premiumTowns, town:getName()) then
            local defaultTown = Town("Thais")
            player:teleportTo(defaultTown:getTemplePosition())
            player:setTown(defaultTown)
            defaultTown:getTemplePosition():sendMagicEffect(CONST_ME_TELEPORT)
        elseif town:getName() ~= "Rookgaard" then
            player:teleportTo(town:getTemplePosition())
            town:getTemplePosition():sendMagicEffect(CONST_ME_TELEPORT)
        end
    end
	
	player:registerEvent('VialCleanup')
	if player:getStorageValue(50000) == 1 then
    removePlayerVials(player:getId())
    end
	
	if (player:getGroup():getId() >= 3) then
        player:setGhostMode(true)
    end
	
	if (player:getAccountType() == ACCOUNT_TYPE_TUTOR) then
        local msg = [[:: Tutor Rules ::

1. 3 Warnings you lose the job.
2. Without parallel conversations with players in Help, if the player starts offending, you simply mute it.
3. Be educated with the players in Help and especially in the Private, try to help as much as possible.
4. Always be on time, if you do not have a justification you will be removed from the staff.
5. Help is only allowed to ask questions related to tibia.
6. It is not allowed to divulge time up or to help in quest.
7. You are not allowed to sell items in the Help.
8. If the player encounters a bug, ask to go to the website to send a ticket and explain in detail.
9. Always keep the Tutors Chat open. (required).
10. You have finished your schedule, you have no tutor online, you communicate with some CM in-game or ts and stay in the help until someone logs in, if you can.
11. Always keep a good Portuguese in the Help, we want tutors who support, not that they speak a satanic ritual.
12. If you see a tutor doing something that violates the rules, take a print and send it to your superiors.

- Commands -
Mute Player: /mute nick, 90. (90 seconds)
Unmute Player: /unmute nick.
- Commands -]]
        player:popupFYI(msg)
    end
	
	-- Events
	player:registerEvent("Tasks")
	player:registerEvent("PlayerDeath")
	player:registerEvent("Shop")
	player:registerEvent("Market")
	player:registerEvent("Spell")
	player:registerEvent('KillDeathCount')
	player:registerEvent("Reward")
	player:registerEvent('BountyHunterKill')
	return true
end
