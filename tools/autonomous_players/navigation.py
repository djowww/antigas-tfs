"""Bounded A* over currently observed tiles; unknown space is never walkable."""
import heapq
from itertools import count
from .world import Position

DIRECTIONS = {(0,-1):0x65,(1,0):0x66,(0,1):0x67,(-1,0):0x68,
              (1,-1):0x6a,(1,1):0x6b,(-1,1):0x6c,(-1,-1):0x6d}


def walkable(world, position, items, floor_changes=False):
    tile = world.tiles.get(position)
    if not tile or not any(not t.creature_id and 'bank' in items[t.id].flags for t in tile):
        return False
    for thing in tile:
        if thing.creature_id and thing.creature_id != world.self_id:
            return False  # Do not shove humans, NPCs or monsters.
        if not thing.creature_id:
            flags = items[thing.id].flags
            if {'unpass','magicfield'} & flags:
                return False
            if 'avoid' in flags and not floor_changes:
                return False
    return True


def find_path(world, start, goal, items, max_nodes=2048, floor_changes=False, blocked=()):
    blocked=frozenset(blocked)
    if (not world.valid or start.z != goal.z or goal in blocked or
            not walkable(world,goal,items,floor_changes)):
        return []
    serial = count()
    queue = [(0,next(serial),start)]
    costs, parent = {start:0}, {}
    while queue and len(costs) <= max_nodes:
        _,_,p = heapq.heappop(queue)
        if p == goal:
            path = []
            while p != start:
                path.append(p)
                p = parent[p]
            return path[::-1]
        for dx,dy in DIRECTIONS:
            n = p.shift(dx,dy)
            if n in blocked or not walkable(world,n,items,floor_changes and n == goal):
                continue
            if dx and dy and (not walkable(world,p.shift(dx,0),items) or not walkable(world,p.shift(0,dy),items)):
                continue
            cost = costs[p] + (3 if dx and dy else 2)
            if cost < costs.get(n,1e20):
                costs[n], parent[n] = cost,p
                heapq.heappush(queue,(cost+2*n.distance(goal),next(serial),n))
    return []


def walk_packet(start, following):
    if start.z != following.z:
        raise ValueError('floor changes require observed stairs or tools')
    delta = (following.x-start.x,following.y-start.y)
    if delta not in DIRECTIONS:
        raise ValueError('walk must be adjacent')
    return bytes([DIRECTIONS[delta]])
