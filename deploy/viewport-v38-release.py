"""Scoped viewport release. No credentials, player data or test fixtures in the ZIP."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import zipfile

OLD='Antigas-7.4-Client-v37.zip'
NEW='Antigas-7.4-Client-v38.zip'
OLD_SHA='d404c2621e18f38b0facedb7f9ca622509b34608ac0736cbae17088877bacb22'
SERVER_SHA='1c05e838a96a858197fadbcafa8d26fe9a881d506a424c4864fa14ffcd5755e8'
CLIENT=('init.lua','LEIA-ME.txt','modules/game_interface/viewport.lua',
 'modules/game_interface/interface.otmod','modules/game_interface/gameinterface.lua',
 'modules/game_interface/gameinterface.otui','modules/client_options/options.lua',
 'modules/client_options/options.otui',
 'modules/client_options/viewport.otui')
SOURCE=('src/mapviewport.h','src/protocolgame.cpp','src/protocolgame.h','src/map.h',
 'src/map.cpp','src/combat.cpp','src/spawn.cpp')
ROOT=Path('/opt/antigas-viewport-v38')
SERVER=Path('/opt/imperium772/server')
WEB=Path('/var/www/otclient')

def sha(data): return hashlib.sha256(data).hexdigest()
def norm(data): return data.replace(b'\r\n',b'\n')

def prepare(workspace):
    stage=workspace/'Historico/viewport-v38/release-final'
    stage.mkdir(exist_ok=False)
    repo=workspace/'Servidor/TFS'
    old_package=workspace/OLD
    if not old_package.is_file(): old_package=workspace/'Historico/Pacotes-antigos'/OLD
    assert sha(old_package.read_bytes())==OLD_SHA
    changed={name:(workspace/'Cliente'/name).read_bytes() for name in CLIENT}
    assert b'APP_VERSION = 38' in changed['init.lua']
    with zipfile.ZipFile(old_package) as old,zipfile.ZipFile(stage/NEW,'x',zipfile.ZIP_DEFLATED) as new:
        for entry in old.infolist(): new.writestr(entry,changed.get(entry.filename,old.read(entry.filename)))
        for name in sorted(set(changed)-set(old.namelist())): new.writestr(name,changed[name])
    with zipfile.ZipFile(old_package) as old,zipfile.ZipFile(stage/NEW) as new:
        assert new.testzip() is None and len(new.namelist())==len(set(new.namelist()))
        assert set(new.namelist())==set(old.namelist())|set(CLIENT)
        for name in old.namelist(): assert new.read(name)==changed.get(name,old.read(name)),name
        assert not any('qa-' in n or 'qa_' in n or 'fixture' in n for n in new.namelist())
    baseline={}
    tracked=subprocess.check_output(['git','ls-tree','-r','--name-only','HEAD','src'],cwd=repo,text=True).splitlines()
    for name in tracked:
        baseline[name]=sha(norm(subprocess.check_output(['git','show','HEAD:'+name],cwd=repo)))
    (stage/'baseline.json').write_text(json.dumps(baseline,indent=2))
    for name in SOURCE:
        target=stage/name; target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(repo/name,target)
    for name in CLIENT:
        target=stage/'client'/name; target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(changed[name])
    manifest={'version':38,'name':'Antigas 7.4 v38','sha256':sha((stage/NEW).read_bytes())}
    (stage/'client-release.json').write_text(json.dumps(manifest,indent=2)+'\n')
    shutil.copy2(__file__,stage/'viewport-v38-release.py')
    with zipfile.ZipFile(stage.with_suffix('.zip'),'x',zipfile.ZIP_STORED) as z:
        for path in sorted(stage.rglob('*')):
            if path.is_file(): z.write(path,path.relative_to(stage).as_posix())
    print(json.dumps(manifest)); print('PASS: exact client allowlist, clean ZIP, source baseline recorded')

def audit(stage):
    mismatch=[]
    for name,digest in json.loads((stage/'baseline.json').read_text()).items():
        path=SERVER/name
        if not path.is_file() or sha(norm(path.read_bytes()))!=digest: mismatch.append(name)
    print('Production source differences:',json.dumps(mismatch))
    assert not mismatch,'Inspect production drift before deploying'
    assert sha((SERVER/'tfs').read_bytes())==SERVER_SHA,'Production binary changed'
    print('PASS production baseline')

def atomic(path,data,owner):
    temp=path.with_name('.'+path.name+'.viewport-v38-new')
    with temp.open('xb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.chmod(temp,owner.st_mode & 0o777); os.chown(temp,owner.st_uid,owner.st_gid)
    os.replace(temp,path)

def deploy(stage):
    audit(stage)
    binary=ROOT/'build/tfs'
    assert binary.is_file() and (stage/'VALIDATED').read_text().strip()==sha(binary.read_bytes())
    backup=stage/'server-before'; backup.mkdir(exist_ok=False)
    shutil.copy2(SERVER/'tfs',backup/'tfs')
    for name in SOURCE:
        if (SERVER/name).exists():
            dest=backup/name; dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(SERVER/name,dest)
    owner=(SERVER/'tfs').stat()
    source_owner=(SERVER/'src/protocolgame.cpp').stat()
    subprocess.run(['systemctl','stop','imperium772'],check=True)
    try:
        atomic(SERVER/'tfs',binary.read_bytes(),owner)
        for name in SOURCE: atomic(SERVER/name,(stage/name).read_bytes(),source_owner)
        subprocess.run(['systemctl','start','imperium772'],check=True)
        time.sleep(8)
        subprocess.run(['systemctl','is-active','--quiet','imperium772'],check=True)
    except BaseException:
        subprocess.run(['systemctl','stop','imperium772'],check=False)
        atomic(SERVER/'tfs',(backup/'tfs').read_bytes(),owner)
        for name in SOURCE:
            if (backup/name).exists(): atomic(SERVER/name,(backup/name).read_bytes(),source_owner)
        subprocess.run(['systemctl','start','imperium772'],check=True)
        raise
    print('PASS server deployed; rollback retained:',backup)

def publish(stage):
    manifest=json.loads((stage/'client-release.json').read_text())
    assert sha((stage/NEW).read_bytes())==manifest['sha256']
    assert sha((SERVER/'tfs').read_bytes())==(stage/'VALIDATED').read_text().strip()
    assert json.loads((WEB/'client-release.json').read_text())['version']==37
    assert not (WEB/NEW).exists()
    index=WEB/'index.php'; original=index.read_bytes()
    assert original.count(OLD.encode())==1
    backup=stage/'website-before'; backup.mkdir(exist_ok=False)
    for name in ('index.php','client-release.json'): shutil.copy2(WEB/name,backup/name)
    atomic(WEB/NEW,(stage/NEW).read_bytes(),(WEB/OLD).stat())
    try:
        atomic(index,original.replace(OLD.encode(),NEW.encode()),index.stat())
        subprocess.run(['php','-l',str(index)],check=True)
        atomic(WEB/'client-release.json',(stage/'client-release.json').read_bytes(),(WEB/'client-release.json').stat())
    except BaseException:
        for name in ('index.php','client-release.json'): atomic(WEB/name,(backup/name).read_bytes(),(WEB/name).stat())
        raise
    print('PASS public client v38; v37 download and website backup retained')

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=('prepare','audit','deploy','publish'))
    p.add_argument('path',type=Path); a=p.parse_args()
    globals()[a.action](a.path.resolve())
