"""One disposable player verifies pending rewards and exactly-once delivery.

Requires the explicit isolated-staging guard. Never edit or test against production.
"""

if not __debug__:
    raise SystemExit('Python optimization (-O) disables validation assertions; refusing to run this tool.')

import hashlib
import importlib.util
from pathlib import Path
import secrets
import time

from staging_safety import require_staging_target

spec = importlib.util.spec_from_file_location('achievements_live', Path(__file__).with_name('achievements-live.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
Probe, sql = module.Probe, module.sql


def logout(probe, player):
    probe.send(b'\x14')
    probe.collect(0.5)
    probe.sock.close()
    for _ in range(20):
        if sql(f'SELECT COUNT(*) FROM players_online WHERE player_id={player}') == '0':
            return
        time.sleep(0.25)
    raise AssertionError('Probe remains online; preserve its data')


def main():
    require_staging_target()
    account = 900000000 + secrets.randbelow(90000000)
    marker = 'claimprobe_' + secrets.token_hex(8) + '@test.invalid'
    password = secrets.token_hex(16)
    name = 'Claim Probe ' + ''.join(secrets.choice('abcdefghijklmnpqrstuvwxyz') for _ in range(8))
    player, probe = None, None
    assert sql(f'SELECT COUNT(*) FROM accounts WHERE id={account}') == '0'
    try:
        sql(f"INSERT INTO accounts(id,email,password,type) VALUES({account},'{marker}','{hashlib.sha1(password.encode()).hexdigest()}',1)")
        sql(f"INSERT INTO players(name,account_id,conditions,comment,cap,town_id,posx,posy,posz,lastlogin) VALUES('{name}',{account},'','',400,1,32097,32219,7,1)")
        player = int(sql(f'SELECT id FROM players WHERE account_id={account}'))
        # An earned level-20 reward is retained even after falling below level 20.
        sql(f'INSERT INTO player_storage(player_id,`key`,`value`) VALUES({player},17821,2)')
        # Login enforces at least 400 capacity. Four plate armors in a backpack
        # exceed that capacity while leaving container slots available.
        rows = [f"({player},3,100,2854,1,'')"]
        rows += [f"({player},100,{sid},3357,1,'')" for sid in range(101, 105)]
        sql('INSERT INTO player_items(player_id,pid,sid,itemtype,count,attributes) VALUES ' + ','.join(rows))
        probe = Probe(account, password, name)
        assert b'Welcome to Antigas' in probe.collect(1)
        entries = probe.progress(fresh=False)
        assert entries['level_1']['ready'] and not entries['level_1']['completed']
        time.sleep(2.1)
        entries = probe.progress('claimRewards', fresh=False)
        assert entries['level_1']['ready'] and not entries['level_1']['completed']
        logout(probe, player); probe = None
        assert sql(f'SELECT value FROM player_storage WHERE player_id={player} AND `key`=17821') == '2'
        assert sql(f'SELECT COUNT(*) FROM player_items WHERE player_id={player} AND itemtype=5291') == '0'
        # Make capacity available only while the disposable character is offline.
        sql(f'UPDATE players SET cap=800 WHERE id={player}')
        probe = Probe(account, password, name)
        assert b'Welcome to Antigas' in probe.collect(1)
        time.sleep(2.1)
        entries = probe.progress(fresh=False)
        assert entries['level_1']['completed'] and not entries['level_1']['ready']
        time.sleep(2.1)
        entries = probe.progress('claimRewards', fresh=False)
        assert entries['level_1']['completed'] and not entries['level_1']['ready']
        logout(probe, player); probe = None
        assert sql(f'SELECT value FROM player_storage WHERE player_id={player} AND `key`=17821') == '1'
        assert sql(f'SELECT COUNT(*) FROM player_items WHERE player_id={player} AND itemtype=5291') == '1'
        print('PASS pending claim: overweight inventory retains reward; reconnect delivers once below original level; repeated claim does not duplicate', flush=True)
    finally:
        if probe:
            logout(probe, player)
        if player:
            assert sql(f'SELECT COUNT(*) FROM players_online WHERE player_id={player}') == '0'
        if sql(f"SELECT COUNT(*) FROM accounts WHERE id={account} AND email='{marker}'") == '1':
            sql(f'DELETE FROM players WHERE account_id={account}')
            sql(f"DELETE FROM accounts WHERE id={account} AND email='{marker}'")
            print('Disposable claim account removed.', flush=True)


if __name__ == '__main__':
    main()
