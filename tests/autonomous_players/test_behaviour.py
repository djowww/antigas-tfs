import random
import tempfile
import unittest
from pathlib import Path

from tools.autonomous_players.world import World, Position, Thing, Creature, Stats, Event, Container
from tools.autonomous_players.definitions import load_items
from tools.autonomous_players.navigation import find_path
from tools.autonomous_players.behaviour import Agent
from tools.autonomous_players.social import Oracle, Purchase, party_action
from tools.autonomous_players.learning import Policy
from tools.autonomous_players.store import Store

ITEMS = load_items(Path(__file__).resolve().parents[2] / 'data/items/items.srv')


class BehaviourTests(unittest.TestCase):
    def test_multiple_adjacent_rats_trigger_retreat_before_health_collapses(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            for cid,position in ((0x40000001,Position(101,100,7)),(0x40000002,Position(100,101,7))):
                w.creatures[cid]=Creature(cid,'Rat',position)
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertTrue(a.priority(1))
            self.assertTrue(all(p[0]!=0xa1 for p in a.step(1)))
            self.assertEqual(a.strategy,'retreat')

    def test_unreachable_pen_prey_does_not_hold_patrol_forever(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            rat=Creature(0x40000001,'Rat',Position(102,100,7))
            w.creatures[rat.id]=rat
            for p in (Position(101,100,7),Position(103,100,7),Position(102,99,7),Position(102,101,7)):
                w.tiles[p]=[]
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertTrue(any(packet[0]==0xa1 for packet in a.step(1)))
            self.assertEqual(a.step(2),[b'\xbe'])
            self.assertFalse(a.priority(3))
            rat.position=Position(100,101,7)
            self.assertTrue(a.priority(4))

    def world(self):
        w = World(self_id=0x10000001,position=Position(100,100,7),stats=Stats(150,150,400,0,1))
        for x in range(98,104):
            for y in range(98,104):
                w.tiles[Position(x,y,7)] = [Thing(102)]
        return w

    def test_path_respects_unknown_and_occupied_tiles(self):
        w = self.world()
        w.tiles[Position(101,100,7)].append(Thing(0,creature_id=0x10000002))
        path = find_path(w,w.position,Position(102,100,7),ITEMS)
        self.assertTrue(path)
        self.assertNotIn(Position(101,100,7),path)
        self.assertEqual(find_path(w,w.position,Position(500,500,7),ITEMS),[])
        self.assertEqual(find_path(w,w.position,Position(100,100,8),ITEMS),[])

    def test_exploration_keeps_a_reachable_destination(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w = self.world()
            a = Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertTrue(a.step(1))
            goal = a.destination
            self.assertIsNotNone(goal)
            self.assertTrue(a.step(2))
            self.assertEqual(a.destination,goal)

    def test_low_health_never_attacks_and_actions_are_rate_limited(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w = self.world()
            w.stats.health = 20
            w.creatures[0x40000001] = Creature(0x40000001,'Rat',Position(101,100,7))
            agent = Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            actions = agent.step(1)
            self.assertTrue(all(a[0] != 0xa1 for a in actions))
            self.assertEqual(agent.step(1.01),[])
            w.valid = False
            self.assertEqual(agent.step(5),[])

    def test_food_is_used_even_when_retreating(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.stats.health=20
            w.containers[0]=Container(0,2853,'bag',20,False,[Thing(3585)])
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertEqual(a.step(1)[0][0],0x82)

    def test_human_is_never_a_combat_target(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w = self.world()
            w.creatures[0x10000002] = Creature(0x10000002,'Rat',Position(101,100,7))
            agent = Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertTrue(all(a[0] != 0xa1 for a in agent.step(1)))

    def test_policy_choice_changes_executor(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            outputs = []
            for strategy in ('explore','hunt'):
                w = self.world()
                w.creatures[0x40000001] = Creature(0x40000001,'Rat',Position(103,100,7))
                policy = Policy(store,'Sim One',random.Random(7))
                policy.choose = lambda *args,choice=strategy:choice
                agent = Agent('Sim One',w,ITEMS,policy)
                outputs.append(agent.step(1))
            self.assertTrue(all(a[0] != 0xa1 for a in outputs[0]))
            self.assertTrue(any(a[0] == 0xa1 for a in outputs[1]))

    def test_rejected_attack_can_retry_after_leaving_protection(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w = self.world()
            w.inventory[3] = Thing(2853)
            from tools.autonomous_players.world import Container
            w.containers[0] = Container(0,2853,'bag',20,False)
            w.creatures[0x40000001] = Creature(0x40000001,'Rat',Position(101,100,7))
            agent = Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            first = agent.step(1)
            second = agent.step(5)
            self.assertTrue(any(a[0] == 0xa1 for a in first))
            self.assertTrue(any(a[0] == 0xa1 for a in second))

    def test_oracle_requires_own_observed_prompts(self):
        for profession in ('knight','paladin','sorcerer','druid'):
            oracle = Oracle('Sim One','thais',profession)
            self.assertIsNone(oracle.start(7,0))
            self.assertEqual(oracle.start(8,1),'hi')
            self.assertIsNone(oracle.reply('Human','ARE YOU SURE?',2))
            self.assertEqual(oracle.reply('The Oracle','SIM ONE, ARE YOU PREPARED TO FACE YOUR DESTINY?',3),'yes')
            self.assertEqual(oracle.reply('The Oracle','IN WHICH TOWN DO YOU WANT TO LIVE: CARLIN, THAIS, OR VENORE?',4),'thais')
            self.assertEqual(oracle.reply('The Oracle','IN THAIS! AND WHAT PROFESSION HAVE YOU CHOSEN: KNIGHT, PALADIN, SORCERER, OR DRUID?',5),profession)
            self.assertIsNone(oracle.reply('The Oracle','ARE YOU SURE?',6))
            self.assertEqual(oracle.reply('The Oracle',f'A {profession.upper()}! ARE YOU SURE? THIS DECISION IS IRREVERSIBLE!',7),'yes')
            self.assertIsNone(oracle.reply('The Oracle',f'A {profession.upper()}! ARE YOU SURE? THIS DECISION IS IRREVERSIBLE!',8))

    def test_buy_confirmation_checks_price_and_name(self):
        p = Purchase('Dixi','rope',50)
        self.assertIsNone(p.start(49))
        self.assertEqual(p.start(60),'hi')
        self.assertEqual(p.reply('Dixi','Hello, Sir. How may I help you, Sim One.'),'rope')
        self.assertIsNone(p.reply('Dixi','Do you want to buy a rope for 500 gold?'))
        self.assertEqual(p.reply('Dixi','Do you want to buy a rope for 50 gold?'),'yes')
        self.assertIsNone(p.reply('Dixi','Do you want to buy a rope for 50 gold?'))
        food=Purchase('Willie','bread',3)
        self.assertEqual(food.start(3),'hi')
        self.assertEqual(food.reply('Willie','Hiho Sim One.'),'bread')

    def test_only_incoming_party_invitation_is_accepted(self):
        c = Creature(0x10000002,'Human',Position(100,101,7),shield=1)
        self.assertEqual(party_action(c,set())[0],0xa4)
        c.shield = 2
        self.assertIsNone(party_action(c,set()))

    def test_loot_requires_own_experience_and_uncontested_corpse(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w = self.world()
            rat = Creature(0x40000001,'Rat',Position(101,100,7))
            w.creatures[rat.id] = rat
            w.inventory[3] = Thing(2853)
            w.containers[0] = Container(0,2853,'bag',20,False)
            a = Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.step(1)
            a.observe([],1)
            rat.position = None
            w.stats.experience = 5
            w.tiles[Position(101,100,7)].append(Thing(3994))
            a.observe([Event('stats',w.stats)],2)
            self.assertIn((Position(101,100,7),3994),a.allowed_corpses)
            self.assertEqual(a.step(3)[0][0],0x82)

    def test_corpse_may_arrive_after_experience_packet(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w = self.world()
            rat = Creature(0x40000001,'Rat',Position(101,100,7))
            w.creatures[rat.id] = rat
            a = Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.step(1)
            a.observe([],1)
            rat.position=None;w.stats.experience=5
            a.observe([Event('stats',w.stats)],2)
            w.tiles[Position(101,100,7)].append(Thing(3994))
            a.observe([Event('tile',Position(101,100,7))],2.1)
            self.assertIn((Position(101,100,7),3994),a.allowed_corpses)

    def test_cancel_target_can_precede_experience_after_kill(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.creatures[0x40000001]=Creature(0x40000001,'Rat',Position(101,100,7))
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.step(1)
            a.observe([Event('cancel_attack')],2)
            w.creatures[0x40000001].position=None
            w.stats.experience=5;w.tiles[Position(101,100,7)].append(Thing(3994))
            a.observe([Event('stats',w.stats)],2.1)
            self.assertIn((Position(101,100,7),3994),a.allowed_corpses)


    def test_food_in_inventory_slot_is_consumed(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.inventory[5]=Thing(3600)
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertEqual(a.step(1)[0][0],0x82)


    def test_nearby_human_hunt_is_not_competed_for(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.creatures[0x40000001]=Creature(0x40000001,'Rat',Position(101,100,7))
            w.creatures[0x10000002]=Creature(0x10000002,'Human',Position(102,100,7))
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertTrue(all(packet[0]!=0xa1 for packet in a.step(1)))


    def test_human_approaching_current_target_cancels_server_attack(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.creatures[0x40000001]=Creature(0x40000001,'Rat',Position(101,100,7))
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertTrue(any(packet[0]==0xa1 for packet in a.step(1)))
            w.creatures[0x10000002]=Creature(0x10000002,'Human',Position(102,100,7))
            self.assertTrue(a.priority(2))
            self.assertEqual(a.step(2),[b'\xbe'])


if __name__ == '__main__':
    unittest.main()
