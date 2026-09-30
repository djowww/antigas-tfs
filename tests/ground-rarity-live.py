"""Bounded v46 ground-rarity smoke using one new ordinary character on loopback.

Always checks opcode129 negotiation/rejection and replacement login. Ground
drop/pickup runs only if this disposable character is the sole online player
and an adjacent tile's native Look is an exact plain-floor description. Every
fixture has an unpredictable ATTR_DESC; pickup requires that exact description.
Otherwise physical ground checks are explicitly skipped, never reported passed.

No movement, combat, GM privileges, existing player writes or admin hooks.
Deletion requires confirmed offline state and recovery of all dropped fixtures.
Reads targeted packet signatures, not a complete game protocol/map decoder.
Use --self-test without database/network access. Existing TFS_DB_NAME is needed
for live execution; use ANTIGAS_STAGING_GAME_PORT=7176 or 7186 with explicit mutation approval.
"""

if not __debug__:
    raise SystemExit('Python optimization (-O) disables validation assertions; refusing to run this tool.')

import importlib.util
import json
import os
from pathlib import Path
import secrets
import struct
import sys
import time

from load_test_protocol import string
from staging_safety import require_staging_target

_spec = importlib.util.spec_from_file_location('loot_live', Path(__file__).with_name('loot-live.py'))
loot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(loot)
rarity = loot.rarity
OPCODE = 129
START = (32097, 32219, 7)
SWORD = (6, 3264, 4, 6, 4, 0, rarity.pack_codes(1, 2, 3), '+4 attack')
ARMOR = (0, 3361, 5, 1, 5, 0, rarity.pack_codes(2, 3, 6, 7), '+5% maximum health')
BACKPACK = 2854
PLAIN_GROUND = {
    'You see stone floor.', 'You see a stone floor.',
    'You see tiled floor.', 'You see a tiled floor.',
    'You see marble floor.', 'You see a marble floor.',
    'You see white marble floor.', 'You see black marble floor.',
    'You see wooden floor.', 'You see a wooden floor.',
    'You see dirt floor.', 'You see grass.',
    'You see cobbled pavement.',
}


def position(value):
    return struct.pack('<HHB', *value)


def wire_records(raw):
    result = []
    for offset in range(max(0, len(raw) - 3)):
        if raw[offset:offset + 2] != bytes((0x32, OPCODE)):
            continue
        length = struct.unpack_from('<H', raw, offset + 2)[0]
        if not 0 < length <= 8192 or offset + 4 + length > len(raw):
            continue
        try:
            value = json.loads(raw[offset + 4:offset + 4 + length].decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            continue
        if isinstance(value, dict):
            result.append((offset, value))
    return result


def records(raw):
    return [value for _, value in wire_records(raw)]


def descriptions(raw):
    result = []
    for offset in range(max(0, len(raw) - 3)):
        if raw[offset] != 0xB4:
            continue
        length = struct.unpack_from('<H', raw, offset + 2)[0]
        if not 0 < length <= 8192 or offset + 4 + length > len(raw):
            continue
        text = raw[offset + 4:offset + 4 + length].decode('latin1')
        if text.startswith('You see '):
            result.append(text)
    return result


def at_tile(events, target):
    target = dict(zip(('x', 'y', 'z'), target))
    return [event for event in events if event.get('event') == 'tile' and event.get('position') == target]


def assert_ready(events):
    matches = [event for event in events if event.get('event') == 'ready']
    assert len(matches) == 1 and matches[0].get('version') == 1, 'Ground capability acknowledgment missing or incompatible'
    assert any(event.get('event') == 'reset' for event in events), 'Ground handshake omitted fresh snapshot reset'


class GroundProbe(loot.LootProbe):
    def opcode(self, payload):
        self.send(bytes((0x32, OPCODE)) + string(payload))
        return self.collect(0.4)

    def look(self, source, item_id=0, stack=0):
        self.send(b'\x8c' + source + struct.pack('<HB', item_id, stack))
        return descriptions(self.collect(0.3))

    def move_fixture(self, item, target, pickup=False):
        source = position(target) if pickup else rarity.position(item['slot'])
        destination = rarity.position(item['slot']) if pickup else position(target)
        self.send(b'\x78' + source + struct.pack('<HB', item['item_id'], 1 if pickup else 0)
                  + destination + b'\x01')
        return self.collect(0.6)


def assert_marked_look(lines, marker):
    assert len(lines) == 1 and marker in lines[0].splitlines(), 'Exact disposable item marker missing; refusing pickup'


def alone(player):
    return rarity.sql(f'SELECT COUNT(*) FROM players_online WHERE player_id<>{player}') == '0'


def choose_empty_tile(probe, player, login):
    if not alone(player):
        return None, 'Another player is online; ground drop/pickup skipped'
    if b'\x64' + position(START) not in login:
        return None, 'Expected starting map position was not confirmed; ground drop/pickup skipped'
    observed = []
    for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1), (1, 1), (-1, 1), (1, -1), (-1, -1)):
        candidate = (START[0] + dx, START[1] + dy, START[2])
        lines = probe.look(position(candidate))
        observed.append({'position': candidate, 'look': lines})
        if len(lines) == 1 and lines[0] in PLAIN_GROUND:
            if alone(player) and probe.look(position(candidate)) == lines:
                return candidate, None
    return None, 'No confirmed empty plain ground; observations: ' + json.dumps(observed)


