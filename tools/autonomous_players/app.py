"""Persistent population lifecycle. The game runner has no SQL credentials."""
import asyncio
import faulthandler
import json
import random
import secrets
import signal
import time
from pathlib import Path
from .behaviour import Agent
from .conversation import Conversation,ReplyBudget
from .creature_rules import PASSIVE_FOOD_CREATURES
from .definitions import load_items
from .health import atomic_json
from .learning import Policy
from .learning_bridge import LearningBridge
from .learning_protocol import LearningObservation
from .learned_navigation import RegionGraph
from .navigation import DIRECTIONS,walkable
from .protocol import Decoder
from .progression import Progression
from .runtime import Session,RateLimit
from .social import party_action
from .store import Store
from .supervisor import HealthSample,Supervisor
from .wire import LoginCredentials,ProtocolError


def new_learning_session_id():
    """Return a process-independent ID so reconnects never reuse an old timeline."""
    return secrets.token_hex(16)


def classify_learning_action(intent,priority,progression_busy,actions,sent,controlled_kind=None):
    """Attribute only learner intents that actually controlled a sent action."""
    if intent is None or progression_busy or controlled_kind != intent.kind:
        return 'none'
    kind=intent.kind
    if kind=='wait':
        return 'none'
    if not sent or kind not in ('move','hunt','retreat'):
        return 'none'
    accepted_packets = sent if isinstance(sent,(list,tuple,set)) else None
    was_sent = lambda action: (action in accepted_packets if accepted_packets is not None else bool(sent))
    if kind in ('hunt','retreat'):
        if controlled_kind != kind:
            return 'none'
        if accepted_packets is None:
            return kind
        relevant_opcodes=set(DIRECTIONS.values())|({0xa0,0xa1} if kind=='hunt' else {0x96})
        return kind if any(action in accepted_packets and action and action[0] in relevant_opcodes
                           for action in actions) else 'none'
    walk_opcodes=frozenset(DIRECTIONS.values())
    if any(isinstance(action,(bytes,bytearray)) and action and action[0] in walk_opcodes and was_sent(action)
           for action in actions):
        return 'move'
    return 'none'


def connection_failure_payload(exc):
    payload={'kind':type(exc).__name__}
    if isinstance(exc,ProtocolError):
        detail=''.join(char for char in str(exc) if char.isprintable())[:160]
        if detail:
            payload['detail']=detail
    return payload


def death_event_payload(world, agent, previous_decision):
    """Capture bounded observed context for diagnosing a real character death."""
    def creature_payload(creature):
        if not creature or not creature.position:
            return None
        return {
            'name': ''.join(c for c in creature.name if c.isprintable())[:32],
            'health': int(creature.health),
            'position': [creature.position.x, creature.position.y, creature.position.z],
        }

    position = world.position
    target_creature = world.creatures.get(agent.target)
    target = creature_payload(target_creature) if target_creature and target_creature.kind == 'monster' else None
    nearby = []
    if position:
        monsters = (c for c in world.creatures.values()
                    if c.kind == 'monster' and c.position and c.health > 0 and
                    c.position.distance(position) <= 7)
        nearby = [creature_payload(c) for c in
                  sorted(monsters, key=lambda c: (c.position.distance(position), c.id))[:5]]

    decision = {}
    if isinstance(previous_decision, dict):
        actions = previous_decision.get('actions')
        if isinstance(actions, (list, tuple)):
            decision['actions'] = [int(action) for action in actions[:3]
                                   if type(action) is int]
        for key in ('walkable_neighbors', 'tiles', 'visible_goals'):
            value = previous_decision.get(key)
            if type(value) is int and 0 <= value <= 10000:
                decision[key] = value
        for key in ('next_action_in', 'receive_age'):
            value = previous_decision.get(key)
            if type(value) in (int, float) and 0 <= value <= 3600:
                decision[key] = round(float(value), 1)

    strategy = agent.strategy if agent.strategy in ('explore', 'hunt', 'retreat', 'forage') else 'unknown'
    return {
        'level': int(world.stats.level),
        'experience': int(world.stats.experience),
        'health': int(world.stats.health),
        'max_health': int(world.stats.max_health),
        'icons': int(world.icons),
        'position': [position.x, position.y, position.z] if position else None,
        'strategy': strategy,
        'retreat_needed': bool(agent.retreat_needed()),
        'food_available': next(agent.food(), None) is not None,
        'target': target,
        'nearby_monsters': nearby,
        'decision': decision,
    }


