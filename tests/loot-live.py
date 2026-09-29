"""Bounded v45 smoke with two newly created ordinary characters on loopback.

Run only against an approved isolated staging database and loopback staging port. This checks the Loot
channel, capability negotiation and rejection of client-forged notifications.
It never moves, fights, creates corpses or edits an existing player's data.
Only the exact generated accounts are removed, after confirmed logout/offline.
Use --self-test for parser checks without a database or network connection.

Real drops and corpse-open authorization belong to the isolated core/client
fixtures. A successful live smoke must not be represented as that coverage.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import socket
import struct
import sys
import time

from load_test_protocol import string
from staging_safety import require_staging_target

_spec = importlib.util.spec_from_file_location('rarity_live', Path(__file__).with_name('rarity-live.py'))
rarity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rarity)

CHANNEL = 10
OPCODE = 128
DENIAL = b'O canal Loot e somente para leitura.'
MAX_PAYLOAD = 8192


def extended(raw):
    """Decode bounded JSON replies in a targeted post-login receive window."""
    result = []
    for offset in range(max(0, len(raw) - 3)):
        if raw[offset:offset + 2] != bytes((0x32, OPCODE)):
            continue
        count = struct.unpack_from('<H', raw, offset + 2)[0]
        if count > MAX_PAYLOAD or offset + 4 + count > len(raw):
            continue
        try:
            value = json.loads(raw[offset + 4:offset + 4 + count].decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(value, dict):
            result.append(value)
    return result


def channel_lists(raw):
    lists = []
    for offset in range(max(0, len(raw) - 1)):
        if raw[offset] != 0xAB:
            continue
        count = raw[offset + 1]
        if not 1 <= count <= 32:
            continue
        entries, index = {}, offset + 2
        for _ in range(count):
            if index + 4 > len(raw):
                break
            channel, length = struct.unpack_from('<HH', raw, index)
            index += 4
            if not 1 <= length <= 80 or index + length > len(raw) or channel in entries:
                break
            try:
                name = raw[index:index + length].decode('ascii')
            except UnicodeDecodeError:
                break
            if not all(32 <= ord(char) < 127 for char in name):
                break
            entries[channel] = name
            index += length
        else:
            if entries.get(4) == 'World Chat':
                lists.append(entries)
    return lists


def ready(records):
    matches = [record for record in records if record.get('event') == 'ready']
    assert len(matches) == 1 and matches[0].get('version') == 1, 'Loot capability acknowledgment missing or incompatible'
    assert not [record for record in records if record.get('event') in ('loot', 'marker')], 'Fresh unrelated character received another owner loot'


class LootProbe(rarity.Probe):
    def reconnect(self, account, password, name):
        """Replace only this test character's socket, retaining its Player object."""
        self.key = struct.unpack('<IIII', secrets.token_bytes(16))
        self.sock = socket.create_connection(('127.0.0.1', int(os.environ['ANTIGAS_STAGING_GAME_PORT'])), timeout=5)
        key_path = Path(os.environ.get('ANTIGAS_RSA_PUBLIC', '/opt/antigas-security-v26/rsa-public.json'))
        modulus = int(json.loads(key_path.read_text())['modulus'])
        plain = b'\0' + struct.pack('<IIII', *self.key) + b'\0' + struct.pack('<I', account) + string(name) + string(password)
        assert len(plain) <= 128, 'Probe login exceeds RSA block'
        encrypted = pow(int.from_bytes(plain.ljust(128, b'\0'), 'big'), 65537, modulus).to_bytes(128, 'big')
        packet = b'\x0a' + struct.pack('<HH', 11, 772) + encrypted
        self.sock.sendall(struct.pack('<H', len(packet)) + packet)
        raw = self.collect(2.5)  # Replacement login has an intentional 1s delay.
        identities = [struct.unpack_from('<I', raw, index + 1)[0]
                      for index in range(max(0, len(raw) - 7))
                      if raw[index] == 0x0A and raw[index + 5:index + 8] == b'\x32\0\0']
        assert identities and not self.peer_closed, 'Replacement session did not enter the game'
        self.creature_id = identities[0]

    def opcode(self, value):
        self.send(bytes((0x32, OPCODE)) + string(value))
        return self.collect(0.35)

    def assert_alive(self):
        self.send(b'\x97')
        lists = channel_lists(self.collect(0.4))
        assert not self.peer_closed and lists and lists[-1].get(CHANNEL) == 'Loot', 'Loot channel missing from a live ordinary session'

    def open_loot(self):
        self.send(b'\x98' + struct.pack('<H', CHANNEL))
        assert b'\xac' + struct.pack('<H', CHANNEL) + string('Loot') in self.collect(0.35), 'Loot channel did not reopen'