def retrieve(probe, item, target):
    # A rejected drop can leave the item in its original slot. Confirm its exact
    # marker there before deciding whether any world pickup is necessary.
    own = probe.look(rarity.position(item['slot']), item['item_id'])
    if len(own) == 1 and item['marker'] in own[0].splitlines():
        return b''
    assert_marked_look(probe.look(position(target), item['item_id'], 1), item['marker'])
    raw = probe.move_fixture(item, target, pickup=True)
    assert_marked_look(probe.look(rarity.position(item['slot']), item['item_id']), item['marker'])
    return raw


def saved_fixtures(player, items):
    raw = rarity.sql(f'SELECT pid,sid,itemtype,HEX(attributes) FROM player_items WHERE player_id={player} ORDER BY sid')
    rows = [line.split('\t') for line in raw.splitlines()]
    assert len(rows) == 3, 'Unexpected fixture item count after save'
    by_id = {int(row[2]): row for row in rows}
    sword, backpack, armor = (by_id[item_id] for item_id in (SWORD[1], BACKPACK, ARMOR[1]))
    assert int(sword[0]) == SWORD[0] and int(backpack[0]) == 3 and armor[0] == backpack[1], 'Fixture containment changed'
    for item in items:
        blob = bytes.fromhex(by_id[item['item_id']][3])
        assert b'\x07' + string(item['marker']) in blob, 'Fixture marker did not persist'
    assert rarity.rarity_bytes(SWORD) in bytes.fromhex(sword[3]), 'Retrieved sword lost rarity'
    assert rarity.rarity_bytes(ARMOR) in bytes.fromhex(armor[3]), 'Closed backpack armor lost rarity'
    state = rarity.sql(f'SELECT level,experience,balance,healthmax,manamax FROM players WHERE id={player}')
    assert state == '1\t0\t0\t150\t100', 'Probe received progress or changed base stats'


