import unittest
from pathlib import Path

from tools.autonomous_players.definitions import load_items
from tools.autonomous_players.wire import Writer, ProtocolError
from tools.autonomous_players.world import World, Position, Creature, Thing
from tools.autonomous_players.protocol import Decoder, attack, say, use_item

ITEMS = load_items(Path(__file__).resolve().parents[2] / 'data/items/items.srv')


def pos(w, x=100, y=100, z=7):
    return w.u16(x).u16(y).u8(z)


def creature(w, cid, name):
    return (w.u16(0x61).u32(0).u32(cid).string(name).u8(100).u8(0)
            .u16(128).raw(bytes(5)).u16(0).u8(0).u8(0).u16(220).raw(bytes(3)))


class DecoderTests(unittest.TestCase):
    def setUp(self):
        self.w = World()
        self.d = Decoder(ITEMS)

    def test_inventory_stats_and_extensions(self):
        packet = Writer().u8(0x78).u8(3).u16(2853).u8(0x32).u8(127).string('P|I|3|0')
        packet.u8(0xa0).u16(150).u16(150).u16(400).u32(100).u16(2).u8(1).u16(0).u16(0).raw(bytes([0, 0, 100]))
        events = self.d.feed_payload(packet.data, self.w)
        self.assertEqual(self.w.inventory[3].id, 2853)
        self.assertEqual((self.w.stats.experience, self.w.stats.level), (100, 2))
        self.assertEqual(events[-1].kind, 'stats')

    def test_map_skips_across_floor_boundaries(self):
        # Entire 18x14x8 view absent: seven 256-position skips and a final 224.
        packet = pos(Writer().u8(0x64)).raw(b'\xff\xff'*7 + b'\xdf\xff')
        self.d.feed_payload(packet.data, self.w)
        self.assertEqual(self.w.position, Position(100, 100, 7))
        self.assertEqual(len(self.w.tiles), 2016)
        self.assertTrue(all(not t for t in self.w.tiles.values()))

    def test_creature_movement_and_no_human_attack(self):
        self.w.self_id = 0x10000001
        p = Position(100, 100, 7)
        packet = pos(Writer().u8(0x6a)).u8(0)
        creature(packet, 0x10000002, 'Human')
        self.d.feed_payload(packet.data, self.w)
        human = self.w.creatures[0x10000002]
        self.assertEqual(human.kind, 'player')
        with self.assertRaises(ValueError):
            attack(human)
        monster_packet = pos(Writer().u8(0x6a), 101).u8(0)
        creature(monster_packet, 0x40000001, 'Rat')
        self.d.feed_payload(monster_packet.data, self.w)
        self.assertEqual(attack(self.w.creatures[0x40000001]), b'\xa1\x01\x00\x00\x40')
        movement = pos(Writer().u8(0x6d), 101).u8(0)
        pos(movement, 102)
        self.d.feed_payload(movement.data, self.w)
        self.assertEqual(self.w.creatures[0x40000001].position, Position(102, 100, 7))
        self.assertEqual(self.w.creatures[0x10000002].position, p)

    def test_server_known_creature_update_survives_local_viewport_prune(self):
        cid=0x40000003
        self.w.position=Position(100,100,7)
        self.w.creatures[cid]=Creature(cid,'Cave Rat',Position(500,500,7))
        self.w.tiles[Position(500,500,7)]=[Thing(0,creature_id=cid)]
        self.w.prune()
        self.assertIsNone(self.w.creatures[cid].position)

        packet=pos(Writer().u8(0x69),101,100,7).u16(0)
        packet.u16(0x62).u32(cid).u8(80).u8(1).u16(128).raw(bytes(5))
        packet.u16(0).u8(0).u8(0).u16(220).raw(bytes(3)).u16(0xff00)
        self.d.feed_payload(packet.data,self.w)

        self.assertEqual(self.w.creatures[cid].health,80)
        self.assertEqual(self.w.creatures[cid].position,Position(101,100,7))

    def test_server_eviction_packet_removes_retained_known_creature(self):
        old_id,new_id=0x40000003,0x40000004
        self.w.position=Position(100,100,7)
        self.w.creatures[old_id]=Creature(old_id,'Rat',Position(500,500,7))
        self.w.tiles[Position(500,500,7)]=[Thing(0,creature_id=old_id)]
        self.w.prune()
        packet=pos(Writer().u8(0x69),100,100,7).u16(0)
        packet.u16(0x61).u32(old_id).u32(new_id).string('Rat').u8(100).u8(0)
        packet.u16(128).raw(bytes(5)).u16(0).u8(0).u8(0).u16(220).raw(bytes(3)).u16(0xff00)

        self.d.feed_payload(packet.data,self.w)

        self.assertNotIn(old_id,self.w.creatures)
        self.assertEqual(self.w.creatures[new_id].name,'Rat')

    def test_unknown_and_truncated_packets_invalidate_world(self):
        for packet in (b'\x01', b'\xa0\x01'):
            world = World()
            with self.assertRaises(ProtocolError):
                self.d.feed_payload(packet, world)
            self.assertFalse(world.valid)

    def test_container_slot_updates(self):
        p = Writer().u8(0x6e).u8(0).u16(2853).string('bag').u8(20).u8(0).u8(2).u16(3031).u8(7).u16(3585).u8(2)
        p.u8(0x71).u8(0).u8(0).u16(3031).u8(8).u8(0x72).u8(0).u8(1)
        events=self.d.feed_payload(p.data, self.w)
        self.assertEqual((events[0].kind,events[0].data),('container_open',(0,2853)))
        self.assertEqual(len(self.w.containers[0].items), 1)
        self.assertEqual(self.w.containers[0].items[0].count, 8)

    def test_first_login_outfit_window(self):
        p = Writer().u8(0xc8).u16(128).raw(bytes(5)).u16(0).u8(1).u16(128).string('Citizen').u8(0).u8(0)
        self.assertEqual(self.d.feed_payload(p.data,self.w)[0].kind,'outfit_window')


if __name__ == '__main__':
    unittest.main()
