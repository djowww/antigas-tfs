"""Optional localhost bridge between the runner and the removable learner."""
import json
import socket
import time
from pathlib import Path
from .learning import Policy
from .learning_protocol import LearningIntent, LearningObservation, decode_message, encode_message
from .learning_store import LearningStore


class LearningAgent:
    def __init__(self, state_path, shadow=False):
        self.store = LearningStore(state_path)
        self.shadow = bool(shadow)
        self.previous = {}
        self.policies = {}

    def _policy(self, agent):
        if agent not in self.policies:
            import random
            self.policies[agent] = Policy(self.store, agent, random.Random(agent))
        return self.policies[agent]

    def handle(self, observation):
        if not isinstance(observation, LearningObservation):
            raise TypeError('LearningObservation required')
        state = json.dumps(observation.state, sort_keys=True, separators=(',', ':'))
        previous = self.previous.get(observation.agent)
        if previous:
            previous_state, previous_action, previous_at = previous
            reward = 1.0 if observation.state.get('floor') != json.loads(state).get('floor') else 0.0
            self.store.record_transition(observation.agent, previous_state, previous_action, state,
                                         {'floor': observation.state.get('floor')}, reward, observation.observed_at)
            self._policy(observation.agent).update(previous_state, previous_action, reward, state,
                                                   ('move', 'hunt', 'retreat', 'wait'))
        if observation.state.get('health_band') in ('critical', 'wounded'):
            kind = 'retreat'
        elif observation.state.get('nearby_threats', 0) > 0:
            kind = 'hunt'
        elif observation.state.get('goal') == 'hunt':
            kind = 'hunt'
        else:
            kind = 'wait'
        self.previous[observation.agent] = (state, kind, observation.observed_at)
        if self.shadow:
            return None
        return LearningIntent(observation.agent, kind, {'source': 'learner'}, observation.observed_at, 2.0)

    def close(self):
        self.store.close()


class LearningBridge:
    def __init__(self, socket_path, connect_timeout=0.2, intent_ttl=2.0):
        self.socket_path = str(socket_path)
        self.connect_timeout = float(connect_timeout)
        self.intent_ttl = float(intent_ttl)
        self._intent = None

    def publish(self, observation):
        if not isinstance(observation, LearningObservation):
            raise TypeError('LearningObservation required')
        if not hasattr(socket, 'AF_UNIX'):
            return None
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(self.connect_timeout)
                sock.connect(self.socket_path)
                sock.sendall(encode_message(observation.to_message()))
                data = sock.recv(32768)
            if not data:
                return None
            message = decode_message(data)
            if message['type'] != 'intent' or message.get('payload', {}).get('shadow'):
                return None
            intent = LearningIntent(message['agent'], message['kind'], message.get('payload', {}),
                                    message['issued_at'], min(message.get('ttl', self.intent_ttl), self.intent_ttl))
            if intent.expired(time.time()):
                return None
            self._intent = intent
            return intent
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    def poll_intent(self, now=None):
        intent, self._intent = self._intent, None
        return None if intent is None or intent.expired(time.time() if now is None else now) else intent

    def close(self):
        self._intent = None


def serve(socket_path, state_path, shadow=False):
    path = Path(socket_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    learner = LearningAgent(state_path, shadow=shadow)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path)); server.listen(8)
    try:
        while True:
            conn, _ = server.accept()
            with conn:
                try:
                    message = decode_message(conn.recv(32768))
                    observation = LearningObservation(message['agent'], message['state'], message['observed_at'])
                    intent = learner.handle(observation)
                    if intent is None:
                        intent = LearningIntent(observation.agent, 'wait', {'shadow': True}, time.time(), 1.0)
                    conn.sendall(encode_message({'schema': 1, 'type': 'intent', 'agent': intent.agent,
                                                  'kind': intent.kind, 'payload': intent.payload,
                                                  'issued_at': intent.issued_at, 'ttl': intent.ttl}))
                except (OSError, ValueError, KeyError, TypeError):
                    continue
    finally:
        learner.close(); server.close()
        try:
            path.unlink()
        except FileNotFoundError:
            pass
