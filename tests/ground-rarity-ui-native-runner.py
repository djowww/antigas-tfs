"""Launch native renderer against a disposable localhost-only silent stub.

The native client needs a C++ LocalPlayer for MapView. Beginning a dummy login
creates that object; the stub sends no game data and does not authenticate.
No real account, password, server connection, or installed settings are used.
"""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading

parser = argparse.ArgumentParser()
parser.add_argument('--archive', type=Path, required=True)
parser.add_argument('--target', type=Path, required=True)
parser.add_argument('--shipped', action='store_true')
args = parser.parse_args()
target = args.target.resolve()
stop = threading.Event()
listener = socket.socket()
listener.bind(('127.0.0.1', 0))
listener.listen(1)
listener.settimeout(0.2)
port = listener.getsockname()[1]
connections = []

def serve():
    while not stop.is_set():
        try:
            client, address = listener.accept()
        except socket.timeout:
            continue
        connections.append(address[0])
        client.settimeout(0.2)
        try:
            while not stop.is_set():
                try:
                    if not client.recv(4096):
                        break
                except socket.timeout:
                    continue
                except OSError:
                    break
        finally:
            client.close()

thread = threading.Thread(target=serve)
thread.start()
process = None
try:
    prepare = [sys.executable, str(Path(__file__).with_name('ground-rarity-ui-prepare.py')),
               '--archive', str(args.archive.resolve()), '--target', str(target),
               '--loopback-port', str(port)]
    if args.shipped:
        prepare.append('--shipped')
    subprocess.run(prepare, check=True, stdout=subprocess.DEVNULL)
    report_path = target / 'ground-rarity-ui-real-report.txt'
    report_path.write_text('', encoding='utf-8')
    env = os.environ.copy()
    for key, folder in [('APPDATA', 'appdata'), ('LOCALAPPDATA', 'localappdata'), ('USERPROFILE', 'userprofile')]:
        env[key] = str(target / 'qa-state' / folder)
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    process = subprocess.Popen([str(target / 'Antigas_gl.exe')], cwd=target, env=env, startupinfo=startup)
    exit_code = process.wait(timeout=20)
    report = report_path.read_text(encoding='utf-8')
    screenshot = target / 'qa-state/userprofile/AppData/Roaming/OTClientV8/otclientv8/ground-rarity-ui-native.png'
    result = {'exit_code': exit_code, 'report': report.strip(), 'screenshot': str(screenshot),
              'loopback_only': connections == ['127.0.0.1'], 'exact_shipped_modules': args.shipped}
    print(json.dumps(result, ensure_ascii=False))
    assert exit_code == 0 and 'PASS:' in report and 'FAIL:' not in report, 'Native fixture failed'
    assert screenshot.is_file() and screenshot.stat().st_size > 1000, 'Native frame was not captured'
    assert result['loopback_only'], 'Expected one isolated localhost connection'
finally:
    if process and process.poll() is None:
        process.kill()
        process.wait(timeout=5)
    stop.set()
    thread.join(timeout=2)
    listener.close()
