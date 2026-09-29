"""Guarded v47 server and client release deployment.

Run backup, install, then website on the authorized production host. The
server is stopped gracefully; no force-kill or database rewind is performed.
"""
import datetime
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import tarfile
import time

PREP = Path('/opt/antigas-rarity-container-v47-20260928')
SERVER = Path('/opt/imperium772/server')
WEB = Path('/var/www/otclient')
SERVICE = 'imperium772.service'
OLD_BINARY = '8cffd8a27e4750d8a0fa463d2e21d94bcb0306e2467eadb2035cc5518a551dd5'
NEW_BINARY = '747d954b2ff080f8b284912552a60a09963700b8e3a7a275e2f9e36cc0728000'
CLIENT = 'Antigas-7.4-Client-v47.zip'
CLIENT_SHA256 = 'a831e6280927b28d557fe41909fe0046970c93b016f2d3bbc5372fbf76e64c11'
WEB_BASELINE = {
    'index.php': 'd11910b140e314efbaac11885a0a6a8e3411703bc2a50e77ad25c45cb2b4dde5',
    'client-release.json': '7a215320e55254e1157ad7b53a90b7e76a6f669e497c4ee550568db2d9003f71',
    'Antigas-7.4-Client-v46.zip': '5b87c70945a1fbc6cd4228f1d4f4b0f30c6ca2c369c88f3bab28a6ca8b6f2fc4',
}


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def note(event, **fields):
    record = {'time': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'event': event, **fields}
    with (PREP / 'deployment.jsonl').open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(record) + '\n')
    print(json.dumps(record), flush=True)


def service_state():
    output = run(['systemctl', 'show', SERVICE,
                  '--property=MainPID,ActiveState,Result,NRestarts'],
                 capture_output=True, text=True).stdout
    return dict(line.split('=', 1) for line in output.splitlines())


def check_ports(timeout=1):
    for port in (7173, 7174):
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=timeout):
                pass
        except OSError:
            return False
    return True


def wait_for_ports(timeout=90):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = service_state()
        if state['MainPID'] != '0' and state['ActiveState'] == 'active' and check_ports():
            return state
        time.sleep(0.5)
    raise TimeoutError('Service did not become active with both game ports open')


def preflight_build():
    assert digest(PREP / 'tfs') == NEW_BINARY, 'Staged server binary checksum mismatch'
    assert '100% tests passed, 0 tests failed out of 1' in (PREP / 'core-test.log').read_text()
    assert digest(PREP / 'incoming' / CLIENT) == CLIENT_SHA256, 'Client ZIP checksum mismatch'
    release = json.loads((PREP / 'incoming' / 'client-release.json').read_text())
    assert release.get('version') == 47 and release.get('name') == 'Antigas 7.4 v47'
    assert str(release.get('sha256', '')).lower() == CLIENT_SHA256


def preflight_baseline():
    assert digest(SERVER / 'tfs') == OLD_BINARY, 'Production binary changed after review'
    for name, expected in WEB_BASELINE.items():
        assert digest(WEB / name) == expected, 'Public file changed during review: ' + name
    target = WEB / CLIENT
    assert not target.exists(), 'The v47 download path already exists; inspect it before continuing'