def validate_config(config):
    required = {'identity','public_authorized','max_players','host','game_port','manifest','state_dir','health_file','items','modulus'}
    if (not required.issubset(config) or config['public_authorized'] is not True or not config['identity'] or
        type(config['max_players']) is not int or not 1 <= config['max_players'] <= 20 or
        not 1 <= config['game_port'] <= 65535):
        raise ValueError('explicit authorized target and maximum 1..20 required')
    if config.get('immediate_target') is not None and (
            type(config['immediate_target']) is not int or config['immediate_target'] not in (10,20) or
            config['max_players'] != config['immediate_target']):
        raise ValueError('direct admission requires matching explicit maximum ten or twenty')
    return config


def admission_available(active,occupied,target):
    return active < target and occupied < target


def reconnect_delay(consecutive_failures):
    """Bounded exponential delay for consecutive connection failures."""
    failures=max(0,int(consecutive_failures))
    return 0 if failures==0 else min(300,5*2**min(failures,6))


def reset_failure_streak(failure_streak,online_seconds,stable_seconds=60):
    """Clear retry backoff only after a sustained online session."""
    return 0 if online_seconds>=stable_seconds else failure_streak


def observed_route_confidence(executed_action,previous_moves,current_moves):
    """Score the last route action only from server-confirmed movement deltas."""
    if (executed_action!='move' or type(previous_moves) is not int or
            type(current_moves) is not int or previous_moves<0 or current_moves<previous_moves):
        return 0.5
    return 1.0 if current_moves>previous_moves else 0.0


def observation_gap_payload(previous_sample_at,sample,controller_loop_gap,now,
                            controller_stage='unknown',controller_stage_seconds=0):
    """Bounded evidence to distinguish a delayed guardian sample from a stalled controller loop."""
    return dict(previous_sample_at=round(previous_sample_at,3),
                sample_at=round(sample.now,3),
                sample_gap_seconds=round(sample.now-previous_sample_at,3),
                sample_age_seconds=round(max(0.0,now-sample.measured_at),3),
                controller_loop_gap_seconds=round(max(0.0,controller_loop_gap),3),
                memory_mib=round(sample.memory_mib,1),
                cpu_percent=round(sample.cpu_percent,1),
                latency_ms=round(sample.latency_ms,1),
                dispatcher_queued=sample.dispatcher_queued,
                sql_age_seconds=round(sample.sql_age_seconds,3),
                server_pid=sample.server_pid,oom=sample.oom,
                counter_anomaly=sample.counter_anomaly,
                controller_stage=str(controller_stage)[:32],
                controller_stage_seconds=round(max(0.0,controller_stage_seconds),3))


async def connection_admission(budget,draining):
    if budget is None:
        return not draining.is_set()
    acquire=asyncio.create_task(budget.acquire())
    stopped=asyncio.create_task(draining.wait())
    try:
        await asyncio.wait((acquire,stopped),return_when=asyncio.FIRST_COMPLETED)
        if draining.is_set():
            return False
        await acquire
        return True
    finally:
        for task in (acquire,stopped):
            if not task.done():task.cancel()
        await asyncio.gather(acquire,stopped,return_exceptions=True)


def choose_actions(agent,progression,now):
    progression.authorization,progression.floor_authorization=None,None
    if agent.priority(now):
        if getattr(progression,'healer_greeted',False) and not agent.retreat_needed():
            finish=getattr(progression,'finish_healer_dialogue',None)
            dialogue=finish(now) if finish else None
            if dialogue is not None:
                return dialogue
        return agent.step(now)
    actions=progression.step(now)
    return actions if actions or progression.busy else agent.step(now)


