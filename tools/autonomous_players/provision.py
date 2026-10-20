"""One-time administrative provisioning, never imported by gameplay sessions.

The private manifest is durably prepared before the database transaction. A
resumed operation verifies its own completed identities, never overwrites them.
"""
import hashlib
import json
import re
import secrets
import subprocess
import time
from pathlib import Path
from .health import atomic_json, command

NAMES = ('Aster','Brisa','Cedro','Duna','Estrela','Faia','Garoa','Hera','Iris','Jade',
         'Kiara','Luar','Malva','Nilo','Olmo','Prisma','Quartzo','Raio','Selva','Trevo')


def file_hash(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1048576),b''):
            digest.update(block)
    return digest.hexdigest()


def backup_database(database,path,identity):
    path=Path(path)
    if not re.fullmatch(r'[A-Za-z0-9_]+',database) or path.exists():
        raise ValueError('invalid backup target or existing backup')
    partial=path.with_name(path.name+'.partial')
    import os
    fd=os.open(partial,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as output:
        subprocess.run(['mysqldump','--single-transaction','--routines','--triggers',database],
                       stdout=output,stderr=subprocess.DEVNULL,check=True,timeout=120)
        output.flush();os.fsync(output.fileno())
    if partial.stat().st_size<1024:
        raise ValueError('empty backup')
    os.replace(partial,path)
    receipt=dict(identity=identity,database=database,completed=time.time(),size=path.stat().st_size,
                 sha256=file_hash(path))
    atomic_json(str(path)+'.receipt.json',receipt,0o600)
    return receipt


def prepare_manifest(path, identity, count, public_authorized):
    if not public_authorized or not identity or not 1 <= count <= 20:
        raise ValueError('explicit world identity and authorization for 1..20 required')
    path = Path(path)
    if path.exists():
        manifest = json.loads(path.read_text())
        if manifest['identity'] != identity or len(manifest['players']) != count:
            raise ValueError('manifest belongs to different world or population')
        return manifest
    players,ids = [],set()
    for index,name in enumerate(NAMES[:count]):
        while (account:=600000000+secrets.randbelow(300000000)) in ids:
            pass
        ids.add(account)
        players.append(dict(account=account,character='Sim '+name,password=secrets.token_hex(16),
                            sex=index%2,city=('thais','carlin','venore')[index%3],
                            vocation=('knight','paladin','sorcerer','druid')[index%4]))
    manifest = dict(version=1,identity=identity,created=int(time.time()),
                    marker='autonomous-'+secrets.token_hex(12),players=players,provisioned=False)
    atomic_json(path,manifest,0o600)
    return manifest


def provision_sql(manifest, existing):
    marker = manifest['marker']
    if not re.fullmatch(r'autonomous-[0-9a-f]{24}',marker):
        raise ValueError('invalid manifest marker')
    statements = []
    for p in manifest['players']:
        account,name,password,sex = p['account'],p['character'],p['password'],p['sex']
        if (type(account) is not int or not 100000 <= account <= 999999999 or
            not re.fullmatch(r'Sim [A-Za-z ]{2,20}',name) or not re.fullmatch(r'[0-9a-f]{32}',password) or sex not in (0,1)):
            raise ValueError('invalid provisioning identity')
        if account in existing:
            continue
        digest = hashlib.sha1(password.encode()).hexdigest()
        statements.append(f"INSERT INTO accounts(id,password,email,created) VALUES({account},'{digest}','',{manifest['created']});")
        statements.append("INSERT INTO players(name,account_id,level,vocation,health,healthmax,conditions,cap,sex,looktype,lookhead,lookbody,looklegs,lookfeet,soul,town_id,posx,posy,posz,comment,created) "
            f"VALUES('{name}',{account},1,0,150,150,'',400,{sex},{128 if sex else 136},78,69,58,76,100,11,32097,32219,7,'{marker}',{manifest['created']});")
    return 'START TRANSACTION;\n'+'\n'.join(statements)+'\nCOMMIT;\n' if statements else ''


def provision(path, identity, database, backup):
    path,backup = Path(path),Path(backup)
    m = json.loads(path.read_text())
    if m['identity'] != identity or not re.fullmatch(r'[a-zA-Z0-9_]+',database):
        raise ValueError('world identity mismatch')
    if not backup.is_file() or backup.stat().st_size < 1024:
        raise ValueError('successful full database backup required')
    receipt=json.loads(Path(str(backup)+'.receipt.json').read_text())
    backup_hash=file_hash(backup)
    if (receipt.get('identity')!=identity or receipt.get('database')!=database or
        receipt.get('sha256')!=backup_hash or not 0<=time.time()-receipt.get('completed',0)<=3600):
        raise ValueError('backup receipt missing, stale or mismatched')
    existing = []
    for p in m['players']:
        # Validate generated fields before constructing any SQL.
        provision_sql(dict(m,players=[p]),[])
        account,name = p['account'],p['character']
        account_rows = command(['mysql','-N','-B',database,'-e',f'SELECT password,type FROM accounts WHERE id={account}'])
        player_rows = command(['mysql','-N','-B',database,'-e',f"SELECT id,account_id,comment,group_id FROM players WHERE name='{name}'"])
        if not account_rows and not player_rows:
            continue
        expected = hashlib.sha1(p['password'].encode()).hexdigest()+'\t1'
        fields = player_rows.split('\t')
        if (account_rows != expected or len(fields) != 4 or fields[1] != str(account) or
            fields[2] != m['marker'] or fields[3] != '1'):
            raise ValueError('existing identity collision; no existing player will be changed')
        existing.append(account)
    query = provision_sql(m,existing)
    if query:
        subprocess.run(['mysql','--batch',database],input=query,text=True,check=True,timeout=30,
                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for p in m['players']:
        p['player_id'] = int(command(['mysql','-N','-B',database,'-e',
            f"SELECT id FROM players WHERE account_id={p['account']} AND name='{p['character']}'"]))
    m.update(provisioned=True,backup_sha256=backup_hash)
    atomic_json(path,m,0o600)
    return m
