local config = {
    -- strong health potion
    [5112] = {health = {min = 25, max = 50}, vocations = {1, 2, 3, 4}, text = 'paladins and knights', level = 0, emptyId = 5111},
    -- strong mana potion
    [5110] = {mana = {min = 20, max = 75}, vocations = {1, 2, 3, 4}, text = 'sorcerers, druids and paladins', level = 0, emptyId = 5111},
    -- great mana potion
    [7590] = {mana = {min = 150, max = 240}, vocations = {1, 2}, text = 'sorcerers and druids', level = 80, emptyId = 7635},
    -- great health potion
    [7591] = {health = {min = 425, max = 575}, vocations = {4}, text = 'knights', level = 80, emptyId = 7635},
    -- health potion
    [5126] = {health = {min = 80, max = 125}, emptyId = 0},
    -- mana potion
    [5125] = {mana = {min = 40, max = 90}, emptyId = 0},
    -- great spirit potion
    [8472] = {health = {min = 250, max = 350}, mana = {min = 100, max = 200}, vocations = {3}, text = 'paladins', level = 80, emptyId = 7635},
    -- ultimate health potion
    [8473] = {health = {min = 650, max = 780}, vocations = {4}, text = 'knights', level = 130, emptyId = 7635},

    -- POT NOVOS

    -- ultimate mana potion 26029
    [26029] = {mana = {min = 430, max = 550}, vocations = {1, 2}, text = 'sorcerers and druids', level = 130, emptyId = 7635},

    -- super mana potion 32255
    [32255] = {mana = {min = 2000, max = 2500}, vocations = {1, 2}, text = 'sorcerers and druids', level = 130, emptyId = 7635},

    -- Supreme Health Potion 26031
    [26031] = {health = {min = 800, max = 950}, vocations = {4}, text = 'knights', level = 200, emptyId = 7635},

    -- Ultimate Spirit Potion 26030
    [26030] = {health = {min = 400, max = 550}, mana = {min = 140, max = 250}, vocations = {3}, text = 'paladins', level = 130, emptyId = 7635},


    -- antidote potion
    [8474] = {antidote = true, emptyId = 7636},
    -- small health potion
    [8704] = {health = {min = 60, max = 85}, emptyId = 7636}
}

local antidote = Combat()
antidote:setParameter(COMBAT_PARAM_TYPE, COMBAT_HEALING)
antidote:setParameter(COMBAT_PARAM_EFFECT, CONST_ME_MAGIC_BLUE)
antidote:setParameter(COMBAT_PARAM_TARGETCASTERORTOPMOST, true)
antidote:setParameter(COMBAT_PARAM_AGGRESSIVE, false)
antidote:setParameter(COMBAT_PARAM_DISPEL, CONDITION_POISON)

function onUse(player, item, fromPosition, target, toPosition, isHotkey)
    local potion = config[item.itemid]
    if not potion then
        return true
    end

    if target.itemid ~= 1 or target.type ~= THING_TYPE_PLAYER then
        return false
    end

    if player:getCondition(CONDITION_EXHAUST_HEAL) then
        player:sendTextMessage(MESSAGE_STATUS_SMALL, Game.getReturnMessage(RETURNVALUE_YOUAREEXHAUSTED))
        return true
    end

    if potion.antidote and not antidote:execute(target, Variant(target.uid)) then
        return false
    end

    if type(potion.health) == 'table' and not doTargetCombatHealth(0, target, COMBAT_HEALING, potion.health.min, potion.health.max, CONST_ME_MAGIC_BLUE) then
        return false
    end

    if type(potion.mana) == 'table' and not doTargetCombatMana(0, target, potion.mana.min, potion.mana.max, CONST_ME_MAGIC_BLUE) then
        return false
    end

   target:say('Aaaah...', TALKTYPE_SAY)

    local topParent = item:getTopParent()
    if topParent.isItem and (not topParent:isItem() or topParent.itemid ~= 460) then
        local parent = item:getParent()
        if not parent:isTile() and (parent:addItem(potion.emptyId, 1) or topParent:addItem(potion.emptyId, 1)) then
             item:remove(1)
            return true
        end
    end

    Game.createItem(potion.emptyId, 1, item:getPosition())
    item:remove(1)

    return true
end