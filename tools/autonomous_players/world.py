"""Connection-scoped observations. Never restore creature IDs after reconnect."""
from dataclasses import dataclass, field


@dataclass(frozen=True, order=True)
class Position:
    x: int
    y: int
    z: int

    def distance(self, other):
        return max(abs(self.x-other.x), abs(self.y-other.y)) if self.z == other.z else 10000

    def shift(self, x=0, y=0, z=0):
        return Position(self.x+x, self.y+y, self.z+z)


@dataclass(frozen=True)
class Thing:
    id: int
    count: int = 1
    creature_id: int = 0


@dataclass
class Creature:
    id: int
    name: str
    position: Position | None = None
    health: int = 100
    direction: int = 0
    shield: int = 0
    blocked: bool = True

    @property
    def kind(self):
        if 0x10000000 <= self.id < 0x40000000:
            return 'player'
        if 0x40000000 <= self.id < 0x80000000:
            return 'monster'
        if 0x80000000 <= self.id < 0xffffffff:
            return 'npc'
        return 'unknown'


@dataclass
class Stats:
    health: int = 0
    max_health: int = 0
    capacity: int = 0
    experience: int = 0
    level: int = 0
    mana: int = 0
    max_mana: int = 0


@dataclass
class Container:
    id: int
    item_id: int
    name: str
    capacity: int
    parent: bool
    items: list = field(default_factory=list)


@dataclass(frozen=True)
class Event:
    kind: str
    data: object = None


@dataclass
class World:
    valid: bool = True
    self_id: int = 0
    position: Position | None = None
    previous_position: Position | None = None
    tiles: dict = field(default_factory=dict)
    creatures: dict = field(default_factory=dict)
    inventory: dict = field(default_factory=dict)
    containers: dict = field(default_factory=dict)
    stats: Stats = field(default_factory=Stats)
    icons: int = 0
    skills: tuple = ()
    floor_strips: list = field(default_factory=list)

    def set_tile(self, position, things):
        old = self.tiles.get(position, [])
        for thing in old:
            c = self.creatures.get(thing.creature_id)
            if c and c.position == position:
                c.position = None
        self.tiles[position] = things
        for thing in things:
            c = self.creatures.get(thing.creature_id)
            if c:
                c.position = position

    def prune(self):
        if self.position:
            p = self.position
            floors = range(p.z-2,min(15,p.z+2)+1) if p.z > 7 else range(8)
            self.tiles = {k: v for k, v in self.tiles.items() if k.z in floors and
                          -8 <= k.x-p.x-(p.z-k.z) <= 9 and -6 <= k.y-p.y-(p.z-k.z) <= 7}
            present = {t.creature_id for tile in self.tiles.values() for t in tile if t.creature_id}
            for creature_id,c in tuple(self.creatures.items()):
                if creature_id not in present:
                    c.position = None
