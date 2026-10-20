import unittest
from tools.autonomous_players.world import World,Position,Creature,Stats
from tools.autonomous_players.progression import Progression
from tools.autonomous_players.protocol import say


class RecoveryTests(unittest.TestCase):
    def test_recovery_replans_if_temple_route_silently_stalls(self):
        from pathlib import Path
        from tools.autonomous_players.progression import Progression
        from tools.autonomous_players.routes import RouteGraph
        from tools.autonomous_players.world import World,Position,Stats,Thing
        from tools.autonomous_players.definitions import load_items

        start=Position(32097,32220,7)
        rejected=Position(32097,32219,7)
        goal=Position(32097,32218,7)
        detour=(Position(32098,32220,7),Position(32098,32219,7),
                Position(32098,32218,7))
        tiles=(start,rejected,goal,*detour)
        world=World(position=start,stats=Stats(30,150,400,0,1))
        for tile in tiles:
            world.tiles[tile]=[Thing(102)]
        routes=RouteGraph({tile:None for tile in tiles})
        items=load_items(Path(__file__).resolve().parents[2]/'data/items/items.srv')
        progression=Progression(dict(character='Sim One',city='thais',vocation='knight'),
                                world,items,routes)

        first=progression.recover(1)
        repeated=progression.recover(10.9)
        alternate=progression.recover(11.1)

        self.assertEqual(first,[b'\x65'])
        self.assertEqual(repeated,first)
        self.assertEqual(alternate,[b'\x66'])
        self.assertIn(rejected,progression.blocked_steps)

    def test_food_trip_is_not_pulled_back_to_temple_after_three_steps(self):
        from types import SimpleNamespace
        from tools.autonomous_players.world import Thing
        w=World(self_id=0x10000001,position=Position(32090,32219,7),stats=Stats(100,150,400,0,1))
        w.inventory[1]=Thing(3031,count=3)
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{3031:SimpleNamespace(attributes={})})
        p.step=lambda now:[b'\x68']
        self.assertEqual(p.recover(1),[b'\x68'])

    def test_wounded_rook_player_requests_real_npc_healing_not_hunting(self):
        w=World(self_id=0x10000001,position=Position(32097,32218,7),stats=Stats(20,150,400,0,1))
        c=Creature(0x80000001,'Cipfried',Position(32097,32217,7));w.creatures[c.id]=c
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{})
        self.assertEqual(p.recover(1),[say('hi')])
        self.assertEqual(p.authorization,(c.id,'hi',6))
        self.assertEqual(p.recover(1.1),[])
        self.assertEqual(p.recover(3),[say('heal')])
        w.stats.health=65
        self.assertEqual(p.recover(5),[say('bye')])

    def test_red_fraction_health_requests_healing_above_old_absolute_hp_threshold(self):
        w=World(self_id=0x10000001,position=Position(32097,32218,7),stats=Stats(80,250,400,0,20))
        c=Creature(0x80000001,'Cipfried',Position(32097,32217,7));w.creatures[c.id]=c
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{})

        self.assertEqual(p.recover(1),[say('hi')])
        self.assertEqual(p.recover(3),[say('heal')])

    def test_full_agent_routes_red_fraction_health_through_healer_dialogue(self):
        from tools.autonomous_players.behaviour import Agent
        w=World(self_id=0x10000001,position=Position(32097,32218,7),stats=Stats(80,250,400,0,20))
        c=Creature(0x80000001,'Cipfried',Position(32097,32217,7));w.creatures[c.id]=c
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{})
        agent=Agent('Sim Test',w,{},object())
        agent.escape=p.recover

        self.assertEqual(agent.step(1),[say('hi')])
        self.assertEqual(p.authorization,(c.id,'hi',6))
        self.assertEqual(agent.step(3),[say('heal')])

    def test_priority_wounded_agent_closes_healer_dialogue_after_hp_leaves_critical_red(self):
        import random
        from tools.autonomous_players.behaviour import Agent
        from tools.autonomous_players.app import select_actions_with_learning

        w=World(self_id=0x10000001,position=Position(32097,32218,7),stats=Stats(20,150,400,0,1))
        c=Creature(0x80000001,'Cipfried',Position(32097,32217,7));w.creatures[c.id]=c
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{})

        class Policy:
            rng=random.Random(7)
            def choose(self,state,actions):return actions[0]
            def update(self,*args):pass

        agent=Agent('Sim Test',w,{},Policy())
        agent.escape=p.recover
        agent.forage=lambda now:[]
        self.assertEqual(agent.step(1),[say('hi')])
        self.assertEqual(agent.step(3),[say('heal')])
        w.stats.health=60

        actions,_=select_actions_with_learning(agent,p,5,None)

        self.assertEqual(actions,[say('bye')])
        self.assertFalse(p.healer_greeted)

    def test_missing_healer_at_temple_falls_back_to_food_after_grace_period(self):
        from unittest.mock import patch
        w=World(self_id=0x10000001,position=Position(32097,32218,7),stats=Stats(20,150,400,0,1))
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{})
        with patch.object(p,'forage',return_value=[b'\x68']) as forage:
            self.assertEqual(p.recover(1),[])
            self.assertEqual(p.recover(8),[])
            self.assertEqual(p.recover(10),[b'\x68'])
            self.assertEqual(p.recover(11),[b'\x68'])
            self.assertEqual(forage.call_count,2)
            c=Creature(0x80000001,'Cipfried',Position(32097,32217,7))
            w.creatures[c.id]=c
            self.assertEqual(p.recover(12),[say('hi')])

    def test_healer_dialogue_retries_after_no_health_effect_without_spamming(self):
        w=World(self_id=0x10000001,position=Position(32097,32218,7),stats=Stats(20,150,400,0,1))
        c=Creature(0x80000001,'Cipfried',Position(32097,32217,7));w.creatures[c.id]=c
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{})
        self.assertEqual(p.recover(1),[say('hi')])
        self.assertEqual(p.recover(3),[say('heal')])
        self.assertEqual(p.recover(4),[])
        self.assertEqual(p.recover(8),[])
        self.assertEqual(p.recover(10),[say('hi')])

    def test_healer_status_records_npc_response_and_health_change(self):
        from tools.autonomous_players.world import Event
        w=World(self_id=0x10000001,position=Position(32097,32218,7),stats=Stats(20,150,400,0,1))
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{})
        p.observe([Event('speech',dict(author='Cipfried',text='You are looking really bad.'))],5)
        status=p.healing_status()
        self.assertEqual(status['last_response'],'You are looking really bad.')
        w.stats.health=65
        p.observe([],6)
        self.assertEqual(p.healing_status()['health'],65)

    def test_repeated_ineffective_healing_switches_to_food_route_temporarily(self):
        from unittest.mock import patch
        w=World(self_id=0x10000001,position=Position(32097,32218,7),stats=Stats(20,150,400,0,1))
        c=Creature(0x80000001,'Cipfried',Position(32097,32217,7));w.creatures[c.id]=c
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{})
        with patch.object(p,'forage',return_value=[b'\x68']) as forage:
            self.assertEqual(p.recover(1),[say('hi')])
            self.assertEqual(p.recover(3),[say('heal')])
            self.assertEqual(p.recover(9),[say('hi')])
            self.assertEqual(p.recover(11),[say('heal')])
            self.assertEqual(p.recover(17),[say('hi')])
            self.assertEqual(p.recover(19),[say('heal')])
            self.assertEqual(p.recover(25),[b'\x68'])
            self.assertEqual(forage.call_count,1)
            self.assertEqual(p.recover(30),[b'\x68'])

    def test_failed_healing_does_not_repeat_dialogue_when_food_route_has_no_step(self):
        from unittest.mock import patch
        w=World(self_id=0x10000001,position=Position(32097,32218,7),stats=Stats(20,150,400,0,1))
        c=Creature(0x80000001,'Cipfried',Position(32097,32217,7));w.creatures[c.id]=c
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{})
        with patch.object(p,'forage',return_value=[]) as forage:
            self.assertEqual(p.recover(1),[say('hi')])
            self.assertEqual(p.recover(3),[say('heal')])
            self.assertEqual(p.recover(9),[say('hi')])
            self.assertEqual(p.recover(11),[say('heal')])
            self.assertEqual(p.recover(17),[say('hi')])
            self.assertEqual(p.recover(19),[say('heal')])

            self.assertEqual(p.recover(25),[])
            self.assertEqual(p.recover(30),[])
            self.assertEqual(p.last_speech,19)
            self.assertGreaterEqual(forage.call_count,2)

    def test_failed_healing_explores_observed_surface_when_food_goal_is_unmapped(self):
        from pathlib import Path
        from tools.autonomous_players.definitions import load_items
        from tools.autonomous_players.navigation import DIRECTIONS
        from tools.autonomous_players.world import Thing

        start=Position(32097,32218,7)
        w=World(self_id=0x10000001,position=start,stats=Stats(20,150,400,0,1))
        for delta in DIRECTIONS:
            w.tiles[start.shift(*delta)]=[Thing(102)]
        healer=Creature(0x80000001,'Cipfried',start.shift(y=-1));w.creatures[healer.id]=healer
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,
                      load_items(Path(__file__).resolve().parents[2]/'data/items/items.srv'))
        p.healer_request_health=20
        p.healer_retry_at=24
        p.healer_greeted=True
        p.healer_retries=2

        actions=p.recover(25)

        self.assertEqual(len(actions),1)
        self.assertIn(actions[0][0],DIRECTIONS.values())

    def test_healed_wounded_player_keeps_food_goal_until_inventory_receipt(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from tools.autonomous_players.world import Thing
        w=World(self_id=0x10000001,position=Position(32097,32218,7),stats=Stats(20,150,400,0,1))
        c=Creature(0x80000001,'Cipfried',Position(32097,32217,7));w.creatures[c.id]=c
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{})
        self.assertEqual(p.recover(1),[say('hi')])
        self.assertEqual(p.recover(3),[say('heal')])
        self.assertTrue(p.needs_food)
        w.stats.health=65
        self.assertEqual(p.recover(5),[say('bye')])
        with patch.object(p,'forage',return_value=[b'\x68']) as forage:
            self.assertEqual(p.step(8),[b'\x68'])
            forage.assert_called_once_with(8)
            p.items={999:SimpleNamespace(attributes={'nutrition':1})}
            w.inventory[1]=Thing(999)
            self.assertEqual(p.step(9),[])
            self.assertFalse(p.needs_food)

    def test_wounded_player_waits_safely_without_gold_or_food(self):
        w=World(self_id=0x10000001,position=Position(32097,32219,7),stats=Stats(80,150,400,0,1))
        p=Progression(dict(character='Sim Test',vocation='knight',city='thais'),w,{})
        self.assertEqual(p.recover(1),[])