def database_snapshot(path):
    database = os.environ.get('TFS_DB_NAME')
    saved_name = PREP / 'database-name.txt'
    if not database and saved_name.exists():
        database = saved_name.read_text(encoding='utf-8').strip()
    if not database:
        pid = service_state()['MainPID']
        if pid != '0':
            for value in Path('/proc', pid, 'environ').read_bytes().split(b'\0'):
                if value.startswith(b'TFS_DB_NAME='):
                    database = os.fsdecode(value.partition(b'=')[2])
                    saved_name.write_text(database + '\n', encoding='utf-8')
                    os.chmod(saved_name, 0o600)
                    break
    assert database, 'The existing private TFS_DB_NAME service environment is required'
    with path.open('wb') as output:
        process = subprocess.Popen([
            'mariadb-dump', '--protocol=socket', '--user=root', '--single-transaction',
            '--quick', '--routines', '--events', '--triggers', database
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with gzip.GzipFile(fileobj=output, mode='wb') as zipped:
            shutil.copyfileobj(process.stdout, zipped)
        error = process.stderr.read()
        assert process.wait(timeout=120) == 0, 'Database backup failed; inspect private diagnostics'
    os.chmod(path, 0o600)
    assert path.stat().st_size > 1000, 'Database snapshot is unexpectedly small'
    run(['gzip', '-t', str(path)])


def atomic_copy(source, target, uid=None, gid=None, mode=None):
    previous = target.stat() if target.exists() else None
    owner = previous.st_uid if previous else (uid if uid is not None else 0)
    group = previous.st_gid if previous else (gid if gid is not None else 0)
    permissions = mode if mode is not None else (previous.st_mode & 0o777 if previous else 0o644)
    temporary = target.with_name(target.name + '.v47-new')
    shutil.copyfile(source, temporary)
    os.chmod(temporary, permissions)
    os.chown(temporary, owner, group)
    with temporary.open('rb') as stream:
        os.fsync(stream.fileno())
    os.replace(temporary, target)


def backup():
    preflight_build()
    preflight_baseline()
    assert not (PREP / 'backup-path.txt').exists(), 'A deployment backup already exists; inspect it first'
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder = Path('/root/antigas-backups') / ('rarity-container-v47-' + stamp)
    folder.mkdir(parents=True, mode=0o700)
    os.chmod(folder, 0o700)
    with tarfile.open(folder / 'files-before.tar.gz', 'w:gz') as archive:
        for name in ('tfs', 'config.lua'):
            archive.add(SERVER / name, arcname='server/' + name)
        for name in ('index.php', 'client-release.json'):
            archive.add(WEB / name, arcname='web/' + name)
    database_snapshot(folder / 'database-before-stop.sql.gz')
    (PREP / 'backup-path.txt').write_text(str(folder) + '\n', encoding='utf-8')
    note('private_backup_complete', backup=str(folder))


def clean_stop(started):
    run(['systemctl', 'stop', '--no-block', SERVICE])
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        state = service_state()
        if state['MainPID'] == '0' and state['ActiveState'] == 'inactive':
            break
        time.sleep(0.25)
    else:
        raise TimeoutError('Graceful shutdown is still pending; do not replace the running binary')
    journal = run(['journalctl', '-u', SERVICE, '--since', started, '--no-pager', '-o', 'cat'],
                  capture_output=True, text=True).stdout
    (PREP / 'shutdown.log').write_text(journal, encoding='utf-8')
    state = service_state()
    assert state['Result'] == 'success' and re.search(r'Shutting down\.+\s*done!', journal), \
        'Clean game shutdown was not confirmed'


def restore_and_start(old_binary):
    state = service_state()
    if state['MainPID'] != '0':
        marker = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        clean_stop(marker)
    stat = (SERVER / 'tfs').stat()
    atomic_copy(old_binary, SERVER / 'tfs', stat.st_uid, stat.st_gid, stat.st_mode & 0o777)
    run(['systemctl', 'start', SERVICE], timeout=60)
    wait_for_ports()


def install():
    preflight_build()
    preflight_baseline()
    backup_path = Path((PREP / 'backup-path.txt').read_text(encoding='utf-8').strip())
    assert backup_path.parent == Path('/root/antigas-backups')
    assert backup_path.name.startswith('rarity-container-v47-')
    old_binary = PREP / 'previous-tfs'
    with tarfile.open(backup_path / 'files-before.tar.gz') as archive:
        member = archive.getmember('server/tfs')
        with archive.extractfile(member) as source, old_binary.open('wb') as output:
            shutil.copyfileobj(source, output)
    os.chmod(old_binary, 0o700)
    assert digest(old_binary) == OLD_BINARY, 'Private previous-binary backup does not match baseline'

    started = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    try:
        clean_stop(started)
        note('clean_shutdown_complete')
        database_snapshot(backup_path / 'database-after-stop.sql.gz')
        stat = (SERVER / 'tfs').stat()
        atomic_copy(PREP / 'tfs', SERVER / 'tfs', stat.st_uid, stat.st_gid, stat.st_mode & 0o777)
        assert digest(SERVER / 'tfs') == NEW_BINARY
        note('candidate_binary_installed', sha256=NEW_BINARY)
        run(['systemctl', 'start', SERVICE], timeout=60)
        state = wait_for_ports()
        assert state['NRestarts'] == '0', 'Service restarted unexpectedly during startup'
        note('server_healthy', main_pid=state['MainPID'], ports=[7173, 7174], sha256=NEW_BINARY)
    except Exception:
        state = service_state()
        if state['MainPID'] != '0':
            marker = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            try:
                clean_stop(marker)
            except Exception:
                note('candidate_start_uncertain_manual_review_required', state=service_state())
                raise
            state = service_state()
        if state['MainPID'] == '0':
            restore_and_start(old_binary)
            note('candidate_failed_previous_binary_restored')
        else:
            note('candidate_start_uncertain_manual_review_required', state=state)
        raise


def website():
    preflight_build()
    assert digest(SERVER / 'tfs') == NEW_BINARY, 'Expected v47 server must be active before publishing its client'
    state = wait_for_ports(timeout=1)
    assert state['NRestarts'] == '0'
    for name in ('index.php', 'client-release.json'):
        current = digest(WEB / name)
        intended = digest(PREP / 'incoming' / name)
        assert current in (WEB_BASELINE[name], intended), 'Public file changed before website publication: ' + name
    assert digest(WEB / 'Antigas-7.4-Client-v46.zip') == WEB_BASELINE['Antigas-7.4-Client-v46.zip']
    run(['php', '-l', str(PREP / 'incoming' / 'index.php')])
    owner = (WEB / 'client-release.json').stat()
    target = WEB / CLIENT
    if target.exists():
        assert digest(target) == CLIENT_SHA256, 'A different v47 file already occupies the release path'
    else:
        atomic_copy(PREP / 'incoming' / CLIENT, target, owner.st_uid, owner.st_gid, 0o644)
    atomic_copy(PREP / 'incoming' / 'index.php', WEB / 'index.php')
    atomic_copy(PREP / 'incoming' / 'client-release.json', WEB / 'client-release.json')
    assert digest(target) == CLIENT_SHA256
    note('client_release_published', version=47, sha256=CLIENT_SHA256)


if __name__ == '__main__':
    import sys
    phases = {'backup': backup, 'install': install, 'website': website}
    if len(sys.argv) != 3 or sys.argv[2] != '--confirm-production-deploy':
        raise SystemExit('Legacy production script: pass a phase and --confirm-production-deploy explicitly')
    if sys.argv[1] not in phases:
        raise SystemExit('Select exactly one phase: backup, install, or website')
    phases[sys.argv[1]]()
