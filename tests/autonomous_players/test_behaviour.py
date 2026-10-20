import random
import tempfile
import unittest
from pathlib import Path

from tools.autonomous_players.world import World, Position, Thing, Creature, Stats, Event, Container
from tools.autonomous_players.definitions import load_items
from tools.autonomous_players.navigation import find_path
from tools.autonomous_players.behaviour import Agent
from tools.autonomous_players.routes import RouteGraph
from tools.autonomous_players.progression import Progression
from tools.autonomous_players.social import Oracle, Purchase, party_action
from tools.autonomous_players.learning import Policy
from tools.autonomous_players.store import Store

ITEMS = load_items(Path(__file__).resolve().parents[2] / 'data/items/items.srv')


class BehaviourTests(unittest.TestCase):
    def test_every_rook_passive_food_spawn_is_supported_by_bot_rules(self):
        from xml.etree import ElementTree
        from tools.autonomous_players.creature_rules import PASSIVE_CORPSES

        root=Path(__file__).resolve().parents[2]
        monsters_dir=root/'data/monster'
        registry=ElementTree.parse(monsters_dir/'monsters.xml').getroot()
        definitions={entry.attrib['name'].lower():ElementTree.parse(
            monsters_dir/entry.attrib['file']).getroot()
            for entry in registry.findall('monster')}
        spawned=set()
        for group in ElementTree.parse(root/'data/world/spawns.xml').getroot().findall('spawn'):
            center_x=int(group.attrib['centerx']); center_y=int(group.attrib['centery'])
            for monster in group.findall('monster'):
                x=center_x+int(monster.attrib.get('x',0))
                y=center_y+int(monster.attrib.get('y',0))
                if 32000<=x<=32200 and 32000<=y<=32350:
                    spawned.add(monster.attrib['name'].lower())

        for name in spawned:
            definition=definitions.get(name)
            if definition is None:
                continue
            flags=definition.find('flags')
            if flags is None or flags.find('flag[@hostile="0"]') is None:
                continue
            nutritious=[int(drop.attrib['id']) for drop in definition.findall('./loot/item')
                        if ITEMS[int(drop.attrib['id'])].attributes.get('nutrition',0)>0]
            if not nutritious:
                continue
            with self.subTest(monster=name):
                self.assertIn(name,PASSIVE_CORPSES)
                corpse=int(definition.find('look').attrib['corpse'])
                self.assertEqual(PASSIVE_CORPSES[name],corpse)

    def test_passive_food_targets_match_server_corpse_and_nutritious_drops(self):
        from xml.etree import ElementTree
        from tools.autonomous_players.behaviour import PASSIVE_CORPSES
        monsters=Path(__file__).resolve().parents[2]/'data/monster'
        for name,expected_corpse in PASSIVE_CORPSES.items():
            with self.subTest(monster=name):
                root=ElementTree.parse(monsters/(name+'.xml')).getroot()
                self.assertEqual(int(root.find('look').attrib['corpse']),expected_corpse)
                nutritious=[int(item.attrib['id']) for item in root.findall('./loot/item')
                            if ITEMS[int(item.attrib['id'])].attributes.get('nutrition',0)>0]
                self.assertTrue(nutritious)

    def test_wounded_bot_hunts_food_animal_instead_of_idling(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.stats.health=70
            rabbit=Creature(0x40000001,'Rabbit',Position(101,100,7))
            rat=Creature(0x40000002,'Rat',Position(104,104,7))
            w.creatures.update({rabbit.id:rabbit,rat.id:rat})
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertEqual([c.name for c in a.prey()],['Rabbit'])
            self.assertTrue(any(p[0]==0xa1 for p in a.step(1)))

    def test_accepted_strategy_hint_is_reported_by_real_agent(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            rabbit=Creature(0x40000001,'Rabbit',Position(101,100,7))
            w.creatures[rabbit.id]=rabbit
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            actions=a.step(1,strategy_hint='hunt')

            self.assertTrue(a.strategy_hint_applied)
            self.assertEqual(a.strategy,'hunt')
            self.assertTrue(any(packet[0]==0xa1 for packet in actions))

    def test_healthy_bot_can_follow_learned_exploration_with_visible_prey(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            rat=Creature(0x40000001,'Rat',Position(104,100,7))
            w.creatures[rat.id]=rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            actions=a.step(1,strategy_hint='explore')

            self.assertTrue(a.strategy_hint_applied)
            self.assertEqual(a.strategy,'explore')
            self.assertTrue(actions)
            self.assertNotEqual(actions[-1][0],0xa1)

    def test_wounded_bot_keeps_food_hunt_priority_over_exploration_hint(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.stats.health=70
            rabbit=Creature(0x40000001,'Rabbit',Position(101,100,7))
            w.creatures[rabbit.id]=rabbit
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            actions=a.step(1,strategy_hint='explore')

            self.assertFalse(a.strategy_hint_applied)
            self.assertEqual(a.strategy,'hunt')
            self.assertIn(0xa1,[packet[0] for packet in actions])

    def test_rejected_strategy_hint_is_not_reported_as_controlled(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            a.step(1,strategy_hint='hunt')

            self.assertFalse(a.strategy_hint_applied)

    def test_wounded_passive_food_animal_does_not_trigger_aggressive_retreat(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.stats.health=70
            prey=Creature(0x40000001,'Rabbit',Position(101,100,7))
            w.creatures[prey.id]=prey
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            self.assertFalse(a.retreat_needed())
            prey.name='Rat'
            self.assertTrue(a.retreat_needed())

    def test_wounded_bot_without_visible_food_uses_foraging_route(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.stats.health=65
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.forage=lambda now:[b'\x66']
            self.assertEqual(a.step(1),[b'\x66'])
            self.assertEqual(a.strategy,'forage')

    def test_red_health_prioritizes_temple_over_passive_animal(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.stats.health=30
            w.creatures[0x40000001]=Creature(0x40000001,'Rabbit',Position(101,100,7))
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.escape=lambda now:[b'\x65']
            self.assertEqual(a.step(1,strategy_hint='hunt'),[b'\x65'])
            self.assertFalse(a.strategy_hint_applied)

    def test_zero_xp_passive_kill_allows_only_new_matching_owned_corpse(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.stats.health=70
            rabbit=Creature(0x40000001,'Rabbit',Position(101,100,7))
            w.creatures[rabbit.id]=rabbit
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.step(1);rabbit.position=None
            w.tiles[Position(101,100,7)].append(Thing(4173))
            a.observe([Event('tile',Position(101,100,7))],2)
            self.assertIn((Position(101,100,7),4173),a.allowed_corpses)
            self.assertEqual(a.passive_corpse_claims,1)
            self.assertEqual(a.confirmed_kills,1)
            self.assertEqual(a.confirmed_kill_types,{'Rabbit':1})

    def test_long_passive_hunt_keeps_tracking_food_corpse_until_kill(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.stats.health=70;tile=Position(101,100,7)
            w.containers[0]=Container(0,2853,'bag',20,False,[])
            rabbit=Creature(0x40000001,'Rabbit',tile)
            w.creatures[rabbit.id]=rabbit
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            for now in (1,4,7,10):
                actions=a.step(now)
                self.assertTrue(any(packet[0]==0xa1 for packet in actions))
            a.observe([],11.1)
            rabbit.position=None
            w.tiles[tile].append(Thing(4173))
            a.observe([Event('tile',tile)],12)

            self.assertIn((tile,4173),a.allowed_corpses)
            opening=a.step(13)
            self.assertEqual(opening[0][0],0x82)
            w.containers[1]=Container(1,4173,'dead rabbit',10,False,[Thing(3577,1)])
            a.observe([Event('container_open',(1,4173))],13.5)
            transfer=a.step(14)
            self.assertEqual(transfer[0][0],0x78)
            w.inventory[5]=Thing(3577,1)
            w.containers[1].items.clear()
            self.assertIsNotNone(next(a.food(),None))

    def test_rat_xp_unlocks_own_corpse_and_nutrition_loot_reaches_inventory(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();tile=Position(101,100,7)
            w.containers[0]=Container(0,2853,'bag',20,False,[])
            rat=Creature(0x40000001,'Rat',tile)
            w.creatures[rat.id]=rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            self.assertTrue(any(packet[0]==0xa1 for packet in a.step(1)))
            rat.position=None
            w.stats.experience=5
            w.tiles[tile].append(Thing(3994))
            a.observe([Event('stats',w.stats)],2)
            self.assertIn((tile,3994),a.allowed_corpses)
            self.assertEqual(a.confirmed_kills,1)
            self.assertEqual(a.confirmed_kill_types,{'Rat':1})
            self.assertEqual(a.step(3)[0][0],0x82)

            w.containers[1]=Container(1,3994,'dead rat',10,False,[Thing(3607,1)])
            a.observe([Event('container_open',(1,3994))],3.5)
            self.assertEqual(a.step(4)[0][0],0x78)
            self.assertFalse(any(packet[0]==0x78 for packet in a.step(4.7)))
            w.inventory[5]=Thing(3607,1)
            w.containers[1].items.clear()
            self.assertIsNotNone(next(a.food(),None))

    def test_human_contest_blocks_loot_but_not_own_xp_kill_count(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();tile=Position(101,100,7)
            rat=Creature(0x40000001,'Rat',tile)
            human=Creature(0x10000002,'Nearby Human',tile.shift(x=1))
            w.creatures[rat.id]=rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            self.assertTrue(any(packet[0]==0xa1 for packet in a.step(1)))
            w.creatures[human.id]=human
            rat.position=None
            w.stats.experience=5
            w.tiles[tile].append(Thing(3994))
            a.observe([Event('stats',w.stats)],2)

            self.assertEqual(a.confirmed_kill_types,{'Rat':1})
            self.assertNotIn((tile,3994),a.allowed_corpses)

    def test_cave_rat_requires_two_attacks_and_yields_xp_and_food_loot(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();tile=Position(101,100,7)
            w.containers[0]=Container(0,2853,'bag',20,False,[])
            cave_rat=Creature(0x40000001,'Cave Rat',tile,health=30)
            w.creatures[cave_rat.id]=cave_rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.strategy,a.next_strategy='hunt',10

            first=a.step(1)
            self.assertTrue(any(packet[0]==0xa1 for packet in first))
            cave_rat.health=10
            second=a.step(4)
            self.assertTrue(any(packet[0]==0xa1 for packet in second))
            cave_rat.position=None
            w.stats.experience=10
            w.tiles[tile].append(Thing(3994))
            a.observe([Event('stats',w.stats)],4.1)
            self.assertIn((tile,3994),a.allowed_corpses)
            self.assertEqual(a.confirmed_kills,1)
            self.assertEqual(a.confirmed_kill_types,{'Cave Rat':1})
            self.assertEqual(a.step(5)[0][0],0x82)

            w.containers[1]=Container(1,3994,'dead rat',10,False,[Thing(3607,1)])
            a.observe([Event('container_open',(1,3994))],5.5)
            transfer=a.step(6)[0]
            self.assertEqual(transfer[0],0x78)
            w.inventory[5]=Thing(3607,1)
            w.containers[1].items.clear()
            self.assertIsNotNone(next(a.food(),None))

    def test_full_backpack_backs_off_corpse_loot_without_repeating_transfer(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();tile=Position(101,100,7)
            w.containers[0]=Container(0,2853,'bag',1,False,[Thing(3031,100)])
            w.containers[1]=Container(1,3994,'dead rat',10,False,[Thing(3607,1)])
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.loot_pending=(tile,3994)
            a.loot_container_id=1

            actions=a.step(1)
            retry_actions=a.step(2)

            self.assertFalse(any(packet[0]==0x78 for packet in actions))
            self.assertFalse(any(packet[0]==0x78 for packet in retry_actions))
            self.assertEqual(a.loot_pending,(tile,3994))
            self.assertEqual(a.loot_transfer_retry,31)

    def test_unresponsive_corpse_open_uses_bounded_progressive_retry(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();tile=Position(101,100,7)
            w.tiles[tile].append(Thing(3994))
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.allowed_corpses[(tile,3994)]=200

            first=a.step(1)
            second=a.step(6)
            before_next=a.step(15.9)
            third=a.step(16.6)

            self.assertTrue(any(packet[0]==0x82 for packet in first))
            self.assertTrue(any(packet[0]==0x82 for packet in second))
            self.assertFalse(any(packet[0]==0x82 for packet in before_next))
            self.assertTrue(any(packet[0]==0x82 for packet in third))
            self.assertEqual(a.loot_retry,36.6)

    def test_loots_pending_corpse_even_when_it_opens_in_a_different_container_slot(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();tile=Position(101,100,7)
            w.containers[0]=Container(0,2853,'bag',20,False,[])
            w.containers[1]=Container(1,4173,'dead rabbit',10,False,[Thing(3031,1)])
            w.containers[2]=Container(2,3994,'dead rat',10,False,[Thing(3607,1)])
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.loot_pending=(tile,3994)
            a.loot_container_id=2

            transfer=a.step(1)

            self.assertEqual(transfer[0][0],0x78)
            self.assertEqual(transfer[0][3:5],bytes((0x42,0x00)))  # source y = 66 (container 2)

    def test_loot_uses_the_container_opened_for_the_pending_corpse(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();tile=Position(101,100,7)
            w.containers[0]=Container(0,2853,'bag',20,False,[])
            w.containers[1]=Container(1,4173,'old dead rabbit',10,False,[Thing(3031,1)])
            w.containers[2]=Container(2,4173,'new dead rabbit',10,False,[Thing(3595,1)])
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.allowed_corpses[(tile,4173)]=100
            a.loot_pending=(tile,4173)
            a.loot_open_requested=True
            a.observe([Event('container_open',(2,4173))],2)

            transfer=a.step(3)

            self.assertEqual(transfer[0][0],0x78)
            self.assertEqual(transfer[0][3:5],bytes((0x42,0x00)))

    def test_passive_food_loot_rejects_existing_corpse_and_human_competition(self):
        for existing,human in ((True,False),(False,True)):
            with self.subTest(existing=existing,human=human), tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
                w=self.world();w.stats.health=70;tile=Position(101,100,7)
                rabbit=Creature(0x40000001,'Rabbit',tile);w.creatures[rabbit.id]=rabbit
                if existing:w.tiles[tile].append(Thing(4173))
                a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
                a.step(1);rabbit.position=None
                if not existing:w.tiles[tile].append(Thing(4173))
                if human:w.creatures[0x10000002]=Creature(0x10000002,'Human',Position(102,100,7))
                a.observe([Event('tile',tile)],2)
                self.assertNotIn((tile,4173),a.allowed_corpses)

    def test_unknown_zero_item_id_in_creature_tile_does_not_crash_corpse_scan(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();tile=Position(101,100,7)
            w.tiles[tile]=[Thing(0,creature_id=0x40000001),Thing(4173)]
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            self.assertEqual(a._corpse_counts(tile),{4173:1})

    def test_removed_or_contested_corpse_does_not_keep_loot_priority(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();tile=Position(101,100,7)
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.allowed_corpses[(tile,4173)]=100
            self.assertFalse(a.priority(1))

            w.tiles[tile]=[Thing(4173)]
            self.assertTrue(a.priority(2))
            w.creatures[0x10000002]=Creature(0x10000002,'Human',Position(103,100,7))
            self.assertFalse(a.priority(3))

    def test_bot_does_not_open_a_corpse_when_a_human_approaches_later(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();tile=Position(101,100,7)
            w.tiles[tile]=[Thing(4173)]
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.allowed_corpses[(tile,4173)]=100
            w.creatures[0x10000002]=Creature(0x10000002,'Human',Position(103,100,7))

            contested=a.step(1)
            w.creatures[0x10000002].position=Position(120,120,7)
            available=a.step(2)

            self.assertFalse(any(packet[0]==0x82 for packet in contested))
            self.assertTrue(any(packet[0]==0x82 for packet in available))

    def test_retreat_uses_observed_escape_route_instead_of_wandering(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.stats.health=50
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.escape=lambda now:[b'\x65']
            self.assertEqual(a.step(1),[b'\x65'])

    def test_retreat_uses_only_observed_neighbor_with_static_route_when_recovery_has_no_step(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            start=Position(32065,32250,8)
            dead_end=Position(32065,32249,8)
            toward_exit=Position(32066,32250,8)
            stair=Position(32067,32250,8)
            temple=Position(32097,32218,7)
            w=World(self_id=0x10000001,position=start,stats=Stats(50,150,400,0,1))
            for position in (start,dead_end,toward_exit,stair):
                w.tiles[position]=[Thing(102)]
            routes=RouteGraph({start:None,dead_end:None,toward_exit:None,
                               stair:temple,temple:None})
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            progression=Progression(dict(account=1,character='Sim One',city='thais',vocation='knight'),
                                    w,ITEMS,routes)
            a.escape=progression.recover
            a.retreat_goal=temple
            a.retreat_routes=progression.routes

            self.assertEqual(a.step(1),[b'\x66'])

    def test_retreat_does_not_choose_disconnected_fallback_without_visible_monsters(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            start=Position(100,100,8)
            north=Position(100,99,8)
            east=Position(101,100,8)
            temple=Position(100,99,7)
            w=World(self_id=0x10000001,position=start,stats=Stats(50,150,400,0,1))
            for position in (start,north,east):
                w.tiles[position]=[Thing(102)]
            routes=RouteGraph({start:None,north:None,east:None,temple:None})
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.escape=lambda now:[]
            a.retreat_goal=temple
            a.retreat_routes=routes

            self.assertEqual(a.step(1),[])

    def test_retreat_does_not_walk_into_disconnected_branch_while_monster_is_nearby(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            start=Position(32065,32250,8)
            north=start.shift(y=-1)
            east=start.shift(x=1)
            temple=Position(32097,32218,7)
            world=World(self_id=0x10000001,position=start,stats=Stats(50,150,400,0,1))
            for position in (start,north,east):
                world.tiles[position]=[Thing(102)]
            monster=Creature(0x40000001,'Rat',north,health=20)
            world.creatures[monster.id]=monster
            routes=RouteGraph({start:None,north:None,east:None,temple:None})
            agent=Agent('Sim One',world,ITEMS,Policy(store,'Sim One',random.Random(7)))
            agent.escape=lambda now:[]
            agent.retreat_goal=temple
            agent.retreat_routes=routes

            self.assertEqual(agent.step(1),[])

    def test_retreat_skips_occupied_connected_tiles_and_uses_free_exit(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            start=Position(100,100,8)
            north=start.shift(y=-1)
            east=start.shift(x=1)
            south=start.shift(y=1)
            corridor=Position(100,102,8)
            stair=Position(100,103,8)
            temple=Position(100,103,7)
            world=World(self_id=0x10000001,position=start,stats=Stats(50,150,400,0,1))
            for position in (start,north,east,south,corridor,stair):
                world.tiles[position]=[Thing(102)]
            world.creatures[0x40000001]=Creature(0x40000001,'Rat',north,health=20)
            southwest=Position(99,101,8)
            world.creatures[0x40000002]=Creature(0x40000002,'Cave Rat',southwest,health=20)
            world.creatures[0x10000002]=Creature(0x10000002,'Other Player',east)
            routes=RouteGraph({start:None,north:None,east:None,south:None,
                               corridor:None,stair:temple,temple:None})
            agent=Agent('Sim One',world,ITEMS,Policy(store,'Sim One',random.Random(7)))
            agent.escape=lambda now:[]
            agent.retreat_goal=temple
            agent.retreat_routes=routes

            self.assertEqual(agent.step(1),[b'\x67'])

    def test_critical_recovery_without_route_graph_explores_observed_safe_tiles(self):
        for routes in (None,RouteGraph({})):
            with self.subTest(routes=routes is not None),tempfile.TemporaryDirectory() as d,Store(Path(d)/'s.db') as store:
                start=Position(32065,32250,8)
                neighbors=(start.shift(y=-1),start.shift(x=1),start.shift(y=1),start.shift(x=-1))
                world=World(self_id=0x10000001,position=start,stats=Stats(20,150,400,0,1))
                for tile in (start,*neighbors):
                    world.tiles[tile]=[Thing(102)]
                agent=Agent('Sim One',world,ITEMS,Policy(store,'Sim One',random.Random(7)))
                agent.escape=lambda now:[]
                agent.retreat_routes=routes
                agent.retreat_goal=Position(32097,32218,7)

                actions=agent.step(1)

                self.assertEqual(len(actions),1)
                self.assertIn(actions[0][0],(0x65,0x66,0x67,0x68))

    def test_cancelled_emergency_step_is_cooled_down_and_replanned(self):
        with tempfile.TemporaryDirectory() as d,Store(Path(d)/'s.db') as store:
            start=Position(32065,32250,8)
            neighbors=(start.shift(y=-1),start.shift(x=1),start.shift(y=1),start.shift(x=-1))
            world=World(self_id=0x10000001,position=start,stats=Stats(20,150,400,0,1))
            for tile in (start,*neighbors):
                world.tiles[tile]=[Thing(102)]
            agent=Agent('Sim One',world,ITEMS,Policy(store,'Sim One',random.Random(7)))
            agent.escape=lambda now:[]
            expected=[b'\x65',b'\x66',b'\x67',b'\x68']
            for index,packet in enumerate(expected):
                now=1+index
                self.assertEqual(agent.step(now),[packet])
                agent.observe([Event('walk_cancel',0)],now+.1)

            self.assertEqual(agent.step(5),[])
            self.assertEqual(agent.step(17),[b'\x65'])

    def test_emergency_step_without_progress_expires_and_replans(self):
        with tempfile.TemporaryDirectory() as d,Store(Path(d)/'s.db') as store:
            start=Position(32065,32250,8)
            neighbors=(start.shift(y=-1),start.shift(x=1))
            world=World(self_id=0x10000001,position=start,stats=Stats(20,150,400,0,1))
            for tile in (start,*neighbors):
                world.tiles[tile]=[Thing(102)]
            agent=Agent('Sim One',world,ITEMS,Policy(store,'Sim One',random.Random(7)))
            agent.escape=lambda now:[]
            agent.step(1)

            second=agent.step(12)

            self.assertEqual(second,[b'\x66'])

    def test_multiple_adjacent_rats_trigger_retreat_before_health_collapses(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            for cid,position in ((0x40000001,Position(101,100,7)),(0x40000002,Position(100,101,7))):
                w.creatures[cid]=Creature(cid,'Rat',position)
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertTrue(a.priority(1))
            self.assertTrue(all(p[0]!=0xa1 for p in a.step(1)))
            self.assertEqual(a.strategy,'retreat')

    def test_healthy_cave_hunter_fights_two_rats_then_retreats_when_wounded(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.position=Position(100,100,8);w.stats.health=102
            for x in range(98,104):
                for y in range(98,104):
                    w.tiles[Position(x,y,8)]=[Thing(102)]
            w.creatures[0x40000001]=Creature(0x40000001,'Rat',Position(101,100,8))
            w.creatures[0x40000002]=Creature(0x40000002,'Cave Rat',Position(100,101,8))
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertFalse(a.retreat_needed())
            self.assertTrue(any(packet[0]==0xa1 for packet in a.step(1)))
            w.stats.health=92
            self.assertTrue(a.retreat_needed())

    def test_unreachable_pen_prey_does_not_hold_patrol_forever(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            rat=Creature(0x40000001,'Rat',Position(102,100,7))
            w.creatures[rat.id]=rat
            for p in (Position(101,100,7),Position(103,100,7),Position(102,99,7),Position(102,101,7)):
                w.tiles[p]=[]
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertTrue(all(packet[0]!=0xa1 for packet in a.step(1)))
            self.assertFalse(a.priority(3))
            rat.position=Position(100,101,7)
            self.assertTrue(a.priority(4))

    def test_unreachable_prey_falls_back_to_walk_instead_of_only_canceling(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            rat=Creature(0x40000001,'Rat',Position(102,100,7))
            w.creatures[rat.id]=rat
            for p in (Position(101,100,7),Position(103,100,7),
                      Position(102,99,7),Position(102,101,7)):
                w.tiles[p]=[]
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            actions=a.step(1)

            self.assertTrue(any(packet[0] in (0x65,0x66,0x67,0x68)
                                for packet in actions))
            self.assertFalse(any(packet[0]==0xa1 for packet in actions))
            self.assertEqual(a.combat_stalls,1)

    def test_attack_stall_counts_one_failed_hunt(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            rat=Creature(0x40000001,'Rat',Position(101,100,7))
            w.creatures[rat.id]=rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            self.assertTrue(any(packet[0]==0xa1 for packet in a.step(1)))
            self.assertEqual(a.combat_stalls,0)
            self.assertEqual(a.step(14),[b'\xbe'])
            self.assertEqual(a.combat_stalls,1)

    def test_distant_prey_is_approached_before_melee_attack(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            rat=Creature(0x40000001,'Rat',Position(102,100,7))
            w.creatures[rat.id]=rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertEqual(a.step(1),[b'\x66'])
            self.assertEqual(a.target,0)
            w.position=Position(101,100,7)
            self.assertTrue(any(packet[0]==0xa1 for packet in a.step(2)))

    def test_safe_visible_prey_overrides_patrol_and_starts_hunt(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            rat=Creature(0x40000001,'Rat',Position(104,100,7))
            w.creatures[rat.id]=rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertTrue(a.priority(1))
            a.policy.choose=lambda state,allowed:'explore' if 'explore' in allowed else allowed[0]
            actions=a.step(1)
            self.assertEqual(a.strategy,'hunt')
            self.assertTrue(actions)
            self.assertEqual(actions[0][0],0x66)

    def test_fleeing_food_animal_keeps_server_follow_until_cancelled_or_unsafe(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.stats.health=70
            rabbit=Creature(0x40000001,'Rabbit',Position(101,100,7))
            w.creatures[rabbit.id]=rabbit
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertEqual(a.step(1)[0],b'\xa0\x01\x01\x00')
            rabbit.position=Position(103,100,7)
            self.assertEqual(a.step(2),[])
            self.assertEqual(a.target,rabbit.id)

    def test_abandoning_living_prey_clears_stale_attack_and_corpse_evidence(self):
        with tempfile.TemporaryDirectory() as d,Store(Path(d)/'s.db') as store:
            world=self.world();world.stats.health=70
            rabbit=Creature(0x40000001,'Rabbit',Position(101,100,7))
            world.creatures[rabbit.id]=rabbit
            agent=Agent('Sim One',world,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertEqual(agent.step(1)[0],b'\xa0\x01\x01\x00')
            self.assertIsNotNone(agent.passive_attack)
            self.assertIsNotNone(agent.attack_evidence)
            rabbit.position=Position(109,100,7)

            self.assertEqual(agent.step(4),[b'\xbe'])

            self.assertEqual(agent.target,0)
            self.assertIsNone(agent.target_position)
            self.assertIsNone(agent.passive_attack)
            self.assertIsNone(agent.attack_evidence)

    def test_cancelled_passive_follow_replans_path_to_fleeing_food_animal(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.stats.health=70
            rabbit=Creature(0x40000001,'Rabbit',Position(103,100,7))
            w.creatures[rabbit.id]=rabbit
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.target=rabbit.id

            self.assertEqual(a.step(1),[])
            a.observe([Event('walk_cancel',0)],1.2)
            actions=a.step(2)

            self.assertTrue(actions)
            self.assertEqual(actions[-1][0],0x66)
            self.assertEqual(a.target,0)

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

    def test_exploration_does_not_repeat_unconfirmed_step_each_decision_tick(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            first=a.step(1)
            early_retry=a.step(1.7)
            timed_retry=a.step(2.4)

            self.assertTrue(first and first[0][0] in (0x65,0x66,0x67,0x68))
            self.assertEqual(early_retry,[])
            self.assertEqual(timed_retry,first)
            old=w.position
            w.previous_position,w.position=old,old.shift(y=1)
            a.observe([Event('move',(w.self_id,old,w.position))],2.5)
            self.assertTrue(a.step(3.1))

    def test_exploration_abandons_destination_after_no_observed_movement(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertTrue(a.step(1))
            first_goal=a.destination

            self.assertTrue(a.step(12))

            self.assertNotEqual(a.destination,first_goal)
            self.assertGreater(a.unreachable_destinations[first_goal],12)

    def test_server_walk_cancel_immediately_replans_around_failed_destination(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertTrue(a.step(1))
            failed_goal=a.destination

            a.observe([Event('walk_cancel',0)],1.2)
            self.assertTrue(a.step(2))

            self.assertNotEqual(a.destination,failed_goal)
            self.assertGreater(a.unreachable_destinations[failed_goal],2)

    def test_cancelled_adjacent_fallback_is_avoided_on_next_exploration_step(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            start=Position(100,100,7)
            rejected=Position(100,101,7)
            alternate=Position(101,100,7)
            w=self.world()
            w.position=start
            w.tiles={start:[Thing(102)],rejected:[Thing(102)],alternate:[Thing(102)]}
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            self.assertEqual(a.step(1),[b'\x67'])
            a.observe([Event('walk_cancel',0)],1.1)

            self.assertEqual(a.step(2),[b'\x66'])
            self.assertIn(rejected,a.unreachable_destinations)

    def test_attack_without_damage_times_out_and_switches_to_another_prey(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            first=Creature(0x40000001,'Rat',Position(101,100,7),health=30)
            second=Creature(0x40000002,'Rabbit',Position(100,101,7),health=30)
            w.creatures[first.id]=first
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            self.assertEqual(a.step(1)[-1][0],0xa1)
            self.assertEqual(a.target,first.id)
            self.assertEqual(a.step(13),[b'\xbe'])
            self.assertIn(first.id,a.unreachable_prey)

            w.creatures[second.id]=second
            actions=a.step(14)
            self.assertEqual(actions[-1][0],0xa1)
            self.assertEqual(a.target,second.id)

    def test_new_prey_spawn_on_unreachable_tile_does_not_repeat_cancel_loop(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            unreachable=Position(106,100,7)
            first=Creature(0x40000001,'Rat',unreachable,health=30)
            w.creatures[first.id]=first
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            initial=a.step(1)
            self.assertTrue(any(packet[0] in (0x65,0x66,0x67,0x68) for packet in initial))
            self.assertNotIn(first, a.prey())  # Same spawn remains blocked by its creature ID.
            replacement=Creature(0x40000002,'Rat',unreachable,health=30)
            del w.creatures[first.id]
            w.creatures[replacement.id]=replacement

            actions=a.step(2)

            self.assertNotEqual(actions,[b'\xbe'])
            self.assertTrue(actions)
            self.assertNotIn(replacement,a.prey())

    def test_unreachable_prey_moving_within_view_does_not_restart_cancel_loop(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            rat=Creature(0x40000001,'Rat',Position(106,100,7),health=30)
            w.creatures[rat.id]=rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            initial=a.step(1)
            self.assertTrue(any(packet[0] in (0x65,0x66,0x67,0x68) for packet in initial))
            rat.position=Position(105,100,7)

            actions=a.step(2)

            self.assertNotEqual(actions,[b'\xbe'])
            self.assertNotIn(rat,a.prey())

    def test_pruned_unreachable_prey_does_not_crash_controller(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            rat=Creature(0x40000001,'Rat',Position(106,100,7),health=30)
            w.creatures[rat.id]=rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a._mark_unreachable_prey(rat,15)

            w.position=Position(200,200,7)
            w.prune()

            self.assertIsNone(rat.position)
            self.assertEqual(a.prey(),[])
            self.assertNotIn(rat.id,a.unreachable_prey)

    def test_new_unreachable_spawns_share_position_backoff(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            blocked=Position(106,100,7)
            first=Creature(0x40000001,'Rat',blocked,health=30)
            w.creatures[first.id]=first
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            monotonic=[100.0]

            with patch('tools.autonomous_players.behaviour.time.monotonic',
                       side_effect=lambda:monotonic[0]):
                a._mark_unreachable_prey(first,15)
                del w.creatures[first.id]
                replacement=Creature(0x40000002,'Rat',blocked,health=30)
                w.creatures[replacement.id]=replacement
                monotonic[0]=115.0
                a.prey()  # The first tile cooldown expired; the next spawn retries it.
                a._mark_unreachable_prey(replacement,15)

                self.assertEqual(a.unreachable_prey_positions[blocked],145.0)

    def test_observed_damage_resets_attack_stall_timer(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            rat=Creature(0x40000001,'Rat',Position(101,100,7),health=30)
            w.creatures[rat.id]=rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            a.step(1)
            rat.health=20
            actions=a.step(13)

            self.assertEqual(actions[-1][0],0xa1)
            self.assertEqual(a.target,rat.id)
            self.assertNotIn(rat.id,a.unreachable_prey)

    def test_late_damage_releases_prey_from_attack_stall_cooldown(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            rat=Creature(0x40000001,'Rat',Position(101,100,7),health=30)
            w.creatures[rat.id]=rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            a.step(1)
            self.assertEqual(a.step(13),[b'\xbe'])
            self.assertIn(rat.id,a.unreachable_prey)

            rat.health=20  # Delayed server health update after timeout cancellation.
            self.assertIn(rat,a.prey())
            actions=a.step(14)
            self.assertEqual(actions[-1][0],0xa1)
            self.assertEqual(a.target,rat.id)

    def test_attack_stall_cooldown_expires_on_monotonic_clock(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            rat=Creature(0x40000001,'Rat',Position(101,100,7),health=30)
            w.creatures[rat.id]=rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            monotonic=[100.0]

            with patch('tools.autonomous_players.behaviour.time.monotonic',
                       side_effect=lambda:monotonic[0]):
                a.step(1)
                self.assertEqual(a.step(13),[b'\xbe'])
                self.assertEqual(a.prey(),[])
                monotonic[0]=129.9
                self.assertEqual(a.prey(),[])
                monotonic[0]=130.0
                self.assertEqual(a.prey(),[rat])
                self.assertEqual(a.step(14)[-1][0],0xa1)

    def test_repeated_attack_stalls_increase_cooldown_until_prey_changes(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            rat=Creature(0x40000001,'Rat',Position(101,100,7),health=30)
            w.creatures[rat.id]=rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            monotonic=[100.0]

            with patch('tools.autonomous_players.behaviour.time.monotonic',
                       side_effect=lambda:monotonic[0]):
                a.step(1)
                self.assertEqual(a.step(13),[b'\xbe'])
                monotonic[0]=130.0
                self.assertEqual(a.step(14)[-1][0],0xa1)
                self.assertEqual(a.step(26),[b'\xbe'])
                monotonic[0]=160.0
                self.assertEqual(a.prey(),[])
                monotonic[0]=189.9
                self.assertEqual(a.prey(),[])
                monotonic[0]=190.0
                self.assertEqual(a.prey(),[rat])

                rat.health=20
                self.assertEqual(a.prey(),[rat])
                self.assertNotIn(rat.id,a.unreachable_prey_failures)

    def test_exploration_tries_reachable_nearby_goal_before_distant_disconnected_tiles(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            w.tiles={Position(100,100,7):[Thing(102)],
                     Position(100,101,7):[Thing(102)],
                     Position(100,102,7):[Thing(102)]}
            for x in range(110,118):
                for y in range(110,118):
                    w.tiles[Position(x,y,7)]=[Thing(102)]
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertEqual(a.step(1),[b'\x67'])

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
            self.assertEqual(outputs[1],[b'\x66'])

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

    def test_only_new_same_type_corpse_is_claimed_after_own_kill(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();tile=Position(101,100,7)
            w.tiles[tile].append(Thing(3994))
            rat=Creature(0x40000001,'Rat',tile)
            w.creatures[rat.id]=rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))

            self.assertTrue(any(packet[0]==0xa1 for packet in a.step(1)))
            rat.position=None
            w.stats.experience=5
            a.observe([Event('stats',w.stats)],2)

            self.assertNotIn((tile,3994),a.allowed_corpses)
            w.tiles[tile].append(Thing(3994))
            a.observe([Event('tile',tile)],2.1)

            self.assertIn((tile,3994),a.allowed_corpses)

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

    def test_cancelled_living_target_cannot_claim_another_same_tile_corpse(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();tile=Position(101,100,7)
            first=Creature(0x40000001,'Rat',tile)
            w.creatures[first.id]=first
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.strategy,a.next_strategy='hunt',10
            a.step(1)
            self.assertEqual(a.target,first.id)

            a.observe([Event('cancel_attack')],2)
            second=Creature(0x40000002,'Rat',tile)
            second.position=None
            w.creatures[second.id]=second
            w.stats.experience=5
            w.tiles[tile].append(Thing(3994))
            a.observe([Event('stats',w.stats)],2.1)

            self.assertNotIn((tile,3994),a.allowed_corpses)

    def test_xp_before_target_removal_correlates_later_corpse_to_victim(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();tile=Position(101,100,7)
            rat=Creature(0x40000001,'Rat',tile)
            w.creatures[rat.id]=rat
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            a.step(1)
            a.observe([],1)

            w.stats.experience=5
            a.observe([Event('stats',w.stats)],2)
            self.assertNotIn((tile,3994),a.allowed_corpses)

            rat.position=None
            a.observe([Event('tile',tile)],2.2)
            w.tiles[tile].append(Thing(3994))
            a.observe([Event('tile',tile)],2.3)

            self.assertIn((tile,3994),a.allowed_corpses)

    def test_unrelated_world_updates_do_not_extend_attack_xp_correlation(self):
        with tempfile.TemporaryDirectory() as d,Store(Path(d)/'s.db') as store:
            world=self.world()
            rat=Creature(0x40000001,'Rat',Position(101,100,7))
            world.creatures[rat.id]=rat
            agent=Agent('Sim One',world,ITEMS,Policy(store,'Sim One',random.Random(7)))
            agent.step(1)
            agent.observe([Event('creature',rat.id)],20)
            rat.position=None
            world.stats.experience=5
            world.tiles[Position(101,100,7)].append(Thing(3994))

            agent.observe([Event('stats',world.stats)],21)

            self.assertNotIn((Position(101,100,7),3994),agent.allowed_corpses)


    def test_food_in_inventory_slot_is_consumed(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world();w.inventory[5]=Thing(3600)
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            self.assertEqual(a.step(1)[0][0],0x82)

    def test_food_ignores_unowned_open_corpse_but_uses_owned_bag(self):
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'s.db') as store:
            w=self.world()
            a=Agent('Sim One',w,ITEMS,Policy(store,'Sim One',random.Random(7)))
            w.containers[1]=Container(1,3994,'dead rat',10,False,[Thing(3600)])

            self.assertIsNone(next(a.food(),None))

            w.containers[0]=Container(0,2853,'bag',10,False,[])
            w.containers[2]=Container(2,2853,'bag',10,True,[Thing(3600)])
            self.assertEqual(next(a.food(),None),(Position(65535,66,0),3600,0))


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
