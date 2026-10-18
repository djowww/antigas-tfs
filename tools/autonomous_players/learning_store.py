"""Private SQLite storage for the optional learner; never opens game storage."""
import hashlib
import json
import math
import sqlite3
import time
from pathlib import Path

VERSION = 1


class LearningStore:
    def __init__(self, path, max_agents=24, max_events=100000):
        self.path = Path(path)
        self.max_agents, self.max_events = max_agents, max_events
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.executescript('''
            PRAGMA journal_mode=WAL;
            PRAGMA synchronous=FULL;
            CREATE TABLE IF NOT EXISTS checkpoints(
                agent TEXT NOT NULL, seq INTEGER NOT NULL, payload TEXT NOT NULL,
                checksum TEXT NOT NULL, PRIMARY KEY(agent,seq));
            CREATE TABLE IF NOT EXISTS transitions(
                id INTEGER PRIMARY KEY, at REAL NOT NULL, agent TEXT NOT NULL,
                state TEXT NOT NULL, action TEXT NOT NULL, next_state TEXT NOT NULL,
                outcome TEXT NOT NULL, reward REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS route_edges(
                agent TEXT NOT NULL, source TEXT NOT NULL, destination TEXT NOT NULL,
                transition_id INTEGER NOT NULL, success INTEGER NOT NULL, at REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS qvalues(
                agent TEXT NOT NULL, state TEXT NOT NULL, action TEXT NOT NULL,
                value REAL NOT NULL, updates INTEGER NOT NULL,
                PRIMARY KEY(agent,state,action));
        ''')
        self.db.execute('PRAGMA wal_autocheckpoint=64')
        self.db.execute('PRAGMA journal_size_limit=1048576')

    def _agent(self, agent):
        if not isinstance(agent, str) or not 1 <= len(agent) <= 64:
            raise ValueError('invalid agent')
        count = self.db.execute('''SELECT count(DISTINCT agent) FROM (
            SELECT agent FROM checkpoints UNION SELECT agent FROM transitions)''').fetchone()[0]
        known = self.db.execute('SELECT 1 FROM checkpoints WHERE agent=? UNION SELECT 1 FROM transitions WHERE agent=?', (agent, agent)).fetchone()
        if not known and count >= self.max_agents:
            raise ValueError('agent budget exhausted')

    def record_transition(self, agent, state, action, next_state, outcome, reward, at):
        self._agent(agent)
        if not all(isinstance(v, str) and 1 <= len(v) <= 256 for v in (state, action, next_state)):
            raise ValueError('invalid transition')
        if not isinstance(reward, (int, float)) or not math.isfinite(reward):
            raise ValueError('invalid reward')
        payload = json.dumps(outcome, allow_nan=False, separators=(',', ':'))
        if len(payload.encode()) > 8192:
            raise ValueError('outcome too large')
        with self.db:
            self.db.execute('INSERT INTO transitions(at,agent,state,action,next_state,outcome,reward) VALUES(?,?,?,?,?,?,?)',
                            (float(at), agent, state, action, next_state, payload, float(reward)))
            self.db.execute('''DELETE FROM transitions WHERE agent=? AND id NOT IN
                               (SELECT id FROM transitions WHERE agent=? ORDER BY id DESC LIMIT ?)''',
                            (agent, agent, self.max_events))

    def route_edge(self, agent, source, destination, transition_id, success, at):
        self._agent(agent)
        with self.db:
            self.db.execute('INSERT INTO route_edges VALUES(?,?,?,?,?,?)',
                            (agent, str(source), str(destination), int(transition_id), int(bool(success)), float(at)))

    def values(self, agent, state):
        return dict(self.db.execute('SELECT action,value FROM qvalues WHERE agent=? AND state=?', (agent, state)))

    def set_value(self, agent, state, action, value):
        self._agent(agent)
        if not isinstance(state, str) or not 1 <= len(state) <= 256 or not isinstance(action, str) or not 1 <= len(action) <= 32:
            raise ValueError('invalid policy key')
        if not isinstance(value, (int, float)) or not math.isfinite(value):
            raise ValueError('invalid policy value')
        with self.db:
            self.db.execute('''INSERT INTO qvalues(agent,state,action,value,updates) VALUES(?,?,?,?,1)
                               ON CONFLICT(agent,state,action) DO UPDATE SET value=excluded.value,updates=updates+1''',
                            (agent, state, action, float(value)))

    def checkpoint(self, agent, payload):
        self._agent(agent)
        encoded = json.dumps(payload, allow_nan=False, separators=(',', ':'))
        if len(encoded.encode()) > 1048576:
            raise ValueError('checkpoint too large')
        checksum = hashlib.sha256(encoded.encode()).hexdigest()
        with self.db:
            seq = self.db.execute('SELECT coalesce(max(seq),0)+1 FROM checkpoints WHERE agent=?', (agent,)).fetchone()[0]
            self.db.execute('INSERT INTO checkpoints VALUES(?,?,?,?)', (agent, seq, encoded, checksum))
        return checksum

    def restore_latest(self, agent):
        row = self.db.execute('SELECT seq,payload,checksum FROM checkpoints WHERE agent=? ORDER BY seq DESC LIMIT 1', (agent,)).fetchone()
        if not row:
            return None
        if hashlib.sha256(row[1].encode()).hexdigest() != row[2]:
            raise ValueError('checkpoint checksum mismatch')
        return json.loads(row[1])

    def quarantine_corrupt(self, agent):
        row = self.db.execute('SELECT payload FROM checkpoints WHERE agent=? ORDER BY seq DESC LIMIT 1', (agent,)).fetchone()
        if not row:
            raise ValueError('checkpoint not found')
        target = self.path.with_name(self.path.name + '.' + agent.replace('/', '_') + '.corrupt')
        target.write_text(row[0], encoding='utf-8')
        with self.db:
            self.db.execute('DELETE FROM checkpoints WHERE agent=? AND seq=(SELECT max(seq) FROM checkpoints WHERE agent=?)', (agent, agent))
        return target

    def summary(self, agent):
        return {
            'transitions': self.db.execute('SELECT count(*) FROM transitions WHERE agent=?', (agent,)).fetchone()[0],
            'edges': self.db.execute('SELECT count(*) FROM route_edges WHERE agent=?', (agent,)).fetchone()[0],
            'checkpoints': self.db.execute('SELECT count(*) FROM checkpoints WHERE agent=?', (agent,)).fetchone()[0],
        }

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
