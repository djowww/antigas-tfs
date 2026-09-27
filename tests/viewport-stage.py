"""Create a disposable tiny-map world, separate SQL schema and RSA key on VPS.

Run once in /opt/antigas-viewport-v38; never changes/stops the official service.
"""
import hashlib
import json
import math
from pathlib import Path
import secrets
import shutil
import struct
import subprocess

ROOT = Path('/opt/antigas-viewport-v38')
DB = 'antigas_viewport_v38'
assert ROOT.is_dir() and not (ROOT/'fixture.json').exists()

def sql(query, database=None):
    return subprocess.check_output(['mariadb', '--batch', '--skip-column-names'] +
        ([database] if database else []) + ['-e', query], text=True).strip()

assert not sql("SHOW DATABASES LIKE 'antigas_viewport_v38'")
runtime = ROOT/'runtime'
runtime.mkdir(exist_ok=True)
shutil.copytree('/opt/imperium772/server/data', runtime/'data',
    ignore=shutil.ignore_patterns('world', 'reports'), dirs_exist_ok=True)
world = runtime/'data/world'
world.mkdir(exist_ok=True)

def node(kind, data=b'', children=b''):
    escaped = b''.join((b'\xfd'+bytes([b]) if b in (253,254,255) else bytes([b])) for b in data)
    return b'\xfe' + bytes([kind]) + escaped + children + b'\xff'

def string(text):
    data = text.encode()
    return struct.pack('<H',len(data))+data

areas = b''
for z in (7,8,9):
    children = b''
    for x in range(960,1041):
        for y in range(960,1041):
            ground = 102 if (x+y)%2 == 0 else 103
            children += node(5, bytes([x-896,y-896,9])+struct.pack('<H',ground))
    areas += node(4, struct.pack('<HHB',896,896,z), children)
towns = node(12, children=b''.join(node(13,struct.pack('<I',i)+string('QA Town')+
    struct.pack('<HHB',1000,1000,7)) for i in (1,2,11)))
header = struct.pack('<IHHII',2,2048,2048,3,0)
metadata = bytes([11])+string('qa-spawn.xml')+bytes([13])+string('qa-house.xml')
(world/'qa.otbm').write_bytes(b'OTBM'+node(0,header,node(2,metadata,areas+towns)))
(world/'qa-spawn.xml').write_text('<spawns/>')
(world/'qa-house.xml').write_text('<houses/>')

password = secrets.token_hex(20)
sql(f'CREATE DATABASE {DB}')
schema = subprocess.check_output(['mysqldump','--no-data','--skip-triggers','antigas_load_v37'])
subprocess.run(['mariadb',DB], input=schema, check=True)
sql(f"CREATE USER '{DB}'@'127.0.0.1' IDENTIFIED BY '{password}'")
sql(f"GRANT ALL ON {DB}.* TO '{DB}'@'127.0.0.1'")
login_password = secrets.token_hex(12)
digest = hashlib.sha1(login_password.encode()).hexdigest()
for i,name in enumerate(('Viewport Tester','Viewport Peer')):
    account,player = 970101+i,970001+i
    sql(f"INSERT INTO accounts(id,password,type,email) VALUES({account},'{digest}',{5 if i==0 else 1},'viewport-{i}@test.invalid')",DB)
    sql(f"INSERT INTO players(id,name,account_id,group_id,level,health,healthmax,town_id,posx,posy,posz,conditions,comment,cap,looktype,lastlogin) "
        f"VALUES({player},'{name}',{account},{3 if i==0 else 1},20,300,300,1,{1000 if i==0 else 1011},1000,7,'','isolated viewport QA',10000,{128+i},1)",DB)

while True:
    p,q=(int(subprocess.check_output(['openssl','prime','-generate','-bits','512','-hex']).strip(),16) for _ in range(2))
    if p!=q and (p*q).bit_length()==1024 and math.gcd(65537,(p-1)*(q-1))==1:
        break
(ROOT/'rsa.txt').write_text(f'{p}\n{q}\n')
(ROOT/'rsa.txt').chmod(0o600)
(ROOT/'runtime.env').write_text(f'TFS_DB_USER={DB}\nTFS_DB_PASSWORD={password}\nTFS_DB_NAME={DB}\nANTIGAS_RSA_KEY_FILE={ROOT}/rsa.txt\n')
(ROOT/'runtime.env').chmod(0o600)
config = Path('/opt/imperium772/server/config.lua').read_text()
config += '\nip="127.0.0.1"\nbindOnlyGlobalAddress=true\nloginProtocolPort=7185\ngameProtocolPort=7186\nstatusProtocolPort=7185\nserverName="Antigas Viewport QA"\nmapName="qa"\nteleportNewbies=false\nmaxPlayers=4\n'
(runtime/'config.lua').write_text(config)
# Replace only this copied world's optional startup events/raids.
(runtime/'data/globalevents/globalevents.xml').write_text('<globalevents/>')
(runtime/'data/raids/raids.xml').write_text('<raids/>')
talks = runtime/'data/talkactions/talkactions.xml'
talks.write_text(talks.read_text().replace('</talkactions>',
    '<talkaction words="!viewportqa" separator=" " script="viewport_qa.lua"/></talkactions>'))
shutil.copyfile(ROOT/'viewport_qa.lua',runtime/'data/talkactions/scripts/viewport_qa.lua')
(ROOT/'fixture.json').write_text(json.dumps({'account':970101,'peerAccount':970102,
    'password':login_password,'rsa':str(p*q),'database':DB,'gamePort':7186}))
(ROOT/'fixture.json').chmod(0o600)
print('Prepared isolated world: 19,683 tiles, own SQL schema and RSA key, loopback ports 7185/7186')
