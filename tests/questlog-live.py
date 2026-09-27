"""Bounded live Quest Log test; two disposable ordinary players, no reward calls."""
import hashlib
import json
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import sys
import time

sys.path.insert(0, '/opt/antigas-market-v2')
from protocol_test import Client, string

def sql(query):
    return subprocess.check_output(['mariadb', '-N', '-B', 'imperium'], input=query, text=True, timeout=10).strip()

class Probe(Client):
    def __init__(self, account, password, name):
        self.key = struct.unpack('<IIII', secrets.token_bytes(16))
        self.sock = socket.create_connection(('127.0.0.1', 7174), timeout=5)
        modulus = int(json.loads(Path('/opt/antigas-security-v26/rsa-public.json').read_text())['modulus'])
        plain = b'\0' + struct.pack('<IIII', *self.key) + b'\0' + struct.pack('<I', account) + string(name) + string(password)
        encrypted = pow(int.from_bytes(plain.ljust(128, b'\0'), 'big'), 65537, modulus).to_bytes(128, 'big')
        packet = b'\x0a' + struct.pack('<HH', 11, 772) + encrypted
        self.sock.sendall(struct.pack('<H', len(packet)) + packet)
        self.buffer, self.serial = b'', 0
        assert b'Welcome to Antigas' in self.collect(1), 'Game login failed'

    def request(self, data, expect=True):
        self.serial += 1
        data['requestId'] = self.serial
        self.send(b'\x32\x7d' + string(json.dumps(data)))
        raw = self.collect(1.2)
        for offset in range(len(raw) - 4):
            if raw[offset:offset+2] != b'\x32\x7d': continue
            size = struct.unpack_from('<H', raw, offset+2)[0]
            try: value = json.loads(raw[offset+4:offset+4+size])
            except (ValueError, UnicodeDecodeError): continue
            if value.get('requestId') == self.serial:
                assert expect, 'Unauthorized request accepted'
                return value
        assert not expect, 'No Quest Log response'

accounts, players, clients = [], [], []
marker = 'questlogprobe_' + secrets.token_hex(8)
try:
    for index in range(2):
        account = 900000000 + secrets.randbelow(90000000)
        assert sql(f'SELECT COUNT(*) FROM accounts WHERE id={account}') == '0'
        password = secrets.token_hex(16)
        name = 'Quest Probe ' + ''.join(secrets.choice('abcdefghijklmnpqrstuvwxyz') for _ in range(8))
        email = f'{marker}_{index}@test.invalid'
        sql(f"INSERT INTO accounts(id,email,password,type) VALUES({account},'{email}','{hashlib.sha1(password.encode()).hexdigest()}',1)")
        accounts.append((account,email))
        sql(f"INSERT INTO players(name,account_id,conditions,comment,cap,town_id,posx,posy,posz,lastlogin) VALUES('{name}',{account},'','',400,1,32097,32219,7,1)")
        player = int(sql(f"SELECT id FROM players WHERE account_id={account} AND name='{name}'")); players.append(player)
        if index == 0: sql(f'INSERT INTO player_storage(player_id,`key`,`value`) VALUES({player},203,1),({player},293,6)')
        client = Probe(account,password,name); clients.append(client)
        result = client.request(dict(action='list'))
        assert result['journal']==2 and result['total']==(2 if index==0 else 0) and result['pages']==1
        assert len(result['entries'])==(2 if index==0 else 0)
        chest = client.request(dict(action='detail',id='chest-203'))
        ape = client.request(dict(action='detail',id='ape-city'))
        if index==0:
            assert chest['quest']['status']=='completed' and chest['quest']['rewards']==''
            assert ape['quest']['done']==3 and ape['quest']['total']==3
            assert 'hydra' not in json.dumps(ape).lower()
        else:
            assert chest['unavailable'] and ape['unavailable']
            assert 'quest' not in chest and 'quest' not in ape
        assert client.request(dict(action='detail',id='blue-djinn'))['unavailable']
        assert client.request(dict(action='list',query='APE CITY',filter='active'))['matched']==(1 if index==0 else 0)
        if index==0: reconnect=account,password,name
    assert sql('SELECT COUNT(*) FROM players_online WHERE player_id IN ('+','.join(map(str,players))+')')=='2'
    clients[0].request(dict(action='list',playerId=players[1]),expect=False)
    clients[0].request(dict(action='claim',id='chest-203'),expect=False)
    assert clients[0].request(dict(action='detail',id='chest-203'))['quest']['status']=='completed'
    print('PASS live: two ordinary players, discovered-only counts/list/search/details, no future stages or hidden rewards, rejected mutations and impersonation',flush=True)
    for client in clients: client.close()
    clients.clear()
    time.sleep(2)
    sql(f'UPDATE player_storage SET `value`=7 WHERE player_id={players[0]} AND `key`=293')
    client=Probe(*reconnect); clients.append(client)
    quest=client.request(dict(action='detail',id='ape-city'))['quest']
    assert quest['done']==3 and quest['total']==4 and not quest['steps'][3]['completed']
    assert client.request(dict(action='detail',id='chest-203'))['quest']['status']=='completed'
    print('PASS live: newly accepted stage discovered after reconnect; original completed progress preserved',flush=True)
finally:
    for client in clients:
        try: client.close()
        except Exception: client.sock.close()
    time.sleep(2)
    for player in players:
        assert sql(f'SELECT COUNT(*) FROM players_online WHERE player_id={player}')=='0','Probe still online; preserve for cleanup'
    for account,email in accounts:
        assert sql(f"SELECT COUNT(*) FROM accounts WHERE id={account} AND email='{email}'")=='1'
        sql(f'DELETE FROM players WHERE account_id={account}')
        sql(f"DELETE FROM accounts WHERE id={account} AND email='{email}'")
    print('Disposable probe accounts removed; real player records untouched',flush=True)
