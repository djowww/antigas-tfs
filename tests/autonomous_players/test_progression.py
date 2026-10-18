import unittest
from pathlib import Path
from tools.autonomous_players.world import World,Position,Creature,Thing,Stats,Event
from tools.autonomous_players.definitions import load_items
from tools.autonomous_players.progression import Progression,FOOD_POINTS
from tools.autonomous_players.routes import RouteGraph

ITEMS=load_items(Path(__file__).resolve().parents[2]/'data/items/items.srv')


class ProgressionTests(unittest.TestCase):
    def test_foraging_uses_distinct_spawn_destinations_and_rotates_after_stall(self):
        from unittest.mock import patch
        start=Position(32097,32219,7)
        w=World(position=start,stats=Stats(65,150,400,0,1))
        p=Progression(dict(account=2,character='Sim One',city='thais',vocation='knight'),
                      w,ITEMS,RouteGraph({start:None}))
        with patch.object(p,'_toward',return_value=[b'\x66']) as toward:
            self.assertEqual(p.forage(1),[b'\x66'])
            self.assertEqual(toward.call_args.args[0],FOOD_POINTS[2])
            self.assertEqual(p.forage(25),[b'\x66'])
            self.assertEqual(toward.call_args.args[0],FOOD_POINTS[3])

    def test_foraging_waits_for_animal_respawn_and_returns_if_it_wanders_away(self):
        from unittest.mock import patch
        goal=FOOD_POINTS[0]
        w=World(position=goal,stats=Stats(65,150,400,0,1))
        p=Progression(dict(account=0,character='Sim One',city='thais',vocation='knight'),
                      w,ITEMS,RouteGraph({goal:None}))
        self.assertEqual(p.forage(1),[])
        w.position=goal.shift(x=7)
        with patch.object(p,'_toward',return_value=[b'\x68']) as toward:
            self.assertEqual(p.forage(10),[b'\x68'])
            self.assertEqual(toward.call_args.args[0],goal)
            self.assertEqual(p.forage(91),[b'\x68'])
            self.assertEqual(toward.call_args.args[0],FOOD_POINTS[1])

    def test_red_health_at_temple_says_hi_then_heal(self):
        w=World(position=Position(32097,32218,7),stats=Stats(30,150,400,0,1))
        npc=Creature(0x80000001,'Cipfried',Position(32097,32217,7))
        w.creatures[npc.id]=npc
        p=Progression(dict(character='Sim One',city='thais',vocation='knight'),w,ITEMS)
        self.assertTrue(p.recover(1)[0].endswith(b'hi'))
        self.assertTrue(p.recover(4)[0].endswith(b'heal'))

    def test_red_health_walks_into_cipfried_actual_speaking_range(self):
        from unittest.mock import patch
        w=World(position=Position(32094,32216,7),stats=Stats(17,150,400,0,1))
        npc=Creature(0x80000001,'Cipfried',Position(32097,32217,7))
        w.creatures[npc.id]=npc
        p=Progression(dict(character='Sim One',city='thais',vocation='knight'),w,ITEMS)
        with patch.object(p,'_toward',return_value=[b'\x66']) as toward:
            self.assertEqual(p.recover(1),[b'\x66'])
            self.assertEqual(toward.call_args.args[0],Position(32097,32218,7))
        self.assertIsNone(p.authorization)

    def test_real_rook_sewer_grate_428_can_be_descended(self):
        from tools.autonomous_players.runtime import ActionGate
        start=Position(32109,32245,7)
        grate=Position(32110,32245,7)
        below=Position(32110,32246,8)
        w=World(position=start,stats=Stats(150,150,400,0,1))
        w.tiles[grate]=[Thing(428)]
        routes=RouteGraph({start:None,grate:below,below:None})
        p=Progression(dict(character='Sim One',city='thais',vocation='knight'),w,ITEMS,routes)
        packets=p._toward(below)
        self.assertEqual(packets,[b'\x66'])
        self.assertEqual(p.floor_authorization,(grate,428))
        gate=ActionGate(w,ITEMS)
        gate.floor_token=p.floor_authorization
        self.assertTrue(gate.permit(packets[0]))
        w.position=below
        self.assertEqual(w.position.z,8)

    def test_real_rook_sewer_grate_still_rejects_wrong_destination(self):
        start=Position(32109,32245,7);grate=Position(32110,32245,7)
        wrong=Position(32110,32245,8)
        w=World(position=start,stats=Stats(150,150,400,0,1))
        w.tiles[grate]=[Thing(428)]
        p=Progression(dict(character='Sim One',city='thais',vocation='knight'),w,ITEMS,
                      RouteGraph({start:None,grate:wrong,wrong:None}))
        self.assertEqual(p._toward(wrong),[])

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

    def test_learned_graph_skips_cooled_down_hunting_goal(self):
        from tools.autonomous_players.learned_navigation import RegionGraph
        a,b,c=Position(100,100,7),Position(101,100,7),Position(102,100,7)
        w=World(position=a,stats=Stats(150,150,400,0,1)); w.tiles[b]=[Thing(102)]
        graph=RouteGraph({a:None,b:None,c:None})
        learned=RegionGraph(); learned.record_failure('Sim One',a,c,'blocked',1)
        profile=dict(account=1,character='Sim One',city='thais',vocation='knight')
        p=Progression(profile,w,ITEMS,graph,rook_bounds=(99,99,105,105),hunting_points=[(102,100,7),(101,100,7)],learned_graph=learned)
        self.assertEqual(p.step(2),[b'\x66'])

    def test_blocked_learned_goal_records_failure_and_tries_alternate(self):
        from unittest.mock import patch
        from tools.autonomous_players.learned_navigation import RegionGraph
        w=World(position=Position(100,100,7),stats=Stats(150,150,400,0,1))
        learned=RegionGraph()
        profile=dict(account=1,character='Sim One',city='thais',vocation='knight')
        p=Progression(profile,w,ITEMS,RouteGraph({w.position:None}),rook_bounds=(99,99,105,105),
                      hunting_points=[(102,100,7),(101,100,7)],learned_graph=learned)
        with patch.object(p,'_toward',side_effect=[[],[b'\x66']]):
            self.assertEqual(p.step(1),[b'\x66'])
        self.assertIsNotNone(learned.next_goal('Sim One',w.position,p.hunting_points,2))

    def test_all_cooled_down_goals_hold_instead_of_repeating_blocked_route(self):
        from tools.autonomous_players.learned_navigation import RegionGraph
        w=World(position=Position(100,100,7),stats=Stats(150,150,400,0,1))
        learned=RegionGraph()
        profile=dict(account=1,character='Sim One',city='thais',vocation='knight')
        goals=[(102,100,7),(101,100,7)]
        p=Progression(profile,w,ITEMS,RouteGraph({w.position:None}),rook_bounds=(99,99,105,105),
                      hunting_points=goals,learned_graph=learned)
        for goal in p.hunting_points:
            learned.record_failure('Sim One', w.position, goal, 'blocked', 1)
        self.assertEqual(p.step(2),[])

    def test_active_hunting_goal_is_kept_until_rotation(self):
        from unittest.mock import patch
        from tools.autonomous_players.learned_navigation import RegionGraph
        w=World(position=Position(98,100,7),stats=Stats(150,150,400,0,1))
        profile=dict(account=0,character='Sim One',city='thais',vocation='knight')
        p=Progression(profile,w,ITEMS,RouteGraph({w.position:None}),rook_bounds=(99,99,110,105),
                      hunting_points=[(100,100,7),(104,100,7),(108,100,7)],learned_graph=RegionGraph())
        with patch.object(p,'_toward',side_effect=lambda goal:[goal]):
            self.assertEqual(p._patrol(1),[Position(100,100,7)])
            self.assertEqual(p._patrol(2),[Position(100,100,7)])
            w.position=Position(98,100,7)
            self.assertEqual(p._patrol(3),[Position(100,100,7)])
            w.position=Position(100,100,7)
            self.assertEqual(p._patrol(4),[Position(104,100,7)])
