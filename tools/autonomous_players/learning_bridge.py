"""Optional localhost bridge between the runner and the removable learner."""
import json
import socket
import time
import asyncio
import os
from pathlib import Path
from .learning import Policy
from .learned_navigation import Curriculum, RegionGraph
from .learning_protocol import LearningIntent, LearningObservation, decode_message, encode_message
from .learning_store import LearningStore


def recv_line(sock, max_bytes=32768):
    data = bytearray()
    while len(data) < max_bytes:
        chunk = sock.recv(min(4096, max_bytes - len(data)))
        if not chunk:
            break
        data.extend(chunk)
        if b'\n' in chunk:
            return bytes(data[:data.index(b'\n') + 1])
    raise ValueError('incomplete or oversized message')


class LearningAgent:
    def __init__(self, state_path, shadow=False, status_path=None):
        self.store = LearningStore(state_path)
        self.shadow = bool(shadow)
        self.status_path = Path(status_path) if status_path else None
        self.previous = {}
        self.policies = {}
        self.restored = set()
        self.last_checkpoint = {}
        self.graph = RegionGraph()
        self.curriculum = Curriculum()

    def _policy(self, agent):
        if agent not in self.policies:
            import random
            self.policies[agent] = Policy(self.store, agent, random.Random(agent))
        return self.policies[agent]

    def handle(self, observation):
        if not isinstance(observation, LearningObservation):
            raise TypeError('LearningObservation required')
        state = json.dumps(observation.state, sort_keys=True, separators=(',', ':'))
        if observation.agent not in self.restored:
            try:
                saved = self.store.restore_latest(observation.agent)
            except ValueError:
                self.store.quarantine_corrupt(observation.agent)
                saved = self.store.restore_latest(observation.agent)
            if saved and saved.get('previous_state') and saved.get('previous_action'):
                self.previous[observation.agent] = (saved['previous_state'], saved['previous_action'], saved.get('updated_at', 0))
            self.restored.add(observation.agent)
        previous = self.previous.get(observation.agent)
        if previous:
            previous_state, previous_action, previous_at = previous
            previous_value = json.loads(previous_state)
            reward = 1.0 if previous_value.get('floor') != observation.state.get('floor') else 0.0
            transition_id = observation.state.get('transition_id')
            if reward and transition_id is not None:
                from .world import Position
                source = Position(previous_value['x'], previous_value['y'], previous_value['floor'])
                destination = Position(observation.state['x'], observation.state['y'], observation.state['floor'])
                self.graph.record_stair_observation(observation.agent, source, transition_id, destination)
                self.graph.observe_transition(observation.agent, source, destination, transition_id, observation.observed_at)
                self.curriculum.record(observation.agent, {'region': 'cave', 'floor': observation.state['floor']})
            self.store.record_transition(observation.agent, previous_state, previous_action, state,
                                         {'floor': observation.state.get('floor'),
                                          'xp_delta': observation.state.get('experience', 0) - previous_value.get('experience', 0),
                                          'health_delta': observation.state.get('health', 0) - previous_value.get('health', 0),
                                          'death': observation.state.get('death', False),
                                          'executed_action': previous_action}, reward, observation.observed_at)
            self._policy(observation.agent).update(previous_state, previous_action, reward, state,
                                                   ('move', 'hunt', 'retreat', 'wait'))
        if observation.state.get('health_band') in ('critical', 'wounded'):
            kind = 'retreat'
        else:
            allowed = ('hunt', 'move', 'wait') if observation.state.get('goal') == 'hunt' else ('move', 'wait')
            kind = self._policy(observation.agent).choose(state, allowed)
        self.previous[observation.agent] = (state, kind, observation.observed_at)
        previous_checkpoint = self.last_checkpoint.get(observation.agent)
        old_floor = json.loads(previous[0]).get('floor') if previous else None
        should_checkpoint = (previous_checkpoint is None or old_floor != observation.state.get('floor') or
                             observation.observed_at - previous_checkpoint >= 30)
        if should_checkpoint:
            self.store.checkpoint(observation.agent, {
                'previous_state': state, 'previous_action': kind, 'updated_at': observation.observed_at})
            self.last_checkpoint[observation.agent] = observation.observed_at
        self._write_status()
        if self.shadow:
            return None
        return LearningIntent(observation.agent, kind, {'source': 'learner'}, observation.observed_at, 2.0)

    def close(self):
        self.store.close()

    def _write_status(self):
        if not self.status_path:
            return
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({'agents': sorted(self.previous), 'shadow': self.shadow,
                              'at': time.time()}, separators=(',', ':'))
        temp = self.status_path.with_suffix('.tmp')
        temp.write_text(payload, encoding='utf-8')
        os.replace(temp, self.status_path)


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
                data = recv_line(sock)
            if not data:
                return None
            message = decode_message(data)
            payload = message.get('payload')
            if not isinstance(payload, dict) or message['type'] != 'intent' or payload.get('shadow'):
                return None
            raw_ttl = message.get('ttl', self.intent_ttl)
            if not isinstance(raw_ttl, (int, float)) or raw_ttl <= 0:
                return None
            intent = LearningIntent(message['agent'], message['kind'], payload,
                                    message['issued_at'], min(raw_ttl, self.intent_ttl))
            if intent.expired(time.time()):
                return None
            self._intent = intent
            return intent
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    async def publish_async(self, observation):
        return await asyncio.to_thread(self.publish, observation)

    def poll_intent(self, now=None):
        intent, self._intent = self._intent, None
        return None if intent is None or intent.expired(time.time() if now is None else now) else intent

    def close(self):
        self._intent = None


def serve(socket_path, state_path, shadow=False, status_path=None):
    path = Path(socket_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    learner = LearningAgent(state_path, shadow=shadow, status_path=status_path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(str(path)); server.listen(8)
    try:
        while True:
            conn, _ = server.accept()
            with conn:
                conn.settimeout(1.0)
                try:
                    message = decode_message(recv_line(conn))
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
