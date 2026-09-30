"""Bounded production smoke with ONE disposable level-1 ordinary character.

Run only against an approved isolated staging database and loopback staging port. Credentials stay in
memory. Only this newly created account is written/deleted; cleanup requires a
closed game connection and a confirmed offline character. The probe moves its
own disposable fixtures between equipment and backpack to check persistence.
No combat, trade, achievements claim or rewards are triggered. --self-test
needs no DB.

The wire checks locate fixed-format stats/skills messages using this fixture's
known low stats; this is a targeted smoke, not a full map/protocol decoder.
"""

if not __debug__:
    raise SystemExit('Python optimization (-O) disables validation assertions; refusing to run this tool.')

import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import socket
import struct
import subprocess
import sys
import time

from load_test_protocol import Client, crypt, string
from staging_safety import require_staging_target, rsa_public_modulus

def pack_codes(*codes):
    return sum(code << (index * 5) for index, code in enumerate(codes))


FIXTURES = (
    # slot, item id, tier, type, value, subtype, packed extras, Look text
    (4, 3361, 5, 1, 5, 0, pack_codes(2, 3, 6, 7), '+5% maximum health'),
    (7, 3559, 5, 2, 5, 0, pack_codes(1, 3, 7, 8), '+5% maximum mana'),
    (8, 3552, 5, 4, 10, 0, pack_codes(1, 2, 7, 9), '+10% speed'),
    (9, 3004, 5, 5, 5, 2, pack_codes(1, 2, 6, 7), '+5 sword'),
    (6, 3264, 4, 6, 4, 0, pack_codes(1, 2, 3), '+4 attack'),
    (5, 3412, 3, 7, 3, 0, pack_codes(1, 6), '+3 defense'),
)
BACKPACK = 2854
STATS = struct.Struct('<HHHIHBHHBBB')


def sql(query):
    completed = subprocess.run(
        ['mariadb', '--protocol=socket', '--user=root', '-N', '-B', os.environ['TFS_DB_NAME']],
        input=query, text=True, capture_output=True, timeout=10)
    if completed.returncode:
        # Do not print SQL/credentials if database setup fails.
        raise RuntimeError('Disposable probe database operation failed')
    return completed.stdout.strip()


def position(slot, container=False):
    return struct.pack('<HHB', 65535, 64 if container else slot, slot if container else 0)


def rarity_bytes(fixture):
    _, _, tier, kind, value, subtype, extras, _ = fixture
    primary = tier | kind << 8 | value << 16 | subtype << 24
    return b'\x27' + struct.pack('<I', primary) + b'\x28' + struct.pack('<I', extras)


def extended(raw):
    records = []
    for offset in range(len(raw) - 3):
        if raw[offset:offset + 2] != b'\x32\x7f':
            continue
        size = struct.unpack_from('<H', raw, offset + 2)[0]
        if size > 8192 or offset + 4 + size > len(raw):
            continue
        try:
            records.append(raw[offset + 4:offset + 4 + size].decode('ascii'))
        except UnicodeDecodeError:
            pass
    return records


def stats(raw):
    candidates = []
    for offset in range(len(raw) - STATS.size):
        if raw[offset] != 0xA0:
            continue
        values = STATS.unpack_from(raw, offset + 1)
        hp, maximum_hp, capacity, experience, level, level_percent, mana, maximum_mana, magic, magic_percent, soul = values
        if (experience == 0 and level == 1 and level_percent == 0 and magic == 0
                and magic_percent == 0 and soul == 100 and 0 <= hp <= maximum_hp
                and 150 <= maximum_hp <= 500 and 0 <= mana <= maximum_mana
                and 100 <= maximum_mana <= 500 and capacity <= 400):
            candidates.append({'max_health': maximum_hp, 'max_mana': maximum_mana})
    assert candidates, 'Expected fixture player-stats packet missing'
    return candidates[-1]


def sword_skill(raw):
    candidates = []
    for offset in range(len(raw) - 14):
        if raw[offset] != 0xA1:
            continue
        values = raw[offset + 1:offset + 15]
        if all(values[index * 2 + 1] == 0 for index in range(7)) and all(
                values[index * 2] == 10 for index in range(7) if index != 2) and values[4] in (10, 15):
            candidates.append(values[4])
    assert candidates, 'Expected fixture skill packet missing'
    return candidates[-1]


