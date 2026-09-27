"""Scoped v36 journal release: stage, verify, deploy, then publish after live QA."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import zipfile

OLD, NEW = 'Antigas-7.4-Client-v35.zip', 'Antigas-7.4-Client-v36.zip'
BASE_SHA = 'e14704fa7d8ebf3020086866b17afa6d319052e0f638a37eb4117f6f93dfb4f3'
BASE_COMMIT = '30f552a976ab85a0382f7aaeeb5e462e4634f5c4'
SERVER = Path('/opt/imperium772/server')
ENDPOINT = 'data/creaturescripts/scripts/questlog.lua'
JOURNAL = 'data/lib/custom/questJournal.lua'
CATALOG = 'data/lib/custom/questCatalog.lua'
CLIENT = ('modules/game_questlog/questlog.lua', 'modules/game_questlog/questlog.otui')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def normalized(data):
    return data.replace(b'\r\n', b'\n')

def prepare(stage, workspace):
    repo=workspace/'Servidor/TFS'
    stage.mkdir(exist_ok=False)
    baseline=subprocess.check_output(['git','show',BASE_COMMIT+':'+ENDPOINT],cwd=repo)
    (stage/'baseline.json').write_text(json.dumps({ENDPOINT:digest(normalized(baseline)),
        CATALOG:digest(normalized((repo/CATALOG).read_bytes()))}))
    for name in (ENDPOINT,JOURNAL,CATALOG):
        target=stage/'new'/name; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,target)
    for name in CLIENT:
        target=stage/'client'/name; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(workspace/'Cliente'/name,target)
    for name in ('tests/questlog-tests.lua','tests/questlog-live.py','deploy/questlog-v36-release.py'):
        shutil.copy2(repo/name,stage/Path(name).name)
    with zipfile.ZipFile(stage.with_suffix('.zip'),'x',zipfile.ZIP_DEFLATED) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file(): z.write(p,p.relative_to(stage).as_posix())
    print('Prepared',stage.with_suffix('.zip'))

def bundle(stage):
    names=['baseline.json','questlog-v36-release.py','questlog-live.py','questlog-tests.lua']
    names += ['new/'+name for name in (ENDPOINT,JOURNAL,CATALOG)]
    names += ['client/'+name for name in CLIENT]
    target=stage.parent/'release-final.zip'
    with zipfile.ZipFile(target,'x',zipfile.ZIP_DEFLATED) as z:
        for name in names: z.write(stage/name,name)
    print('Final source bundle:',target,digest(target.read_bytes()))

def test(stage):
    core=stage/'new/data/lib/core/json.lua'; core.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(SERVER/'data/lib/core/json.lua',core)
    lib=ctypes.CDLL('libluajit-5.1.so.2')
    lib.luaL_newstate.restype=ctypes.c_void_p
    for fn in ('luaL_openlibs','lua_close'): getattr(lib,fn).argtypes=[ctypes.c_void_p]
    lib.luaL_loadfile.argtypes=[ctypes.c_void_p,ctypes.c_char_p]
    lib.lua_pcall.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_int,ctypes.c_int]
    lib.lua_settop.argtypes=[ctypes.c_void_p,ctypes.c_int]
    lib.lua_tolstring.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_void_p]
    lib.lua_tolstring.restype=ctypes.c_char_p
    state=lib.luaL_newstate(); cwd=Path.cwd()
    try:
        lib.luaL_openlibs(state); os.chdir(stage/'new')
        for p in list((stage/'new').rglob('*.lua'))+list((stage/'client').rglob('*.lua')):
            if lib.luaL_loadfile(state,str(p).encode()): raise RuntimeError(lib.lua_tolstring(state,-1,None).decode())
            lib.lua_settop(state,0)
        if lib.luaL_loadfile(state,str(stage/'questlog-tests.lua').encode()) or lib.lua_pcall(state,0,0,0):
            raise RuntimeError(lib.lua_tolstring(state,-1,None).decode())
    finally:
        os.chdir(cwd); lib.lua_close(state)

def atomic(path,data,reference):
    tmp=path.with_name('.'+path.name+'.v36-new')
    with tmp.open('xb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.chmod(tmp,reference.st_mode & 0o777); os.chown(tmp,reference.st_uid,reference.st_gid)
    os.replace(tmp,path)

def deploy(stage):
    for name,checksum in json.loads((stage/'baseline.json').read_text()).items():
        assert digest(normalized((SERVER/name).read_bytes()))==checksum,'Production drift: '+name
    assert not (SERVER/JOURNAL).exists(),'Journal already present; inspect before replacing'
    test(stage)
    backup=stage/'server-before'; backup.mkdir()
    shutil.copy2(SERVER/ENDPOINT,backup/'questlog.lua')
    owner=(SERVER/ENDPOINT).stat()
    atomic(SERVER/JOURNAL,(stage/'new'/JOURNAL).read_bytes(),owner)
    atomic(SERVER/ENDPOINT,(stage/'new'/ENDPOINT).read_bytes(),owner)
    print('Server files verified and deployed; restart required. Backup:',backup)

def changes(web,stage):
    assert digest((web/OLD).read_bytes())==BASE_SHA,'Public base ZIP changed'
    result={name:(stage/'client'/name).read_bytes() for name in CLIENT}
    with zipfile.ZipFile(web/OLD) as z:
        init=z.read('init.lua'); assert init.count(b'APP_VERSION = 35')==1
        result['init.lua']=init.replace(b'APP_VERSION = 35',b'APP_VERSION = 36')
    return result

def verify(web,stage):
    changed=changes(web,stage)
    with zipfile.ZipFile(web/OLD) as old,zipfile.ZipFile(stage/NEW) as new:
        assert old.namelist()==new.namelist() and new.testzip() is None
        assert len(new.namelist())==len(set(new.namelist()))
        for name in old.namelist(): assert new.read(name)==changed.get(name,old.read(name)),name
    manifest=json.loads((stage/'client-release.json').read_text())
    assert manifest['version']==36 and manifest['sha256']==digest((stage/NEW).read_bytes())

def package(web,stage):
    changed=changes(web,stage)
    with zipfile.ZipFile(web/OLD) as old,zipfile.ZipFile(stage/NEW,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as new:
        for entry in old.infolist(): new.writestr(entry,changed.get(entry.filename,old.read(entry.filename)))
    manifest=dict(version=36,name='Antigas 7.4 v36',sha256=digest((stage/NEW).read_bytes()))
    (stage/'client-release.json').write_text(json.dumps(manifest,indent=2)+'\n')
    verify(web,stage); print('PASS package:',manifest)

def publish(web,stage):
    verify(web,stage)
    assert json.loads((web/'client-release.json').read_text())['version']==35
    assert not (web/NEW).exists()
    index=web/'index.php'; original=index.read_bytes()
    assert original.count(OLD.encode())==1,'Download link changed'
    backup=stage/'website-before'; backup.mkdir()
    for name in ('index.php','client-release.json'): shutil.copy2(web/name,backup/name)
    atomic(web/NEW,(stage/NEW).read_bytes(),(web/OLD).stat())
    try:
        atomic(index,original.replace(OLD.encode(),NEW.encode()),index.stat())
        atomic(web/'client-release.json',(stage/'client-release.json').read_bytes(),(web/'client-release.json').stat())
        subprocess.run(['php','-l',str(index)],check=True)
    except Exception:
        for name in ('index.php','client-release.json'): atomic(web/name,(backup/name).read_bytes(),(web/name).stat())
        raise
    print('PASS: public client v36 and release manifest published; v35 and website backup retained')

def qa(web,stage,workspace):
    root=stage.parent/'client-qa'; root.mkdir(exist_ok=False)
    changed=changes(web,stage)
    with zipfile.ZipFile(web/OLD) as old: old.extractall(root)
    for name,data in changed.items(): (root/name).write_bytes(data)
    init=(root/'init.lua').read_text()
    init=init.replace('APP_NAME = "imperium 1.3"','APP_NAME = "antigas-questlog-qa36"')
    init=init.replace('https://tibia74.tech/client-release.json','')
    init+='\nQUESTLOG_QA_PREVIEW = true\ndofile(\'/modules/game_questlog/questlog-ui-tests.lua\')\n'
    (root/'init.lua').write_text(init)
    shutil.copy2(workspace/'Servidor/TFS/tests/questlog-ui-tests.lua',root/'modules/game_questlog/questlog-ui-tests.lua')
    print('QA client:',root)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=('prepare','test','deploy','package','publish','verify','qa','bundle'))
    p.add_argument('stage',type=Path); p.add_argument('--workspace',type=Path)
    p.add_argument('--web-root',type=Path,default=Path('/var/www/otclient'))
    a=p.parse_args(); stage=a.stage.resolve()
    if a.action=='prepare': prepare(stage,a.workspace.resolve())
    elif a.action=='bundle': bundle(stage)
    elif a.action in ('test','deploy'): globals()[a.action](stage)
    elif a.action=='qa': qa(a.web_root.resolve(),stage,a.workspace.resolve())
    else: globals()[a.action](a.web_root.resolve(),stage)
