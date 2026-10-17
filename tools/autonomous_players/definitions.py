"""Read immutable wire properties from the server's authoritative item file."""
import re
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class ItemType:
    id: int
    name: str
    flags: frozenset
    attributes: object

    @property
    def stackable(self):
        return 'cumulative' in self.flags

    @property
    def fluid(self):
        return bool({'splash', 'fluidcontainer'} & self.flags)

    @property
    def container(self):
        return bool({'container', 'chest'} & self.flags)

    @property
    def extra_byte(self):
        return self.stackable or self.fluid

    @property
    def blocked(self):
        return bool({'unpass', 'avoid', 'magicfield'} & self.flags)


def load_items(path):
    source = path.read_text(encoding='latin1')
    source = re.sub(r'#.*', '', source)
    result = {}
    for match in re.finditer(r'\bTypeID\s*=\s*(\d+)(.*?)(?=\bTypeID\s*=|\Z)', source, re.S | re.I):
        item_id, body = int(match[1]), match[2]
        if item_id in result or not 0 < item_id < 0xff00:
            raise ValueError('duplicate or invalid item definition')
        name = re.search(r'\bName\s*=\s*"([^"]*)"', body, re.I)
        flags = re.search(r'\bFlags\s*=\s*\{([^}]*)\}', body, re.I)
        attrs = re.search(r'\bAttributes\s*=\s*\{([^}]*)\}', body, re.I)
        values = {} if not attrs else {k.lower(): int(v) for k, v in re.findall(r'(\w+)\s*=\s*(-?\d+)', attrs[1])}
        result[item_id] = ItemType(item_id, name[1] if name else '',
                                  frozenset(re.findall(r'\w+', flags[1].lower())) if flags else frozenset(),
                                  MappingProxyType(values))
    if not result:
        raise ValueError('empty item definitions')
    return MappingProxyType(result)