def new_character():
    account = 900000000 + secrets.randbelow(90000000)
    marker = 'lootprobe_' + secrets.token_hex(8) + '@test.invalid'
    password = secrets.token_hex(16)
    name = 'Loot Probe ' + ''.join(secrets.choice('abcdefghijklmnpqrstuvwxyz') for _ in range(8))
    return {'account': account, 'marker': marker, 'password': password, 'name': name,
            'player': None, 'created': False, 'probe': None, 'cleanup': False}


def create_character(fixture):
    account, marker, password, name = (fixture[key] for key in ('account', 'marker', 'password', 'name'))
    assert rarity.sql(f'SELECT COUNT(*) FROM accounts WHERE id={account}') == '0', 'Disposable account collision'
    rarity.sql(f"INSERT INTO accounts(id,email,password,type) VALUES({account},'{marker}','{hashlib.sha1(password.encode()).hexdigest()}',1)")
    fixture['created'] = True
    rarity.sql(f"INSERT INTO players(name,account_id,group_id,conditions,comment,cap,town_id,posx,posy,posz,lastlogin,level,experience,health,healthmax,mana,manamax,soul,skill_sword,offlinetraining_skill) VALUES('{name}',{account},1,'','',400,1,32097,32219,7,1,1,0,150,150,100,100,100,10,-1)")
    fixture['player'] = int(rarity.sql(f"SELECT id FROM players WHERE account_id={account} AND name='{name}'"))


def cleanup(fixture):
    if fixture['probe']:
        fixture['probe'].logout(fixture['player'])
        fixture['probe'] = None
    account, marker, player = (fixture[key] for key in ('account', 'marker', 'player'))
    if player:
        rarity.wait_offline(player)
    if fixture['created']:
        assert rarity.sql(f"SELECT COUNT(*) FROM accounts WHERE id={account} AND email='{marker}'") == '1', 'Disposable marker changed; retaining account'
        # Refuse a cleanup if an unexpected second character was attached.
        expected = '0' if player is None else str(player)
        existing = rarity.sql(f'SELECT COALESCE(MAX(id),0) FROM players WHERE account_id={account}')
        assert existing == expected, 'Unexpected disposable account membership; retaining account'
        assert int(rarity.sql(f'SELECT COUNT(*) FROM players WHERE account_id={account}')) <= 1
        rarity.sql(f"DELETE p FROM players p JOIN accounts a ON a.id=p.account_id WHERE a.id={account} AND a.email='{marker}'")
        rarity.sql(f"DELETE FROM accounts WHERE id={account} AND email='{marker}'")
        assert rarity.sql(f'SELECT COUNT(*) FROM accounts WHERE id={account}') == '0'
        if player:
            assert rarity.sql(f'SELECT COUNT(*) FROM players WHERE id={player}') == '0'
            assert rarity.sql(f'SELECT COUNT(*) FROM player_items WHERE player_id={player}') == '0'
        fixture['cleanup'] = True


