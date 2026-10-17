"""Independent Linux guardian. Root-owned metrics cannot be renewed by players.

Only SELECTs are issued by this collector; no game-state mutation capability is
passed to the unprivileged game clients. Failure publishes a failed health lease.
"""
import json
import os
import re
import socket
import struct
import subprocess
import time
from pathlib import Path
from .supervisor import HealthSample


def parse_meminfo(text):
    match = re.search(r'^MemAvailable:\s+(\d+) kB$',text,re.M)
    if not match:
        raise ValueError('available memory missing')
    return int(match[1])/1024


def cpu_usage(previous, current):
    difference = [b-a for a,b in zip(previous,current)]
    if len(difference) < 5 or min(difference) < 0 or sum(difference) <= 0:
        raise ValueError('invalid CPU sample')
    idle = difference[3]+difference[4]
    return 100*(sum(difference)-idle)/sum(difference)


def parse_queue(text):
    sections = text.split(';')
    if len(sections) != 3:
        raise ValueError('incomplete queue metrics')
    def value(section,key):
        match = re.search(r'\b'+key+r'=(\d+)\b',section)
        if not match:
            raise ValueError('queue metric missing')
        return int(match[1])
    return dict(dispatcher_queued=value(sections[0],'queued'),
                sql_age_seconds=value(sections[2],'oldest_queued_age_ms')/1000,
                counter_anomaly=any(value(section,'counter_anomaly') != 0 for section in sections))


def latest_queue_entry(raw, now):
    # Read a bounded journal window before filtering: on the deployed journalctl,
    # -n 1 combined with --grep can return nothing after an ordinary login.
    entries = [json.loads(line) for line in raw.splitlines() if line.strip()]
    matches = [entry for entry in entries if entry.get('MESSAGE','').startswith('[QueueMetrics]')]
    if not matches:
        raise ValueError('queue metrics missing')
    entry = max(matches,key=lambda item:int(item['__REALTIME_TIMESTAMP']))
    if not 0 <= now-int(entry['__REALTIME_TIMESTAMP'])/1000000 <= 120:
        raise ValueError('queue metrics stale')
    return entry


def atomic_json(path, data, mode=0o640):
    path = Path(path)
    tmp = path.with_name(path.name+'.tmp')
    fd = os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,mode)
    with os.fdopen(fd,'w',encoding='utf8') as out:
        json.dump(data,out,allow_nan=False,separators=(',',':'))
        out.flush();os.fsync(out.fileno())
    os.replace(tmp,path)


def command(args):
    return subprocess.check_output(args,text=True,timeout=4).strip()


def collect_once(collector):
    try:
        return collector.sample()
    except (OSError,ValueError,KeyError,TimeoutError,subprocess.SubprocessError) as exc:
        # Command arguments may contain private operational details.
        return dict(at=time.time(),error=type(exc).__name__)


def status_latency(host, port):
    started = time.monotonic()
    # Protocol ID FF is consumed by Connection, next FF selects XML info.
    payload = b'\xff\xffinfo'
    with socket.create_connection((host,port),timeout=2) as sock:
        sock.settimeout(2)
        sock.sendall(struct.pack('<H',len(payload))+payload)
        data = bytearray()
        while b'</tsqp>' not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > 16384:
                raise ValueError('oversized status response')
    if b'</tsqp>' not in data:
        raise ValueError('invalid game status response')
    return (time.monotonic()-started)*1000


class Collector:
    def __init__(self, service, database, player_ids, status_port, mysql_defaults=None):
        if not re.fullmatch(r'[a-zA-Z0-9_.@-]+\.service',service) or not re.fullmatch(r'[a-zA-Z0-9_]+',database):
            raise ValueError('invalid target identity')
        if not player_ids or len(player_ids) > 20 or any(type(i) is not int or i <= 0 for i in player_ids):
            raise ValueError('invalid population IDs')
        self.service,self.database,self.ids,self.port = service,database,player_ids,status_port
        self.mysql_defaults = mysql_defaults
        self.previous_cpu = self._cpu()
        self.last_sql = 0
        self.population = {}
        self.oom_count = self._oom()

    @staticmethod
    def _cpu():
        return tuple(map(int,Path('/proc/stat').read_text().splitlines()[0].split()[1:9]))

    def _oom(self):
        path = Path('/sys/fs/cgroup/system.slice')/self.service/'memory.events'
        if not path.exists():
            return 0
        return int(dict(line.split() for line in path.read_text().splitlines()).get('oom_kill',0))

    def sample(self):
        now = time.time()
        current_cpu = self._cpu()
        cpu = cpu_usage(self.previous_cpu,current_cpu)
        self.previous_cpu = current_cpu
        pid = int(command(['systemctl','show','--value','--property=MainPID',self.service]))
        raw = command(['journalctl','-u',self.service,'-n','128','-o','json','--no-pager'])
        entry = latest_queue_entry(raw,now)
        queue = parse_queue(entry['MESSAGE'])
        if now-self.last_sql >= 30:
            ids = ','.join(map(str,self.ids))
            query = ('SELECT p.id,p.level,p.experience,p.health,p.vocation,p.posx,p.posy,p.posz,'
                     'EXISTS(SELECT 1 FROM players_online o WHERE o.player_id=p.id) FROM players p '
                     'WHERE p.id IN ('+ids+'); SELECT COUNT(*) FROM players_online WHERE player_id NOT IN ('+ids+');')
            mysql = ['mysql']+(['--defaults-extra-file='+self.mysql_defaults] if self.mysql_defaults else [])
            rows = command(mysql+['-N','-B',self.database,'-e',query]).splitlines()
            self.population = dict(players=[list(map(int,line.split('\t'))) for line in rows[:-1]],humans_online=int(rows[-1]))
            self.last_sql = now
        oom = self._oom()
        sample = HealthSample(now,now,parse_meminfo(Path('/proc/meminfo').read_text()),cpu,
                              status_latency('127.0.0.1',self.port),pid,oom=oom>self.oom_count,**queue)
        self.oom_count = oom
        from dataclasses import asdict
        return dict(sample=asdict(sample),population=self.population,sql_measured_at=self.last_sql)