def apply_learning_intent(intent, progression, now, fallback):
    if intent is not None and intent.kind == 'retreat':
        recovered = progression.recover(now)
        return recovered or fallback
    return fallback


def select_actions_with_learning(agent, progression, now, intent):
    progression.authorization, progression.floor_authorization = None, None
    if agent.priority(now):
        if getattr(progression,'healer_greeted',False) and not agent.retreat_needed():
            finish=getattr(progression,'finish_healer_dialogue',None)
            dialogue=finish(now) if finish else None
            if dialogue is not None:
                return dialogue, None
        if intent is not None and intent.kind in ('move','hunt'):
            hint='explore' if intent.kind=='move' else 'hunt'
            actions=agent.step(now,strategy_hint=hint)
            controlled_kind=(intent.kind if getattr(agent,'strategy_hint_applied',False) else None)
            return actions, controlled_kind
        return agent.step(now), None
    if intent is not None and not progression.busy:
        if intent.kind == 'retreat':
            recovered = progression.recover(now)
            if recovered:
                return recovered, 'retreat'
        if intent.kind in ('move', 'hunt'):
            step_with_intent=getattr(progression,'step_with_intent',None)
            if callable(step_with_intent):
                actions=step_with_intent(now,intent.kind)
            else:
                actions=progression.step(now)
            if actions or progression.busy:
                controlled_kind=(intent.kind if actions and not progression.busy and
                                 getattr(progression,'strategy_hint_applied',False) else None)
                return actions, controlled_kind
            if intent.kind == 'move':
                actions=agent.step(now, strategy_hint='explore')
                controlled_kind='move' if getattr(agent,'strategy_hint_applied',False) else None
                return actions, controlled_kind
            actions=agent.step(now,strategy_hint='hunt')
            controlled_kind='hunt' if getattr(agent,'strategy_hint_applied',False) else None
            return actions, controlled_kind
    actions = progression.step(now)
    if actions or progression.busy:
        return actions, None
    return agent.step(now), None


def choose_actions_with_learning(agent, progression, now, intent):
    return select_actions_with_learning(agent, progression, now, intent)[0]


def occupancy_ids(active_tasks,disconnected,rows,sql_at):
    occupied=set(active_tasks)
    online={row[0] for row in rows if row[-1]==1}
    occupied.update(online)
    for player_id,at in disconnected.items():
        if at>sql_at:
            occupied.add(player_id)
    return occupied


def functional_population(status,population,target,now=None):
    now = time.time() if now is None else now
    online = {row[0] for row in population.get('players',[]) if row[-1] == 1}
    active = [key for key,value in status.items() if value.get('online')]
    return (target > 0 and len(active) >= target and all(key in online and status[key].get('moves',0) >= 5 and
            status[key].get('xp_gain',0) > 0 and 0 <= now-status[key].get('last_progress_at',0) <= 120 and
            0 <= now-status[key].get('last_xp_at',0) <= 600 for key in active))


def sync_confirmed_kills(store,character,current,reported,baseline,status,at,learned_navigation=None):
    totals=dict(baseline)
    for name,count in current.items():
        totals[name]=totals.get(name,0)+count
    events=[]
    for name,count in current.items():
        delta=count-reported.get(name,0)
        if delta>0:
            events.append((at,'kill_confirmed',
                           dict(creature=name,count=delta,total=totals[name])))
    if events:
        checkpoint=dict(status)
        checkpoint['confirmed_kill_types']=totals
        checkpoint['confirmed_kills']=sum(totals.values())
        if learned_navigation is not None:
            checkpoint['learned_navigation']=learned_navigation
        store.record_events_and_checkpoint(character,events,checkpoint)
        for name,count in current.items():
            reported[name]=count
    status['confirmed_kill_types']=totals
    status['confirmed_kills']=sum(totals.values())


