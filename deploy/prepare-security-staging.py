#!/usr/bin/env python3
"""One-time isolation of the existing empty staging world; never clone player data.

Run as root on the VPS with --confirm-staging-provision. The production service
is not stopped or modified. Credentials and RSA primes never leave this host.
"""
import argparse
import json
import os
from pathlib import Path
import pwd
import secrets
import shutil
import subprocess

ROOT = Path('/opt/imperium772-staging/server')
BACKUP = Path('/opt/antigas-security-validation-20260930/staging-before')
DB = 'antigas_security_staging'
USER = 'tfs74-stage'


def sql(query, database=None):
    args = ['mariadb', '--batch', '--skip-column-names']
    if database:
        args.append(database)
    result = subprocess.run(args, input=query, text=True, capture_output=True, timeout=60)
    if result.returncode:
        raise RuntimeError('Staging SQL operation failed; sensitive SQL output withheld')
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-staging-provision', action='store_true', required=True)
    parser.parse_args()
    if os.geteuid() != 0 or ROOT.resolve() != ROOT:
        raise SystemExit('Requires root and the real staging directory')
    state = subprocess.check_output(['systemctl', 'show', 'imperium772-staging', '-p', 'ActiveState', '--value'], text=True).strip()
    if state != 'inactive':
        raise SystemExit('Staging must be inactive')
    if BACKUP.exists() or sql(f"SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME='{DB}'") != '0':
        raise SystemExit('Already provisioned or partial run detected; inspect before retrying')
    for table in ('accounts', 'players'):
        if sql(f'SELECT COUNT(*) FROM {table}', 'antigas_load_v37') != '0':
            raise SystemExit('Source staging contains player/account data; refusing to copy')
    for entry in ROOT.rglob('*'):
        if entry.is_symlink() or (entry.is_file() and entry.stat().st_nlink != 1):
            raise SystemExit('Staging contains linked files; refusing shared writes')
    from cryptography.hazmat.primitives.asymmetric import rsa
    BACKUP.mkdir(mode=0o700)
    shutil.copy2('/etc/imperium772-staging.env', BACKUP / 'staging.env')
    shutil.copy2(ROOT / 'config.lua', BACKUP / 'config.lua')
    try:
        account = pwd.getpwnam(USER)
    except KeyError:
        subprocess.run(['useradd', '--system', '--no-create-home', '--shell', '/usr/sbin/nologin', USER], check=True)
        account = pwd.getpwnam(USER)
    password = secrets.token_hex(32)
    grant_db = DB.replace('_', r'\_')
    sql(f"CREATE DATABASE `{DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE USER '{DB}'@'127.0.0.1' IDENTIFIED BY '{password}'; GRANT ALL PRIVILEGES ON `{grant_db}`.* TO '{DB}'@'127.0.0.1';")
    dump = subprocess.run(['mariadb-dump', '--single-transaction', '--skip-lock-tables', '--hex-blob', 'antigas_load_v37'], capture_output=True, check=True)
    result = subprocess.run(['mariadb', DB], input=dump.stdout, capture_output=True)
    if result.returncode:
        raise RuntimeError('Staging schema import failed')
    shutil.copytree('/opt/imperium772/server/data', ROOT / 'data', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('reports', 'logs', '*.log', '*.save'))
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024).private_numbers()
    keyfile = ROOT / 'staging-rsa.key'
    with keyfile.open('x') as stream:
        stream.write(f'{key.p}\n{key.q}\n')
    keyfile.chmod(0o600)
    (ROOT / 'staging-rsa-public.json').write_text(json.dumps({'modulus': str(key.public_numbers.n), 'exponent': 65537}))
    for entry in (ROOT, *ROOT.rglob('*')):
        os.chown(entry, account.pw_uid, account.pw_gid)
    env = Path('/etc/imperium772-staging.env')
    env.write_text(f'TFS_DB_NAME={DB}\nTFS_DB_USER={DB}\nTFS_DB_PASSWORD={password}\nANTIGAS_RSA_KEY_FILE={keyfile}\n')
    env.chmod(0o600)
    dropin = Path('/etc/systemd/system/imperium772-staging.service.d/security-isolation.conf')
    dropin.parent.mkdir(exist_ok=True)
    dropin.write_text(f'''[Service]
User={USER}
Group={USER}
ProtectSystem=strict
ReadWritePaths={ROOT}
InaccessiblePaths=/opt/imperium772/server /etc/imperium772.env /opt/antigas-security-v26 /var/www/otclient
KillSignal=SIGINT
TimeoutStopSec=45
''')
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    print(json.dumps({'database': DB, 'unix_user': USER, 'staging': 'inactive', 'player_data_copied': False, 'production_untouched': True}))


if __name__ == '__main__':
    main()
