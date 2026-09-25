function onDeath(creature, corpse, killer, mostDamage, unjustified, mostDamage_unjustified)
    creature:getPosition():sendMagicEffect(16)
     return true
end