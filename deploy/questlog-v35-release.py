"""Scoped, reversible Quest Log release. No database migration or reward changes.

prepare STAGE --workspace ROOT; deploy/package/publish STAGE on the VPS.
package also works on Windows with --web-root containing the verified v34 ZIP.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import tarfile
import xml.etree.ElementTree as ET
import zipfile

OLD, NEW = 'Antigas-7.4-Client-v34.zip', 'Antigas-7.4-Client-v35.zip'
BASE_SHA = '8a7cae4c7d70840e9b85ec351540fa674e6264989ce063592167d2b01d73ee5c'
SERVER = Path('/opt/imperium772/server')
CLIENT = ('modules/game_questlog/questlog.lua', 'modules/game_questlog/questlog.otui',
          'modules/game_questlog/questlog.otmod', 'modules/game_playerbars/playerbars.lua',
          'modules/game_playerbars/playerbars.otui')
SERVER_FILES = ('data/creaturescripts/creaturescripts.xml', 'data/creaturescripts/scripts/login.lua',
                'data/creaturescripts/scripts/questlog.lua', 'data/lib/custom/questCatalog.lua')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def normalized(data):
    return data.replace(b'\r\n', b'\n')

def prepare(stage, workspace):
    repo = workspace / 'Servidor/TFS'
    stage.mkdir(exist_ok=False)
    for name in SERVER_FILES:
        target = stage / 'new' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo / name, target)
    for name in SERVER_FILES[:2]:
        target = stage / 'base' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=repo))
    for name in CLIENT:
        target = stage / 'client' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(workspace / 'Cliente' / name, target)
    for name in ('tests/questlog-tests.lua', 'tests/questlog-live.py', 'deploy/questlog-v35-release.py'):
        shutil.copy2(repo / name, stage / Path(name).name)
    sources = [repo / 'data/world/map.otbm', repo / 'data/items/items.srv']
    sources += sorted((repo / 'data/npc').rglob('*.npc')) + sorted((repo / 'data/npc').rglob('*.ndb'))
    fingerprints = {p.relative_to(repo).as_posix(): hashlib.sha256(
        p.read_bytes() if p.suffix == '.otbm' else normalized(p.read_bytes())).hexdigest() for p in sources}
    (stage / 'sources.json').write_text(json.dumps(fingerprints, indent=2))
    archive = stage.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
        for path in sorted(stage.rglob('*')):
            if path.is_file(): z.write(path, path.relative_to(stage).as_posix())
    print('Prepared', archive, digest(archive), flush=True)

def lua_test(stage):
    root = stage / 'new'
    core = root / 'data/lib/core/json.lua'
    core.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SERVER / 'data/lib/core/json.lua', core)
    lib = ctypes.CDLL('libluajit-5.1.so.2')
    lib.luaL_newstate.restype = ctypes.c_void_p
    for func in ('luaL_openlibs', 'lua_close'): getattr(lib, func).argtypes = [ctypes.c_void_p]
    lib.luaL_loadfile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
    lib.lua_pcall.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    lib.lua_settop.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.lua_tolstring.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    lib.lua_tolstring.restype = ctypes.c_char_p
    state, previous = lib.luaL_newstate(), Path.cwd()
    try:
        lib.luaL_openlibs(state)
        os.chdir(root)
        for path in list(root.rglob('*.lua')) + list((stage / 'client').rglob('*.lua')):
            if lib.luaL_loadfile(state, str(path).encode()):
                raise RuntimeError(lib.lua_tolstring(state, -1, None).decode())
            lib.lua_settop(state, 0)
        if lib.luaL_loadfile(state, str(stage / 'questlog-tests.lua').encode()) or lib.lua_pcall(state, 0, 0, 0):
            raise RuntimeError(lib.lua_tolstring(state, -1, None).decode())
    finally:
        os.chdir(previous)
        lib.lua_close(state)

def atomic(path, data, reference):
    temp = path.with_name(path.name + '.v35-new')
    with temp.open('xb') as handle:
        handle.write(data); handle.flush(); os.fsync(handle.fileno())
    os.chmod(temp, reference.st_mode & 0o777)
    os.chown(temp, reference.st_uid, reference.st_gid)
    os.replace(temp, path)

def deploy(stage):
    for name in SERVER_FILES[:2]:
        assert normalized((stage / 'base' / name).read_bytes()) == normalized((SERVER / name).read_bytes()), 'Production drift: ' + name
    for name in SERVER_FILES[2:]:
        assert not (SERVER / name).exists(), 'Already deployed: ' + name
    for name, expected in json.loads((stage / 'sources.json').read_text()).items():
        data = (SERVER / name).read_bytes()
        if not name.endswith('.otbm'): data = normalized(data)
        assert hashlib.sha256(data).hexdigest() == expected, 'Catalog source drift: ' + name
    ET.parse(stage / 'new' / SERVER_FILES[0])
    lua_test(stage)
    backup = stage / 'server-before.tar.gz'
    with tarfile.open(backup, 'x:gz') as archive:
        for name in SERVER_FILES[:2]: archive.add(SERVER / name, arcname=name)
    owner = (SERVER / SERVER_FILES[1]).stat()
    try:
        for name in SERVER_FILES:
            atomic(SERVER / name, (stage / 'new' / name).read_bytes(), owner)
    except Exception:
        for name in SERVER_FILES[:2]: atomic(SERVER / name, (stage / 'base' / name).read_bytes(), owner)
        raise
    print('PASS server files deployed; source hashes and Lua tests passed; restart required. Backup:', backup, flush=True)

def reconcile_map(stage):
    """Accept map-only drift only after an independent production-map audit.

    The audit and builder must be the reviewed scripts copied into this stage.
    Never replace the production map or silently accept different quest rules.
    """
    audit = json.loads((stage / 'production-audit.json').read_text())
    assert digest(SERVER / 'data/world/map.otbm') == audit['map_sha256'], 'Map changed after audit'
    build = runpy.run_path(str(stage / 'build-quest-catalog.py'))['build']
    text = (stage / 'new/data/lib/custom/questCatalog.lua').read_text()
    expected = json.loads(text.split('[=[', 1)[1].rsplit(']=]', 1)[0])
    assert build(audit) == expected, 'Production quests differ; manual review required'
    path = stage / 'sources.json'
    sources = json.loads(path.read_text())
    for name, checksum in sources.items():
        if name != 'data/world/map.otbm':
            assert hashlib.sha256(normalized((SERVER / name).read_bytes())).hexdigest() == checksum, name
    shutil.copy2(path, stage / 'sources-before-map-audit.json')
    sources['data/world/map.otbm'] = audit['map_sha256']
    path.write_text(json.dumps(sources, indent=2))
    print('PASS independent map audit: every catalog entry identical; other sources identical; map untouched', flush=True)

def changes(web, stage):
    assert digest(web / OLD) == BASE_SHA, 'Public v34 changed'
    changed = {name: (stage / 'client' / name).read_bytes() for name in CLIENT}
    with zipfile.ZipFile(web / OLD) as source:
        init = source.read('init.lua')
        assert init.count(b'APP_VERSION = 34') == 1
        changed['init.lua'] = init.replace(b'APP_VERSION = 34', b'APP_VERSION = 35')
    return changed

def check_package(web, stage):
    changed = changes(web, stage)
    with zipfile.ZipFile(stage / NEW) as target, zipfile.ZipFile(web / OLD) as base:
        expected = base.namelist() + [name for name in CLIENT if name not in base.namelist()]
        assert target.namelist() == expected
        assert len(set(expected)) == len(expected) and target.testzip() is None
        for name in expected:
            assert target.read(name) == (changed[name] if name in changed else base.read(name)), name
    manifest = json.loads((stage / 'client-release.json').read_text())
    assert manifest['version'] == 35 and manifest['sha256'] == digest(stage / NEW)

def package(web, stage):
    changed = changes(web, stage)
    with zipfile.ZipFile(web / OLD) as source, zipfile.ZipFile(stage / NEW, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as target:
        for entry in source.infolist(): target.writestr(entry, changed.get(entry.filename, source.read(entry.filename)))
        for name in CLIENT:
            if name in source.namelist(): continue
            entry = zipfile.ZipInfo(name, (2026, 9, 27, 0, 0, 0))
            entry.create_system, entry.compress_type, entry.external_attr = 3, zipfile.ZIP_DEFLATED, 0o100644 << 16
            target.writestr(entry, changed[name])
    manifest = dict(version=35, name='Antigas 7.4 v35', sha256=digest(stage / NEW))
    with (stage / 'client-release.json').open('x') as handle: json.dump(manifest, handle, indent=2); handle.write('\n')
    check_package(web, stage)
    print('PASS package: only Quest Log, sidebar and version changed. SHA256', manifest['sha256'], flush=True)

def publish(web, stage):
    check_package(web, stage)
    assert json.loads((web / 'client-release.json').read_text())['version'] == 34
    assert not (web / NEW).exists()
    index = web / 'index.php'
    original = index.read_bytes()
    assert original.count(OLD.encode()) == 1
    backup = stage / 'website-before'; backup.mkdir()
    for name in ('index.php', 'client-release.json'): shutil.copy2(web / name, backup / name)
    atomic(web / NEW, (stage / NEW).read_bytes(), (web / OLD).stat())
    try:
        atomic(index, original.replace(OLD.encode(), NEW.encode()), index.stat())
        manifest = web / 'client-release.json'
        atomic(manifest, (stage / manifest.name).read_bytes(), manifest.stat())
    except Exception:
        for name in ('index.php', 'client-release.json'): atomic(web / name, (backup / name).read_bytes(), (web / name).stat())
        raise
    print('PASS website published v35; v34 and site backup preserved', flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('prepare', 'deploy', 'package', 'publish', 'test', 'reconcile-map'))
    parser.add_argument('stage', type=Path)
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--web-root', type=Path, default=Path('/var/www/otclient'))
    args = parser.parse_args(); stage = args.stage.resolve()
    if args.action == 'prepare': prepare(stage, args.workspace.resolve())
    elif args.action == 'deploy': deploy(stage)
    elif args.action == 'test': lua_test(stage)
    elif args.action == 'reconcile-map': reconcile_map(stage)
    else: globals()[args.action](args.web_root.resolve(), stage)
