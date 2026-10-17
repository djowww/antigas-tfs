import unittest
from pathlib import Path
from tools.autonomous_players.world import World,Position,Creature,Thing,Stats,Event
from tools.autonomous_players.definitions import load_items
from tools.autonomous_players.progression import Progression
from tools.autonomous_players.routes import RouteGraph

ITEMS=load_items(Path(__file__).resolve().parents[2]/'data/items/items.srv')


class ProgressionTests(unittest.TestCase):
    def test_finished_purchase_does_not_leave_player_permanently_busy(self):
        w=World(position=Position(32047,32205,7),stats=Stats(150,150,400,0,1))
        w.inventory[10]=Thing(3031,3)
        w.creatures[0x80000001]=Creature(0x80000001,'Willie',Position(32047,32204,7))
        p=Progression(dict(character='Sim One',city='thais',vocation='knight'),w,ITEMS)
        p.step(1)
        p.observe([Event('speech',dict(author='Willie',text='Hiho Sim One.'))],2)
        p.step(4)
        p.observe([Event('speech',dict(author='Willie',text='Do you want to buy a bread for 3 gold?'))],5)
        p.step(7)
        w.inventory[10]=Thing(3600,1)
        p.step(10)
        self.assertFalse(p.busy)

    def test_unconfirmed_oracle_timeout_restarts_with_greeting(self):
        w=World(position=Position(32104,32191,6),stats=Stats(150,150,400,4200,8))
        w.creatures[0x80000001]=Creature(0x80000001,'The Oracle',Position(32104,32190,6))
        p=Progression(dict(character='Sim One',city='thais',vocation='knight',observed_vocation=0),w,ITEMS)
        self.assertTrue(p.step(1)[0].endswith(b'hi'))
        self.assertTrue(p.step(40)[0].endswith(b'hi'))

    def test_observed_oracle_dialogue_is_connected_to_actions(self):
        w=World(self_id=0x10000001,position=Position(32104,32191,6),stats=Stats(150,150,400,4200,8))
        w.creatures[0x80000001]=Creature(0x80000001,'The Oracle',Position(32104,32190,6))
        profile=dict(character='Sim One',city='thais',vocation='knight',observed_vocation=0)
        progression=Progression(profile,w,ITEMS)
        self.assertEqual(progression.step(1)[0][0],0x96)
        progression.observe([Event('speech',dict(author='The Oracle',text='SIM ONE, ARE YOU PREPARED TO FACE YOUR DESTINY?'))],2)
        self.assertTrue(progression.step(4)[0].endswith(b'yes'))
        self.assertEqual(progression.authorization[0],0x80000001)

    def test_route_stair_requires_matching_observed_transition(self):
        a,b,c=Position(32104,32192,7),Position(32104,32191,7),Position(32104,32190,6)
        goal=Position(32104,32191,6)
        graph=RouteGraph({a:None,b:c,c:None,goal:None})
        w=World(position=a,stats=Stats(150,150,400,4200,8))
        w.tiles[b]=[Thing(410),Thing(1947)]
        p=Progression(dict(character='Sim One',city='thais',vocation='knight',observed_vocation=0),w,ITEMS,graph)
        self.assertEqual(p.step(1),[b'\x65'])
        self.assertEqual(p.floor_authorization,(b,1947))
        w.tiles[b]=[Thing(410),Thing(2130)]
        self.assertEqual(p.step(2),[])

    def test_supply_trip_expires_without_position_progress(self):
        from unittest.mock import patch
        w=World(position=Position(32097,32219,7),stats=Stats(150,150,400,0,1));w.inventory[10]=Thing(3031,7)
        p=Progression(dict(character='Sim One',city='thais',vocation='knight'),w,ITEMS)
        with patch.object(p,'_toward',return_value=[b'\x66']):
            self.assertEqual(p.step(1),[b'\x66'])
            self.assertEqual(p.step(25),[])
            self.assertEqual(p.step(30),[])
        self.assertGreaterEqual(p.next_purchase,115)

    def test_individual_hunting_route_rotates_and_still_validates_steps(self):
        a,b,c=Position(100,100,7),Position(101,100,7),Position(102,100,7)
        w=World(position=a,stats=Stats(150,150,400,0,1));w.tiles[b]=[Thing(102)]
        profile=dict(account=10,character='Sim One',city='thais',vocation='knight')
        p=Progression(profile,w,ITEMS,RouteGraph({a:None,b:None,c:None}),rook_bounds=(99,99,105,105),hunting_points=[(102,100,7)])
        self.assertEqual(p.step(1),[b'\x66'])
        w.tiles[b]=[Thing(102),Thing(0,creature_id=0x10000002)]
        self.assertEqual(p.step(2),[])
