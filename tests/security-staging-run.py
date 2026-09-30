#!/usr/bin/env python3
"""Bounded isolated validation; run under systemd with independent ExecStopPost recovery."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from staging_safety import require_staging_target

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path('/opt/imperium772-staging/server')


def value(unit, prop):
    return subprocess.check_output(['systemctl', 'show', unit, '-p', prop, '--value'], text=True, timeout=10).strip()


def command(*args, timeout=50):
    subprocess.run(args, check=True, timeout=timeout)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-maintenance', action='store_true', required=True)
    parser.add_argument('--binary-sha256', required=True)
    parser.add_argument('--phase', choices=('full', 'ground'), default='full')
    args = parser.parse_args()
    require_staging_target()
    if not os.environ.get('INVOCATION_ID') or value('imperium772', 'ActiveState') != 'active':
        raise SystemExit('Requires systemd watchdog and active production before maintenance')
    if value('imperium772-staging', 'ActiveState') != 'inactive' or value('imperium772-staging', 'User') != 'tfs74-stage':
        raise SystemExit('Staging must be stopped and use its isolated OS account')
    if hashlib.sha256((STAGE / 'tfs').read_bytes()).hexdigest() != args.binary_sha256:
        raise SystemExit('Staging binary does not match tested CI artifact')
    for probe in ('rarity-live.py', 'ground-rarity-live.py'):
        command('python3', str(ROOT/'tests'/probe), '--self-test', timeout=20)
    report = {'started': time.time(), 'binary_sha256': args.binary_sha256, 'target_sessions': 50 if args.phase == 'full' else 1, 'status': 'failed', 'phases': [], 'samples': []}
    stop = threading.Event()
    def sample():
        while not stop.wait(2):
            try:
                pid = int(value('imperium772-staging', 'MainPID'))
                if not pid:
                    continue
                stat = Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()
                report['samples'].append({'time': time.time(), 'rss_mib': int(stat[21])*os.sysconf('SC_PAGE_SIZE')/1024**2, 'cpu_seconds': (int(stat[11])+int(stat[12]))/os.sysconf('SC_CLK_TCK')})
            except (OSError, ValueError, subprocess.SubprocessError):
                pass
    monitor = threading.Thread(target=sample, daemon=True)
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        command('systemctl', 'stop', 'imperium772')
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))
        if available < 2600*1024:
            raise RuntimeError('Not enough memory for isolated full-map test')
        command('systemctl', 'set-property', '--runtime', 'imperium772-staging', 'MemoryMax=3G')
        command('systemctl', 'start', 'imperium772-staging')
        monitor.start()
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            if value('imperium772-staging', 'ActiveState') != 'active':
                raise RuntimeError('Staging exited during startup')
            listeners = subprocess.check_output(['ss', '-ltn'], text=True)
            if '127.0.0.1:7175' in listeners and '127.0.0.1:7176' in listeners:
                if any(f'{host}:{port}' in listeners for host in ('0.0.0.0', '[::]', '*') for port in (7175, 7176)):
                    raise RuntimeError('Staging listener is publicly bound')
                break
            time.sleep(1)
        else:
            raise TimeoutError('Staging startup timeout')
        phases = [('rarity-live.py', [], 120), ('ground-rarity-live.py', [], 120),
                  ('load-test-50.py', ['--maintenance-window', '--players', '50'], 240)]
        if args.phase == 'ground':
            phases = [phases[1]]
        for name, extra, limit in phases:
            started = time.monotonic()
            log = ROOT / (name.removesuffix('.py') + '-validation.log')
            with log.open('w') as stream:
                env = dict(os.environ, ANTIGAS_REQUIRE_GROUND_LIFECYCLE='1')
                result = subprocess.run(['python3', str(ROOT/'tests'/name), *extra], env=env, stdout=stream, stderr=subprocess.STDOUT, timeout=limit)
            phase = {'name': name, 'exit_code': result.returncode, 'seconds': round(time.monotonic()-started, 2)}
            report['phases'].append(phase)
            print(json.dumps(phase), flush=True)
            if result.returncode:
                raise RuntimeError(f'{name} failed; see isolated validation log')
        report['status'] = 'passed'
    finally:
        stop.set()
        if monitor.is_alive():
            monitor.join(timeout=3)
        recovery = []
        for cmd in (['systemctl','stop','imperium772-staging'], ['systemctl','set-property','--runtime','imperium772-staging','MemoryMax=1G'], ['systemctl','start','imperium772']):
            try:
                recovery.append(subprocess.run(cmd, timeout=55).returncode)
            except (OSError, subprocess.TimeoutExpired):
                recovery.append(-1)
        report.update(ended=time.time(), recovery=recovery, production=value('imperium772','ActiveState'), staging=value('imperium772-staging','ActiveState'))
        if report['samples']:
            report['peak_rss_mib'] = max(s['rss_mib'] for s in report['samples'])
        report_name = 'security-validation-result.json' if args.phase == 'full' else 'security-validation-ground-result.json'
        (ROOT/report_name).write_text(json.dumps(report, indent=2))
        print(json.dumps({k:v for k,v in report.items() if k!='samples'}), flush=True)


if __name__ == '__main__':
    main()