def creature_speed(raw, creature_id):
    marker = b'\x8f' + struct.pack('<I', creature_id)
    values = [struct.unpack_from('<H', raw, offset + 5)[0]
              for offset in range(len(raw) - 6) if raw[offset:offset + 5] == marker]
    assert values, 'Expected speed update for disposable player missing'
    return values[-1]


def fixture_statuses(fixture):
    slot, _, tier, kind, value, subtype, packed, _ = fixture
    statuses = [(kind, value, subtype, True)]
    resistance_subtypes = {6: 0, 7: 1, 8: 2, 9: 3, 10: 8}
    for index in range(tier - 1):
        code = (packed >> (index * 5)) & 0x1F
        if code == 1:
            status = (1, tier, 0, False)
        elif code == 2:
            status = (2, tier, 0, False)
        elif code == 3:
            status = (4, tier * 2, 0, False)
        elif 6 <= code <= 10:
            status = (3, tier, resistance_subtypes[code], False)
        elif 11 <= code <= 18:
            status = (5, tier, code - 11, False)
        else:
            raise AssertionError('Invalid packed rarity status code')
        statuses.append(status)
    return slot, statuses


def primary_allowed(slot, kind):
    if kind in (1, 2, 3):
        return slot in (4, 7)
    if kind == 4:
        return slot == 8
    if kind == 5:
        return slot in (2, 9)
    if kind in (6, 7):
        return slot in (5, 6)
    return False


def expected_stats(fixtures):
    maximum_health, maximum_mana = 150, 100
    for fixture in fixtures:
        slot, statuses = fixture_statuses(fixture)
        for kind, value, _, primary in statuses:
            if primary and not primary_allowed(slot, kind):
                continue
            if kind == 1:
                maximum_health += math.ceil(150 * value / 100)
            elif kind == 2:
                maximum_mana += math.ceil(100 * value / 100)
    return {'max_health': maximum_health, 'max_mana': maximum_mana}


def expected_speed(fixtures):
    speed = 220
    for fixture in fixtures:
        slot, statuses = fixture_statuses(fixture)
        for kind, value, _, primary in statuses:
            if kind == 4 and (not primary or primary_allowed(slot, kind)):
                speed += math.floor(220 * value / 100 + 0.5)
    return speed


def expected_sword_skill(fixtures):
    value = 10
    for fixture in fixtures:
        slot, statuses = fixture_statuses(fixture)
        for kind, bonus, subtype, primary in statuses:
            if kind == 5 and subtype == 2 and (not primary or primary_allowed(slot, kind)):
                value += bonus
    return value


