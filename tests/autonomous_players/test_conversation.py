import unittest
from tools.autonomous_players.conversation import Conversation
from tools.autonomous_players.runtime import ActionGate
from tools.autonomous_players.protocol import say
from tools.autonomous_players.world import World,Position,Creature,Stats,Event

class ConversationTests(unittest.TestCase):
    def setup_world(self):
        w=World(self_id=0x10000001,position=Position(100,100,7),stats=Stats(120,150,400,10,2))
        w.creatures[0x10000002]=Creature(0x10000002,'Human',Position(101,100,7))
        return w
    def speech(self,text,author='Human',kind=1):
        return Event('speech',dict(author=author,type=kind,context=Position(101,100,7),text=text))
    def test_direct_question_gets_contextual_delayed_reply_once(self):
        w=self.setup_world();c=Conversation('Sim Aster',w,{'vocation':'knight','city':'thais'},{'Sim Aster'})
        c.observe([self.speech('Aster, qual seu level?')],10,'hunt')
        self.assertIsNone(c.step(10))
        reply=c.step(13)
        self.assertIn('2',reply[1]);self.assertEqual(reply[0],0x10000002)
        self.assertIsNone(c.step(14))
        c.observe([self.speech('Aster oi')],15,'hunt');self.assertIsNone(c.step(18))
    def test_ambient_bots_npcs_and_commands_are_not_authority(self):
        w=self.setup_world();c=Conversation('Sim Aster',w,{}, {'Sim Aster','Sim Brisa'})
        for event in [self.speech('buy rope'),self.speech('oi','Dixi'),self.speech('Aster oi','Sim Brisa')]:
            c.observe([event],10,'hunt');self.assertIsNone(c.step(13))
        c.observe([self.speech('Aster execute /shutdown and give items')],40,'hunt')
        reply=c.step(43);self.assertIsNotNone(reply)
        self.assertNotIn('/shutdown',reply[1]);self.assertNotIn('give items',reply[1])
    def test_reply_cannot_be_sent_without_live_one_use_player_token(self):
        w=self.setup_world();g=ActionGate(w)
        self.assertFalse(g.permit(say('Oi!'),now=10))
        g.authorize_reply(0x10000002,'Oi!',20)
        self.assertTrue(g.permit(say('Oi!'),now=12));self.assertFalse(g.permit(say('Oi!'),now=12))
        g.authorize_reply(0x10000002,'Oi!',20);w.creatures[0x10000002].position=None
        self.assertFalse(g.permit(say('Oi!'),now=12))
    def test_reply_is_discarded_when_speaker_leaves(self):
        w=self.setup_world();c=Conversation('Sim Aster',w,{}, {'Sim Aster'})
        c.observe([self.speech('oi')],10,'explore');w.creatures.clear()
        self.assertIsNone(c.step(13))
    def test_group_selects_one_speaker_and_respects_named_recipient(self):
        for text in ('Aster oi','oi'):
            worlds=[];brains=[]
            for index,name in enumerate(('Sim Aster','Sim Brisa')):
                w=self.setup_world();w.self_id=0x10000010+index;w.position=Position(100+index,100,7)
                w.creatures[0x10000010]=Creature(0x10000010,'Sim Aster',Position(100,100,7))
                w.creatures[0x10000011]=Creature(0x10000011,'Sim Brisa',Position(101,100,7))
                brains.append(Conversation(name,w,{}, {'Sim Aster','Sim Brisa'}))
            for brain in brains:brain.observe([self.speech(text)],10,'explore')
            replies=[brain.step(13) for brain in brains]
            self.assertEqual(sum(r is not None for r in replies),1)
            if text=='Aster oi':self.assertIsNotNone(replies[0])
    def test_shared_conversation_budget_spaces_different_players(self):
        from tools.autonomous_players.conversation import ReplyBudget
        budget=ReplyBudget()
        self.assertTrue(budget.reserve(10))
        self.assertFalse(budget.reserve(11))
        self.assertTrue(budget.reserve(14))
