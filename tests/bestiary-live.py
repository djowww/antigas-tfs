"""Isolated staging smoke test with disposable, unprivileged characters."""
import hashlib
import json
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import sys
import time

from staging_safety import require_staging_target
from load_test_protocol import Client, string

STAGING_DB_NAME = None
STAGING_GAME_PORT = None


def sql(query):
    return subprocess.check_output(['mariadb', '--protocol=socket', '-N', '-B', STAGING_DB_NAME], input=query, text=True, timeout=10).strip()


class Probe(Client):
    def __init__(self, account, password, name):
        self.key = struct.unpack('<IIII', secrets.token_bytes(16))
        self.sock = socket.create_connection(('127.0.0.1', STAGING_GAME_PORT), timeout=5)
        modulus = int(json.loads(Path('/opt/antigas-security-v26/rsa-public.json').read_text())['modulus'])
        plain = b'\0' + struct.pack('<IIII', *self.key) + b'\0' + struct.pack('<I', account) + string(name) + string(password)
        encrypted = pow(int.from_bytes(plain.ljust(128, b'\0'), 'big'), 65537, modulus).to_bytes(128, 'big')
        packet = b'\x0a' + struct.pack('<HH', 11, 772) + encrypted
        self.sock.sendall(struct.pack('<H', len(packet)) + packet)
        self.buffer = b''
        initial = self.collect(1)
        assert b'Welcome to Antigas' in initial, 'Game login failed'

    def progress(self):
        request = json.dumps(dict(action='getProgress', monsters=['rat', 'dragon', 'not-a-monster']))
        self.send(b'\x32\x7c' + string(request))
        data = self.collect(1)
        for offset in range(len(data) - 4):
            if data[offset:offset + 2] != b'\x32\x7c':
                continue
            size = struct.unpack_from('<H', data, offset + 2)[0]
            try:
                value = json.loads(data[offset + 4:offset + 4 + size])
            except (ValueError, UnicodeDecodeError):
                continue
            if value.get('action') == 'progress':
                return value['data']
        raise AssertionError('No Bestiary response')

def main():
    global STAGING_DB_NAME, STAGING_GAME_PORT
    STAGING_DB_NAME, STAGING_GAME_PORT = require_staging_target()
    accounts, players, clients = [], [], []
    key_hash = 5381
    for byte in b'rat':
        key_hash = (key_hash * 33 + byte) % 600000000
    rat_key = 1500000000 + key_hash
    marker = 'bestiaryprobe_' + secrets.token_hex(8)
    try:
        for index in range(2):
            account = 900000000 + secrets.randbelow(90000000)
            assert sql(f'SELECT COUNT(*) FROM accounts WHERE id={account}') == '0'
            password = secrets.token_hex(16)
            name = 'Bestiary Probe ' + ''.join(secrets.choice('abcdefghijklmnpqrstuvwxyz') for _ in range(8))
            email = f'{marker}_{index}@test.invalid'
            sql(f"INSERT INTO accounts(id,email,password,type) VALUES({account},'{email}','{hashlib.sha1(password.encode()).hexdigest()}',1)")
            accounts.append((account, email))
            sql(f"INSERT INTO players(name,account_id,conditions,comment,cap,town_id,posx,posy,posz,lastlogin) VALUES('{name}',{account},'','',400,1,32097,32219,7,1)")
            player = int(sql(f"SELECT id FROM players WHERE account_id={account} AND name='{name}'"))
            players.append(player)
            if index == 0:
                sql(f'INSERT INTO player_storage(player_id,`key`,`value`) VALUES({player},{rat_key},42)')
            client = Probe(account, password, name)
            clients.append(client)
            progress = client.progress()
            assert progress['rat'] == (42 if index == 0 else 0), progress
            assert progress['dragon'] == 0 and 'not-a-monster' not in progress
            if index == 0:
                reconnect = account, password, name
        assert sql('SELECT COUNT(*) FROM players_online WHERE player_id IN (' + ','.join(map(str, players)) + ')') == '2'
        print('PASS live: two ordinary players online with independent Bestiary progress', flush=True)
        for client in clients:
            client.close()
        clients.clear()
        client = Probe(*reconnect)
        clients.append(client)
        assert client.progress()['rat'] == 42
        print('PASS live: progress survives logout and login', flush=True)
    finally:
        for client in clients:
            try:
                client.close()
            except Exception:
                client.sock.close()
        time.sleep(2)
        for player in players:
            assert sql(f'SELECT COUNT(*) FROM players_online WHERE player_id={player}') == '0', 'Probe still online; keep data for cleanup'
        for account, email in accounts:
            assert sql(f"SELECT COUNT(*) FROM accounts WHERE id={account} AND email='{email}'") == '1'
            sql(f'DELETE FROM players WHERE account_id={account}')
            sql(f"DELETE FROM accounts WHERE id={account} AND email='{email}'")
        print('Temporary test accounts and characters removed', flush=True)

if __name__ == "__main__":
    main()
