"""Explicit v44 production deployment; invoked only after isolated validation."""
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile

PREP = Path('/opt/antigas-rarity-20260928')
SERVER = Path('/opt/imperium772/server')
WEB = Path('/var/www/otclient')
OLD_BINARY = '450f2b1a8e75243afedd36c72df5ac7da44de00f7ddebe3b76440e04c48aa797'
CLIENT = 'Antigas-7.4-Client-v44.zip'
CLIENT_HASH = 'cb48865197d7982b0cd0effbbcac302fc573da0a6f568226dfebfe74adcdb145'
RUNTIME = ['data/creaturescripts/creaturescripts.xml', 'data/creaturescripts/scripts/login.lua',
           'data/creaturescripts/scripts/market.lua', 'data/creaturescripts/scripts/rarity.lua']

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def note(event, **extra):
    record = {'time': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'event': event, **extra}
    with (PREP / 'deployment.jsonl').open('a') as out:
        out.write(json.dumps(record) + '\n')
    print(json.dumps(record), flush=True)

def run(args, **kw):
    return subprocess.run(args, check=True, **kw)

def atomic(source, target, uid=None, gid=None, mode=None):
    previous = target.stat() if target.exists() else None
    temporary = target.with_name(target.name + '.v44-new')
    shutil.copyfile(source, temporary)
    os.chmod(temporary, mode if mode is not None else previous.st_mode & 0o777)
    os.chown(temporary, uid if uid is not None else previous.st_uid,
             gid if gid is not None else previous.st_gid)
    with temporary.open('rb') as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, target)

def server():
    assert (PREP / 'build.exit').read_text().strip() == '0', 'Build must pass'
    assert (PREP / 'core-test.exit').read_text().strip() == '0', 'Core tests must pass'
    assert digest(SERVER / 'tfs') == OLD_BINARY, 'Production binary changed during review'
    expected = json.loads((PREP / 'runtime-baseline.json').read_text())
    for name, checksum in expected.items():
        assert digest(SERVER / name) == checksum, 'Production runtime changed during review: ' + name
    assert not (SERVER / RUNTIME[-1]).exists(), 'Unexpected existing rarity handler'
    assert digest(PREP / CLIENT) == CLIENT_HASH
    web_owner = (WEB / 'client-release.json').stat()
    # Make the immutable download available before the new welcome message references it.
    atomic(PREP / CLIENT, WEB / CLIENT, web_owner.st_uid, web_owner.st_gid, 0o644)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup = Path('/root/antigas-backups') / ('rarity-v44-' + stamp)
    backup.mkdir(parents=True, mode=0o700)
    os.chmod(backup, 0o700)
    with tarfile.open(backup / 'files-before.tar.gz', 'w:gz') as tar:
        for name in ['tfs', 'config.lua'] + RUNTIME[:-1]:
            tar.add(SERVER / name, arcname='server/' + name)
        for name in ['index.php', 'client-release.json']:
            tar.add(WEB / name, arcname='web/' + name)
    (PREP / 'backup-path.txt').write_text(str(backup) + '\n')
    # Keep configuration private and preserve every unrelated setting.
    config = (SERVER / 'config.lua').read_text()
    pattern = r'(?m)^\s*itemRarityLootChance\s*=.*$'
    replacement = 'itemRarityLootChance = 1000'
    config = re.sub(pattern, replacement, config) if re.search(pattern, config) else config.rstrip() + '\n\n' + replacement + '\n'
    staged_config = PREP / 'config-v44.lua'
    staged_config.write_text(config)
    os.chmod(staged_config, 0o600)
    run(['/opt/antigas-stability-20260927/lua52_runner', '--syntax-only', str(staged_config)])
    note('backup_files_complete', backup=str(backup))
    run(['systemctl', 'stop', 'imperium772.service'], timeout=300)
    assert subprocess.run(['systemctl', 'is-active', '--quiet', 'imperium772.service']).returncode != 0, 'Service must be stopped before install'
    note('service_stopped_after_shutdown', residual_termination=(PREP / 'post-shutdown-residual-termination.txt').exists())
    installed = False
    try:
        # Snapshot after the graceful player/world save. Credentials remain in env.
        with (backup / 'database.sql.gz').open('wb') as target:
            process = subprocess.Popen(['mariadb-dump', '--protocol=socket', '--user=root',
                '--single-transaction', '--quick', '--routines', '--events', '--triggers',
                os.environ['TFS_DB_NAME']], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            with gzip.GzipFile(fileobj=target, mode='wb') as zipped:
                shutil.copyfileobj(process.stdout, zipped)
            error = process.stderr.read()
            assert process.wait(timeout=60) == 0, 'Database backup failed'
        assert (backup / 'database.sql.gz').stat().st_size > 1000, 'Database backup unexpectedly small'
        note('database_snapshot_complete', bytes=(backup / 'database.sql.gz').stat().st_size)
        server_stat = (SERVER / 'tfs').stat()
        atomic(PREP / 'build/tfs', SERVER / 'tfs')
        installed = True
        for name in RUNTIME:
            atomic(PREP / 'runtime' / name, SERVER / name, server_stat.st_uid, server_stat.st_gid, 0o640)
        atomic(staged_config, SERVER / 'config.lua')
        note('server_installed', sha256=digest(SERVER / 'tfs'), loot_chance=1000)
    except Exception:
        # No new binary has been started: restoring files is safe and needs no DB rollback.
        if installed:
            with tarfile.open(backup / 'files-before.tar.gz') as tar:
                for name in ['tfs', 'config.lua'] + RUNTIME[:-1]:
                    member = tar.getmember('server/' + name)
                    target = SERVER / name
                    temporary = PREP / 'restore-one-file'
                    with tar.extractfile(member) as stream, temporary.open('wb') as out:
                        shutil.copyfileobj(stream, out)
                    atomic(temporary, target, member.uid, member.gid, member.mode)
            if (SERVER / RUNTIME[-1]).exists():
                (SERVER / RUNTIME[-1]).unlink()
        run(['systemctl', 'start', 'imperium772.service'], timeout=60)
        note('prestart_failure_original_service_restored')
        raise
    run(['systemctl', 'start', 'imperium772.service'], timeout=60)
    note('new_service_start_requested')
    # Never revert to a binary that cannot read tag 39 after this point.

def website():
    live = json.loads((PREP / 'rarity-live-result.json').read_text())
    assert live['status'] == 'passed' and live['cleanup'], 'Production smoke must pass'
    assert digest(PREP / CLIENT) == CLIENT_HASH
    release = json.loads((PREP / 'client-release.json').read_text())
    assert release['version'] == 44 and release['sha256'] == CLIENT_HASH
    expected = json.loads((PREP / 'web-baseline.json').read_text())
    for name, checksum in expected.items():
        assert digest(WEB / name) == checksum, 'Public files changed during review: ' + name
    run(['php', '-l', str(PREP / 'index.php')])
    owner = (WEB / 'client-release.json').stat()
    atomic(PREP / CLIENT, WEB / CLIENT, owner.st_uid, owner.st_gid, 0o644)
    atomic(PREP / 'index.php', WEB / 'index.php')
    atomic(PREP / 'client-release.json', WEB / 'client-release.json')
    note('client_and_download_published', version=44, sha256=CLIENT_HASH)

if sys.argv[1:] == ['server']:
    server()
elif sys.argv[1:] == ['website']:
    website()
else:
    raise SystemExit('Select server or website explicitly')
