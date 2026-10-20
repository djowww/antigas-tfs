import unittest
from pathlib import Path
from tools.autonomous_players.world import World,Position,Creature,Thing,Stats,Event,Container
from tools.autonomous_players.definitions import load_items
from tools.autonomous_players.progression import Progression,FOOD_POINTS
from tools.autonomous_players.protocol import say
from tools.autonomous_players.routes import RouteGraph

ITEMS=load_items(Path(__file__).resolve().parents[2]/'data/items/items.srv')


class ProgressionTests(unittest.TestCase):
    def test_hunt_intent_selects_patrol_while_move_intent_skips_it(self):
        start=Position(100,100,7)
        goal=Position(101,101,7)
        world=World(position=start,stats=Stats(150,150,400,0,1))
        for tile in (start,goal,Position(101,100,7),Position(100,101,7)):
            world.tiles[tile]=[Thing(102)]
        routes=RouteGraph({tile:None for tile in world.tiles})

        hunter=Progression(dict(account=1,character='Sim Hunter',city='thais',vocation='knight'),
            world,ITEMS,routes,rook_bounds=(0,0,200,200),hunting_points=[(goal.x,goal.y,goal.z)])
        explorer=Progression(dict(account=2,character='Sim Mover',city='thais',vocation='knight'),
            world,ITEMS,routes,rook_bounds=(0,0,200,200),hunting_points=[(goal.x,goal.y,goal.z)])

        hunt_actions=hunter.step_with_intent(1,'hunt')
        move_actions=explorer.step_with_intent(1,'move')

        self.assertTrue(hunt_actions)
        self.assertTrue(hunter.strategy_hint_applied)
        self.assertEqual(move_actions,[])
        self.assertFalse(explorer.strategy_hint_applied)
        self.assertIsNone(explorer.hunting_started)

    def test_progression_does_not_treat_corpse_food_as_carried_food(self):
        from unittest.mock import patch

        world=World(position=Position(32097,32218,7),stats=Stats(90,150,400,0,1))
        world.containers[1]=Container(1,3994,'dead rat',10,False,[Thing(3600)])
        progression=Progression(dict(character='Sim Test',vocation='knight',city='thais'),
                                world,ITEMS)

        with patch.object(progression,'forage',return_value=[b'\x66']) as forage:
            self.assertEqual(progression.step(1),[b'\x66'])
            self.assertTrue(progression.needs_food)
            forage.assert_called_once_with(1)

        world.containers[1]=Container(1,2853,'bag',10,False,[Thing(3600)])
        progression.needs_food=False
        with patch.object(progression,'forage',return_value=[b'\x66']) as forage:
            self.assertEqual(progression.step(2),[])
            self.assertFalse(progression.needs_food)
            forage.assert_not_called()

    def test_food_points_match_real_rook_spawns_with_nutritious_loot(self):
        from xml.etree import ElementTree
        from tools.autonomous_players.creature_rules import PASSIVE_CORPSES

        root=Path(__file__).resolve().parents[2]
        monster_dir=root/'data/monster'
        registry=ElementTree.parse(monster_dir/'monsters.xml').getroot()
        definitions={entry.attrib['name'].lower():ElementTree.parse(
            monster_dir/entry.attrib['file']).getroot()
            for entry in registry.findall('monster')}
        spawned={}
        for group in ElementTree.parse(root/'data/world/spawns.xml').getroot().findall('spawn'):
            cx=int(group.attrib['centerx']);cy=int(group.attrib['centery'])
            for monster in group.findall('monster'):
                pos=Position(cx+int(monster.attrib.get('x',0)),
                             cy+int(monster.attrib.get('y',0)),
                             int(monster.attrib.get('z',group.attrib['centerz'])))
                spawned.setdefault(pos,set()).add(monster.attrib['name'].lower())

        for point in FOOD_POINTS:
            with self.subTest(point=point):
                self.assertTrue(spawned.get(point))
                for name in spawned[point]:
                    definition=definitions[name]
                    if name not in PASSIVE_CORPSES:
                        continue
                    self.assertEqual(int(definition.find('look').attrib['corpse']),
                                     PASSIVE_CORPSES[name])
                    self.assertTrue(any(ITEMS[int(drop.attrib['id'])].attributes.get('nutrition',0)>0
                                        for drop in definition.findall('./loot/item')))
                self.assertTrue(any(name in PASSIVE_CORPSES for name in spawned[point]))

    def test_twenty_foragers_distribute_across_twelve_real_spawn_points(self):
        world=World(position=Position(32097,32218,7),stats=Stats(65,150,400,0,1))
        destinations=set()
        for account in range(1,21):
            profile=dict(account=account,character=f'Sim {account}',city='thais',vocation='knight')
            progression=Progression(profile,world,ITEMS)
            destinations.add(FOOD_POINTS[progression.forage_index])
        self.assertGreaterEqual(len(destinations),12)

    def test_walk_cancelled_route_step_is_temporarily_avoided(self):
        start=Position(100,100,7)
        rejected=Position(100,101,7)
        alternate=Position(101,100,7)
        goal=Position(101,101,7)
        w=World(position=start,stats=Stats(150,150,400,0,1))
        for tile in (start,rejected,alternate,goal):
            w.tiles[tile]=[Thing(102)]
        routes=RouteGraph({start:None,rejected:None,alternate:None,goal:None})
        p=Progression(dict(account=0,character='Sim One',city='thais',vocation='knight'),
                      w,ITEMS,routes,rook_bounds=(0,0,200,200),hunting_points=[(goal.x,goal.y,goal.z)])

        self.assertEqual(p.step(1),[b'\x67'])
        p.observe([Event('walk_cancel',0)],1.1)
        self.assertEqual(p.step(2),[b'\x66'])

    def test_silently_ignored_route_step_times_out_and_tries_alternate(self):
        start=Position(100,100,7)
        rejected=Position(100,101,7)
        alternate=Position(101,100,7)
        detour=Position(101,101,7)
        lower=Position(101,102,7)
        goal=Position(100,102,7)
        w=World(position=start,stats=Stats(150,150,400,0,1))
        for tile in (start,rejected,alternate,detour,lower,goal):
            w.tiles[tile]=[Thing(102)]
        routes=RouteGraph({tile:None for tile in (start,rejected,alternate,detour,lower,goal)})
        p=Progression(dict(account=0,character='Sim One',city='thais',vocation='knight'),
                      w,ITEMS,routes,rook_bounds=(0,0,200,200),hunting_points=[(goal.x,goal.y,goal.z)])

        first=p._toward(goal,1)
        repeated=p._toward(goal,10.9)
        replanned=p._toward(goal,11.1)

        self.assertEqual(first,[b'\x67'])
        self.assertEqual(repeated,first)
        self.assertEqual(replanned,[b'\x66'])
        self.assertIn(rejected,p.blocked_steps)

    def test_route_does_not_spam_duplicate_step_while_waiting_for_movement(self):
        start=Position(100,100,7)
        following=Position(100,101,7)
        goal=Position(100,102,7)
        w=World(position=start,stats=Stats(150,150,400,0,1))
        for tile in (start,following,goal):
            w.tiles[tile]=[Thing(102)]
        p=Progression(dict(account=0,character='Sim One',city='thais',vocation='knight'),
                      w,ITEMS,RouteGraph({tile:None for tile in (start,following,goal)}),
                      rook_bounds=(0,0,200,200),hunting_points=[(goal.x,goal.y,goal.z)])

        first=p._toward(goal,1)
        immediate_retry=p._toward(goal,1.2)
        timed_retry=p._toward(goal,2.01)

        self.assertEqual(first,[b'\x67'])
        self.assertEqual(immediate_retry,[])
        self.assertEqual(timed_retry,first)

    def test_route_retry_cooldown_skips_expensive_replanning(self):
        from unittest.mock import patch
        start=Position(100,100,7)
        following=Position(100,101,7)
        goal=Position(100,102,7)
        w=World(position=start,stats=Stats(150,150,400,0,1))
        for tile in (start,following,goal):
            w.tiles[tile]=[Thing(102)]
        routes=RouteGraph({tile:None for tile in (start,following,goal)})
        p=Progression(dict(account=0,character='Sim One',city='thais',vocation='knight'),
                      w,ITEMS,routes,rook_bounds=(0,0,200,200))

        self.assertEqual(p._toward(goal,1),[b'\x67'])
        with patch.object(routes,'next_step',side_effect=AssertionError('route recalculated')) as search:
            self.assertEqual(p._toward(goal,1.2),[])
            search.assert_not_called()

    def test_hunting_status_distinguishes_missing_routes_from_stalled_patrol(self):
        w=World(position=Position(100,100,7),stats=Stats(150,150,400,0,1))
        profile=dict(account=1,character='Sim One',city='thais',vocation='knight')
        without_routes=Progression(profile,w,ITEMS)
        missing=without_routes.hunting_status(30)
        self.assertFalse(missing['route_graph_loaded'])
        self.assertEqual(missing['hunting_points'],0)
        self.assertIsNone(missing['goal'])

        with_routes=Progression(profile,w,ITEMS,RouteGraph({w.position:None}),
                                rook_bounds=(99,99,105,105),hunting_points=[(103,100,8)])
        with_routes.hunting_progress=5
        hunting=with_routes.hunting_status(30)
        self.assertTrue(hunting['route_graph_loaded'])
        self.assertEqual(hunting['hunting_points'],1)
        self.assertEqual(hunting['goal'],[103,100,8])
        self.assertEqual(hunting['stalled_seconds'],25)
        self.assertTrue(hunting['stalled'])

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

    def test_foraging_uses_observed_tiles_without_static_route_graph(self):
        goal=FOOD_POINTS[0]
        start=goal.shift(x=-7)
        w=World(position=start,stats=Stats(80,150,400,0,1))
        for x in range(start.x,goal.x+1):
            w.tiles[Position(x,start.y,7)]=[Thing(102)]
        p=Progression(dict(account=0,character='Sim One',city='thais',vocation='knight'),w,ITEMS)

        self.assertEqual(p.forage(1),[b'\x66'])

    def test_foraging_frontier_throttles_repeated_unconfirmed_steps(self):
        start=Position(32097,32218,7)
        w=World(position=start,stats=Stats(40,150,400,0,1))
        for delta in ((0,1),(1,0),(0,-1),(-1,0)):
            w.tiles[start.shift(*delta)]=[Thing(102)]
        p=Progression(dict(account=0,character='Sim One',city='thais',vocation='knight'),w,ITEMS)

        first=p.forage(1)
        repeated=p.forage(1.2)

        self.assertEqual(len(first),1)
        self.assertEqual(repeated,[])

    def test_foraging_frontier_blocks_silent_stall_and_tries_another_tile(self):
        start=Position(32097,32218,7)
        w=World(position=start,stats=Stats(40,150,400,0,1))
        for delta in ((0,1),(1,0),(0,-1),(-1,0)):
            w.tiles[start.shift(*delta)]=[Thing(102)]
        p=Progression(dict(account=0,character='Sim One',city='thais',vocation='knight'),w,ITEMS)

        first=p.forage(1)
        alternate=p.forage(11.1)

        self.assertEqual(len(alternate),1)
        self.assertNotEqual(alternate,first)
        self.assertTrue(p.blocked_steps)

    def test_patrol_uses_observed_rook_sewer_without_static_route_graph(self):
        start=Position(32109,32245,7)
        grate=Position(32110,32245,7)
        below=Position(32110,32246,8)
        middle=Position(32111,32246,8)
        goal=Position(32112,32246,8)
        world=World(self_id=0x10000001,position=start,stats=Stats(150,150,400,0,1))
        world.tiles[start]=[Thing(102)]
        world.tiles[grate]=[Thing(428)]
        for tile in (below,middle,goal):
            world.tiles[tile]=[Thing(102)]
        progression=Progression(dict(account=1,character='Sim One',city='thais',vocation='knight'),
                                world,ITEMS,routes=None,rook_bounds=(32000,32000,32200,32350),
                                hunting_points=[(goal.x,goal.y,goal.z)])

        actions=progression._patrol(1)

        self.assertEqual(actions,[b'\x66'])
        self.assertEqual(progression.floor_authorization,(grate,428))

        world.previous_position,world.position=start,below
        progression.observe([Event('move',(world.self_id,start,below))],2)
        self.assertEqual(progression._patrol(2),[b'\x66'])

    def test_throttled_stair_step_does_not_leak_floor_authorization(self):
        start=Position(32109,32245,7)
        grate=Position(32110,32245,7)
        below=Position(32110,32246,8)
        goal=Position(32112,32246,8)
        world=World(self_id=0x10000001,position=start,stats=Stats(150,150,400,0,1))
        world.tiles[start]=[Thing(102)]
        world.tiles[grate]=[Thing(428)]
        world.tiles[below]=[Thing(102)]
        routes=RouteGraph({start:None,grate:below,below:None,goal:None})
        progression=Progression(dict(account=1,character='Sim One',city='thais',vocation='knight'),
                                world,ITEMS,routes,rook_bounds=(32000,32000,32200,32350),
                                hunting_points=[(goal.x,goal.y,goal.z)])

        first=progression.step(1)
        first_floor_authorization=progression.floor_authorization
        repeated=progression.step(1.2)

        self.assertEqual(first,[b'\x66'])
        self.assertEqual(first_floor_authorization,(grate,428))
        self.assertEqual(repeated,[])
        self.assertIsNone(progression.floor_authorization)

    def test_recovery_uses_observed_up_stair_without_static_route_graph(self):
        start=Position(32110,32245,8)
        stair=Position(32110,32244,8)
        world=World(position=start,stats=Stats(30,150,400,0,1))
        world.tiles[start]=[Thing(102)]
        world.tiles[stair]=[Thing(102),Thing(1947)]
        progression=Progression(dict(account=1,character='Sim One',city='thais',vocation='knight'),
                                world,ITEMS,routes=None,rook_bounds=(32000,32000,32200,32350))

        actions=progression.recover(1)

        self.assertEqual(actions,[b'\x65'])
        self.assertEqual(progression.floor_authorization,(stair,1947))
        from tools.autonomous_players.runtime import ActionGate
        gate=ActionGate(world,ITEMS)
        gate.floor_token=progression.floor_authorization
        self.assertTrue(gate.permit(actions[0]))

    def test_confirmed_learned_stair_overrides_stale_static_destination(self):
        from tools.autonomous_players.learned_navigation import RegionGraph

        start=Position(32109,32245,7)
        grate=Position(32110,32245,7)
        below=Position(32110,32246,8)
        goal=Position(32112,32246,8)
        stale=Position(32110,32244,8)
        world=World(self_id=0x10000001,position=start,stats=Stats(150,150,400,0,1))
        world.tiles[start]=[Thing(102)]
        world.tiles[grate]=[Thing(428)]
        world.tiles[below]=[Thing(102)]
        routes=RouteGraph({start:None,grate:stale,stale:None,below:None,goal:None})
        unlearned=Progression(dict(account=1,character='Sim One',city='thais',vocation='knight'),
                              world,ITEMS,routes,rook_bounds=(32000,32000,32200,32350),
                              hunting_points=[(goal.x,goal.y,goal.z)],learned_graph=RegionGraph())
        self.assertEqual(unlearned._toward(goal,2),[])
        learned=RegionGraph()
        learned.record_stair_observation('Sim One',start,428,below)
        self.assertTrue(learned.observe_transition('Sim One',start,below,428,1))
        progression=Progression(dict(account=1,character='Sim One',city='thais',vocation='knight'),
                                world,ITEMS,routes,rook_bounds=(32000,32000,32200,32350),
                                hunting_points=[(goal.x,goal.y,goal.z)],learned_graph=learned)

        actions=progression._toward(goal,2)

        self.assertEqual(actions,[b'\x66'])
        self.assertEqual(progression.floor_authorization,(grate,428))

        blocked=RegionGraph(cooldown=30)
        blocked.record_stair_observation('Sim One',start,428,below)
        self.assertTrue(blocked.observe_transition('Sim One',start,below,428,1))
        blocked.record_failure('Sim One',start,below,'rejected',2)
        cautious=Progression(dict(account=1,character='Sim One',city='thais',vocation='knight'),
                             world,ITEMS,routes,rook_bounds=(32000,32000,32200,32350),
                             hunting_points=[(goal.x,goal.y,goal.z)],learned_graph=blocked)
        self.assertEqual(cautious._toward(goal,3),[])
        self.assertIsNone(cautious.floor_authorization)

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

    def test_red_health_speaks_within_server_supported_three_tile_range(self):
        w=World(position=Position(32094,32216,7),stats=Stats(17,150,400,0,1))
        npc=Creature(0x80000001,'Cipfried',Position(32097,32217,7))
        w.creatures[npc.id]=npc
        p=Progression(dict(character='Sim One',city='thais',vocation='knight'),w,ITEMS)
        self.assertEqual(p.recover(1),[say('hi')])
        self.assertEqual(p.authorization,(npc.id,'hi',6))

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

    def test_hunting_patrol_routes_from_rook_surface_through_grate_to_cave_goal(self):
        start=Position(32109,32245,7)
        grate=Position(32110,32245,7)
        below=Position(32110,32246,8)
        middle=Position(32111,32246,8)
        goal=Position(32112,32246,8)
        w=World(position=start,stats=Stats(150,150,400,0,1))
        w.tiles[grate]=[Thing(428)]
        w.tiles[middle]=[Thing(102)]
        routes=RouteGraph({start:None,grate:below,below:None,middle:None,goal:None})
        p=Progression(dict(account=1,character='Sim One',city='thais',vocation='knight'),w,ITEMS,routes,
                      rook_bounds=(32000,32000,32200,32350),
                      hunting_points=[(goal.x,goal.y,goal.z)])

        self.assertEqual(p.step(1),[b'\x66'])
        self.assertEqual(p.floor_authorization,(grate,428))
        w.position=below
        self.assertEqual(p.step(2),[b'\x66'])

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

    def test_routed_player_detours_around_another_player_blocking_a_corridor(self):
        start,blocked,goal=(Position(100,100,7),Position(101,100,7),Position(102,100,7))
        detour=(Position(100,101,7),Position(101,101,7),Position(102,101,7))
        tiles={p:None for p in (start,blocked,goal,*detour)}
        w=World(self_id=1,position=start,stats=Stats(150,150,400,0,1))
        for p in tiles:
            w.tiles[p]=[Thing(102)]
        w.creatures[2]=Creature(2,'Sim Other',blocked)
        w.tiles[blocked].append(Thing(0,creature_id=2))
        progression=Progression(dict(character='Sim One',city='thais',vocation='knight'),
                               w,ITEMS,RouteGraph(tiles))
        self.assertEqual(progression._toward(goal),[b'\x67'])

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

    def test_all_cooled_down_hunt_routes_fall_back_to_observed_exploration(self):
        import random
        import tempfile
        from pathlib import Path
        from tools.autonomous_players.app import choose_actions
        from tools.autonomous_players.behaviour import Agent
        from tools.autonomous_players.learned_navigation import RegionGraph
        from tools.autonomous_players.learning import Policy
        from tools.autonomous_players.store import Store

        start=Position(100,100,7)
        goals=[Position(104,100,7),Position(103,101,7)]
        w=World(self_id=0x10000001,position=start,stats=Stats(150,150,400,0,1))
        for x in range(98,105):
            for y in range(98,104):
                tile=Position(x,y,7)
                w.tiles[tile]=[Thing(102)]
        learned=RegionGraph()
        for goal in goals:
            learned.record_failure('Sim One',start,goal,'blocked',1)
        profile=dict(account=1,character='Sim One',city='thais',vocation='knight')
        progression=Progression(profile,w,ITEMS,RouteGraph({tile:None for tile in w.tiles}),
                                rook_bounds=(98,98,105,104),
                                hunting_points=[(goal.x,goal.y,goal.z) for goal in goals],
                                learned_graph=learned)

        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'state.db') as store:
            agent=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(4)))
            actions=choose_actions(agent,progression,2)

        self.assertTrue(actions)
        self.assertIn(actions[0][0],(0x65,0x66,0x67,0x68))

    def test_active_hunting_goal_is_kept_until_rotation(self):
        from unittest.mock import patch
        from tools.autonomous_players.learned_navigation import RegionGraph
        w=World(position=Position(98,100,7),stats=Stats(150,150,400,0,1))
        profile=dict(account=0,character='Sim One',city='thais',vocation='knight')
        p=Progression(profile,w,ITEMS,RouteGraph({w.position:None}),rook_bounds=(99,99,110,105),
                      hunting_points=[(100,100,7),(104,100,7),(108,100,7)],learned_graph=RegionGraph())
        with patch.object(p,'_toward',side_effect=lambda goal,now=None:[goal]):
            self.assertEqual(p._patrol(1),[Position(100,100,7)])
            self.assertEqual(p._patrol(2),[Position(100,100,7)])
            w.position=Position(98,100,7)
            self.assertEqual(p._patrol(3),[Position(100,100,7)])
            w.position=Position(100,100,7)
            self.assertEqual(p._patrol(4),[Position(104,100,7)])
