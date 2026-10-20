"""NPC dialogue requires observed prompts; confirmation is never replayed."""
import re
from .wire import Writer


class Oracle:
    def __init__(self, name, city, vocation):
        if city not in ('thais','carlin','venore') or vocation not in ('knight','paladin','sorcerer','druid'):
            raise ValueError('invalid free-account destination or vocation')
        self.name, self.city, self.vocation = name.upper(),city,vocation
        self.state, self.last = 'idle',0

    def start(self, level, now):
        if level < 8 or self.state != 'idle':
            return None
        self.state,self.last = 'greeting',now
        return 'hi'

    def reply(self, author, text, now):
        if author != 'The Oracle' or now-self.last > 30 or self.state in ('idle','confirmed'):
            return None
        text = text.upper()
        if 'WAIT UNTIL' in text or 'COME BACK' in text:
            self.state = 'idle'
            return None
        expected = {'greeting':self.name+', ARE YOU PREPARED TO FACE YOUR DESTINY?',
                    'town':'IN WHICH TOWN DO YOU WANT TO LIVE:',
                    'profession':'IN '+self.city.upper()+'! AND WHAT PROFESSION HAVE YOU CHOSEN:',
                    'confirmation':'A '+self.vocation.upper()+'! ARE YOU SURE? THIS DECISION IS IRREVERSIBLE!'}
        if expected[self.state] not in text:
            return None
        response = {'greeting':'yes','town':self.city,'profession':self.vocation,'confirmation':'yes'}[self.state]
        self.state = {'greeting':'town','town':'profession','profession':'confirmation','confirmation':'confirmed'}[self.state]
        self.last = now
        return response


class Purchase:
    def __init__(self, npc, item, price):
        self.npc,self.item,self.price = npc,item,price
        self.state = 'idle'

    def start(self, gold):
        if gold < self.price or self.state != 'idle':
            return None
        self.state = 'greeting'
        return 'hi'

    def reply(self, author, text):
        if author != self.npc:
            return None
        normalized = text.lower()
        if self.state == 'greeting' and ('hello' in normalized or 'hiho' in normalized):
            self.state = 'quote'
            return self.item
        if self.state == 'quote' and re.search(r'\b'+re.escape(self.item)+r'\b', normalized):
            match = re.search(r'for (\d+) gold\?',normalized)
            if match and int(match[1]) == self.price and 'buy' in normalized:
                self.state = 'confirmed'
                return 'yes'
        return None


def party_action(creature, own_names):
    if creature.kind != 'player' or creature.position is None:
        return None
    # Player::getPartyShield: white-yellow=other invited us; white-blue=we invited other.
    if creature.shield == 1:
        return Writer().u8(0xa4).u32(creature.id).data
    if creature.name in own_names and creature.shield == 0:
        return Writer().u8(0xa3).u32(creature.id).data
    return None
