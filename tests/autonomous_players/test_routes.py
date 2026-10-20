import unittest
import struct
import tempfile
from pathlib import Path
from tools.autonomous_players.routes import RouteGraph
from tools.autonomous_players.routes import compile_region
from tools.autonomous_players.definitions import load_items
from tools.autonomous_players.world import Position


class RouteTests(unittest.TestCase):
    def test_runtime_route_audit_requires_outbound_and_return_paths(self):
        import json
        import tempfile
        from tools.autonomous_players.route_audit import audit_runtime_routes

        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            runtime=root/'runtime.json'
            route_file=root/'routes.json'
            runtime.write_text(json.dumps({'hunting_points':[[12,10,8],[20,10,8]]}))
            route_file.write_text(json.dumps({'version':1,'tiles':[
                [10,10,7],[10,11,7],[11,10,7,11,10,8],[11,10,8],
                [12,10,8],[12,11,8],[11,11,8,11,11,7],[11,11,7],
                [20,10,8],
            ]}))

            result=audit_runtime_routes(runtime,route_file,[Position(10,10,7)])

        self.assertEqual(result['total'],2)
        self.assertEqual(result['reachable'],1)
        self.assertEqual(result['unreachable'][0]['target'],[20,10,8])
        self.assertTrue(result['routes'][0]['outbound'])
        self.assertTrue(result['routes'][0]['return'])

    def test_runtime_route_audit_rejects_missing_or_duplicate_targets(self):
        import json
        import tempfile
        from tools.autonomous_players.route_audit import audit_runtime_routes

        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            runtime=root/'runtime.json'
            route_file=root/'routes.json'
            route_file.write_text(json.dumps({'version':1,'tiles':[[10,10,7]]}))
            runtime.write_text(json.dumps({'hunting_points':[]}))
            with self.assertRaisesRegex(ValueError,'no hunting_points'):
                audit_runtime_routes(runtime,route_file,[Position(10,10,7)])
            runtime.write_text(json.dumps({'hunting_points':[[10,10,7],[10,10,7]]}))
            with self.assertRaisesRegex(ValueError,'duplicate hunting point'):
                audit_runtime_routes(runtime,route_file,[Position(10,10,7)])

    def test_runtime_route_audit_accepts_source_already_at_hunting_point(self):
        import json
        import tempfile
        from tools.autonomous_players.route_audit import audit_runtime_routes

        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            runtime=root/'runtime.json'
            routes=root/'routes.json'
            runtime.write_text(json.dumps({'hunting_points':[[10,10,7]]}))
            routes.write_text(json.dumps({'version':1,'tiles':[[10,10,7]]}))
            result=audit_runtime_routes(runtime,routes,[Position(10,10,7)])

        self.assertEqual(result['reachable'],1)

    def test_stairs_return_step_tile_and_actual_destination(self):
        start,stairs,end = Position(10,10,7),Position(11,10,7),Position(12,10,6)
        graph = RouteGraph({start:None,stairs:end,end:None})
        self.assertEqual(graph.next_step(start,end),stairs)
        self.assertIsNone(graph.next_step(end,start))

    def test_unknown_target_and_walls_have_no_route(self):
        a,b,c = Position(10,10,7),Position(11,10,7),Position(12,10,7)
        graph = RouteGraph({a:None,c:None})
        self.assertIsNone(graph.next_step(a,c))
        self.assertIsNone(graph.next_step(a,b))

    def test_route_avoids_a_tile_occupied_by_another_player(self):
        start = Position(10,10,7)
        occupied = Position(11,10,7)
        goal = Position(12,10,7)
        detour = {
            start:None, occupied:None, goal:None,
            Position(10,11,7):None, Position(11,11,7):None,
            Position(12,11,7):None,
        }
        graph = RouteGraph(detour)
        self.assertEqual(graph.next_step(start,goal),occupied)
        self.assertEqual(graph.next_step(start,goal,blocked={occupied}),Position(10,11,7))

    def test_unrelated_moving_occupants_reuse_cached_static_route(self):
        from unittest.mock import patch
        start,step,goal = (Position(x,10,7) for x in (10,11,12))
        away = Position(20,20,7)
        graph = RouteGraph({start:None,step:None,goal:None,away:None})
        self.assertEqual(graph.next_step(start,goal),step)
        with patch('tools.autonomous_players.routes.heapq.heappop',
                   side_effect=AssertionError('unrelated occupant triggered graph search')):
            self.assertEqual(graph.next_step(start,goal,blocked={away}),step)

    def test_cached_route_still_detours_around_distant_occupant(self):
        start = Position(10,10,7)
        first = Position(11,10,7)
        occupied = Position(12,10,7)
        goal = Position(13,10,7)
        graph = RouteGraph({tile:None for tile in (
            start,first,occupied,goal,Position(10,11,7),Position(11,11,7),
            Position(12,11,7),Position(13,11,7))})
        self.assertEqual(graph.next_step(start,goal),first)
        self.assertEqual(graph.next_step(start,goal,blocked={occupied}),Position(10,11,7))

    def test_chained_transitions_and_cycles(self):
        a,b,c,d = Position(10,10,7),Position(11,10,7),Position(11,10,6),Position(11,11,5)
        self.assertEqual(RouteGraph({a:None,b:c,c:d,d:None}).next_step(a,d),b)
        self.assertIsNone(RouteGraph({a:None,b:c,c:b,d:None}).next_step(a,d))

    def test_escaped_map_unknown_items_and_house_exclusion(self):
        def node(kind,props=b'',children=b''):
            escaped=b''.join(b'\xfd'+bytes([v]) if v>=253 else bytes([v]) for v in props)
            return b'\xfe'+bytes([kind])+escaped+children+b'\xff'
        tiles = node(5,bytes([0,0,9])+struct.pack('<H',102),node(6,struct.pack('<H',2853),node(6,struct.pack('<H',101))))
        tiles += node(5,bytes([1,0,9])+struct.pack('<H',102),node(6,struct.pack('<H',65000)))
        tiles += node(14,bytes([2,0])+struct.pack('<I',7)+bytes([9])+struct.pack('<H',102))
        tiles += node(5,bytes([253,0,9])+struct.pack('<H',102))
        raw=bytes(4)+node(0,b'',node(2,b'',node(4,struct.pack('<HHB',250,250,7),tiles)))
        root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'tiny.otbm';p.write_bytes(raw)
            graph=compile_region(p,load_items(root/'data/items/items.srv'),root/'data/movements/scripts/others/floorchange.lua',(249,249,504,251))
            self.assertIn(Position(250,250,7),graph.tiles)
            self.assertIn(Position(503,250,7),graph.tiles)
            self.assertNotIn(Position(251,250,7),graph.tiles)
            self.assertNotIn(Position(252,250,7),graph.tiles)

    def test_following_cached_route_does_not_search_graph_again(self):
        from unittest.mock import patch
        a,b,c=Position(10,10,7),Position(11,10,7),Position(12,10,7)
        g=RouteGraph({a:None,b:None,c:None})
        self.assertEqual(g.next_step(a,c),b)
        with patch('tools.autonomous_players.routes.heapq.heappop',side_effect=AssertionError('duplicate graph search')):
            self.assertEqual(g.next_step(b,c),c)

    def test_unreachable_route_result_is_cached(self):
        from unittest.mock import patch
        a,b=Position(10,10,7),Position(12,10,7)
        g=RouteGraph({a:None,b:None})
        self.assertIsNone(g.next_step(a,b))
        with patch('tools.autonomous_players.routes.heapq.heappop',
                   side_effect=AssertionError('repeated unreachable graph search')):
            self.assertIsNone(g.next_step(a,b))

    def test_low_node_budget_failure_does_not_poison_full_route_search(self):
        a,b,c=Position(10,10,7),Position(11,10,7),Position(12,10,7)
        g=RouteGraph({a:None,b:None,c:None})
        self.assertIsNone(g.next_step(a,c,max_nodes=1))
        self.assertEqual(g.next_step(a,c),b)
