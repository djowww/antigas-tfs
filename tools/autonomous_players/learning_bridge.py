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
from .neural_policy import DeepQPolicy


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
    def __init__(self, state_path, shadow=False, status_path=None, neural_mode='off', neural_agents=None):
        if neural_mode not in ('off','shadow','active'):
            raise ValueError('invalid neural mode')
        self.store = LearningStore(state_path)
        self.shadow = bool(shadow)
        self.status_path = Path(status_path) if status_path else None
        self.neural_mode = neural_mode
        self.neural_agents = None if neural_agents is None else frozenset(neural_agents)
        if self.neural_agents is not None and any(not isinstance(name,str) or not 1<=len(name)<=64
                                                   for name in self.neural_agents):
            raise ValueError('invalid neural agent')
        self.neural_decisions = {}
        self.neural_confirmed = {}
        self.previous_neural = {}
        self.neural_error = None
        self.neural = None
        if neural_mode != 'off':
            try:
                self.neural = DeepQPolicy(Path(state_path).with_suffix('.neural.json'))
            except ValueError:
                # A corrupt optional model must never block the tabular learner.
                self.neural_error = 'invalid checkpoint'
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

    @staticmethod
    def policy_key(state):
        """Abstract spatial observations so outcomes transfer between nearby tiles."""
        level=max(0,int(state.get('level',0)))
        return json.dumps({
            'policy_schema':3,
            'floor':int(state.get('floor',0)),
            'level_band':level//5,
            'health_band':state.get('health_band'),
            'nearby_threats':min(8,max(0,int(state.get('nearby_threats',0)))),
            'goal':state.get('goal'),
            'retreat_required':state.get('retreat_required',False),
            'prey_available':state.get('prey_available',False),
            'food_prey_available':state.get('food_prey_available',False),
            'route_confidence':round(float(state.get('route_confidence',0)),3),
            'food_available':state.get('food_available'),
            'retreat_available':state.get('retreat_available'),
        },sort_keys=True,separators=(',',':'))

    def _migrate_legacy_values(self,agent,legacy_state,policy_state):
        """Copy exact-state and prior-context values without deleting history."""
        if legacy_state==policy_state:
            return
        current=self.store.values(agent,policy_state)
        sources=[legacy_state]
        try:
            observation=json.loads(legacy_state)
        except (TypeError,ValueError):
            observation=None
        if isinstance(observation,dict) and all(key in observation for key in
                ('floor','level','health_band','nearby_threats','goal','route_confidence')):
            shared_context={
                'floor':int(observation.get('floor',0)),
                'level_band':max(0,int(observation.get('level',0)))//5,
                'health_band':observation.get('health_band'),
                'nearby_threats':min(8,max(0,int(observation.get('nearby_threats',0)))),
                'goal':observation.get('goal'),
                'route_confidence':round(float(observation.get('route_confidence',0)),3),
                'food_available':observation.get('food_available'),
                'retreat_available':observation.get('retreat_available'),
            }
            prior_contexts=[]
            prior_contexts.append(dict(shared_context,policy_schema=2,
                                       retreat_required=observation.get('retreat_required',False)))
            prior_contexts.append(dict(shared_context,policy_schema=1))
            for prior in prior_contexts:
                prior_context=json.dumps(prior,sort_keys=True,separators=(',',':'))
                if prior_context not in sources and prior_context!=policy_state:
                    sources.append(prior_context)
        for source in sources:
            values=self.store.values(agent,source)
            for action,value in values.items():
                if action not in current:
                    self.store.set_value(agent,policy_state,action,value)
                    current[action]=value

    @staticmethod
    def _reward(previous, current, previous_action=None):
        """Turn observed outcomes into a bounded learning signal.

        Rewards come only from the world snapshot: floor progress and real XP
        are positive, damage and death are negative.  The cap prevents one
        unusually large server-side XP update from dominating future policy.
        """
        xp_delta = current.get('experience', 0) - previous.get('experience', 0)
        health_delta = current.get('health', 0) - previous.get('health', 0)
        previous_floor = previous.get('floor')
        current_floor = current.get('floor')
        reward = 0.0
        if previous_floor != current_floor:
            goal = previous.get('goal')
            # Rook caves descend toward larger z values; retreat routes return
            # toward the surface. Keep legacy observations useful when no goal
            # was recorded, while teaching direction-specific outcomes.
            if goal == 'hunt':
                reward = 1.0 if current_floor > previous_floor else -1.0
            elif goal == 'retreat':
                reward = 1.0 if current_floor < previous_floor else -1.0
            else:
                reward = 1.0
        if xp_delta > 0:
            reward += min(2.0, xp_delta / 100.0)
        if health_delta < 0:
            reward -= min(1.0, abs(health_delta) / max(1.0, previous.get('max_health', 1)))
        elif health_delta > 0:
            reward += min(1.0, health_delta / max(1.0, previous.get('max_health', 1)))
        if previous.get('food_available') is False and current.get('food_available') is True:
            reward += 0.5
        same_position = all(key in previous and key in current and previous[key] == current[key]
                            for key in ('floor', 'x', 'y'))
        previous_moves,current_moves=previous.get('move_count'),current.get('move_count')
        if type(previous_moves) is int and type(current_moves) is int:
            # A lower count means the runner restarted; its movement history is
            # no longer comparable, so never infer a stall from position alone.
            no_observed_movement=current_moves==previous_moves
        else:
            no_observed_movement=same_position
        if current.get('executed_action') == 'move' and no_observed_movement and xp_delta <= 0:
            reward -= 0.25  # A sent move with no observed displacement is weak negative evidence.
        previous_stalls=previous.get('combat_stalls',0)
        current_stalls=current.get('combat_stalls',0)
        if (previous_action=='hunt' and type(previous_stalls) is int and
                type(current_stalls) is int and current_stalls>previous_stalls):
            reward -= 1.0  # The runner cancelled a hunt after a confirmed no-progress timeout.
        previous_kills=previous.get('hunt_kills',0)
        current_kills=current.get('hunt_kills',0)
        if (previous_action=='hunt' and type(previous_kills) is int and
                type(current_kills) is int and current_kills>previous_kills):
            reward += min(2.0, float(current_kills-previous_kills))
        if current.get('death'):
            reward -= 3.0
        return max(-5.0, min(5.0, reward))

    def handle(self, observation):
        if not isinstance(observation, LearningObservation):
            raise TypeError('LearningObservation required')
        state = json.dumps(observation.state, sort_keys=True, separators=(',', ':'))
        policy_state=self.policy_key(observation.state)
        self._migrate_legacy_values(observation.agent,state,policy_state)
        if observation.agent not in self.restored:
            try:
                self.store.restore_latest(observation.agent)
            except ValueError:
                self.store.quarantine_corrupt(observation.agent)
                self.store.restore_latest(observation.agent)
            # Keep the checkpoint for recovery/audit, but do not train across
            # a process restart: the runner's next executed_action cannot be
            # matched reliably to the learner's pre-restart intent.
            self.restored.add(observation.agent)
        if (observation.state.get('health_band') == 'critical' or
                observation.state.get('retreat_required',False)):
            allowed_actions=('retreat',)
        else:
            allowed_actions=('hunt','move') if observation.state.get('goal') == 'hunt' else ('move',)
        previous = self.previous.get(observation.agent)
        if previous:
            previous_value=json.loads(previous[0])
            previous_session=previous_value.get('session_id')
            current_session=observation.state.get('session_id')
            if previous_session!=current_session and (previous_session is not None or current_session is not None):
                # A reconnect starts a new world timeline. Do not attribute XP,
                # movement, or stair changes during the disconnect to the last
                # action sent in the previous game session.
                previous=None
        if previous:
            previous_state, previous_action, previous_at = previous
            previous_value = json.loads(previous_state)
            previous_policy_state=self.policy_key(previous_value)
            self._migrate_legacy_values(observation.agent,previous_state,previous_policy_state)
            reward = self._reward(previous_value, observation.state,previous_action)
            transition_id = observation.state.get('transition_id')
            if previous_value.get('floor') != observation.state.get('floor') and transition_id is not None:
                from .world import Position
                source = Position(previous_value['x'], previous_value['y'], previous_value['floor'])
                destination = Position(observation.state['x'], observation.state['y'], observation.state['floor'])
                self.graph.record_stair_observation(observation.agent, source, transition_id, destination)
                verified = self.graph.observe_transition(observation.agent, source, destination, transition_id, observation.observed_at)
                self.store.route_edge(observation.agent, source, destination, transition_id, verified, observation.observed_at)
                from types import SimpleNamespace
                world_like = SimpleNamespace(stats=SimpleNamespace(
                    health=observation.state.get('health', 0),
                    max_health=observation.state.get('max_health', 0)))
                if self.curriculum.ready_for(observation.agent, 'cave', world_like,
                                             observation.state.get('food_available', False),
                                             observation.state.get('retreat_available', False)):
                    self.curriculum.record(observation.agent, {'region': 'cave', 'floor': observation.state['floor']})
            executed_action = observation.state.get('executed_action')
            self.store.record_transition(observation.agent, previous_state, previous_action, state,
                                         {'floor': observation.state.get('floor'),
                                          'xp_delta': observation.state.get('experience', 0) - previous_value.get('experience', 0),
                                          'health_delta': observation.state.get('health', 0) - previous_value.get('health', 0),
                                          'death': observation.state.get('death', False),
                                          'executed_action': executed_action}, reward, observation.observed_at)
            # The runner may replace or reject an intent because of urgent
            # health, progression, cooldown, or safety rules. Only credit the
            # action when the observation confirms that the prior intent ran.
            combat_stall=(previous_action=='hunt' and
                          type(previous_value.get('combat_stalls',0)) is int and
                          type(observation.state.get('combat_stalls',0)) is int and
                          observation.state.get('combat_stalls',0)>previous_value.get('combat_stalls',0))
            confirmed_hunt_kill=(previous_action=='hunt' and
                                 type(previous_value.get('hunt_kills',0)) is int and
                                 type(observation.state.get('hunt_kills',0)) is int and
                                 observation.state.get('hunt_kills',0)>previous_value.get('hunt_kills',0))
            if ((executed_action == previous_action or combat_stall or confirmed_hunt_kill) and
                    previous_action in ('move', 'hunt', 'retreat', 'wait')):
                if executed_action==previous_action and self.previous_neural.get(observation.agent,False):
                    self.neural_confirmed[observation.agent]=self.neural_confirmed.get(observation.agent,0)+1
                self._policy(observation.agent).update(previous_policy_state, previous_action, reward, policy_state,
                                                       allowed_actions,
                                                       terminal=bool(observation.state.get('death')))
                if self.neural is not None and previous_action in ('move','hunt'):
                    try:
                        self.neural.observe(previous_value,previous_action,reward,
                                            observation.state,allowed_actions,
                                            terminal=bool(observation.state.get('death')))
                    except ValueError:
                        self.neural_error='invalid transition'
                        self.neural=None
        neural_selected=False
        if allowed_actions == ('retreat',):
            kind = 'retreat'
        elif (self.neural_mode=='active' and self.neural is not None and self.neural.updates>=1000
              and (self.neural_agents is None or observation.agent in self.neural_agents)):
            try:
                kind=self.neural.choose(observation.state,allowed_actions)
                if kind not in allowed_actions:
                    raise ValueError('neural action outside safety mask')
                self.neural_decisions[observation.agent]=self.neural_decisions.get(observation.agent,0)+1
                neural_selected=True
            except ValueError:
                self.neural_error='invalid action'
                kind=self._policy(observation.agent).choose(policy_state,allowed_actions)
        else:
            # Waiting without a threat, active server action, or other explicit
            # reason can freeze a newly initialized policy in place.
            kind = self._policy(observation.agent).choose(policy_state, allowed_actions)
        self.previous[observation.agent] = (state, kind, observation.observed_at)
        self.previous_neural[observation.agent]=neural_selected
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
        if self.neural is not None:
            self.neural.save()
        self.store.close()

    def _write_status(self):
        if not self.status_path:
            return
        self.status_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({'agents': sorted(self.previous), 'shadow': self.shadow,
                              'neural_mode':self.neural_mode,
                              'neural_updates':self.neural.updates if self.neural else 0,
                              'neural_error':self.neural_error,
                              'neural_agents':sorted(self.neural_agents) if self.neural_agents is not None else None,
                              'neural_decisions':self.neural_decisions,
                              'neural_confirmed':self.neural_confirmed,
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
        # A failed or mismatched reply must never leave an older action queued.
        self._intent = None
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
            if (message.get('agent') != observation.agent or not isinstance(payload, dict) or
                    message['type'] != 'intent' or payload.get('shadow')):
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


def serve(socket_path, state_path, shadow=False, status_path=None, neural_mode='off', neural_agents=None):
    path = Path(socket_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.unlink()
    except FileNotFoundError:
        pass
    learner = LearningAgent(state_path, shadow=shadow, status_path=status_path,
                            neural_mode=neural_mode, neural_agents=neural_agents)
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