def main():
    require_staging_target()
    report = {'test': 'loot-live', 'status': 'failed', 'checks': [], 'cleanup': False,
              'limitations': ['No monster kill, real corpse or visual rendering in staging',
                              'Targeted packet parsing; not a full game client decoder']}
    fixtures = [new_character(), new_character()]
    start, phase = time.monotonic(), 'setup'
    try:
        for fixture in fixtures:
            create_character(fixture)
            fixture['probe'] = LootProbe()
            fixture['probe'].connect(fixture['account'], fixture['password'], fixture['name'])
            time.sleep(0.8)  # Respect the existing connection throttle.
        first, second = (fixture['probe'] for fixture in fixtures)
        phase = 'capability'
        for probe in (first, second):
            for invalid in ('H|2', 'S|1', '{"event":"opened","id":"1"}'):
                assert extended(probe.opcode(invalid)) == [], 'Unnegotiated or forged opcode accepted'
            probe.assert_alive()
        report['checks'].append('Both ordinary sessions reject invalid handshake, early sync and forged opened notification')
        ready(extended(first.opcode('H|1')))
        assert extended(second.collect(0.3)) == [], 'Capability reply crossed between unrelated players'
        ready(extended(second.opcode('H|1')))
        assert extended(first.collect(0.3)) == [], 'Capability reply crossed between unrelated players'
        report['checks'].append('Version 1 negotiation replies only to the requesting session')
        phase = 'channel'
        for probe in (first, second):
            probe.assert_alive()
            probe.send(b'\x99' + struct.pack('<H', CHANNEL))
            probe.collect(0.2)
            probe.open_loot()
        marker = 'loot-probe-' + secrets.token_hex(8)
        first.send(b'\x96\x05' + struct.pack('<H', CHANNEL) + string(marker))
        own = first.collect(0.35)
        other = second.collect(0.35)
        assert DENIAL in own, 'Loot channel did not explicitly reject player speech'
        assert marker.encode('ascii') not in own + other, 'Player speech was relayed into Loot'
        report['checks'].append('Channel 10 is listed, can close/reopen and rejects speech without relaying to another session')
        phase = 'forged_and_sync'
        for probe in (first, second):
            for invalid in ('O|1', '{"event":"removed","id":"1"}', 'H|' + '1' * 128):
                assert extended(probe.opcode(invalid)) == [], 'Forged notification produced a Loot response'
            assert extended(probe.opcode('S|1')) == [], 'Fresh unrelated character received corpse metadata on sync'
            probe.assert_alive()
        report['checks'].append('Malformed/forged messages leave both sessions healthy; own-corpse sync reveals no unrelated loot')
        phase = 'reconnect'
        replacement = LootProbe()
        original = fixtures[0]['probe']
        # Keep both handles until replacement succeeded; never leave an orphaned
        # test connection outside the fixture cleanup on a failed login.
        try:
            replacement.reconnect(fixtures[0]['account'], fixtures[0]['password'], fixtures[0]['name'])
        except Exception:
            if replacement.sock:
                replacement.sock.close()
            raise
        fixtures[0]['probe'] = replacement
        try:
            original.collect(0.3)
            assert original.peer_closed, 'Old test session remained connected after replacement login'
        finally:
            original.sock.close()
        assert replacement.creature_id == original.creature_id, 'Replacement created a second player instead of reusing the test character'
        ready(extended(replacement.opcode('H|1')))
        replacement.assert_alive()
        replacement.send(b'\x99' + struct.pack('<H', CHANNEL))
        replacement.collect(0.2)
        replacement.open_loot()
        report['checks'].append('Replacement login reuses the same player safely and renegotiates Loot on the new session')
        phase = 'logout'
        for fixture in fixtures:
            fixture['probe'].logout(fixture['player'])
            fixture['probe'] = None
            actual = rarity.sql(f"SELECT level,experience,balance,healthmax,manamax,skill_sword FROM players WHERE id={fixture['player']}")
            assert actual == '1\t0\t0\t150\t100\t10', 'Probe gained progress or modified base stats'
            assert rarity.sql(f"SELECT COUNT(*) FROM player_items WHERE player_id={fixture['player']}") == '0', 'Probe created unexpected items'
        assert time.monotonic() - start < 60, 'Bounded probe time budget exceeded'
        report['checks'].append('Both characters logout with zero rewards/items and unchanged level, experience and base stats')
        report['status'] = 'passed'
    except Exception as exc:
        report['failure_phase'] = phase
        report['failure_type'] = type(exc).__name__
        if isinstance(exc, AssertionError):
            report['failure'] = str(exc)
    finally:
        for fixture in fixtures:
            try:
                cleanup(fixture)
            except Exception as exc:
                report.setdefault('retained_disposable_data', []).append({
                    'account_id': fixture['account'], 'player_id': fixture['player'],
                    'cleanup_failure': type(exc).__name__})
                report['status'] = 'failed'
        report['cleanup'] = all(not entry['created'] or entry['cleanup'] for entry in fixtures)
        report['elapsed_seconds'] = round(time.monotonic() - start, 2)
        print(json.dumps(report, sort_keys=True), flush=True)
    return 0 if report['status'] == 'passed' and report['cleanup'] else 1


def self_test():
    reply = {'event': 'ready', 'version': 1}
    frame = b'\x32\x80' + string(json.dumps(reply))
    assert extended(frame) == [reply]
    assert extended(b'\0garbage' + frame + b'\0') == [reply]
    assert extended(frame[:-1]) == []
    assert extended(b'\x32\x80' + struct.pack('<H', 65535) + b'{}') == []
    assert extended(b'\x32\x80' + string('[]')) == []
    assert extended(b'\x32\x80' + string('{')) == []
    ready([reply])
    channels = b'\xab\x02' + struct.pack('<H', 4) + string('World Chat') + struct.pack('<H', CHANNEL) + string('Loot')
    assert channel_lists(channels) == [{4: 'World Chat', CHANNEL: 'Loot'}]
    assert channel_lists(channels[:-1]) == []
    assert channel_lists(b'\xab\xff' + channels[2:]) == []
    assert string('H|1') == b'\x03\0H|1'
    print(json.dumps({'test': 'loot-live-parser', 'status': 'passed', 'database_access': False, 'checks': 11}))


if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']:
        self_test()
    elif sys.argv[1:]:
        raise SystemExit('Usage: loot-live.py [--self-test]')
    else:
        raise SystemExit(main())
