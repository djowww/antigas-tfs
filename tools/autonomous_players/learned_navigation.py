"""Per-character route memory built only from observed world transitions."""
from dataclasses import dataclass


@dataclass
class _Edge:
    source: object
    destination: object
    transition_id: int
    verified: bool = False
    cooldown_until: float = 0.0
    failures: int = 0


class RegionGraph:
    def __init__(self, cooldown=120.0):
        self.cooldown = float(cooldown)
        self._edges = {}
        self._candidates = {}

    def record_stair_observation(self, agent, source, transition_id, destination):
        self._candidates[(agent, source, int(transition_id))] = destination

    def observe_transition(self, agent, before, after, transition_id, observed_at):
        destination = self._candidates.get((agent, before, int(transition_id)))
        if destination != after:
            return False
        key = (agent, before, after, int(transition_id))
        edge = self._edges.setdefault(key, _Edge(before, after, int(transition_id)))
        edge.verified = True
        edge.cooldown_until = 0.0
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
            matching = [self._edges.setdefault(key, _Edge(source, target, -1))]
        for edge in matching:
            edge.failures += 1
            edge.cooldown_until = float(at) + self.cooldown

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


class Curriculum:
    def __init__(self, minimum_health_ratio=0.65):
        self.minimum_health_ratio = float(minimum_health_ratio)
        self._outcomes = {}

    def record(self, agent, outcome):
        self._outcomes.setdefault(agent, []).append(dict(outcome))

    def ready_for(self, agent, region, world, has_food, has_retreat):
        del agent
        if region != 'cave' or not has_food or not has_retreat:
            return False
        if world.stats.max_health <= 0:
            return False
        return world.stats.health / world.stats.max_health >= self.minimum_health_ratio