def owned_food_count(world,items):
    possessions=list(world.inventory.values())
    possessions.extend(item for container in world.containers.values()
                       if 'dead' not in container.name.lower() and
                       'dead' not in items[container.item_id].name.lower()
                       for item in container.items)
    return sum(max(1,item.count) for item in possessions
               if items[item.id].attributes.get('nutrition',0)>0)


class PlayerRunner:
    def __init__(self,profile,config,items,store,names,routes=None,budget=None,conversation_budget=None,connection_budget=None):
        self.profile,self.config,self.items,self.store,self.names = profile,config,items,store,names
        self.draining = asyncio.Event()
        self.session = None
        self.routes=routes
        self.budget=budget
        self.connection_budget=connection_budget
        self.conversation_budget=conversation_budget or ReplyBudget()
        self.status = dict(online=False,moves=0,xp_gain=0,failures=0,
                           confirmed_kills=0,confirmed_kill_types={})
        self.learning = LearningBridge(config['learning_socket']) if config.get('learning_socket') else None
        self.learned_graph = RegionGraph()
        saved=self.store.restore(profile['character'])
        if isinstance(saved,dict):
            try:
                self.status['confirmed_kill_types']={name:max(0,int(count))
                    for name,count in saved.get('confirmed_kill_types',{}).items()
                    if isinstance(name,str) and 0<len(name)<=80}
                self.status['confirmed_kills']=sum(self.status['confirmed_kill_types'].values())
            except (AttributeError,TypeError,ValueError):
                self.status['confirmed_kill_types']={}
                self.status['confirmed_kills']=0
        if isinstance(saved,dict) and saved.get('learned_navigation') is not None:
            try:
                self.learned_graph.restore(profile['character'],saved['learned_navigation'])
            except ValueError:
                self.store.event(time.time(),profile['character'],'navigation_memory_invalid',{})

    def save_checkpoint(self):
        checkpoint=dict(self.status)
        checkpoint['learned_navigation']=self.learned_graph.snapshot(self.profile['character'])
        self.store.checkpoint(self.profile['character'],checkpoint)

    def record_learned_transition(self,source,destination,transition_id,observed_at):
        character=self.profile['character']
        self.learned_graph.record_stair_observation(character,source,transition_id,destination)
        confirmed=self.learned_graph.observe_transition(
            character,source,destination,transition_id,observed_at)
        if confirmed:
            self.save_checkpoint()
        return confirmed

    async def run(self):
        p = self.profile
        failures = 0
        failure_streak = 0
        while not self.draining.is_set():
            task = None
            connected_since = None
            try:
                if not await connection_admission(self.connection_budget,self.draining):
                    return
                s = self.session = await Session.connect(self.config['host'],self.config['game_port'],
                    LoginCredentials(p['account'],p['character'],p['password']),int(self.config['modulus']),Decoder(self.items))
                learning_session_id=new_learning_session_id()
                connected_since = time.monotonic()
                s.gate.own_names = self.names
                s.global_budget=self.budget
                policy = Policy(self.store,p['character'],random.Random(p['account']+failures))
                agent = Agent(p['character'],s.world,self.items,policy)
                agent.own_names = self.names
                kill_type_baseline=dict(self.status.get('confirmed_kill_types',{}))
                reported_kill_types={}
                conversation=Conversation(p['character'],s.world,p,self.names)
                from .world import Position
                progression=Progression(p,s.world,self.items,self.routes,
                    Position(*self.config.get('oracle_position',[32104,32190,6])),
                    tuple(self.config.get('rook_bounds',[32000,32000,32200,32350])),
                    self.config.get('hunting_points',[]), learned_graph=self.learned_graph)
                agent.escape=progression.recover
                agent.retreat_routes=progression.routes
                agent.retreat_goal=Position(32097,32218,7)
                agent.forage=progression.forage
                initial_exp,last_social,last_ping,last_saved,last_learning = None,0,0,0,0
                last_food_count=None
                last_executed_action = 'none'
                last_learning_moves = self.status['moves']
                pending_transition_id = None
                pending_transition_source = None
                pending_transition_deadline = 0
                last_learning_floor = None
                async def observed(events):
                    agent.observe(events,time.monotonic())
                    sync_confirmed_kills(self.store,p['character'],agent.confirmed_kill_types,
                                         reported_kill_types,kill_type_baseline,self.status,time.time(),
                                         self.learned_graph.snapshot(p['character']))
                    progression.observe(events,time.monotonic())
                    conversation.observe(events,time.monotonic(),agent.strategy)
                    s.gate.allowed_corpses = set(agent.allowed_corpses)
                    for e in events:
                        if e.kind == 'move' and e.data[0] == s.world.self_id:
                            self.status['moves'] += 1
                            self.status['last_progress_at'] = time.time()
                s.on_events = observed
                task = asyncio.create_task(s.receive())
                drain_started = None
                while True:
                    if task.done():
                        await task
                    now = time.monotonic()
                    w = s.world
                    self.status['online'] = bool(w.valid and w.self_id and w.position and w.stats.level)
                    if self.status['online'] and connected_since is not None:
                        failure_streak=reset_failure_streak(failure_streak,now-connected_since)
                        if failure_streak==0:
                            connected_since=None
                    if initial_exp is None and self.status['online']:
                        initial_exp = w.stats.experience
                    if w.stats.experience > self.status.get('experience',w.stats.experience):
                        self.status['last_progress_at'] = self.status['last_xp_at'] = time.time()
                    self.status.update(level=w.stats.level,experience=w.stats.experience,
                        xp_gain=max(0,w.stats.experience-(initial_exp or 0)),health=w.stats.health,
                        position=[w.position.x,w.position.y,w.position.z] if w.position else None)
                    sync_confirmed_kills(self.store,p['character'],agent.confirmed_kill_types,
                                         reported_kill_types,kill_type_baseline,self.status,time.time(),
                                         self.learned_graph.snapshot(p['character']))
                    if self.status['online']:
                        food_count=owned_food_count(w,self.items)
                        if last_food_count is not None and food_count>last_food_count:
                            gained=food_count-last_food_count
                            self.status['food_received']=self.status.get('food_received',0)+gained
                            self.status['last_food_at']=time.time()
                            self.store.event(time.time(),p['character'],'food_received',dict(count=gained))
                        last_food_count=food_count
                    learned_intent = None
                    if self.learning and self.status['online'] and now-last_learning >= 2:
                        if pending_transition_id is not None and now > pending_transition_deadline:
                            pending_transition_id = None
                            pending_transition_source = None
                        retreat_signal=agent.retreat_needed()
                        retreat_required=retreat_signal if type(retreat_signal) is bool else False
                        available_prey=agent.prey()
                        observed_moves=self.status['moves']
                        route_confidence=observed_route_confidence(
                            last_executed_action,last_learning_moves,observed_moves)
                        observation = LearningObservation.from_world(p['character'], w,
                            'retreat' if retreat_required else 'hunt',
                            route_confidence, transition_id=pending_transition_id,
                            executed_action=last_executed_action,
                            food_available=next(agent.food(), None) is not None,
                            retreat_available=progression.in_rook(),
                            move_count=self.status['moves'],session_id=learning_session_id,
                            combat_stalls=(agent.combat_stalls
                                           if type(getattr(agent,'combat_stalls',0)) is int else 0),
                            hunt_kills=(agent.confirmed_kills
                                        if type(getattr(agent,'confirmed_kills',0)) is int else 0),
                            retreat_required=retreat_required,
                            prey_available=bool(available_prey),
                            food_prey_available=any(c.name.lower() in PASSIVE_FOOD_CREATURES
                                                    for c in available_prey))
                        last_learning_moves=observed_moves
                        last_executed_action = 'none'
                        if (pending_transition_id is not None and pending_transition_source is not None and
                                last_learning_floor is not None and w.position.z != last_learning_floor):
                            self.record_learned_transition(
                                pending_transition_source,w.position,pending_transition_id,time.time())
                        await self.learning.publish_async(observation)
                        learned_intent = self.learning.poll_intent(time.time())
                        if pending_transition_id is not None and last_learning_floor is not None and w.position.z != last_learning_floor:
                            pending_transition_id = None
                            pending_transition_source = None
                        last_learning_floor = w.position.z
                        last_learning = now
                    if (not self.draining.is_set() and self.status['online'] and
                            w.stats.max_health>0 and w.stats.health<=0):
                        self.status['deaths']=self.status.get('deaths',0)+1
                        self.store.event(time.time(),p['character'],'death',
                                         death_event_payload(w,agent,self.status.get('decision',{})))
                        break  # Dead clients cannot receive new-ping replies.
                    if self.draining.is_set():
                        if drain_started is None:
                            drain_started = now
                            await s.send(b'\xbe',control=True)
                        s.gate.suspended = True
                        if not (w.icons & 128) or now-drain_started >= 90:
                            break
                    else:
                        priority = agent.priority(now)
                        actions,controlled_kind=select_actions_with_learning(agent,progression,now,learned_intent)
                        floor_attempt = progression.floor_authorization if actions else None
                        floor_source = w.position if floor_attempt else None
                        if progression.authorization:
                            s.gate.authorize_speech(*progression.authorization)
                        s.gate.floor_token=progression.floor_authorization
                        self.status.update(strategy=agent.strategy,npc_busy=progression.busy,
                            purchase=progression.purchase.state if progression.purchase else None,
                            food_available=next(agent.food(),None) is not None,
                            healing=progression.healing_status(now),
                            hunting=progression.hunting_status(now))
                        # Bounded operational evidence for diagnosing idle clients and ping loss.
                        visible_prey=agent.prey() if w.position else []
                        visible_goals=self.status.get('decision',{}).get('visible_goals')
                        if (visible_goals is None and w.position and not actions and
                                self.status['moves']==0):
                            visible_goals=sum(p.z==w.position.z and p.distance(w.position)>1 and
                                              walkable(w,p,self.items) for p in w.tiles)
                        self.status['decision']={
                            'priority': bool(priority),
                            'retreat': bool(agent.retreat_needed()),
                            'actions': [a[0] for a in actions[:3] if a],
                            'target': agent.target,
                            'prey': [(c.name,c.position.x,c.position.y,c.position.z)
                                     for c in visible_prey[:3]],
                            'tiles': len(w.tiles),
                            'walkable_neighbors': sum(walkable(w,w.position.shift(dx,dy),self.items)
                                                      for dx,dy in ((0,1),(1,0),(0,-1),(-1,0))) if w.position else 0,
                            'visible_goals': visible_goals,
                            'next_action_in': round(max(0,agent.next_action-now),1),
                            'ping_pending': len(s.pings),
                            'oldest_ping_age': round(now-min(s.pings.values()),1) if s.pings else 0,
                            'receive_age': round(now-s.last_received,1),
                        }
                        victim=w.creatures.get(agent.target)
                        self.status['combat']={
                            'victim':(victim.name,victim.health,
                                      [victim.position.x,victim.position.y,victim.position.z])
                                      if victim and victim.position else None,
                            'passive_corpse_claims':agent.passive_corpse_claims,
                            'owned_corpses':len(agent.allowed_corpses),
                            'loot_pending':bool(agent.loot_pending),
                            'corpse_food':sum(max(1,item.count) for container in w.containers.values()
                                               if agent.loot_pending and container.item_id==agent.loot_pending[1]
                                               for item in container.items
                                               if self.items[item.id].attributes.get('nutrition',0)>0),
                        }
                        sent = False
                        sent_packets=[]
                        for action in actions:
                            action_sent=bool(await s.send(action))
                            sent = action_sent or sent
                            if action_sent:
                                sent_packets.append(action)
                        classified_action=classify_learning_action(
                            learned_intent,priority,progression.busy,actions,sent_packets,controlled_kind)
                        if classified_action!='none':
                            last_executed_action=classified_action
                        elif priority or progression.busy or learned_intent is not None:
                            # A new urgent, busy or learner-selected decision supersedes the pending sample.
                            last_executed_action='none'
                        if floor_attempt:
                            if sent:
                                pending_transition_id = floor_attempt[1]
                                pending_transition_source = floor_source
                                pending_transition_deadline = now + 15
                            else:
                                pending_transition_id = None
                                pending_transition_source = None
                        reply=conversation.step(now,self.conversation_budget) if not progression.busy else None
                        if reply:
                            from .protocol import say
                            s.gate.authorize_reply(reply[0],reply[1],time.monotonic()+5)
                            await s.send(say(reply[1]))
                            self.status['replies']=conversation.replies
                        if now-last_social >= 15:
                            last_social = now
                            for c in w.creatures.values():
                                if c.id == w.self_id or not c.position:
                                    continue
                                if c.shield == 1 or (c.name in self.names and p['character'] < c.name):
                                    action = party_action(c,self.names)
                                    if action:
                                        await s.send(action)
                                        break
                        if now-last_ping >= 10 and self.status['online']:
                            await s.ping();last_ping=now
                    if now-last_saved >= 30:
                        self.save_checkpoint()
                        last_saved = now
                    await asyncio.sleep(.2)
                if self.draining.is_set():
                    return
            except (OSError,EOFError,TimeoutError,ProtocolError) as exc:
                failures += 1
                failure_streak += 1
                failure=connection_failure_payload(exc)
                self.status.update(failures=failures,error=failure['kind'])
                if 'detail' in failure:
                    self.status['error_detail']=failure['detail']
                stage=getattr(exc,'stage',None)
                self.status['error_stage']=stage
                failure['stage']=stage
                self.store.event(time.time(),p['character'],'connection_failure',failure)
                if isinstance(exc,ProtocolError):
                    # A changed layout needs a reviewed fix, not an endless login loop.
                    self.status['halted'] = True
                    return
            finally:
                self.status['online'] = False
                self.status['disconnected_at']=time.time()
                self.save_checkpoint()
                if self.session:
                    try:
                        await self.session.close()
                    except (OSError,TimeoutError):
                        pass
                if task:
                    task.cancel();await asyncio.gather(task,return_exceptions=True)
                self.session = None
                if self.learning:
                    self.learning.close()
            try:
                await asyncio.wait_for(self.draining.wait(),reconnect_delay(failure_streak))
            except asyncio.TimeoutError:
                pass


