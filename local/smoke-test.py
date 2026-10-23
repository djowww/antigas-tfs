"""Verify real local login, advertised loopback address, map and movement."""
import asyncio
from pathlib import Path
import socket
import struct
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.autonomous_players.wire import Writer, Reader, rsa_block, FrameCodec, LoginCredentials
from tools.autonomous_players.runtime import Session
from tools.autonomous_players.protocol import Decoder
from tools.autonomous_players.definitions import load_items
from tools.autonomous_players.navigation import DIRECTIONS, walkable

def read_exact(sock, length):
    data = b''
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise RuntimeError('Login connection closed')
        data += chunk
    return data

def check_list(modulus):
    key = (1234567, 2345678, 3456789, 4567890)
    plain = Writer().u8(0)
    for value in key:
        plain.u32(value)
    plain.u32(1).string('local123').u16(0)
    packet = Writer().u8(1).u16(11).u16(772).raw(bytes(12)).string('Antigas-26').raw(rsa_block(plain.data, modulus)).data
    with socket.create_connection(('127.0.0.1', 17173), timeout=15) as sock:
        sock.sendall(Writer().u16(len(packet)).raw(packet).data)
        length = struct.unpack('<H', read_exact(sock, 2))[0]
        payload = FrameCodec(key).feed(struct.pack('<H', length) + read_exact(sock, length))[0]
    r = Reader(payload)
    op = r.u8()
    if op == 0x14:
        r.string()
        op = r.u8()
    assert op == 0x64 and r.u8() == 1, 'Expected the clean demo account character list'
    assert r.string() == 'Local Adventurer'
    world = r.string()
    assert r.take(4) == socket.inet_aton('127.0.0.1'), 'Server advertised a non-local address'
    assert r.u16() == 17174
    print('LOGIN_LIST_OK', world, '127.0.0.1:17174')

async def check_game(modulus):
    decoder = Decoder(load_items(Path('data/items/items.srv')))
    s = await Session.connect('127.0.0.1', 17174, LoginCredentials(1, 'Local Adventurer', 'local123'), modulus, decoder)
    task = asyncio.create_task(s.receive())
    try:
        for _ in range(100):
            if task.done():
                await task
            if s.world.valid and s.world.position and s.world.stats.health > 0:
                break
            await asyncio.sleep(.1)
        else:
            raise RuntimeError('No valid game map/stats after login')
        start = s.world.position
        for (dx, dy), op in DIRECTIONS.items():
            if walkable(s.world, start.shift(dx, dy), decoder.items):
                assert await s.send(bytes([op]))
                break
        else:
            raise RuntimeError('Demo character has no walkable neighbour')
        for _ in range(50):
            if s.world.position != start:
                break
            await asyncio.sleep(.1)
        assert s.world.position != start, 'Server did not confirm movement'
        print('GAME_LOGIN_MAP_MOVEMENT_OK', start, s.world.position, 'HP', s.world.stats.health)
    finally:
        await s.close()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

if __name__ == '__main__':
    modulus = int(subprocess.check_output(['docker', 'compose', 'exec', '-T', 'server', 'cat', '/local-state/public-modulus.txt']))
    check_list(modulus)
    asyncio.run(check_game(modulus))