def main():
    require_staging_target()
    report = {'test': 'ground-rarity-live', 'status': 'failed', 'checks': [], 'cleanup': False,
              'ground_lifecycle': 'not_attempted',
              'limitations': ['Targeted packet signatures; not a complete map/protocol decoder',
                              'No visual rendering or combat in staging',
                              'Physical fixture skipped if other players are online or tile is uncertain']}
    fixture = loot.new_character()
    fixture['marker'] = 'groundprobe_' + secrets.token_hex(8) + '@test.invalid'
    fixture['name'] = 'Ground Probe ' + ''.join(secrets.choice('abcdefghijklmnpqrstuvwxyz') for _ in range(8))
    marker = 'ground-fixture-' + secrets.token_hex(16)
    items = [{'slot': 6, 'item_id': SWORD[1], 'tier': 4, 'marker': marker + '-sword'},
             {'slot': 3, 'item_id': BACKPACK, 'tier': 0, 'marker': marker + '-closed-bag'}]
    pending, target, phase = None, None, 'setup'
    started = time.monotonic()
    try:
        loot.create_character(fixture)
        player = fixture['player']
        sword_blob = b'\x07' + string(items[0]['marker']) + rarity.rarity_bytes(SWORD) + b'\0'
        bag_blob = b'\x07' + string(items[1]['marker']) + b'\0'
        armor_blob = rarity.rarity_bytes(ARMOR) + b'\0'
        rarity.sql('INSERT INTO player_items(player_id,pid,sid,itemtype,count,attributes) VALUES '
                   f"({player},6,101,{SWORD[1]},1,UNHEX('{sword_blob.hex()}')),"
                   f"({player},3,102,{BACKPACK},1,UNHEX('{bag_blob.hex()}')),"
                   f"({player},102,103,{ARMOR[1]},1,UNHEX('{armor_blob.hex()}'))")
        probe = GroundProbe()
        fixture['probe'] = probe
        login = probe.connect(fixture['account'], fixture['password'], fixture['name'])
        probe.rarity(6, SWORD)
        phase = 'negotiation'
        for invalid in ('H|2', 'S|1', '{"event":"tile","position":{"x":1,"y":1,"z":7},"items":[]}'):
            assert records(probe.opcode(invalid)) == [], 'Unnegotiated or forged ground request produced a response'
        assert_ready(records(probe.opcode('H|1')))
        probe.assert_alive()
        for invalid in ('H|2', 'T|1|1|7', '{"event":"reset","seq":999999}'):
            # Authorized periodic snapshots may arrive independently. The probe
            # cannot require an empty response after negotiation.
            raw = probe.opcode(invalid)
            assert not any(event.get('event') in ('ready', 'reset') for event in records(raw)), 'Invalid request reset or renegotiated the ground protocol'
        probe.assert_alive()
        report['checks'].append('Version 1 ground negotiation/reset succeeds; invalid/forged requests leave the ordinary session healthy')
        phase = 'ground_preflight'
        target, skip = choose_empty_tile(probe, player, login)
        if target is None:
            report['ground_lifecycle'] = 'skipped'
            report['ground_skip_reason'] = skip
        else:
            report['ground_lifecycle'] = 'started'
            completed = []
            for item in items:
                assert time.monotonic() - started < 70, 'Bounded probe budget exceeded'
                if not alone(player):
                    report['ground_lifecycle'] = 'partial' if completed else 'skipped'
                    report['ground_skip_reason'] = 'Another player joined; remaining ground fixtures skipped before drop'
                    break
                before = probe.look(position(target))
                if len(before) != 1 or before[0] not in PLAIN_GROUND:
                    report['ground_lifecycle'] = 'partial' if completed else 'skipped'
                    report['ground_skip_reason'] = 'Ground tile changed; remaining fixtures skipped before drop'
                    break
                assert_marked_look(probe.look(rarity.position(item['slot']), item['item_id']), item['marker'])
                pending = item
                phase = 'ground_drop'
                raw = probe.move_fixture(item, target)
                assert_marked_look(probe.look(position(target), item['item_id'], 1), item['marker'])
                tiles = at_tile(records(raw), target)
                expected = [{'itemId': item['item_id'], 'stackpos': 1, 'tier': item['tier']}] if item['tier'] else []
                if item['tier']:
                    assert tiles and tiles[-1].get('items') == expected, 'Visible ground rarity differs from the exact sword fixture'
                else:
                    assert all(tile.get('items') == [] for tile in tiles), 'Closed ground bag revealed its nested mythic armor'
                native = b'\x6a' + position(target) + b'\x01' + struct.pack('<H', item['item_id'])
                assert native in raw, 'Fixture drop native tile add missing'
                for offset, event in wire_records(raw):
                    if at_tile([event], target):
                        assert raw.find(native) < offset, 'Ground rarity arrived before its corresponding native item'
                phase = 'ground_pickup'
                recovered = retrieve(probe, item, target)
                pending = None
                if item['tier']:
                    cleared = at_tile(records(recovered), target)
                    assert cleared and cleared[-1].get('items') == [], 'Pickup did not clear ground rarity metadata'
                assert probe.look(position(target)) == before, 'Original empty floor did not return after fixture retrieval'
                completed.append(item['item_id'])
            probe.rarity(6, SWORD)
            if len(completed) == len(items):
                report['ground_lifecycle'] = 'passed'
            if SWORD[1] in completed:
                report['checks'].append('Exact marked sword drop sends native add then tier4 tile metadata; pickup clears it and preserves inventory rarity')
            if BACKPACK in completed:
                report['checks'].append('Closed marked backpack on the ground emits no rarity for its nested mythic armor; bag retrieved intact')
        phase = 'replacement_login'
        replacement = GroundProbe()
        try:
            replacement.reconnect(fixture['account'], fixture['password'], fixture['name'])
        except Exception:
            if replacement.sock:
                replacement.sock.close()
            raise
        fixture['probe'] = replacement
        try:
            probe.collect(0.3)
            assert probe.peer_closed, 'Original probe socket remained connected after replacement'
        finally:
            probe.sock.close()
        assert replacement.creature_id == probe.creature_id, 'Replacement duplicated the test player'
        assert_ready(records(replacement.opcode('H|1')))
        replacement.assert_alive()
        report['checks'].append('Replacement login preserves one player and negotiates a fresh ground snapshot')
        phase = 'persistence'
        replacement.logout(player)
        fixture['probe'] = None
        saved_fixtures(player, items)
        report['checks'].append('Logout saves exactly sword, backpack and nested armor with original rarity and unique markers; no progress/rewards')
        if os.environ.get('ANTIGAS_REQUIRE_GROUND_LIFECYCLE') == '1':
            assert report['ground_lifecycle'] == 'passed', 'Required physical ground lifecycle was not exercised'
        report['status'] = 'passed'
    except Exception as exc:
        report['failure_phase'] = phase
        report['failure_type'] = type(exc).__name__
        if isinstance(exc, AssertionError):
            report['failure'] = str(exc)
        if report['ground_lifecycle'] == 'started':
            report['ground_lifecycle'] = 'failed'
    finally:
        if pending:
            try:
                assert fixture['probe'] and not fixture['probe'].peer_closed
                retrieve(fixture['probe'], pending, target)
                pending = None
            except Exception as exc:
                report['unrecovered_world_fixture'] = {
                    'item_id': pending['item_id'], 'position': target,
                    'marker': pending['marker'], 'reason': type(exc).__name__}
                report['status'] = 'failed'
        try:
            if pending:
                # Keep the exact test identity available for directed recovery.
                if fixture['probe']:
                    fixture['probe'].logout(fixture['player'])
                    fixture['probe'] = None
                raise AssertionError('Ground fixture not recovered; retaining disposable account')
            loot.cleanup(fixture)
            report['cleanup'] = not fixture['created'] or fixture['cleanup']
        except Exception as exc:
            report['status'] = 'failed'
            report['retained_disposable_data'] = {'account_id': fixture['account'], 'player_id': fixture['player'],
                                                  'cleanup_failure': type(exc).__name__}
        report['elapsed_seconds'] = round(time.monotonic() - started, 2)
        print(json.dumps(report, sort_keys=True), flush=True)
    return 0 if report['status'] == 'passed' and report['cleanup'] else 1


