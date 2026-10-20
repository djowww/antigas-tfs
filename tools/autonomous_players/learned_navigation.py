"""Per-character route memory built only from observed world transitions."""
from dataclasses import dataclass
import math
import time
from .world import Position


@dataclass
class _Edge:
    source: object
    destination: object
    transition_id: int
    verified: bool = False
    cooldown_until: float = 0.0
    failures: int = 0


class RegionGraph:
    MAX_EDGES_PER_AGENT = 2048
    MAX_CANDIDATES_PER_AGENT = 256
    MAX_FAILURE_COOLDOWN = 1800.0

    def __init__(self, cooldown=120.0):
        self.cooldown = float(cooldown)
        self._edges = {}
        self._candidates = {}

    @staticmethod
    def _put_bounded(mapping, key, value, limit):
        if key not in mapping:
            oldest = next((candidate for candidate in mapping if candidate[0] == key[0]), None)
            if oldest is not None:
                count = sum(candidate[0] == key[0] for candidate in mapping)
                if count >= limit:
                    del mapping[oldest]
        mapping[key] = value
        return value

    def record_stair_observation(self, agent, source, transition_id, destination):
        key=(agent, source, int(transition_id))
        self._put_bounded(self._candidates,key,destination,self.MAX_CANDIDATES_PER_AGENT)

    def observe_transition(self, agent, before, after, transition_id, observed_at):
        candidate_key=(agent, before, int(transition_id))
        destination = self._candidates.pop(candidate_key,None)
        if destination != after:
            return False
        key = (agent, before, after, int(transition_id))
        edge = self._edges.get(key)
        if edge is None:
            edge=self._put_bounded(self._edges,key,_Edge(before, after, int(transition_id)),self.MAX_EDGES_PER_AGENT)
        edge.verified = True
        edge.cooldown_until = 0.0
        # A confirmed crossing proves this source/destination route works;
        # clear stale failures regardless of which stair id recorded them.
        for (owner, source, end, _), route_edge in self._edges.items():
            if owner == agent and source == before and end == after:
                route_edge.failures = 0
                route_edge.cooldown_until = 0.0
        return True

    def can_use(self, agent, source, destination, now, transition_id=None):
        return any(edge.verified and edge.source == source and edge.destination == destination and
                   (transition_id is None or edge.transition_id == transition_id) and
                   edge.cooldown_until <= now for (owner, *_), edge in self._edges.items() if owner == agent)

    def record_failure(self, agent, source, target, reason, at):
        matching = [edge for (owner, *_), edge in self._edges.items()
                    if owner == agent and edge.source == source and edge.destination == target]
        if not matching:
            key = (agent, source, target, -1)
            edge=self._edges.get(key)
            if edge is None:
                edge=self._put_bounded(self._edges,key,_Edge(source, target, -1),self.MAX_EDGES_PER_AGENT)
            matching = [edge]
        for edge in matching:
            edge.failures += 1
            multiplier=2 ** min(edge.failures-1, 16)
            delay=min(self.cooldown*multiplier,self.MAX_FAILURE_COOLDOWN)
            edge.cooldown_until = float(at) + delay

    def next_goal(self, agent, current, safe_routes, now):
        candidates = []
        for target in safe_routes:
            blocked = any(owner == agent and edge.source == current and edge.destination == target and
                          edge.cooldown_until > now for (owner, *_), edge in self._edges.items())
            if not blocked:
                candidates.append(target)
        return min(candidates, key=lambda target: current.distance(target)) if candidates else None

    def has_blocked_goal(self, agent, current, safe_routes, now):
        """Whether learned evidence currently blocks every supplied goal."""
        targets = set(safe_routes)
        return any(owner == agent and edge.source == current and edge.destination in targets and
                   edge.cooldown_until > now for (owner, *_), edge in self._edges.items())

    def is_blocked(self, agent, source, target, now):
        return any(owner == agent and edge.source == source and edge.destination == target and
                   edge.cooldown_until > now for (owner, *_), edge in self._edges.items())

    def snapshot(self,agent,now=None):
        now=time.monotonic() if now is None else float(now)
        edges=[]
        for (owner,source,destination,transition_id),edge in self._edges.items():
            if owner!=agent:
                continue
            edges.append({
                'source':[source.x,source.y,source.z],
                'destination':[destination.x,destination.y,destination.z],
                'transition_id':transition_id,
                'verified':edge.verified,
                'cooldown_remaining':max(0.0,edge.cooldown_until-now),
                'failures':edge.failures,
            })
        return {'version':1,'edges':edges}

    def restore(self,agent,snapshot,now=None):
        if (not isinstance(snapshot,dict) or snapshot.get('version')!=1 or
                not isinstance(snapshot.get('edges'),list) or
                len(snapshot['edges'])>self.MAX_EDGES_PER_AGENT):
            raise ValueError('invalid navigation memory')
        now=time.monotonic() if now is None else float(now)
        restored={}
        for row in snapshot['edges']:
            if not isinstance(row,dict):
                raise ValueError('invalid navigation edge')
            source=row.get('source');destination=row.get('destination')
            transition_id=row.get('transition_id');verified=row.get('verified')
            remaining=row.get('cooldown_remaining');failures=row.get('failures')
            if (not isinstance(source,list) or len(source)!=3 or
                    not isinstance(destination,list) or len(destination)!=3 or
                    any(type(value) is not int for value in source+destination) or
                    type(transition_id) is not int or type(verified) is not bool or
                    not isinstance(remaining,(int,float)) or not math.isfinite(remaining) or remaining<0 or
                    type(failures) is not int or failures<0):
                raise ValueError('invalid navigation edge')
            start,end=Position(*source),Position(*destination)
            key=(agent,start,end,transition_id)
            restored[key]=_Edge(start,end,transition_id,verified,now+remaining,failures)
        self._edges={key:edge for key,edge in self._edges.items() if key[0]!=agent}
        self._edges.update(restored)


class Curriculum:
    MAX_OUTCOMES_PER_AGENT = 128

    def __init__(self, minimum_health_ratio=0.65):
        self.minimum_health_ratio = float(minimum_health_ratio)
        self._outcomes = {}

    def record(self, agent, outcome):
        outcomes=self._outcomes.setdefault(agent, [])
        outcomes.append(dict(outcome))
        if len(outcomes)>self.MAX_OUTCOMES_PER_AGENT:
            del outcomes[:-self.MAX_OUTCOMES_PER_AGENT]

    def ready_for(self, agent, region, world, has_food, has_retreat):
        del agent
        if region != 'cave' or not has_food or not has_retreat:
            return False
        if world.stats.max_health <= 0:
            return False
        return world.stats.health / world.stats.max_health >= self.minimum_health_ratio
