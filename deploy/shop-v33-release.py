"""Build and publish Antigas client v33 from the verified public v32 ZIP.

Only the Shop's OTUI/Lua and APP_VERSION may differ from v32. The live game
service, database, executable, sprites, products and protocol are untouched.

python3 shop-v33-release.py package STAGE CHANGES --web-root WEB
python3 shop-v33-release.py publish STAGE CHANGES --web-root WEB
"""

import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import zipfile


OLD = 'Antigas-7.4-Client-v32.zip'
NEW = 'Antigas-7.4-Client-v33.zip'
BASE_SHA = 'c0fe853eaec3918a34418ec7f3f6f20925a80a3f5fafeccd5b3c1ee11587d98a'
FILES = ('modules/game_shop/shop.otui', 'modules/game_shop/shop.lua')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_base(web, require_manifest=False):
    assert digest(web / OLD) == BASE_SHA, 'Public v32 ZIP changed'
    if require_manifest:
        manifest = json.loads((web / 'client-release.json').read_text())
        assert manifest['version'] == 32 and manifest['sha256'] == BASE_SHA, \
            'Public release manifest changed'
        assert not (web / NEW).exists(), 'v33 already exists; do not overwrite'


def check_lua(path):
    if os.name == 'nt':
        # The isolated Windows OTClient runtime QA validates this file as well.
        return
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


def changes(web, root):
    changed = {name: (root / name).read_bytes() for name in FILES}
    assert b'id: price' in changed[FILES[0]]
    assert b'id: spriteArea' in changed[FILES[0]]
    assert b'offer.price:setText' in changed[FILES[1]]
    check_lua(root / FILES[1])
    with zipfile.ZipFile(web / OLD) as source:
        init = source.read('init.lua')
        assert init.count(b'APP_VERSION = 32') == 1
        changed['init.lua'] = init.replace(b'APP_VERSION = 32', b'APP_VERSION = 33')
        assert set(changed) <= set(source.namelist())
    return changed


def check_package(web, stage, root):
    changed = changes(web, root)
    with zipfile.ZipFile(stage / NEW) as target, zipfile.ZipFile(web / OLD) as base:
        assert target.namelist() == base.namelist(), 'Archive entries changed'
        assert len(set(target.namelist())) == len(target.namelist()), 'Duplicate ZIP entries'
        assert target.testzip() is None, 'Corrupt ZIP'
        for name in target.namelist():
            assert target.read(name) == changed.get(name, base.read(name)), \
                f'Unexpected file change: {name}'
    manifest = json.loads((stage / 'client-release.json').read_text())
    assert manifest['version'] == 33 and manifest['sha256'] == digest(stage / NEW)


def package(web, stage, root):
    check_base(web)
    changed = changes(web, root)
    assert not (stage / NEW).exists() and not (stage / 'client-release.json').exists()
    with zipfile.ZipFile(web / OLD) as source, \
            zipfile.ZipFile(stage / NEW, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        for entry in source.infolist():
            target.writestr(entry, changed.get(entry.filename, source.read(entry.filename)))
    manifest = dict(version=33, name='Antigas 7.4 v33', sha256=digest(stage / NEW))
    with (stage / 'client-release.json').open('x') as handle:
        json.dump(manifest, handle, indent=2)
        handle.write('\n')
    check_package(web, stage, root)
    print('PASS: v33 ZIP integrity; only Shop OTUI/Lua and init version changed; SHA256',
          manifest['sha256'], flush=True)


def atomic(path, data, reference):
    temp = path.with_name(path.name + '.v33-new')
    with temp.open('xb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.chmod(temp, reference.st_mode & 0o777)
    os.chown(temp, reference.st_uid, reference.st_gid)
    os.replace(temp, path)


def publish(web, stage, root):
    check_base(web, require_manifest=True)
    check_package(web, stage, root)
    index = web / 'index.php'
    original = index.read_bytes()
    assert original.count(OLD.encode()) == 1, 'Unexpected homepage download link'
    backup = stage / 'website-before'
    backup.mkdir()
    for name in ('index.php', 'client-release.json'):
        shutil.copy2(web / name, backup / name)
    atomic(web / NEW, (stage / NEW).read_bytes(), (web / OLD).stat())
    try:
        atomic(index, original.replace(OLD.encode(), NEW.encode()), index.stat())
        manifest = web / 'client-release.json'
        atomic(manifest, (stage / 'client-release.json').read_bytes(), manifest.stat())
    except Exception:
        for name in ('index.php', 'client-release.json'):
            target = web / name
            atomic(target, (backup / name).read_bytes(), target.stat())
        raise
    assert digest(web / NEW) == digest(stage / NEW)
    assert json.loads((web / 'client-release.json').read_text())['version'] == 33
    assert index.read_bytes().count(NEW.encode()) == 1
    print('PASS: website points to v33; v32 and website backups retained', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('package', 'publish'))
    parser.add_argument('stage', type=Path)
    parser.add_argument('changes', type=Path)
    parser.add_argument('--web-root', type=Path, default=Path('/var/www/otclient'))
    args = parser.parse_args()
    globals()[args.action](args.web_root.resolve(), args.stage.resolve(),
                           args.changes.resolve())
