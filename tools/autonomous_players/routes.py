"""Static route knowledge is distinct from fresh actionable observations.

Regional graph compilation reads a map without modifying it. Runtime still
validates each adjacent step against its current received tile before sending.
"""
import heapq
import json
import re
import struct
from itertools import count
from pathlib import Path
from .world import Position


class RouteGraph:
    def __init__(self, tiles):
        if len(tiles) > 150000:
            raise ValueError('regional graph too large')
        self.tiles = tiles

    @classmethod
    def load(cls,path):
        data = json.loads(Path(path).read_text())
        if data.get('version') != 1:
            raise ValueError('unknown route format')
        tiles = {}
        for row in data['tiles']:
            if (len(row) not in (3,6) or any(type(v) is not int for v in row) or
                any(not (0 <= row[i] <= (15 if i%3==2 else 65534)) for i in range(len(row)))):
                raise ValueError('invalid route row')
            key=Position(*row[:3])
            if key in tiles:
                raise ValueError('duplicate route tile')
            tiles[key]=Position(*row[3:]) if len(row)==6 else None
        return cls(tiles)

    def destination(self,step):
        seen = set()
        while step in self.tiles and self.tiles[step] is not None:
            if step in seen or len(seen) >= 8:
                return None
            seen.add(step)
            step = self.tiles[step]
        return step if step in self.tiles else None

    def next_step(self,start,goal,max_nodes=40000):
        if start not in self.tiles or goal not in self.tiles or start == goal:
            return None
        serial = count()
        queue,costs,parent = [(0,next(serial),start)],{start:0},{}
        while queue and len(costs) <= max_nodes:
            _,_,p = heapq.heappop(queue)
            if p == goal:
                while parent[p][0] != start:
                    p = parent[p][0]
                return parent[p][1]
            for dx,dy in ((0,1),(1,0),(0,-1),(-1,0)):
                step = p.shift(dx,dy)
                if step not in self.tiles:
                    continue
                destination = self.destination(step)
                if destination not in self.tiles:
                    continue
                cost = costs[p]+1
                if cost < costs.get(destination,1e20):
                    costs[destination],parent[destination] = cost,(p,step)
                    heapq.heappush(queue,(cost,next(serial),destination))
        return None


def compile_region(map_path, item_types, movement_path, bounds):
    xmin,ymin,xmax,ymax = bounds
    if not 0 <= xmin <= xmax < 65535 or not 0 <= ymin <= ymax < 65535 or xmax-xmin > 500 or ymax-ymin > 500:
        raise ValueError('compile a bounded region')
    movement = Path(movement_path).read_text()
    transitions = {int(i):(int(x),int(y),int(z)) for i,x,y,z in
        re.findall(r'\[(\d+)\]\s*=\s*\{x\s*=\s*(-?\d+),\s*y\s*=\s*(-?\d+),\s*z\s*=\s*(-?\d+)\}',movement)}
    raw = Path(map_path).read_bytes()
    stack,tiles = [],{}
    def finish(node):
        if node['done']:
            return
        node['done'] = True
        data = bytes(node['props'])
        kind = node['kind']
        if kind == 4:
            node['pos'] = Position(*struct.unpack_from('<HHB',data))
        elif kind in (5,14):
            p = node['pos']
            node['pos'] = p.shift(data[0],data[1])
            node['items'] = []
            offset = 6 if kind == 14 else 2
            while offset < len(data):
                attribute = data[offset];offset += 1
                if attribute == 3:
                    offset += 4
                elif attribute == 9:
                    node['items'].append(struct.unpack_from('<H',data,offset)[0]);offset += 2
                else:
                    raise ValueError('unsupported inline tile attribute')
        elif kind == 6 and len(stack) >= 2 and stack[-2]['kind'] in (5,14):
            stack[-2]['items'].append(struct.unpack_from('<H',data)[0])
    cursor = 4
    # Skip ordinary property runs in C rather than a Python loop over 86 MiB.
    for marker in re.finditer(b'\xfd.|[\xfe\xff]',raw[4:],re.S):
        at = marker.start()+4
        token = raw[at]
        if stack and not stack[-1]['done']:
            stack[-1]['props'].extend(raw[cursor:at])
        if token == 253:
            if stack and not stack[-1]['done']:
                stack[-1]['props'].append(raw[at+1])
            cursor = at+2
        elif token == 254:
            if stack:
                finish(stack[-1])
            kind = raw[at+1]
            stack.append(dict(kind=kind,props=bytearray(),pos=stack[-1].get('pos') if stack else None,done=False))
            cursor = at+2
        else:
            if not stack:
                raise ValueError('unbalanced map node')
            finish(stack[-1]);node=stack.pop()
            if node['kind'] == 5:
                p,ids = node['pos'],node['items']
                if xmin <= p.x <= xmax and ymin <= p.y <= ymax:
                    if any(i not in item_types for i in ids):
                        continue  # Unknown/retired types cannot be assumed traversable.
                    definitions = [item_types[i] for i in ids]
                    if any('bank' in i.flags for i in definitions) and not any({'unpass','magicfield'} & i.flags for i in definitions):
                        transition = next((transitions[i] for i in ids if i in transitions),None)
                        if not any('avoid' in i.flags for i in definitions) or transition:
                            tiles[p] = p.shift(*transition) if transition else None
            cursor = at+1
    if stack:
        raise ValueError('unclosed map node')
    return RouteGraph(tiles)
