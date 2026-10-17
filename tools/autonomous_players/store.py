"""Transactional local state. This database never connects to game storage."""
import json
import math
import sqlite3
from pathlib import Path

VERSION = 1


class Store:
    def __init__(self, path):
        self.path = Path(path)
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

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.db.close()

    def checkpoint(self, agent, state):
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
        if not math.isfinite(value):
            raise ValueError('nonfinite learned value')
        with self.db:
            self.db.execute('''INSERT INTO qvalues VALUES(?,?,?,?,1)
                ON CONFLICT(agent,state,action) DO UPDATE SET value=excluded.value,updates=updates+1''',
                (agent, state, action, value))

    def event(self, at, agent, kind, payload):
        encoded = json.dumps(payload, allow_nan=False, separators=(',', ':'))
        if len(encoded.encode()) > 8192:
            raise ValueError('event too large')
        with self.db:
            self.db.execute('INSERT INTO events(at,agent,kind,payload) VALUES(?,?,?,?)', (at, agent, kind, encoded))
            # Bounded rows as well as age: preserve models/checkpoints under log pressure.
            self.db.execute('DELETE FROM events WHERE at<? OR id<coalesce((SELECT max(id)-10000 FROM events),0)', (at-7*86400,))
        self.db.execute('PRAGMA wal_checkpoint(PASSIVE)')
