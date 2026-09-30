"""Bounded wire regression: one disposable ordinary player; no reward mutation.

Run only against an approved isolated staging database and loopback staging port.
Set ANTIGAS_ALLOW_STAGING_MUTATIONS=1, TFS_DB_NAME to a *_test/*_qa/*_staging database, and ANTIGAS_STAGING_GAME_PORT to 7176 or 7186.
"""

if not __debug__:
    raise SystemExit('Python optimization (-O) disables validation assertions; refusing to run this tool.')

import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import time

from load_test_protocol import Client, string
from staging_safety import require_staging_target, rsa_public_modulus


def sql(query):
    return subprocess.check_output(
        ['mariadb', '--protocol=socket', '--user=root', '-N', '-B', os.environ['TFS_DB_NAME']],
        input=query, text=True, timeout=10).strip()


class Probe(Client):
    def __init__(self, account, password, name):
        self.key = struct.unpack('<IIII', secrets.token_bytes(16))
        self.sock = socket.create_connection(('127.0.0.1', int(os.environ['ANTIGAS_STAGING_GAME_PORT'])), timeout=5)
        modulus = rsa_public_modulus()
        plain = b'\0' + struct.pack('<IIII', *self.key) + b'\0' + struct.pack('<I', account) + string(name) + string(password)
        encrypted = pow(int.from_bytes(plain.ljust(128, b'\0'), 'big'), 65537, modulus).to_bytes(128, 'big')
        packet = b'\x0a' + struct.pack('<HH', 11, 772) + encrypted
        self.sock.sendall(struct.pack('<H', len(packet)) + packet)
        self.buffer = b''

    def progress(self, action='getProgress', fresh=True):
        self.send(b'\x32\x7e' + string(json.dumps({'action': action})))
        raw = self.collect(2)
        pages, payloads, maximum, snapshot = {}, {}, 0, None
        for offset in range(len(raw) - 4):
            if raw[offset:offset + 2] != b'\x32\x7e':
                continue
            size = struct.unpack_from('<H', raw, offset + 2)[0]
            try:
                payload = json.loads(raw[offset + 4:offset + 4 + size])
            except (ValueError, UnicodeDecodeError):
                continue
            if payload.get('action') != 'progress':
                continue
            assert size <= 7000, 'Achievement page exceeds the wire budget'
            assert snapshot in (None, payload['snapshotId']), 'Mixed snapshots'
            snapshot = payload['snapshotId']
            assert payload['pages'] == 5, payload
            assert payload['page'] not in pages, 'Duplicate response page'
            pages[payload['page']] = payload['entries']
            payloads[payload['page']] = payload
            maximum = max(maximum, size)
        assert sorted(pages) == [1, 2, 3, 4, 5], f'Incomplete catalogue: {sorted(pages)}'
        entries = [entry for page in sorted(pages) for entry in pages[page]]
        assert len(entries) == len({entry['id'] for entry in entries}) == 60
        assert all(entry['target'] > 0 and entry['reward'] for entry in entries)
        if fresh:
            assert all(not entry['completed'] and not entry.get('ready', False) for entry in entries)
        assert {'steps_1', 'steps_5', 'monsterKills_5', 'deaths_5', 'pvpKills_5', 'level_5', 'skill_7_5'} <= {entry['id'] for entry in entries}
        capture = os.environ.get('ANTIGAS_ACHIEVEMENTS_CAPTURE')
        if capture:
            Path(capture).write_text(json.dumps([payloads[page] for page in sorted(payloads)]), encoding='utf-8')
        print(f'PASS live Achievements: 60 objectives, 5 complete pages, largest payload {maximum} bytes', flush=True)
        return {entry['id']: entry for entry in entries}


def main():
    require_staging_target()
    account, player, probe = None, None, None
    marker = 'achievementsprobe_' + secrets.token_hex(8) + '@test.invalid'
    try:
        account = 900000000 + secrets.randbelow(90000000)
        assert sql(f'SELECT COUNT(*) FROM accounts WHERE id={account}') == '0'
        password = secrets.token_hex(16)
        name = 'Achievement Probe ' + ''.join(secrets.choice('abcdefghijklmnpqrstuvwxyz') for _ in range(8))
        sql(f"INSERT INTO accounts(id,email,password,type) VALUES({account},'{marker}','{hashlib.sha1(password.encode()).hexdigest()}',1)")
        sql(f"INSERT INTO players(name,account_id,conditions,comment,cap,town_id,posx,posy,posz,lastlogin) VALUES('{name}',{account},'','',400,1,32097,32219,7,1)")
        player = int(sql(f"SELECT id FROM players WHERE account_id={account} AND name='{name}'"))
        probe = Probe(account, password, name)
        assert b'Welcome to Antigas' in probe.collect(1), 'Game login failed'
        probe.progress()
    finally:
        if probe:
            try:
                probe.send(b'\x14')
                probe.collect(0.5)
            finally:
                probe.sock.close()
        if player:
            for _ in range(20):
                if sql(f'SELECT COUNT(*) FROM players_online WHERE player_id={player}') == '0':
                    break
                time.sleep(0.25)
            assert sql(f'SELECT COUNT(*) FROM players_online WHERE player_id={player}') == '0', 'Probe still online; keep its data for cleanup'
        if account and sql(f"SELECT COUNT(*) FROM accounts WHERE id={account} AND email='{marker}'") == '1':
            sql(f'DELETE FROM players WHERE account_id={account}')
            sql(f"DELETE FROM accounts WHERE id={account} AND email='{marker}'")
            print('Disposable account and character removed.', flush=True)


if __name__ == '__main__':
    main()
