"""Server-only hotfix for immediate rarity snapshots on map scroll (client v46).

Run backup, then install. Private database credentials come from the service
environment. Installation waits for a normal save/shutdown; it never force-kills.
"""
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
import time

PREP = Path('/opt/antigas-groundrarity-scroll-20260928')
SERVER = Path('/opt/imperium772/server')
SOURCE = Path('/opt/antigas-rarity-20260928/source')
SERVICE = 'imperium772.service'
OLD_BINARY = 'eceb3937795720583a724e46ef45715faca7b9adb865bccbdd183edce5929686'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def note(event, **fields):
    result = dict(time=datetime.datetime.now(datetime.timezone.utc).isoformat(), event=event, **fields)
    with (PREP / 'deployment.jsonl').open('a') as out:
        out.write(json.dumps(result) + '\n')
    print(json.dumps(result), flush=True)


def run(args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def state():
    output = run(['systemctl', 'show', SERVICE, '--property=MainPID,ActiveState,Result'],
                 capture_output=True, text=True).stdout
    return dict(line.split('=', 1) for line in output.splitlines())


def preflight():
    assert digest(SERVER / 'tfs') == OLD_BINARY, 'Production changed since review'
    for name in ('build.exit', 'core-test.exit'):
        assert (PREP / name).read_text().strip() == '0', 'Build and core tests must pass'
    assert digest(PREP / 'tfs') == json.loads((PREP / 'binary-manifest.json').read_text())['sha256']
    for name, expected in json.loads((PREP / 'source-manifest.json').read_text()).items():
        assert digest(SOURCE / name) == expected, 'Build source drift: ' + name


def database_snapshot(path):
    with path.open('wb') as target:
        process = subprocess.Popen(['mariadb-dump', '--protocol=socket', '--user=root',
            '--single-transaction', '--quick', '--routines', '--events', '--triggers',
            os.environ['TFS_DB_NAME']], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with gzip.GzipFile(fileobj=target, mode='wb') as compressed:
            shutil.copyfileobj(process.stdout, compressed)
        error = process.stderr.read()
        assert process.wait(timeout=60) == 0, 'Database backup failed; inspect private diagnostics'
    os.chmod(path, 0o600)
    assert path.stat().st_size > 1000
    run(['gzip', '-t', str(path)])


def replace_binary(source):
    previous = (SERVER / 'tfs').stat()
    temporary = SERVER / 'tfs.scroll-new'
    shutil.copyfile(source, temporary)
    os.chown(temporary, previous.st_uid, previous.st_gid)
    os.chmod(temporary, previous.st_mode & 0o777)
    with temporary.open('rb') as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, SERVER / 'tfs')


def backup():
    preflight()
    assert not (PREP / 'backup-path.txt').exists(), 'Backup already exists; inspect before repeating'
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    folder = Path('/root/antigas-backups') / ('groundrarity-scroll-' + stamp)
    folder.mkdir(mode=0o700)
    shutil.copyfile(SERVER / 'tfs', folder / 'tfs-v46')
    with tarfile.open(folder / 'files-before.tar.gz', 'w:gz') as archive:
        for name in ('tfs', 'config.lua'):
            archive.add(SERVER / name, arcname=name)
    database_snapshot(folder / 'database-before-stop.sql.gz')
    (PREP / 'backup-path.txt').write_text(str(folder) + '\n')
    note('private_backup_complete', backup=str(folder))


def install():
    preflight()
    folder = Path((PREP / 'backup-path.txt').read_text().strip())
    assert folder.parent == Path('/root/antigas-backups') and folder.name.startswith('groundrarity-scroll-')
    assert digest(folder / 'tfs-v46') == OLD_BINARY
    marker = PREP / 'shutdown-start.txt'
    current = state()
    if current['MainPID'] == '0' and current['ActiveState'] == 'inactive':
        assert marker.exists(), 'An earlier supervised stop must be recorded before resuming'
        started = marker.read_text().strip()
    else:
        started = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        marker.write_text(started + '\n')
        run(['systemctl', 'stop', '--no-block', SERVICE])
    deadline = time.monotonic() + 55
    while True:
        current = state()
        if current['MainPID'] == '0' and current['ActiveState'] == 'inactive':
            break
        assert time.monotonic() < deadline, 'Graceful stop still pending; inspect without forcing termination'
        time.sleep(0.25)
    journal = run(['journalctl', '-u', SERVICE, '--since', started, '--no-pager', '-o', 'cat'],
                  capture_output=True, text=True).stdout
    (PREP / 'shutdown.log').write_text(journal)
    assert current['Result'] == 'success' and re.search(r'Shutting down\.\.\.\s*done!', journal), 'Clean shutdown not confirmed'
    note('clean_shutdown_complete')
    try:
        database_snapshot(folder / 'database-after-stop.sql.gz')
        replace_binary(PREP / 'tfs')
        note('server_installed', sha256=digest(SERVER / 'tfs'))
    except Exception:
        replace_binary(folder / 'tfs-v46')
        run(['systemctl', 'start', SERVICE], timeout=30)
        note('prestart_failure_v46_restored')
        raise
    try:
        run(['systemctl', 'start', SERVICE], timeout=30)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        # Never overwrite a binary while an uncertain new process is running.
        if state()['MainPID'] == '0':
            replace_binary(folder / 'tfs-v46')
            run(['systemctl', 'start', SERVICE], timeout=30)
            note('startup_failure_v46_restored')
        else:
            note('startup_uncertain_manual_inspection_required')
        raise
    note('hotfix_start_requested', client_version=46)


if len(sys.argv) != 2 or sys.argv[1] not in ('backup', 'install'):
    raise SystemExit('Select backup or install')
{'backup': backup, 'install': install}[sys.argv[1]]()