async def run(config):
    config = validate_config(config)
    manifest = json.loads(Path(config['manifest']).read_text())
    if manifest['identity'] != config['identity'] or not manifest.get('provisioned'):
        raise ValueError('manifest is not provisioned for this world')
    profiles = manifest['players']
    if not 1 <= len(profiles) <= 20 or any('player_id' not in p for p in profiles):
        raise ValueError('invalid persistent population')
    state_dir = Path(config['state_dir']);state_dir.mkdir(parents=True,exist_ok=True)
    items = load_items(Path(config['items']))
    from .routes import RouteGraph
    routes=RouteGraph.load(config['routes']) if config.get('routes') else None
    stop = asyncio.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(sig,stop.set)
    with Store(state_dir/'state.db') as store:
        saved = store.restore('_supervisor')
        guard = Supervisor(saved,immediate_target=config.get('immediate_target'))
        if saved is None and config.get('preflight_baseline'):
            try:
                previous=json.loads(Path(config['preflight_baseline']).read_text())
                health=json.loads(Path(config['health_file']).read_text())
                guard=Supervisor.from_preflight([HealthSample(**row['sample']) for row in previous],
                                               HealthSample(**health['sample']))
            except (OSError,KeyError,TypeError,ValueError):
                guard=Supervisor()
        runners,tasks = {},{}
        names = {p['character'] for p in profiles}
        last_admission,last_measurement = 0,None
        last_loop_at=None
        last_loop_stage,last_loop_stage_at='startup',time.monotonic()
        budget=RateLimit(40,40)
        connection_budget=RateLimit(.1,1)
        conversation_budget=ReplyBudget()
        paused = False
        try:
            while not stop.is_set():
                now = time.time()
                loop_gap=0.0 if last_loop_at is None else now-last_loop_at
                previous_loop_stage=last_loop_stage
                previous_loop_stage_seconds=max(0.0,time.monotonic()-last_loop_stage_at)
                last_loop_at=now
                control = state_dir/'control.json'
                last_loop_stage,last_loop_stage_at='control_read',time.monotonic()
                if control.exists():
                    request = json.loads(control.read_text())
                    if request.get('action') == 'stop':
                        stop.set()
                    paused = request.get('action') in ('pause','stop')
                target,population = 0,{}
                try:
                    last_loop_stage,last_loop_stage_at='health_read',time.monotonic()
                    health = json.loads(Path(config['health_file']).read_text())
                    if health.get('error'):
                        raise ValueError('guardian failed')
                    sample = HealthSample(**health['sample'])
                    population = health['population']
                    observed={row[0]:row for row in population.get('players',[])}
                    for p in profiles:
                        if p['player_id'] in observed:
                            p['observed_vocation']=observed[p['player_id']][4]
                    if now-sample.measured_at > 120 or now-health['sql_measured_at'] > 90:
                        raise ValueError('health lease expired')
                    if sample.measured_at != last_measurement:
                        last_loop_stage,last_loop_stage_at='supervisor_observe',time.monotonic()
                        status = {key:r.status for key,r in runners.items()}
                        previous_sample_at=guard.state.get('last')
                        if (previous_sample_at is not None and
                                sample.now-previous_sample_at>15):
                            store.event(time.time(),'_supervisor','observation_gap',
                                observation_gap_payload(previous_sample_at,sample,loop_gap,now,
                                    previous_loop_stage,previous_loop_stage_seconds))
                        decision = guard.observe(sample,functional_population(status,population,guard.state['target']))
                        store.checkpoint('_supervisor',guard.snapshot())
                        last_measurement = sample.measured_at
                    target = min(guard.state['target'],config['max_players'],len(profiles))
                except (OSError,KeyError,TypeError,ValueError):
                    guard._suspend('guardian unavailable')
                    store.checkpoint('_supervisor',guard.snapshot())
                if paused or stop.is_set():
                    target = 0
                if any(r.status.get('halted') for r in runners.values()):
                    guard._suspend('client protocol fault')
                    store.checkpoint('_supervisor',guard.snapshot())
                    target=0
                active = [key for key,r in runners.items() if not r.draining.is_set() and not tasks[key].done()]
                last_loop_stage,last_loop_stage_at='runner_scheduling',time.monotonic()
                for key in active[target:]:
                    runners[key].draining.set()
                occupied=len(occupancy_ids({key for key,t in tasks.items() if not t.done()},
                    {key:r.status['disconnected_at'] for key,r in runners.items() if 'disconnected_at' in r.status},
                    population.get('players',[]),health.get('sql_measured_at',0) if 'health' in locals() else 0))
                if admission_available(len(active),occupied,target) and now-last_admission >= 2:
                    for p in profiles:
                        key = p['player_id']
                        if key in runners and (not tasks[key].done() or runners[key].status.get('halted')):
                            continue
                        runner = PlayerRunner(p,config,items,store,names,routes,budget,conversation_budget,connection_budget)
                        runners[key],tasks[key] = runner,asyncio.create_task(runner.run())
                        last_admission = now
                        break
                for task in tasks.values():
                    if task.done() and not task.cancelled() and task.exception():
                        raise task.exception()
                last_loop_stage,last_loop_stage_at='status_persist',time.monotonic()
                atomic_json(state_dir/'status.json',dict(at=now,target=target,supervisor=guard.snapshot(),
                    players={key:r.status for key,r in runners.items()},population=population),0o600)
                last_loop_stage,last_loop_stage_at='event_loop_yield',time.monotonic()
                faulthandler.dump_traceback_later(15,repeat=False)
                try:
                    await asyncio.sleep(.5)
                finally:
                    faulthandler.cancel_dump_traceback_later()
        finally:
            for runner in runners.values():
                runner.draining.set()
            if tasks:
                await asyncio.gather(*tasks.values(),return_exceptions=True)
