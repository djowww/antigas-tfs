"""Transactional local state. This database never connects to game storage."""
import json
import math
import sqlite3
from pathlib import Path

VERSION = 1


class Store:
    def __init__(self, path, max_agents=24, max_states=4096):
        self.path = Path(path)
        self.max_agents,self.max_states = max_agents,max_states
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (0, VERSION):
            self.db.close()
            raise ValueError('unsupported state schema')
        self.db.executescript('''
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS checkpoints (
                agent TEXT PRIMARY KEY, version INTEGER NOT NULL, payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS qvalues (
                agent TEXT, state TEXT, action TEXT, value REAL NOT NULL, updates INTEGER NOT NULL,
                PRIMARY KEY(agent,state,action));
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, at REAL NOT NULL, agent TEXT, kind TEXT, payload TEXT);
            PRAGMA user_version=1;
        ''')
        # Main DB <=128 MiB; WAL checkpoints prevent an unbounded sidecar.
        self.db.execute('PRAGMA max_page_count=32768')
        self.db.execute('PRAGMA wal_autocheckpoint=64')
        self.db.execute('PRAGMA journal_size_limit=1048576')

    def _agent(self, agent):
        if not isinstance(agent,str) or not 1 <= len(agent) <= 64:
            raise ValueError('invalid agent key')
        agents = {row[0] for row in self.db.execute('SELECT agent FROM checkpoints UNION SELECT agent FROM qvalues')}
        if agent not in agents and len(agents) >= self.max_agents:
            raise ValueError('agent budget exhausted')

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def checkpoint(self, agent, state):
        self._agent(agent)
        payload = json.dumps(state, allow_nan=False, separators=(',', ':'))
        if len(payload.encode()) > 1048576:
            raise ValueError('checkpoint too large')
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO checkpoints VALUES(?,?,?)', (agent, VERSION, payload))

    def restore(self, agent):
        row = self.db.execute('SELECT version,payload FROM checkpoints WHERE agent=?', (agent,)).fetchone()
        if row is None:
            return None
        if row[0] != VERSION:
            raise ValueError('unsupported checkpoint version')
        return json.loads(row[1])

    def values(self, agent, state):
        return dict(self.db.execute('SELECT action,value FROM qvalues WHERE agent=? AND state=?', (agent, state)))

    def set_value(self, agent, state, action, value):
        self._agent(agent)
        if not isinstance(state,str) or not 1 <= len(state) <= 256 or not isinstance(action,str) or not 1 <= len(action) <= 32:
            raise ValueError('invalid policy key')
        count = self.db.execute('SELECT count(*) FROM qvalues WHERE agent=?',(agent,)).fetchone()[0]
        exists = self.db.execute('SELECT 1 FROM qvalues WHERE agent=? AND state=? AND action=?',(agent,state,action)).fetchone()
        if not exists and count >= self.max_states:
            raise ValueError('policy state budget exhausted')
        if not math.isfinite(value):
            raise ValueError('nonfinite learned value')
        with self.db:
            self.db.execute('''INSERT INTO qvalues VALUES(?,?,?,?,1)
                ON CONFLICT(agent,state,action) DO UPDATE SET value=excluded.value,updates=updates+1''',
                (agent, state, action, value))

    def event(self, at, agent, kind, payload):
        if agent != '_supervisor':
            self._agent(agent)
        encoded = json.dumps(payload, allow_nan=False, separators=(',', ':'))
        if len(encoded.encode()) > 8192:
            raise ValueError('event too large')
        with self.db:
            self.db.execute('INSERT INTO events(at,agent,kind,payload) VALUES(?,?,?,?)', (at, agent, kind, encoded))
            # Bounded rows as well as age: preserve models/checkpoints under log pressure.
            self.db.execute('DELETE FROM events WHERE at<? OR id<coalesce((SELECT max(id)-10000 FROM events),0)', (at-7*86400,))
        self.db.execute('PRAGMA wal_checkpoint(PASSIVE)')

    def record_events_and_checkpoint(self, agent, events, state):
        """Commit related events and their recovery checkpoint atomically."""
        self._agent(agent)
        checkpoint=json.dumps(state,allow_nan=False,separators=(',',':'))
        if len(checkpoint.encode())>1048576:
            raise ValueError('checkpoint too large')
        rows=[]
        for at,kind,payload in events:
            encoded=json.dumps(payload,allow_nan=False,separators=(',',':'))
            if len(encoded.encode())>8192:
                raise ValueError('event too large')
            rows.append((at,agent,kind,encoded))
        if not rows:
            raise ValueError('at least one event is required')
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO checkpoints VALUES(?,?,?)',
                            (agent,VERSION,checkpoint))
            self.db.executemany('INSERT INTO events(at,agent,kind,payload) VALUES(?,?,?,?)',rows)
            self.db.execute('DELETE FROM events WHERE at<? OR id<coalesce((SELECT max(id)-10000 FROM events),0)',
                            (max(row[0] for row in rows)-7*86400,))
        self.db.execute('PRAGMA wal_checkpoint(PASSIVE)')
