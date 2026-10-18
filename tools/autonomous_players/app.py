"""Persistent population lifecycle. The game runner has no SQL credentials."""
import asyncio
import json
import random
import signal
import time
from pathlib import Path
from .behaviour import Agent
from .conversation import Conversation,ReplyBudget
from .definitions import load_items
from .health import atomic_json
from .learning import Policy
from .protocol import Decoder
from .progression import Progression
from .runtime import Session,RateLimit
from .social import party_action
from .store import Store
from .supervisor import HealthSample,Supervisor
from .wire import LoginCredentials,ProtocolError


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
        return agent.step(now)
    actions=progression.step(now)
    return actions if actions or progression.busy else agent.step(now)


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


class PlayerRunner:
    def __init__(self,profile,config,items,store,names,routes=None,budget=None,conversation_budget=None,connection_budget=None):
        self.profile,self.config,self.items,self.store,self.names = profile,config,items,store,names
        self.draining = asyncio.Event()
        self.session = None
        self.routes=routes
        self.budget=budget
        self.connection_budget=connection_budget
        self.conversation_budget=conversation_budget or ReplyBudget()
        self.status = dict(online=False,moves=0,xp_gain=0,failures=0)

    async def run(self):
        p = self.profile
        failures = 0
        while not self.draining.is_set():
            task = None
            try:
                if not await connection_admission(self.connection_budget,self.draining):
                    return
                s = self.session = await Session.connect(self.config['host'],self.config['game_port'],
                    LoginCredentials(p['account'],p['character'],p['password']),int(self.config['modulus']),Decoder(self.items))
                s.gate.own_names = self.names
                s.global_budget=self.budget
                policy = Policy(self.store,p['character'],random.Random(p['account']+failures))
                agent = Agent(p['character'],s.world,self.items,policy)
                agent.own_names = self.names
                conversation=Conversation(p['character'],s.world,p,self.names)
                from .world import Position
                progression=Progression(p,s.world,self.items,self.routes,
                    Position(*self.config.get('oracle_position',[32104,32190,6])),
                    tuple(self.config.get('rook_bounds',[32000,32000,32200,32350])),
                    self.config.get('hunting_points',[]))
                initial_exp,last_social,last_ping,last_saved = None,0,0,0
                async def observed(events):
                    agent.observe(events,time.monotonic())
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
                    if initial_exp is None and self.status['online']:
                        initial_exp = w.stats.experience
                    if w.stats.experience > self.status.get('experience',w.stats.experience):
                        self.status['last_progress_at'] = self.status['last_xp_at'] = time.time()
                    self.status.update(level=w.stats.level,experience=w.stats.experience,
                        xp_gain=max(0,w.stats.experience-(initial_exp or 0)),health=w.stats.health,
                        position=[w.position.x,w.position.y,w.position.z] if w.position else None)
                    if self.draining.is_set():
                        if drain_started is None:
                            drain_started = now
                            await s.send(b'\xbe',control=True)
                        s.gate.suspended = True
                        if not (w.icons & 128) or now-drain_started >= 90:
                            break
                    else:
                        actions=choose_actions(agent,progression,now)
                        if progression.authorization:
                            s.gate.authorize_speech(*progression.authorization)
                        s.gate.floor_token=progression.floor_authorization
                        self.status.update(strategy=agent.strategy,npc_busy=progression.busy,
                            purchase=progression.purchase.state if progression.purchase else None,
                            food_available=next(agent.food(),None) is not None)
                        for action in actions:
                            await s.send(action)
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
                        self.store.checkpoint(p['character'],dict(self.status))
                        last_saved = now
                    await asyncio.sleep(.2)
                return
            except (OSError,EOFError,TimeoutError,ProtocolError) as exc:
                failures += 1
                self.status.update(failures=failures,error=type(exc).__name__)
                stage=getattr(exc,'stage',None)
                self.status['error_stage']=stage
                self.store.event(time.time(),p['character'],'connection_failure',dict(kind=type(exc).__name__))
                if isinstance(exc,ProtocolError):
                    # A changed layout needs a reviewed fix, not an endless login loop.
                    self.status['halted'] = True
                    return
            finally:
                self.status['online'] = False
                self.status['disconnected_at']=time.time()
                if self.session:
                    try:
                        await self.session.close()
                    except (OSError,TimeoutError):
                        pass
                if task:
                    task.cancel();await asyncio.gather(task,return_exceptions=True)
                self.session = None
            try:
                await asyncio.wait_for(self.draining.wait(),min(300,5*2**min(failures,6)))
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
        budget=RateLimit(40,40)
        connection_budget=RateLimit(.1,1)
        conversation_budget=ReplyBudget()
        paused = False
        try:
            while not stop.is_set():
                now = time.time()
                control = state_dir/'control.json'
                if control.exists():
                    request = json.loads(control.read_text())
                    if request.get('action') == 'stop':
                        stop.set()
                    paused = request.get('action') in ('pause','stop')
                target,population = 0,{}
                try:
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
                        status = {key:r.status for key,r in runners.items()}
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
                atomic_json(state_dir/'status.json',dict(at=now,target=target,supervisor=guard.snapshot(),
                    players={key:r.status for key,r in runners.items()},population=population),0o600)
                await asyncio.sleep(.5)
        finally:
            for runner in runners.values():
                runner.draining.set()
            if tasks:
                await asyncio.gather(*tasks.values(),return_exceptions=True)
