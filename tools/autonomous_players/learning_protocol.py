"""Versioned, local-only observations exchanged with the optional learner."""
from dataclasses import dataclass
import json
import math
import time

SCHEMA = 1
MAX_MESSAGE = 32 * 1024
_INTENTS = {'move', 'hunt', 'retreat', 'supply', 'talk', 'wait'}


def _finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


@dataclass(frozen=True)
class LearningObservation:
    agent: str
    state: dict
    observed_at: float

    @classmethod
    def from_world(cls, agent, world, goal, route_confidence, transition_id=None):
        if not isinstance(agent, str) or not 1 <= len(agent) <= 64:
            raise ValueError('invalid agent')
        if not world.position or not _finite(route_confidence) or not 0 <= route_confidence <= 1:
            raise ValueError('invalid observation')
        health_band = 'critical' if world.stats.max_health and world.stats.health * 100 < world.stats.max_health * 35 else (
            'wounded' if world.stats.max_health and world.stats.health * 100 < world.stats.max_health * 65 else 'healthy')
        monsters = sum(1 for c in world.creatures.values() if c.kind == 'monster' and c.position and
                       c.position.distance(world.position) <= 3)
        state = {
            'floor': int(world.position.z),
            'x': int(world.position.x),
            'y': int(world.position.y),
            'health_band': health_band,
            'nearby_threats': min(monsters, 8),
            'level': int(world.stats.level),
            'experience': int(world.stats.experience),
            'health': int(world.stats.health),
            'max_health': int(world.stats.max_health),
            'death': bool(world.stats.max_health > 0 and world.stats.health <= 0),
            'goal': str(goal)[:32],
            'route_confidence': round(float(route_confidence), 3),
        }
        if transition_id is not None:
            if not isinstance(transition_id, int) or transition_id < 0:
                raise ValueError('invalid transition id')
            state['transition_id'] = transition_id
        return cls(agent, state, time.time())

    def to_message(self):
        return {'schema': SCHEMA, 'type': 'observation', 'agent': self.agent,
                'state': self.state, 'observed_at': self.observed_at}


@dataclass(frozen=True)
class LearningIntent:
    agent: str
    kind: str
    payload: dict
    issued_at: float
    ttl: float

    def __post_init__(self):
        if not isinstance(self.agent, str) or not 1 <= len(self.agent) <= 64:
            raise ValueError('invalid agent')
        if self.kind not in _INTENTS or not _finite(self.issued_at) or not _finite(self.ttl) or self.ttl <= 0:
            raise ValueError('invalid intent')

    def expired(self, now):
        return now >= self.issued_at + self.ttl


def encode_message(value):
    if not isinstance(value, dict) or value.get('schema') != SCHEMA:
        raise ValueError('invalid message schema')
    encoded = (json.dumps(value, allow_nan=False, separators=(',', ':')) + '\n').encode('utf-8')
    if len(encoded) > MAX_MESSAGE:
        raise ValueError('message too large')
    return encoded


def decode_message(line):
    if not isinstance(line, (bytes, bytearray)) or len(line) > MAX_MESSAGE:
        raise ValueError('message too large')
    try:
        value = json.loads(bytes(line).decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid message') from exc
    if not isinstance(value, dict) or value.get('schema') != SCHEMA or value.get('type') not in {'observation', 'intent'}:
        raise ValueError('invalid message schema')
    if value.get('type') == 'observation' and (not isinstance(value.get('agent'), str) or
                                               not isinstance(value.get('state'), dict) or
                                               not _finite(value.get('observed_at'))):
        raise ValueError('invalid observation')
    if value.get('type') == 'intent' and (value.get('kind') not in _INTENTS or
                                         not isinstance(value.get('agent'), str) or
                                         not _finite(value.get('issued_at'))):
        raise ValueError('invalid intent')
    return value
