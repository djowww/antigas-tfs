"""Read-only OTBM/NPC audit. Never modifies the map or player data."""

if not __debug__:
    raise SystemExit('Python optimization (-O) disables validation assertions; refusing to run this tool.')

import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

SIZES = {3:4,4:2,5:2,8:5,9:2,10:2,12:1,14:1,15:1,16:4,17:1,
         18:4,20:4,21:4,22:2,23:2,24:2,25:2,26:2,27:2,28:2,
         33:4,34:4,35:4,36:4,37:1,38:1}
STRINGS = {1,2,6,7,11,13,19,30,31,32}


def attributes(data, offset=2):
    result = {}
    while offset < len(data):
        key = data[offset]
        offset += 1
        if key == 0:
            break
        if key in STRINGS:
            size = struct.unpack_from('<H', data, offset)[0]
            offset += 2
            result[key] = data[offset:offset+size].decode('latin1')
        else:
            assert key in SIZES, f'Unknown OTBM attribute {key}'
            size = SIZES[key]
            result[key] = int.from_bytes(data[offset:offset+size], 'little')
        assert offset + size <= len(data), 'Truncated OTBM attribute'
        offset += size
    return result


def audit(root):
    names = {}
    items = (root/'data/items/items.srv').read_text(encoding='latin1')
    for match in re.finditer(r'TypeID\s*=\s*(\d+)(.*?)(?=\nTypeID\s*=|\Z)', items, re.S):
        name = re.search(r'\bName\s*=\s*"([^"]*)"', match[2])
        if name: names[int(match[1])] = name[1]
    raw = (root/'data/world/map.otbm').read_bytes()
    stack, chests, action_ids, movement_ids, towns = [], [], defaultdict(int), defaultdict(int), []
    def finish_props(node):
        if 'data' in node:
            return
        data = bytes(node.pop('props'))
        node['data'] = data
        kind = node['kind']
        if kind == 4:
            node['pos'] = struct.unpack_from('<HHB', data)
        elif kind in (5,14):
            x,y,z = node['pos']
            node['pos'] = (x+data[0],y+data[1],z)
        elif kind == 6:
            item_id = struct.unpack_from('<H', data)[0]
            attrs = attributes(data)
            node['item'] = dict(item=item_id, name=names.get(item_id, f'item {item_id}'),
                                attributes=attrs, contents=[])
            if attrs.get(4): action_ids[attrs[4]] += 1
            if attrs.get(5): movement_ids[attrs[5]] += 1
        elif kind == 13:
            size = struct.unpack_from('<H', data,4)[0]
            towns.append(dict(id=struct.unpack_from('<I',data)[0],
                name=data[6:6+size].decode('latin1'), pos=struct.unpack_from('<HHB',data,6+size)))
    pos = 4
    while pos < len(raw):
        token = raw[pos]
        pos += 1
        if token == 253:
            stack[-1]['props'].append(raw[pos]); pos += 1
        elif token == 254:
            if stack: finish_props(stack[-1])
            node = dict(kind=raw[pos], props=bytearray(), pos=stack[-1].get('pos') if stack else None)
            stack.append(node); pos += 1
        elif token == 255:
            node = stack.pop(); finish_props(node)
            if node['kind'] == 6:
                item = node['item']
                if item['attributes'].get(28):
                    chests.append(dict(pos=node['pos'], **item))
                if stack and stack[-1]['kind'] == 6:
                    stack[-1]['item']['contents'].append(item)
        else:
            stack[-1]['props'].append(token)
    assert not stack, 'Unclosed OTBM node'
    npc = defaultdict(list)
    npc_paths = set((root/'data/npc').glob('*.npc'))
    pending = list(npc_paths)
    while pending:
        path = pending.pop()
        for include in re.findall(r'@"([^"]+)"',path.read_text(encoding='latin1')):
            included = root/'data/npc'/include
            if included not in npc_paths:
                npc_paths.add(included); pending.append(included)
    for path in sorted(npc_paths):
        text = path.read_text(encoding='latin1')
        for number,line in enumerate(text.splitlines(),1):
            if line.lstrip().startswith('#'): continue
            for match in re.finditer(r'SetQuestValue\s*\(\s*(\d+)\s*,\s*([^\)]+)\)',line,re.I):
                npc[int(match[1])].append(dict(file=path.name, line=number, value=match[2], text=line.strip()))
    return dict(map_sha256=hashlib.sha256(raw).hexdigest(), chests=chests,
                npc_storages=dict(sorted(npc.items())), action_ids=action_ids,
                movement_ids=movement_ids, towns=towns)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('.'))
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.root)
    args.out.write_text(json.dumps(result,indent=2,ensure_ascii=True)+'\n')
    print('chests:',len(result['chests']), 'unique chest storages:',
          len({c['attributes'][28] for c in result['chests']}))
    print('NPC storage writers:',len(result['npc_storages']))
    for key,rows in result['npc_storages'].items():
        print(key, sorted({r['value'] for r in rows}), sorted({r['file'] for r in rows}))
