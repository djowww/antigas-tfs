import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.autonomous_players.wire import Reader, Writer, FrameCodec, ProtocolError, crypt, rsa_block, LoginCredentials
from tools.autonomous_players.definitions import load_items


class WireTests(unittest.TestCase):
    def test_reader_bounds_and_strings(self):
        r = Reader(Writer().u8(7).u16(65535).u32(123456).string('olá').data)
        self.assertEqual((r.u8(), r.u16(), r.u32(), r.string()), (7, 65535, 123456, 'olá'))
        with self.assertRaises(ProtocolError):
            r.u8()
        with self.assertRaises(ProtocolError):
            Reader(b'\xff\xffx').string()
        with self.assertRaises(ValueError):
            Writer().u16(-1)

    def test_xtea_published_zero_vector_and_roundtrip(self):
        self.assertEqual(crypt(bytes(8), (0, 0, 0, 0)).hex(), 'd8d4e9ded91e13f7')
        key = (0x01020304, 8, 19, 0xffffffff)
        data = bytes(range(64))
        self.assertEqual(crypt(crypt(data, key), key, True), data)
        with self.assertRaises(ValueError):
            crypt(b'a', key)

    def test_fragmented_coalesced_frames(self):
        codec = FrameCodec((1, 2, 3, 4))
        encoded = codec.encode(b'hello') + codec.encode(bytes(range(255)))
        found = []
        for byte in encoded:
            found.extend(codec.feed(bytes([byte])))
        self.assertEqual(found, [b'hello', bytes(range(255))])
        self.assertEqual(codec.feed(codec.encode(b'x') + codec.encode(b'y')), [b'x', b'y'])

    def test_bad_frame_poisoning_is_terminal(self):
        codec = FrameCodec((1, 2, 3, 4))
        with self.assertRaises(ProtocolError):
            codec.feed(b'\x07\x00')
        with self.assertRaises(ProtocolError):
            codec.feed(codec.encode(b'ok'))
        codec = FrameCodec((1, 2, 3, 4))
        broken = crypt(b'\xff\xff' + bytes(6), (1, 2, 3, 4))
        with self.assertRaises(ProtocolError):
            codec.feed(b'\x08\x00' + broken)

    def test_rsa_and_secret_repr(self):
        modulus = (1 << 1024) - 109
        block = rsa_block(b'\x00hello', modulus)
        self.assertEqual(len(block), 128)
        self.assertEqual(int.from_bytes(block, 'big'), pow(int.from_bytes(b'\x00hello' + bytes(122), 'big'), 65537, modulus))
        with self.assertRaises(ValueError):
            rsa_block(bytes(129), modulus)
        with self.assertRaises(ValueError):
            rsa_block(b'bad', modulus)
        c = LoginCredentials(123456, 'Sim Tester', 'TOP_SECRET')
        self.assertNotIn('TOP_SECRET', repr(c))

    def test_actual_item_definitions(self):
        items = load_items(ROOT / 'data/items/items.srv')
        self.assertTrue(items[3031].stackable)
        self.assertTrue(items[5130].stackable)
        self.assertTrue(items[2853].container)
        self.assertFalse(items[3270].extra_byte)
        self.assertTrue(any(i.fluid for i in items.values()))
        with self.assertRaises(TypeError):
            items[3031] = items[3270]


if __name__ == '__main__':
    unittest.main()
