"""Package an explicitly supplied, complete Windows client; never copy user settings."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

def package(source, output):
    root = Path(__file__).resolve().parents[1]
    files = {}
    for directory in ('data', 'modules'):
        for p in (source / directory).rglob('*'):
            if p.is_file() and p.suffix.lower() not in ('.log', '.key', '.pem', '.bak'):
                files[p.relative_to(source).as_posix()] = p
    for name in ('Antigas_dx.exe', 'Antigas_gl.exe', 'd3dcompiler_46.dll', 'libEGL.dll', 'libGLESv2.dll'):
        p = source / name
        if not p.is_file():
            raise ValueError('Missing required client runtime: ' + name)
        files[name] = p
    if not any(k.endswith('.spr') for k in files) or not any(k.endswith('.dat') for k in files):
        raise ValueError('The supplied client must contain its DAT and SPR assets')
    for p in (root / 'deploy/client-current/modules').rglob('*'):
        if p.is_file():
            files['modules/' + p.relative_to(root / 'deploy/client-current/modules').as_posix()] = p
    files['init.lua'] = root / 'deploy/client-current/init.lua'
    files['NOTICE.md'] = root / 'NOTICE.md'
    # Root config.otml, remembered passwords, logs, updater and production launcher
    # are deliberately absent. The starter installs a fresh local public key.
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, p in sorted(files.items()):
            z.write(p, name)
        z.writestr('LEIA-ME-LOCAL.txt', 'Use START-LOCAL.cmd from the server repository.\nAccount: 1 / local123\nThis client is configured only for 127.0.0.1:17173.\n')
        # Last archive member: interrupted extraction cannot leave an early
        # executable mistaken for a completed bundled installation.
        z.writestr('.local-client-complete', 'local-v1\n')
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return {'url': 'https://github.com/djowww/tibia-7.4-a-classic-rpg-version/releases/download/local-test-v1/' + output.name,
            'sha256': digest, 'size': output.stat().st_size}

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    print(json.dumps(package(args.source, args.output), indent=2))
