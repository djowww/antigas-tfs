"""Scoped Bestiary deployment. Run on the VPS against the reviewed base/new archives."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import tarfile
import xml.etree.ElementTree as ET
import zipfile

SERVER = Path('/opt/imperium772/server')
WEB = Path('/var/www/otclient')


def lua_check(root, test):
    lib = ctypes.CDLL('libluajit-5.1.so.2')
    lib.luaL_newstate.restype = ctypes.c_void_p
    lib.luaL_openlibs.argtypes = [ctypes.c_void_p]
    lib.luaL_loadfile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.lua_pcall.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    lib.lua_tolstring.restype = ctypes.c_char_p
    lib.lua_settop.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.lua_close.argtypes = [ctypes.c_void_p]
    state = lib.luaL_newstate()
    previous = Path.cwd()
    try:
        lib.luaL_openlibs(state)
        os.chdir(root)
        for path in root.rglob('*.lua'):
            if lib.luaL_loadfile(state, str(path).encode()):
                raise RuntimeError(lib.lua_tolstring(state, -1, None).decode())
            lib.lua_settop(state, 0)
        if lib.luaL_loadfile(state, str(test).encode()) or lib.lua_pcall(state, 0, 0, 0):
            raise RuntimeError(lib.lua_tolstring(state, -1, None).decode())
    finally:
        os.chdir(previous)
        lib.lua_close(state)


def atomic(path, content, owner=None):
    temp = path.with_name(path.name + '.bestiary-new')
    with temp.open('xb') as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    reference = path.stat() if path.exists() else owner
    os.chmod(temp, (reference.st_mode & 0o777) if reference else 0o644)
    if reference:
        os.chown(temp, reference.st_uid, reference.st_gid)
    os.replace(temp, path)


def deploy(stage):
    base, new = stage / 'base', stage / 'new'
    for path in base.rglob('*'):
        if path.is_file():
            assert path.read_text() == (SERVER / path.relative_to(base)).read_text(), f'Production drift: {path}'
    library = SERVER / 'data/lib/lib.lua'
    original = library.read_text()
    old = "dofile('data/lib/custom/antigasTasks.lua')"
    assert original.count(old) == 1
    replacement = original.replace(old, "dofile('data/lib/custom/antigasBestiary.lua')")
    replacement = replacement.replace('-- GM-only task window and kill-counter configuration.', '-- Persistent per-character Bestiary kill progress.')
    for path in (new / 'data').rglob('*.xml'):
        ET.parse(path)
    lua_check(new, stage / 'bestiary-tests.lua')
    backup = stage / 'server-before.tar.gz'
    assert not backup.exists(), 'Deployment already started'
    with tarfile.open(backup, 'w:gz') as archive:
        archive.add(library, arcname='data/lib/lib.lua')
        for path in base.rglob('*'):
            if path.is_file():
                rel = path.relative_to(base)
                archive.add(SERVER / rel, arcname=str(rel))
    owner = library.stat()
    for path in (new / 'data').rglob('*'):
        if path.is_file():
            atomic(SERVER / path.relative_to(new), path.read_bytes(), owner)
    atomic(library, replacement.encode(), owner)
    # Retired task handlers are recoverable from server-before.tar.gz.
    for rel in ('data/lib/custom/antigasTasks.lua', 'data/talkactions/scripts/task.lua',
                'data/creaturescripts/scripts/antigas_task_kill.lua', 'data/creaturescripts/scripts/antigas_task_modal.lua'):
        (SERVER / rel).unlink()
    print('PASS server deployed; backup:', backup, flush=True)


def package(stage):
    old = WEB / 'Antigas-7.4-Client-v30.zip'
    assert json.loads((WEB / 'client-release.json').read_text())['version'] == 30
    patches = stage / 'new/deploy/client-bestiary'
    changed = {p.relative_to(patches).as_posix(): p.read_bytes() for p in (patches / 'modules').rglob('*') if p.is_file()}
    assert len(changed) == 5
    target = stage / 'Antigas-7.4-Client-v31.zip'
    assert not target.exists()
    with zipfile.ZipFile(old) as source:
        init = source.read('init.lua')
        assert init.count(b'APP_VERSION = 30') == 1
        changed['init.lua'] = init.replace(b'APP_VERSION = 30', b'APP_VERSION = 31')
        assert set(changed) <= set(source.namelist())
        with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as dest:
            for entry in source.infolist():
                dest.writestr(entry, changed.get(entry.filename, source.read(entry.filename)))
    with zipfile.ZipFile(target) as dest, zipfile.ZipFile(old) as source:
        assert dest.testzip() is None
        for name in dest.namelist():
            assert dest.read(name) == changed.get(name, source.read(name)), name
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    manifest = json.dumps(dict(version=31, name='Antigas 7.4 v31', sha256=digest), indent=2) + '\n'
    (stage / 'client-release.json').write_text(manifest)
    print('PASS package v31; only six reviewed files changed; SHA256', digest, flush=True)


def publish(stage):
    assert not (WEB / 'Antigas-7.4-Client-v31.zip').exists()
    index = WEB / 'index.php'
    old = index.read_bytes()
    assert old.count(b'Antigas-7.4-Client-v30.zip') == 1
    backup = stage / 'website-before'
    backup.mkdir()
    for name in ('index.php', 'client-release.json'):
        shutil.copy2(WEB / name, backup / name)
    target = WEB / 'Antigas-7.4-Client-v31.zip'
    atomic(target, (stage / target.name).read_bytes(), (WEB / 'Antigas-7.4-Client-v30.zip').stat())
    atomic(index, old.replace(b'Antigas-7.4-Client-v30.zip', b'Antigas-7.4-Client-v31.zip'))
    atomic(WEB / 'client-release.json', (stage / 'client-release.json').read_bytes())
    print('PASS website points to v31', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('deploy', 'package', 'publish'))
    parser.add_argument('stage', type=Path)
    args = parser.parse_args()
    globals()[args.action](args.stage.resolve())