class Probe(Client):
    def __init__(self):
        self.sock = None
        self.buffer = b''
        self.peer_closed = False
        self.request = 0
        self.creature_id = None
        self.rarity_extras = {}

    def connect(self, account, password, name):
        self.key = struct.unpack('<IIII', secrets.token_bytes(16))
        self.sock = socket.create_connection(('127.0.0.1', int(os.environ['ANTIGAS_STAGING_GAME_PORT'])), timeout=5)
        modulus = rsa_public_modulus()
        plain = b'\0' + struct.pack('<IIII', *self.key) + b'\0' + struct.pack('<I', account) + string(name) + string(password)
        assert len(plain) <= 128, 'Probe login exceeds RSA block'
        encrypted = pow(int.from_bytes(plain.ljust(128, b'\0'), 'big'), 65537, modulus).to_bytes(128, 'big')
        packet = b'\x0a' + struct.pack('<HH', 11, 772) + encrypted
        self.sock.sendall(struct.pack('<H', len(packet)) + packet)
        raw = self.collect(1)
        assert b'Welcome to Antigas' in raw, 'Disposable character login failed'
        candidates = [struct.unpack_from('<I', raw, index + 1)[0]
                      for index in range(len(raw) - 7)
                      if raw[index] == 0x0A and raw[index + 5:index + 8] == b'\x32\0\0']
        assert candidates, 'Player identity packet missing'
        self.creature_id = candidates[0]
        return raw

    def collect(self, seconds=0.6):
        end, decoded = time.monotonic() + seconds, bytearray()
        while time.monotonic() < end:
            self.sock.settimeout(max(0.05, end - time.monotonic()))
            try:
                data = self.sock.recv(65536)
            except socket.timeout:
                break
            if not data:
                self.peer_closed = True
                break
            self.buffer += data
            assert len(self.buffer) <= 1024 * 1024, 'Probe wire receive limit exceeded'
            while len(self.buffer) >= 2:
                size = struct.unpack_from('<H', self.buffer)[0]
                assert size and size % 8 == 0, 'Invalid encrypted frame'
                if len(self.buffer) < size + 2:
                    break
                packet = crypt(self.buffer[2:size + 2], self.key, True)
                self.buffer = self.buffer[size + 2:]
                count = struct.unpack_from('<H', packet)[0]
                assert count <= size - 2, 'Invalid decrypted payload size'
                payload = packet[2:count + 2]
                decoded.extend(payload)
                assert len(decoded) <= 1024 * 1024, 'Probe wire response limit exceeded'
                if payload == b'\x1d':
                    self.send(b'\x1e')
        return bytes(decoded)

    def rarity(self, slot, fixture=None, container=False):
        self.request += 1
        if container:
            query = f'Q|C|{self.request}|0|{slot}|1'
            prefix = f'R|C|{self.request}|0|{slot}|'
        else:
            query = f'Q|I|{self.request}|{slot}'
            prefix = f'R|I|{self.request}|'
        self.send(b'\x32\x7f' + string(query))
        records = [entry[len(prefix):] for entry in extended(self.collect()) if entry.startswith(prefix)]
        fields = fixture[2:6] + (fixture[6],) if fixture else (0, 0, 0, 0, 0)
        expected = ','.join(map(str, (slot, *fields)))
        assert records == [expected], 'Rarity wire response differs from the exact owned instance'
        if fixture:
            tier, extras = fixture[2], fixture[6]
            codes = [(extras >> (index * 5)) & 0x1F for index in range(tier - 1)]
            assert all(codes) and len(set(codes)) == tier - 1, 'Extra statuses are incomplete or duplicated'
            self.rarity_extras[slot] = extras

    def look(self, fixture):
        slot, item_id, *unused = fixture
        self.send(b'\x8c' + position(slot) + struct.pack('<HB', item_id, 0))
        raw = self.collect()
        assert fixture[-1].encode('ascii') in raw, 'Look omitted the rarity bonus'
        if item_id == 3264:
            assert b'Atk:18' in raw, 'Weapon Look does not include base attack + rarity'
        if item_id == 3412:
            assert b'Def:17' in raw, 'Shield Look does not include base defense + rarity'

    def initial_inventory_pushes(self, raw):
        messages = set(extended(raw))
        expected = []
        for fixture in FIXTURES:
            slot, item_id, tier, kind, value, subtype, extras, _ = fixture
            record = f'P|I|{slot}|{item_id},1,1,{tier},{kind},{value},{subtype},{extras}'
            expected.append(record)
        missing = [record for record in expected if record not in messages]
        if missing:
            pushes = sorted(message for message in messages if message.startswith('P|I|'))
            raise AssertionError('Login omitted same-packet inventory rarity metadata; '
                                 f'missing={missing}; received={pushes}')

    def open_backpack(self):
        self.send(b'\x82' + position(3) + struct.pack('<HBB', BACKPACK, 0, 0))
        assert b'\x6e\0' + struct.pack('<H', BACKPACK) in self.collect(), 'Backpack container did not open'

    def move(self, fixture, equip):
        slot, item_id, *unused = fixture
        source = position(0, True) if equip else position(slot)
        destination = position(slot) if equip else position(0, True)
        self.send(b'\x78' + source + struct.pack('<HB', item_id, 0) + destination + b'\x01')
        return self.collect(0.7)

    def logout(self, player):
        try:
            if self.sock and not self.peer_closed:
                self.send(b'\x14')
                self.collect(2)
        finally:
            if self.sock:
                self.sock.close()
        assert self.peer_closed, 'Logout not confirmed by server; retain disposable data'
        wait_offline(player)


def wait_offline(player):
    consecutive = 0
    for _ in range(24):
        if sql(f'SELECT COUNT(*) FROM players_online WHERE player_id={player}') == '0':
            consecutive += 1
            if consecutive == 3:
                return
        else:
            consecutive = 0
        time.sleep(0.25)
    raise AssertionError('Disposable player remains online; retain its data')


