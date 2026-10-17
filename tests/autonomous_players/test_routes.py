import unittest
import struct
import tempfile
from pathlib import Path
from tools.autonomous_players.routes import RouteGraph
from tools.autonomous_players.routes import compile_region
from tools.autonomous_players.definitions import load_items
from tools.autonomous_players.world import Position


class RouteTests(unittest.TestCase):
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
