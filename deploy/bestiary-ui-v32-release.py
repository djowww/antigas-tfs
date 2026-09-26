"""Publish only the reviewed Bestiary UI on top of the public v31 client.

Run on the website host: python3 bestiary-ui-v32-release.py package|publish STAGE
STAGE contains the three reviewed modules/game_wiki files, never a QA client.
No game-service restart or database access is performed.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import zipfile

WEB = Path('/var/www/otclient')
OLD = 'Antigas-7.4-Client-v31.zip'
NEW = 'Antigas-7.4-Client-v32.zip'
BASE_SHA = '5ef0fc7bdb282b926220c6412a167c0f41ce4be90351b5b7800bda308e8d99f3'
FILES = ('modules/game_wiki/wiki.lua', 'modules/game_wiki/wiki.otui', 'modules/game_wiki/creature.otui')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_base():
    manifest = json.loads((WEB / 'client-release.json').read_text())
    assert manifest['version'] == 31 and manifest['sha256'] == BASE_SHA, 'Public release changed'
    assert digest(WEB / OLD) == BASE_SHA, 'Base ZIP checksum mismatch'
    assert not (WEB / NEW).exists(), 'v32 already exists; do not overwrite'


def check_lua(path):
    lib = ctypes.CDLL('libluajit-5.1.so.2')
    lib.luaL_newstate.restype = ctypes.c_void_p
    lib.luaL_loadfile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    lib.lua_tolstring.restype = ctypes.c_char_p
    lib.lua_close.argtypes = [ctypes.c_void_p]
    state = lib.luaL_newstate()
    try:
        if lib.luaL_loadfile(state, str(path).encode()):
            raise RuntimeError(lib.lua_tolstring(state, -1, None).decode())
    finally:
        lib.lua_close(state)


def changes(stage):
    changed = {name: (stage / name).read_bytes() for name in FILES}
    with zipfile.ZipFile(WEB / OLD) as source:
        init = source.read('init.lua')
        assert init.count(b'APP_VERSION = 31') == 1
        changed['init.lua'] = init.replace(b'APP_VERSION = 31', b'APP_VERSION = 32')
    return changed


def check_package(stage):
    changed = changes(stage)
    with zipfile.ZipFile(stage / NEW) as target, zipfile.ZipFile(WEB / OLD) as base:
        assert target.namelist() == base.namelist(), 'Unexpected archive entries'
        assert len(set(target.namelist())) == len(target.namelist()), 'Duplicate ZIP entries'
        assert target.testzip() is None, 'Corrupt ZIP'
        assert set(changed) <= set(target.namelist())
        for name in target.namelist():
            assert target.read(name) == changed.get(name, base.read(name)), f'Unexpected change: {name}'
    manifest = json.loads((stage / 'client-release.json').read_text())
    assert manifest['version'] == 32 and manifest['sha256'] == digest(stage / NEW)


def package(stage):
    check_base()
    check_lua(stage / FILES[0])
    changed = changes(stage)
    with zipfile.ZipFile(WEB / OLD) as source, zipfile.ZipFile(stage / NEW, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        for entry in source.infolist():
            target.writestr(entry, changed.get(entry.filename, source.read(entry.filename)))
    manifest = dict(version=32, name='Antigas 7.4 v32', sha256=digest(stage / NEW))
    with (stage / 'client-release.json').open('x') as handle:
        json.dump(manifest, handle, indent=2)
        handle.write('\n')
    check_package(stage)
    print('PASS: v32 ZIP integrity; exactly 3 UI files + init version; SHA256', manifest['sha256'], flush=True)


def atomic(path, data, reference):
    temp = path.with_name(path.name + '.v32-new')
    with temp.open('xb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temp, reference.st_mode & 0o777)
    os.chown(temp, reference.st_uid, reference.st_gid)
    os.replace(temp, path)


def publish(stage):
    check_base()
    check_package(stage)
    index = WEB / 'index.php'
    original = index.read_bytes()
    assert original.count(OLD.encode()) == 1, 'Unexpected homepage link'
    backup = stage / 'website-before'
    backup.mkdir()
    for name in ('index.php', 'client-release.json'):
        shutil.copy2(WEB / name, backup / name)
    atomic(WEB / NEW, (stage / NEW).read_bytes(), (WEB / OLD).stat())
    try:
        atomic(index, original.replace(OLD.encode(), NEW.encode()), index.stat())
        manifest = WEB / 'client-release.json'
        atomic(manifest, (stage / 'client-release.json').read_bytes(), manifest.stat())
    except Exception:
        for name in ('index.php', 'client-release.json'):
            target = WEB / name
            # Recovery file stays in the protected staging directory as well.
            atomic(target, (backup / name).read_bytes(), target.stat())
        raise
    print('PASS: website points to v32; v31 and website backup retained', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('package', 'publish'))
    parser.add_argument('stage', type=Path)
    args = parser.parse_args()
    globals()[args.action](args.stage.resolve())