def persisted(player):
    rows = sql(f'SELECT pid,itemtype,HEX(attributes) FROM player_items WHERE player_id={player} ORDER BY pid')
    saved = {}
    for row in rows.splitlines():
        slot, item_id, attributes = row.split('\t')
        saved[(int(slot), int(item_id))] = bytes.fromhex(attributes)
    for fixture in FIXTURES:
        blob = saved.get(fixture[:2])
        assert blob in (rarity_bytes(fixture), rarity_bytes(fixture) + b'\0'), 'Saved item lost or changed its rarity bytes'
    assert len(saved) == len(FIXTURES) + 1, 'Unexpected item count: possible duplication or reward generation'
    values = sql(f'SELECT healthmax,manamax,skill_sword,level,experience,balance FROM players WHERE id={player}')
    assert values == '150\t100\t10\t1\t0\t0', 'Derived bonuses leaked into base persisted stats or test advanced'


def main():
    require_staging_target()
    report = {'test': 'rarity-live', 'status': 'failed', 'checks': [], 'cleanup': False,
              'limitations': ['No combat/resistance probability validation', 'No visual border screenshot',
                              'Targeted protocol parsing using known fixture stats; not a full client decoder']}
    account = 900000000 + secrets.randbelow(90000000)
    marker = 'rarityprobe_' + secrets.token_hex(8) + '@test.invalid'
    password = secrets.token_hex(16)
    name = 'Rarity Probe ' + ''.join(secrets.choice('abcdefghijklmnpqrstuvwxyz') for _ in range(8))
    player, probe, created = None, None, False
    phase = 'setup'
    started = time.monotonic()
    try:
        assert sql(f'SELECT COUNT(*) FROM accounts WHERE id={account}') == '0', 'Disposable account collision'
        sql(f"INSERT INTO accounts(id,email,password,type) VALUES({account},'{marker}','{hashlib.sha1(password.encode()).hexdigest()}',1)")
        created = True
        sql(f"INSERT INTO players(name,account_id,group_id,conditions,comment,cap,town_id,posx,posy,posz,lastlogin,level,experience,health,healthmax,mana,manamax,soul,skill_sword,offlinetraining_skill) VALUES('{name}',{account},1,'','',400,1,32097,32219,7,1,1,0,150,150,100,100,100,10,-1)")
        player = int(sql(f"SELECT id FROM players WHERE account_id={account} AND name='{name}'"))
        rows = [f"({player},3,101,{BACKPACK},1,'')"]
        for sid, fixture in enumerate(FIXTURES, 102):
            blob = (rarity_bytes(fixture) + b'\0').hex()
            rows.append(f"({player},{fixture[0]},{sid},{fixture[1]},1,UNHEX('{blob}'))")
        sql('INSERT INTO player_items(player_id,pid,sid,itemtype,count,attributes) VALUES ' + ','.join(rows))
        phase = 'initial_login'
        probe = Probe()
        raw = probe.connect(account, password, name)
        probe.initial_inventory_pushes(raw)
        assert stats(raw) == expected_stats(FIXTURES), 'Tier statuses missing from maxima on initial login'
        assert sword_skill(raw) == expected_sword_skill(FIXTURES), 'Equipped rarity skill missing on login'
        assert creature_speed(raw, probe.creature_id) == expected_speed(FIXTURES), 'Tier statuses missing from speed on initial login'
        report['checks'].append('login sends same-packet item metadata and applies complete tier statuses')
        for fixture in FIXTURES:
            probe.rarity(fixture[0], fixture)
            probe.look(fixture)
        report['checks'].append('opcode127 exact inventory metadata and Look for all six fixtures')
        phase = 'equipment'
        probe.open_backpack()
        for fixture in FIXTURES:
            assert time.monotonic() - started < 100, 'Bounded probe time budget exceeded'
            raw = probe.move(fixture, False)
            active = tuple(entry for entry in FIXTURES if entry != fixture)
            assert stats(raw) == expected_stats(active), 'Status remains active after unequip'
            if expected_speed(active) != expected_speed(FIXTURES):
                assert creature_speed(raw, probe.creature_id) == expected_speed(active), 'Speed status remains after unequip'
            if expected_sword_skill(active) != expected_sword_skill(FIXTURES):
                assert sword_skill(raw) == expected_sword_skill(active), 'Skill bonus remains after unequip'
            probe.rarity(fixture[0])
            probe.rarity(0, fixture, container=True)
            raw = probe.move(fixture, True)
            assert stats(raw) == expected_stats(FIXTURES), 'Statuses differ after reequip'
            if expected_speed(active) != expected_speed(FIXTURES):
                assert creature_speed(raw, probe.creature_id) == expected_speed(FIXTURES), 'Speed differs after reequip'
            if expected_sword_skill(active) != expected_sword_skill(FIXTURES):
                assert sword_skill(raw) == expected_sword_skill(FIXTURES), 'Skill differs after reequip'
            probe.rarity(fixture[0], fixture)
        report['checks'].append('all six items move backpack/equipment without losing metadata; health/mana/speed/skill remove and reapply exactly')
        phase = 'persistence'
        probe.logout(player)
        probe = None
        persisted(player)
        report['checks'].append('logout saves exact rarity metadata and unmodified base stats; no extra items')
        phase = 'relogin'
        probe = Probe()
        raw = probe.connect(account, password, name)
        probe.initial_inventory_pushes(raw)
        assert stats(raw) == expected_stats(FIXTURES)
        assert sword_skill(raw) == expected_sword_skill(FIXTURES)
        assert creature_speed(raw, probe.creature_id) == expected_speed(FIXTURES)
        for fixture in FIXTURES:
            probe.rarity(fixture[0], fixture)
        probe.logout(player)
        probe = None
        persisted(player)
        report['checks'].append('second login/logout retains bonuses exactly once and saves metadata again')
        report['status'] = 'passed'
    except Exception as exc:
        report['failure_phase'] = phase
        report['failure_type'] = type(exc).__name__
        if isinstance(exc, AssertionError):
            report['failure'] = str(exc)
    finally:
        try:
            if probe:
                probe.logout(player)
                probe = None
            if player:
                wait_offline(player)
            if created and sql(f"SELECT COUNT(*) FROM accounts WHERE id={account} AND email='{marker}'") == '1':
                # Exact ID + generated marker prevent touching any pre-existing account.
                sql(f"DELETE p FROM players p JOIN accounts a ON a.id=p.account_id WHERE a.id={account} AND a.email='{marker}'")
                sql(f"DELETE FROM accounts WHERE id={account} AND email='{marker}'")
                report['cleanup'] = True
        except Exception as exc:
            report['cleanup_failure'] = type(exc).__name__
            report['retained_disposable_account_id'] = account
            report['retained_disposable_player_id'] = player
            report['status'] = 'failed'
        report['elapsed_seconds'] = round(time.monotonic() - started, 2)
        print(json.dumps(report, sort_keys=True), flush=True)
    return 0 if report['status'] == 'passed' and report['cleanup'] else 1