def self_test():
    # Fixture serialization must track the complete status payload before live setup.
    assert len(rarity.rarity_bytes(SWORD)) == 10
    assert len(rarity.rarity_bytes(ARMOR)) == 10
    data = {'event': 'tile', 'seq': 2, 'position': {'x': 100, 'y': 101, 'z': 7},
            'items': [{'itemId': 3264, 'stackpos': 1, 'tier': 4}]}
    encoded = b'\x32\x81' + string(json.dumps(data))
    assert records(encoded) == [data]
    assert records(b'\0' + encoded + b'\0') == [data]
    assert records(encoded[:-1]) == []
    assert records(b'\x32\x81' + struct.pack('<H', 8193) + b'{}') == []
    assert records(b'\x32\x81' + string('[]')) == []
    assert at_tile([data], (100, 101, 7)) == [data]
    assert at_tile([data], (100, 102, 7)) == []
    assert_ready([{'event': 'ready', 'version': 1}, {'event': 'reset', 'seq': 1}])
    text = 'You see a sword.\nfixture-123\nLegendary: +4 attack'
    assert descriptions(b'\xb4\x13' + string(text)) == [text]
    assert_marked_look([text], 'fixture-123')
    try:
        assert_marked_look([text], 'fixture-12')
    except AssertionError:
        pass
    else:
        raise AssertionError('Partial marker matched')
    assert position(START) == struct.pack('<HHB', *START)
    print(json.dumps({'test': 'ground-rarity-live-parser', 'status': 'passed', 'checks': 12,
                      'database_access': False, 'network_access': False}))


if __name__ == '__main__':
    if sys.argv[1:] == ['--self-test']:
        self_test()
    elif sys.argv[1:]:
        raise SystemExit('Usage: ground-rarity-live.py [--self-test]')
    else:
        raise SystemExit(main())
