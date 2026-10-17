"""Strict current OS11/no-OTCv8 server decoder (src/protocolgame.cpp).

An unknown layout invalidates the session. No scanning for familiar bytes and
no action may use an invalid world. Integer item IDs are server IDs.
"""
from .wire import Reader, Writer, ProtocolError
from .world import Position, Thing, Creature, Container, Stats, Event


def read_position(r):
    p = Position(r.u16(), r.u16(), r.u8())
    if p.z > 15 or p.x == 65535:
        raise ProtocolError('invalid map position')
    return p


def write_position(w, p):
    return w.u16(p.x).u16(p.y).u8(p.z)


def attack(creature):
    if creature.kind != 'monster' or creature.position is None or creature.health <= 0:
        raise ValueError('target is not an observed living monster')
    return Writer().u8(0xa1).u32(creature.id).data


def say(text):
    if not text or len(text.encode('latin1')) > 255:
        raise ValueError('invalid speech')
    return Writer().u8(0x96).u8(1).string(text).data


def use_item(position, item_id, stack=0, container=0):
    return write_position(Writer().u8(0x82), position).u16(item_id).u8(stack).u8(container).data


def move_item(position, item_id, stack, destination, count=1):
    if not 1 <= count <= 100:
        raise ValueError('invalid move count')
    w = write_position(Writer().u8(0x78), position).u16(item_id).u8(stack)
    return write_position(w, destination).u8(count).data