def self_test():
    expected = expected_stats(FIXTURES)
    packet = b'\xa0' + STATS.pack(150, expected['max_health'], 256, 0,
                                  1, 0, 100, expected['max_mana'], 0, 0, 100)
    assert stats(packet) == expected
    assert sword_skill(b'\xa1' + bytes([10, 0, 10, 0, 15, 0, 10, 0, 10, 0, 10, 0, 10, 0])) == 15
    assert creature_speed(b'\x8f' + struct.pack('<IH', 12345, expected_speed(FIXTURES)),
                          12345) == expected_speed(FIXTURES)
    payload = f'R|I|123|4,5,1,5,0,{FIXTURES[0][6]}'
    assert extended(b'\x32\x7f' + string(payload)) == [payload]
    assert rarity_bytes(FIXTURES[0]) == (b'\x27' + struct.pack('<I', 5 | 1 << 8 | 5 << 16) +
                                         b'\x28' + struct.pack('<I', FIXTURES[0][6]))
    assert position(4).hex() == 'ffff040000'
    assert position(0, True).hex() == 'ffff400000'
    print(json.dumps({'test': 'rarity-live-parser', 'status': 'passed', 'database_access': False}))


if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']:
        self_test()
    elif sys.argv[1:]:
        raise SystemExit('Usage: rarity-live.py [--self-test]')
    else:
        raise SystemExit(main())
