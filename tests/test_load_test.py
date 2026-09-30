"""Offline harness regressions. Run: python3 tests/test_load_test.py"""
import importlib.util
import json
from pathlib import Path
import socket
import struct
import unittest
from unittest.mock import Mock, patch

from load_test_protocol import Client, crypt, string

spec = importlib.util.spec_from_file_location("load_test_50", Path(__file__).with_name("load-test-50.py"))
harness = importlib.util.module_from_spec(spec)
spec.loader.exec_module(harness)


class SocketStub:
    def __init__(self, chunks=()):
        self.chunks = list(chunks)
        self.sent = []

    def sendall(self, data):
        self.sent.append(data)

    def settimeout(self, seconds):
        pass

    def recv(self, size):
        if self.chunks:
            return self.chunks.pop(0)
        raise socket.timeout()


def transport(sock):
    client = Client()
    client.sock, client.key, client.buffer = sock, (1, 2, 3, 4), b""
    return client


class MarketStub:
    def __init__(self, ok):
        self.ok, self.parts = ok, []

    def send(self, data):
        request = json.loads(data[4:])
        response = {"action": "message", "data": {"requestId": request["requestId"], "ok": self.ok}}
        packet = b"\x32\xca" + string(json.dumps(response))
        self.parts = [packet[:9], packet[9:]]

    def collect(self, seconds):
        return self.parts.pop(0) if self.parts else b""


class LoadTestRegression(unittest.TestCase):
    def test_keepalive_drains_world_roles_without_stealing_market_receipts(self):
        for role in ('hunter', 'chat', 'walker', 'seller', 'buyer'):
            with self.subTest(role=role):
                client = Mock(record={'role': role})
                stop = Mock()
                stop.is_set.side_effect = [False, True]
                harness.StageClient.keepalive(client, stop)
                client.send.assert_called_once_with(b'\x1e')
                if role in ('hunter', 'chat', 'walker'):
                    client.collect.assert_called_once_with(0.05)
                else:
                    client.collect.assert_not_called()

    def test_xtea_roundtrip(self):
        plain = bytes(range(32))
        key = (1, 2, 3, 4)
        self.assertEqual(crypt(crypt(plain, key), key, True), plain)

    def test_fragmented_frames_and_ping(self):
        sender = transport(SocketStub())
        sender.send(b"first payload")
        sender.send(b"\x1d")
        sender.send(b"last payload")
        wire = b"".join(sender.sock.sent)
        receiver = transport(SocketStub([wire[:1], wire[1:5], wire[5:]]))
        self.assertEqual(receiver.collect(), b"first payload\x1dlast payload")
        self.assertEqual(receiver.buffer, b"")
        self.assertEqual(len(receiver.sock.sent), 1)
        pong = transport(SocketStub(receiver.sock.sent))
        self.assertEqual(pong.collect(), b"\x1e")

    def test_hunt_target_case_and_offset(self):
        packet = b"prefix" + struct.pack("<HII", 0x61, 0, 123456) + string("Rat") + b"tail"
        self.assertEqual(harness.find_hunt_target(packet), (123456, "rat"))

    def test_seed_uses_real_backpack_and_two_fish(self):
        queries = []

        def sql(query):
            queries.append(query)
            return "501" if query.startswith("SELECT id") else ""

        with patch.object(harness, "sql", sql), patch.object(harness, "created", []):
            harness.seed_player(10, "seller")
        self.assertTrue(any("501,3,101,2854,1" in query for query in queries))
        self.assertTrue(any("501,101,102,3578,2" in query for query in queries))

    def test_hunter_fixture_survives_capacity_run_without_changing_permissions(self):
        queries = []
        def sql(query):
            queries.append(query)
            return '501' if query.startswith('SELECT id') else ''
        with patch.object(harness, 'sql', sql), patch.object(harness, 'created', []):
            harness.seed_player(9, 'hunter')
        player_insert = next(query for query in queries if query.startswith('INSERT INTO players('))
        self.assertIn("'LoadV37-010',980010,1,8,4200,60000,60000", player_insert)

    def test_market_receipt_fragmentation_and_rejection(self):
        self.assertTrue(harness.market_request(MarketStub(True), "create", {})["data"]["ok"])
        with self.assertRaises(RuntimeError):
            harness.market_request(MarketStub(False), "fill", {})


if __name__ == "__main__":
    unittest.main()
