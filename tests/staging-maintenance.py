#!/usr/bin/env python3
"""Bounded offline staging run. Requires an explicitly approved maintenance window.

Run under a systemd transient service with RuntimeMaxSec=570 and an ExecStopPost
that stops staging, restores MemoryMax=1G, and starts production. This gives the
recovery an independent owner even if the test process is killed.
"""

if not __debug__:
    raise SystemExit('Python optimization (-O) disables validation assertions; refusing to run this tool.')

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
from staging_recovery import record_recovery, recover_staging
from staging_safety import pin_staging_rsa_public, require_isolated_staging_service, require_staging_target

ROOT = Path(__file__).resolve().parents[1]
STAGE = Path('/opt/imperium772-staging/server')
SAMPLES = []
STOP = threading.Event()

def run(*args, **kwargs):
    return subprocess.run(args, check=True, timeout=30, **kwargs)

def value(unit, prop):
    return subprocess.check_output(['systemctl', 'show', unit, '-p', prop, '--value'], text=True).strip()

def sample():
    while not STOP.wait(1):
        try:
            pid = int(value('imperium772-staging', 'MainPID'))
            if not pid:
                continue
            stat = Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()
            SAMPLES.append({'time': time.time(), 'rss_bytes': int(stat[21])*os.sysconf('SC_PAGE_SIZE'),
                            'cpu_seconds': (int(stat[11])+int(stat[12]))/os.sysconf('SC_CLK_TCK'),
                            'memory_current': int(value('imperium772-staging', 'MemoryCurrent'))})
        except (OSError, ValueError, subprocess.SubprocessError):
            pass

def interrupt(signum, frame):
    raise KeyboardInterrupt(f'signal {signum}')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--approved-maintenance', action='store_true', required=True)
    parser.add_argument('--skip-smoke', action='store_true', help='only after a passed smoke on this exact build')
    options = parser.parse_args()
    require_staging_target()
    assert value('imperium772', 'ActiveState') == 'active'
    assert value('imperium772-staging', 'ActiveState') == 'inactive'
    require_isolated_staging_service(value)
    assert os.environ.get('INVOCATION_ID'), 'Run under the documented systemd watchdog'
    pin_staging_rsa_public(os.environ, STAGE / 'staging-rsa-public.json')
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    monitor = threading.Thread(target=sample, daemon=True)
    result = {'started': time.time(), 'status': 'failed'}
    try:
        run('systemctl', 'stop', 'imperium772')
        available = int(next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines() if line.startswith('MemAvailable:')))
        assert available >= 2600*1024, 'Insufficient available memory even with production stopped'
        run('systemctl', 'set-property', '--runtime', 'imperium772-staging', 'MemoryMax=3G')
        run('systemctl', 'start', 'imperium772-staging')
        monitor.start()
        deadline = time.monotonic() + 90
        while True:
            assert value('imperium772-staging', 'ActiveState') == 'active', 'Staging failed during startup'
            listeners = subprocess.check_output(['ss', '-ltn'], text=True)
            if '127.0.0.1:7175' in listeners and '127.0.0.1:7176' in listeners:
                break
            if time.monotonic() >= deadline:
                raise TimeoutError('Staging did not open both loopback ports within 90 seconds')
            time.sleep(1)
        phases = [['--players', '50']] if options.skip_smoke else [['--smoke'], ['--players', '50']]
        for args in phases:
            subprocess.run(['python3', str(ROOT/'tests/load-test-50.py'), '--maintenance-window', *args], check=True, timeout=220)
        result['status'] = 'passed'
    finally:
        STOP.set()
        monitor.join(timeout=2) if monitor.is_alive() else None
        recovery = recover_staging()
        recovery_ok = record_recovery(result, recovery, ended=time.time(), samples=SAMPLES)
        if SAMPLES:
            result['peak_rss_mib'] = max(s['rss_bytes'] for s in SAMPLES)/1024**2
            result['peak_memory_mib'] = max(s['memory_current'] for s in SAMPLES)/1024**2
            result['cpu_seconds'] = SAMPLES[-1]['cpu_seconds'] - SAMPLES[0]['cpu_seconds']
        (ROOT/'load-result.json').write_text(json.dumps(result, indent=2))
        print(json.dumps({k:v for k,v in result.items() if k!='samples'}), flush=True)
    if not recovery_ok:
        raise SystemExit('Staging recovery failed; inspect the recovery fields in load-result.json')

if __name__ == '__main__':
    main()
