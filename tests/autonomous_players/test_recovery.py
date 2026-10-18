import unittest
from tools.autonomous_players.world import World,Position,Creature,Stats
from tools.autonomous_players.progression import Progression
from tools.autonomous_players.protocol import say


class RecoveryTests(unittest.TestCase):
    def test_food_trip_is_not_pulled_back_to_temple_after_three_steps(self):
        from types import SimpleNamespace
        from tools.autonomous_players.world import Thing
        w=World(self_id=0x10000001,position=Position(32090,32219,7),stats=Stats(80,150,400,0,1))
        w.inventory[1]=Thing(3031,count=3)
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{3031:SimpleNamespace(attributes={})})
        p.step=lambda now:[b'\x68']
        self.assertEqual(p.recover(1),[b'\x68'])

    def test_wounded_rook_player_requests_real_npc_healing_not_hunting(self):
        w=World(self_id=0x10000001,position=Position(32097,32219,7),stats=Stats(20,150,400,0,1))
        c=Creature(0x80000001,'Cipfried',Position(32097,32217,7));w.creatures[c.id]=c
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{})
        self.assertEqual(p.recover(1),[say('hi')])
        self.assertEqual(p.authorization,(c.id,'hi',6))
        self.assertEqual(p.recover(1.1),[])
        self.assertEqual(p.recover(3),[say('heal')])
        w.stats.health=65
        self.assertEqual(p.recover(5),[say('bye')])

    def test_wounded_player_waits_safely_without_gold_or_food(self):
        w=World(self_id=0x10000001,position=Position(32097,32219,7),stats=Stats(80,150,400,0,1))
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{})
        self.assertEqual(p.recover(1),[])
