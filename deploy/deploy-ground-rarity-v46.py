"""Guarded v46 deployment phases; run on the authorized principal VPS.

Usage: backup, install, website. Stop the service between backup and install,
checking its save journal explicitly. No shutdown force-kill is automated here.
Credentials are inherited from the existing private service environment.
"""
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

PREP = Path('/opt/antigas-groundrarity-20260928')
SERVER = Path('/opt/imperium772/server')
WEB = Path('/var/www/otclient')
SERVICE = 'imperium772.service'
OLD_BINARY = 'e147af97d53b6867e777e5428148c337a2c9648ab0ed777e843d9c22cd8f3208'
CLIENT = 'Antigas-7.4-Client-v46.zip'
RUNTIME = ['data/creaturescripts/scripts/login.lua']


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
    temporary = target.with_name(target.name + '.v46-new')
    shutil.copyfile(source, temporary)
    os.chmod(temporary, mode if mode is not None else previous.st_mode & 0o777)
    os.chown(temporary, uid if uid is not None else previous.st_uid,
             gid if gid is not None else previous.st_gid)
    with temporary.open('rb') as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, target)


def baseline():
    assert digest(SERVER / 'tfs') == OLD_BINARY, 'Production binary changed during review'
    expected = json.loads((PREP / 'runtime-baseline.json').read_text())
    for name, checksum in expected.items():
        path = SERVER / name
        assert (digest(path) if path.exists() else None) == checksum, 'Runtime changed: ' + name


def preflight():
    assert (PREP / 'build.exit').read_text().strip() == '0', 'Build must pass'
    assert (PREP / 'core-test.exit').read_text().strip() == '0', 'Core tests must pass'
    binary = json.loads((PREP / 'binary-manifest.json').read_text())
    assert digest(PREP / 'tfs') == binary['sha256'], 'Staged binary changed'
    for name, checksum in json.loads((PREP / 'runtime-manifest.json').read_text()).items():
        assert digest(PREP / 'runtime' / name) == checksum, 'Staged runtime changed: ' + name
    release = json.loads((PREP / 'client-release.json').read_text())
    assert release['version'] == 46 and release['sha256'] == digest(PREP / CLIENT), 'Invalid client package'


def database_snapshot(target):
    with target.open('wb') as stream:
        process = subprocess.Popen(['mariadb-dump', '--protocol=socket', '--user=root',
            '--single-transaction', '--quick', '--routines', '--events', '--triggers',
            os.environ['TFS_DB_NAME']], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with gzip.GzipFile(fileobj=stream, mode='wb') as zipped:
            shutil.copyfileobj(process.stdout, zipped)
        error = process.stderr.read()
        assert process.wait(timeout=60) == 0, 'Database backup failed; inspect private diagnostics'
    os.chmod(target, 0o600)
    assert target.stat().st_size > 1000, 'Database backup unexpectedly small'
    run(['gzip', '-t', str(target)])


def backup():
    preflight()
    baseline()
    assert not (PREP / 'backup-path.txt').exists(), 'Deployment backup already exists; inspect before repeating'
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder = Path('/root/antigas-backups') / ('groundrarity-v46-' + stamp)
    folder.mkdir(parents=True, mode=0o700)
    os.chmod(folder, 0o700)
    with tarfile.open(folder / 'files-before.tar.gz', 'w:gz') as tar:
        for name in ['tfs', 'config.lua'] + RUNTIME:
            if (SERVER / name).exists():
                tar.add(SERVER / name, arcname='server/' + name)
        for name in ['index.php', 'client-release.json']:
            tar.add(WEB / name, arcname='web/' + name)
    database_snapshot(folder / 'database-before-stop.sql.gz')
    (PREP / 'backup-path.txt').write_text(str(folder) + '\n')
    # The versioned ZIP can exist before the manifest switches to the release.
    owner = (WEB / 'client-release.json').stat()
    atomic(PREP / CLIENT, WEB / CLIENT, owner.st_uid, owner.st_gid, 0o644)
    note('private_backup_complete', backup=str(folder))


def install():
    preflight()
    baseline()
    state = run(['systemctl', 'show', SERVICE, '--property=MainPID', '--value'], capture_output=True, text=True).stdout.strip()
    assert state == '0', 'Main process must have finished shutdown before installation'
    assert subprocess.run(['systemctl', 'is-active', '--quiet', SERVICE]).returncode != 0
    folder = Path((PREP / 'backup-path.txt').read_text().strip())
    assert folder.parent == Path('/root/antigas-backups') and folder.name.startswith('groundrarity-v46-')
    assert (folder / 'files-before.tar.gz').is_file()
    try:
        database_snapshot(folder / 'database-after-stop.sql.gz')
        stat = (SERVER / 'tfs').stat()
        atomic(PREP / 'tfs', SERVER / 'tfs')
        for name in RUNTIME:
            atomic(PREP / 'runtime' / name, SERVER / name, stat.st_uid, stat.st_gid, 0o640)
        note('server_installed', sha256=digest(SERVER / 'tfs'))
    except Exception:
        # No new code has started. Restore only changed files, never rewind DB state.
        expected = json.loads((PREP / 'runtime-baseline.json').read_text())
        with tarfile.open(folder / 'files-before.tar.gz') as tar:
            for name in ['tfs'] + RUNTIME:
                target = SERVER / name
                if name in expected and expected[name] is None:
                    if target.exists():
                        target.unlink()
                    continue
                member = tar.getmember('server/' + name)
                temporary = PREP / 'restore-one-file'
                with tar.extractfile(member) as source, temporary.open('wb') as out:
                    shutil.copyfileobj(source, out)
                atomic(temporary, target, member.uid, member.gid, member.mode)
        run(['systemctl', 'start', SERVICE], timeout=60)
        note('prestart_failure_v45_restored')
        raise
    run(['systemctl', 'start', SERVICE], timeout=60)
    note('v46_start_requested')


def website():
    preflight()
    for name in ('ground-rarity-live-result.json', 'loot-live-result.json', 'rarity-live-result.json'):
        live = json.loads((PREP / name).read_text())
        assert live['status'] == 'passed' and live['cleanup'], 'Production smoke must pass: ' + name
    expected = json.loads((PREP / 'web-baseline.json').read_text())
    for name, checksum in expected.items():
        assert digest(WEB / name) == checksum, 'Public file changed during review: ' + name
    run(['php', '-l', str(PREP / 'index.php')])
    owner = (WEB / 'client-release.json').stat()
    atomic(PREP / CLIENT, WEB / CLIENT, owner.st_uid, owner.st_gid, 0o644)
    atomic(PREP / 'index.php', WEB / 'index.php')
    atomic(PREP / 'client-release.json', WEB / 'client-release.json')
    note('client_and_download_published', version=46, sha256=digest(PREP / CLIENT))


if __name__ == '__main__':
    phases = {'backup': backup, 'install': install, 'website': website}
    if len(sys.argv) != 3 or sys.argv[2] != '--confirm-production-deploy':
        raise SystemExit('Legacy production script: pass a phase and --confirm-production-deploy explicitly')
    if sys.argv[1] not in phases:
        raise SystemExit('Select backup, install or website')
    phases[sys.argv[1]]()