class Decoder:
    def __init__(self, items):
        self.items = items

    def item(self, r, item_id=None):
        item_id = r.u16() if item_id is None else item_id
        definition = self.items.get(item_id)
        if not definition:
            raise ProtocolError('unknown item type')
        return Thing(item_id, r.u8() if definition.extra_byte else 1)

    def outfit(self, r):
        look = r.u16()
        r.take(5 if look else 2)
        r.u16()  # Mounts are unconditional in this server, even protocol 772.

    def thing(self, r, world):
        kind = r.u16()
        if kind not in (0x61, 0x62, 0x63):
            return self.item(r, kind)
        if kind == 0x61:
            removed, cid, name = r.u32(), r.u32(), r.string(255)
            if removed:
                world.creatures.pop(removed, None)
            c = Creature(cid, name)
            world.creatures[cid] = c
        else:
            cid = r.u32()
            c = world.creatures.get(cid)
            if c is None:
                raise ProtocolError('missing known creature')
        if kind == 0x63:
            c.direction = r.u8()
            return Thing(0, creature_id=cid)
        c.health, c.direction = r.u8(), r.u8()
        self.outfit(r)
        r.take(4)  # light and step speed
        r.u8()  # skull
        c.shield, c.blocked = r.u8(), bool(r.u8())
        return Thing(0, creature_id=cid)

    def map_cells(self, r, world, cells):
        skip = 0
        for p in cells:
            if skip:
                world.set_tile(p, [])
                skip -= 1
                continue
            if r.remaining < 2:
                raise ProtocolError('truncated map')
            word = int.from_bytes(r.data[r.offset:r.offset+2], 'little')
            if word >= 0xff00:
                skip = r.u16() & 255
                world.set_tile(p, [])
                continue
            if r.u16() != 0:
                raise ProtocolError('unexpected tile environment profile')
            things = []
            while True:
                if r.remaining < 2:
                    raise ProtocolError('unterminated tile')
                word = int.from_bytes(r.data[r.offset:r.offset+2], 'little')
                if word >= 0xff00:
                    skip = r.u16() & 255
                    break
                if len(things) >= 10:
                    raise ProtocolError('oversized tile stack')
                things.append(self.thing(r, world))
            world.set_tile(p, things)
        if skip:
            # Single-tile absent updates use 01 FF; full map skips must fit.
            raise ProtocolError('map skip beyond viewport')

    @staticmethod
    def cells(x, y, z, width, height):
        floors = range(z-2, min(15, z+2)+1) if z > 7 else range(7, -1, -1)
        return (Position(x+dx+z-f, y+dy+z-f, f)
                for f in floors for dx in range(width) for dy in range(height))

    def feed_payload(self, payload, world):
        if not world.valid:
            raise ProtocolError('invalid world requires reconnect')
        r, events = Reader(payload), []
        try:
            while r.remaining:
                opcode = r.u8()
                event = self.parse(opcode, r, world)
                if event:
                    events.append(event)
            world.prune()
        except (ProtocolError, IndexError, KeyError, ValueError) as exc:
            world.valid = False
            if isinstance(exc, ProtocolError):
                raise
            raise ProtocolError('inconsistent observed world') from exc
        return events

    def parse(self, op, r, w):
        if op == 0x0a:
            w.self_id = r.u32()
            r.take(3)
            return Event('login', w.self_id)
        if op == 0x0b:
            raise ProtocolError('privileged account refused')
        if op in (0x11, 0x1d, 0x1e, 0x7f, 0xa3, 0xb1):
            return Event({0x11:'update_required', 0x1d:'ping', 0x1e:'pong', 0xa3:'cancel_attack'}.get(op, 'notice'))
        if op in (0x14, 0x15, 0x16):
            message = r.string()
            if op == 0x16:
                r.u8()
            return Event('error' if op != 0x15 else 'text', message)
        if op == 0x32:
            return Event('extended', (r.u8(), r.string(65535)))
        if op == 0x40:
            return Event('latency', r.u32())
        if op == 0x64:
            w.previous_position = w.position
            w.position = p = read_position(r)
            w.tiles.clear()
            w.floor_strips.clear()
            for creature in w.creatures.values():
                creature.position = None
            self.map_cells(r, w, self.cells(p.x-8, p.y-6, p.z, 18, 14))
            return Event('map', p)
        if op in (0x65, 0x66, 0x67, 0x68):
            p = w.position
            if not p:
                raise ProtocolError('strip before map')
            # For diagonal moves N/S use the previous x; E/W use new y.
            old = w.previous_position or p
            coordinates = {0x65:(old.x-8,p.y-6,18,1), 0x67:(old.x-8,p.y+7,18,1),
                           0x66:(p.x+9,p.y-6,1,14), 0x68:(p.x-8,p.y-6,1,14)}
            x,y,width,height = coordinates[op]
            if w.floor_strips:
                expected,x,y,width,height = w.floor_strips.pop(0)
                if op != expected:
                    raise ProtocolError('missing floor compensation strip')
            self.map_cells(r,w,self.cells(x,y,p.z,width,height))
            return None
        if op == 0x69:
            p = read_position(r)
            if r.remaining >= 2 and bytes(r.data[r.offset:r.offset+2]) == b'\x01\xff':
                r.take(2)
                w.set_tile(p, [])
            else:
                self.map_cells(r, w, [p])
            return Event('tile', p)
        if op in (0x6a, 0x6b, 0x6c):
            p, stack = read_position(r), r.u8()
            if stack >= 10:
                raise ProtocolError('invalid tile stack index')
            tile = list(w.tiles.get(p, []))
            if op == 0x6a:
                thing = self.thing(r, w)
                if stack > len(tile):
                    raise ProtocolError('missing tile insertion context')
                tile.insert(stack, thing)
            else:
                if stack >= len(tile):
                    raise ProtocolError('missing tile update context')
                if op == 0x6b:
                    tile[stack] = self.thing(r, w)
                else:
                    removed = tile.pop(stack)
                    if removed.creature_id == w.self_id:
                        w.previous_position = p
            w.set_tile(p, tile[:10])
            return Event('tile', p)
        if op == 0x6d:
            old, stack, new = read_position(r), r.u8(), read_position(r)
            tile = list(w.tiles.get(old, []))
            if stack >= len(tile) or not tile[stack].creature_id:
                raise ProtocolError('movement references missing creature')
            thing = tile.pop(stack)
            w.set_tile(old, tile)
            # Creatures appear after ground/top items and before bottom items.
            target = list(w.tiles.get(new, []))
            index = 0
            for item in target:
                if item.creature_id:
                    break
                flags = self.items[item.id].flags
                if not ({'bank','clip','bottom','top'} & flags):
                    break
                index += 1
            target.insert(index, thing)
            w.set_tile(new, target[:10])
            if thing.creature_id == w.self_id:
                w.previous_position, w.position = old, new
            return Event('move', (thing.creature_id, old, new))
        if op in (0xbe, 0xbf):
            old = w.previous_position or w.position
            if old is None:
                raise ProtocolError('floor change before map')
            # 6D already supplies new position except the surface->underground case.
            p = w.position
            if p == old:
                p = old.shift(z=1 if op == 0xbf else -1)
                w.position = p
            floors = []
            if op == 0xbe:
                w.floor_strips = [(0x68,old.x-8,old.y-5,1,14),(0x65,old.x-8,old.y-6,18,1)]
                if p.z == 7:
                    floors = [(f, 8-f) for f in range(5,-1,-1)]
                elif p.z > 7:
                    floors = [(old.z-3,3)]
            elif p.z == 8:
                floors = [(8,-1),(9,-2),(10,-3)]
            elif 8 < p.z < 14:
                floors = [(p.z+2,-3)]
            if op == 0xbf:
                w.floor_strips = [(0x66,old.x+9,old.y-7,1,14),(0x67,old.x-8,old.y+7,18,1)]
            cells = (Position(old.x-8+dx+offset,old.y-6+dy+offset,f)
                     for f,offset in floors for dx in range(18) for dy in range(14))
            self.map_cells(r,w,cells)
            return Event('floor', p)
        if op == 0x6e:
            cid, item = r.u8(), self.item(r)
            name, capacity, parent, count = r.string(255), r.u8(), bool(r.u8()), r.u8()
            w.containers[cid] = Container(cid,item.id,name,capacity,parent,[self.item(r) for _ in range(count)])
            return Event('container', cid)
        if op == 0x6f:
            cid = r.u8()
            w.containers.pop(cid,None)
            return Event('container_closed',cid)
        if op in (0x70,0x71,0x72):
            cid = r.u8()
            c = w.containers[cid]
            if op == 0x70:
                c.items.insert(0,self.item(r))
            else:
                slot = r.u8()
                if op == 0x71:
                    c.items[slot] = self.item(r)
                else:
                    c.items.pop(slot)
            return Event('container',cid)
        if op in (0x78,0x79):
            slot = r.u8()
            if op == 0x78:
                w.inventory[slot] = self.item(r)
            else:
                w.inventory.pop(slot,None)
            return Event('inventory',slot)
        if op in (0x7d,0x7e):
            r.string(255)
            for _ in range(r.u8()):
                self.item(r)
            return Event('trade')
        if op == 0xa0:
            hp,maxhp,cap,exp,level = r.u16(),r.u16(),r.u16(),r.u32(),r.u16()
            r.u8()
            mana,maxmana = r.u16(),r.u16()
            r.take(3)
            w.stats = Stats(hp,maxhp,cap,exp,level,mana,maxmana)
            return Event('stats',w.stats)
        if op == 0xa1:
            w.skills = tuple((r.u8(),r.u8()) for _ in range(7))
            return Event('skills',w.skills)
        if op == 0xa2:
            w.icons = r.u8()
            return Event('icons',w.icons)
        if op == 0xa7:
            r.take(3)
            return None
        if op == 0xaa:
            r.u32()
            author,kind = r.string(255),r.u8()
            context = None
            if kind in (1,2,3,16,17):
                context = read_position(r)
            elif kind in (5,10,12,13):
                context = r.u16()
            elif kind == 6:
                context = r.u32()
            elif kind == 7:
                raise ProtocolError('ambiguous rule violation chat unsupported')
            return Event('speech',dict(author=author,type=kind,context=context,text=r.string()))
        if op == 0xb4:
            return Event('text', (r.u8(),r.string()))
        if op == 0xb5:
            return Event('walk_cancel',r.u8())
        if op in (0x82,):
            r.take(2)
            return None
        if op in (0x83,0x84,0x85):
            p = read_position(r)
            if op == 0x85:
                read_position(r)
            r.u8()
            if op == 0x84:
                r.string()
            return Event('effect',p)
        if op in (0x86,0x8c,0x8d,0x8e,0x8f,0x90,0x91,0x92):
            cid = r.u32()
            c = w.creatures.get(cid)
            if op == 0x8e:
                self.outfit(r)
            elif op in (0x8d,0x8f):
                r.take(2)
            else:
                value = r.u8()
                if c and op == 0x8c:
                    c.health = value
                elif c and op == 0x91:
                    c.shield = value
                elif c and op == 0x92:
                    c.blocked = bool(value)
            return Event('creature',cid)
        if op in (0xab,):
            for _ in range(r.u8()):
                r.u16(); r.string(255)
            return None
        if op in (0xac,0xb2):
            r.u16(); r.string(255)
            return None
        if op in (0xae,0xb3):
            r.u16()
            return None
        if op in (0xad,0xaf,0xb0):
            r.string(255)
            return None
        if op == 0xd2:
            r.u32(); r.string(255); r.u8()
            return None
        if op in (0xd3,0xd4):
            r.u32()
            return None
        if op == 0xc8:
            self.outfit(r)
            for _ in range(r.u8()):
                r.u16(); r.string(255); r.u8()
            for _ in range(r.u8()):
                r.u16(); r.string(255)
            return Event('outfit_window')
        if op == 0xfa:
            identifier = r.u32()
            r.string(); r.string()
            for _ in range(r.u8()):
                r.string(255); r.u8()
            for _ in range(r.u8()):
                r.string(255); r.u8()
            r.take(3)
            return Event('modal',identifier)
        # Text windows have inconsistent overloads; fail closed until disambiguated.
        raise ProtocolError(f'unsupported server opcode 0x{op:02x}')
