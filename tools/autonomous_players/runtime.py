"""One receive task per connection, with an observation gate at transmission."""
import asyncio
import secrets
import struct
import time
from .wire import FrameCodec, ProtocolError, Reader
from .world import World
from .protocol import read_position
from .navigation import DIRECTIONS, walkable


class SessionTimeout(TimeoutError):
    def __init__(self,stage):
        self.stage=stage
        super().__init__(stage)


async def deadline(operation,seconds,stage):
    try:
        return await asyncio.wait_for(operation,seconds)
    except TimeoutError:
        raise SessionTimeout(stage) from None


class RateLimit:
    def __init__(self,rate,burst,clock=time.monotonic,sleep=asyncio.sleep):
        if rate<=0 or burst<1:
            raise ValueError('invalid action budget')
        self.rate,self.capacity,self.tokens=rate,burst,float(burst)
        self.clock,self.sleep=clock,sleep
        self.updated=clock()
        self.lock=asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            while True:
                now=self.clock()
                self.tokens=min(self.capacity,self.tokens+max(0,now-self.updated)*self.rate)
                self.updated=now
                if self.tokens>=1:
                    self.tokens-=1
                    return
                await self.sleep((1-self.tokens)/self.rate)


class ActionGate:
    def __init__(self, world, items=None):
        self.world,self.items = world,items
        self.suspended = False
        self.allowed_corpses = set()
        self.own_names = set()
        self.speech_token = None
        self.floor_token = None
        self.reply_token = None

    def authorize_speech(self,npc_id,text,expires):
        self.speech_token=(npc_id,text,expires)

    def authorize_reply(self,player_id,text,expires):
        self.reply_token=(player_id,text,expires)

    def _item_at(self, position, item_id, stack):
        w = self.world
        if position.x == 65535:
            if position.y < 64:
                item = w.inventory.get(position.y)
            else:
                c = w.containers.get(position.y-64)
                item = c.items[position.z] if c and position.z < len(c.items) else None
            return item is not None and item.id == item_id
        if not w.position or w.position.distance(position) > 1:
            return False
        tile = w.tiles.get(position,[])
        return (stack < len(tile) and tile[stack].id == item_id and
                (position,item_id) in self.allowed_corpses)

    def permit(self, packet, now=None):
        now=time.monotonic() if now is None else now
        if packet in (b'\x14',b'\x1e',b'\x1d',b'\xbe'):
            return True
        w = self.world
        if not packet or not w.valid or self.suspended or not w.position:
            return False
        r = Reader(packet)
        op = r.u8()
        try:
            if op == 0xa1:
                cid = r.u32()
                c = w.creatures.get(cid)
                return (not r.remaining and c is not None and c.kind == 'monster' and
                        c.position is not None and c.health > 0 and w.position.distance(c.position) <= 7)
            if op in DIRECTIONS.values():
                if r.remaining or self.items is None:
                    return False
                dx,dy = next(k for k,v in DIRECTIONS.items() if v == op)
                destination=w.position.shift(dx,dy)
                if self.floor_token and self.floor_token[0] == destination:
                    item_id=self.floor_token[1]
                    self.floor_token=None
                    return (any(t.id==item_id for t in w.tiles.get(destination,[])) and
                            walkable(w,destination,self.items,True))
                return walkable(w,destination,self.items)
            if op == 0xa0:
                return r.take(3) in (b'\x01\x00\x00',b'\x01\x01\x00',b'\x03\x00\x00') and not r.remaining
            if op == 0x82:
                x,y,z = r.u16(),r.u16(),r.u8()
                item,stack,index = r.u16(),r.u8(),r.u8()
                from .world import Position
                return not r.remaining and index <= 15 and self._item_at(Position(x,y,z),item,stack)
            if op == 0x78:
                from .world import Position
                source = Position(r.u16(),r.u16(),r.u8())
                item,stack = r.u16(),r.u8()
                destination = Position(r.u16(),r.u16(),r.u8())
                count = r.u8()
                return (not r.remaining and 1 <= count <= 100 and self._item_at(source,item,stack) and
                        destination.x == 65535 and 64 <= destination.y <= 79 and
                        destination.y-64 in w.containers)
            if op in (0xa3,0xa4):
                c = w.creatures.get(r.u32())
                return (not r.remaining and c is not None and c.kind == 'player' and c.position is not None and
                        ((op == 0xa4 and c.shield == 1) or (op == 0xa3 and c.name in self.own_names)))
            if op == 0xa8:
                return r.u8() == 1 and not r.remaining
            if op == 0x40:
                r.take(8)
                return not r.remaining
            if op == 0x96 and self.reply_token:
                cid,text,expires=self.reply_token
                self.reply_token=None
                c=w.creatures.get(cid)
                return (r.u8()==1 and r.string(255)==text and not r.remaining and now<=expires and
                        c is not None and c.id!=w.self_id and c.kind=='player' and c.position is not None and
                        w.position.distance(c.position)<=7)
            if op == 0x96 and self.speech_token:
                npc,text,expires=self.speech_token
                c=w.creatures.get(npc)
                if r.u8()!=1 or r.string(255)!=text or r.remaining or now>expires:
                    return False
                self.speech_token=None
                return c is not None and c.kind=='npc' and c.position is not None and w.position.distance(c.position)<=3
            # Chat and irreversible NPC actions require their own dialogue executor.
            return False
        except (ProtocolError,ValueError):
            return False


class Session:
    def __init__(self, reader, writer, key, world, decoder):
        self.reader,self.writer,self.world,self.decoder = reader,writer,world,decoder
        self.codec = FrameCodec(key)
        self.gate = ActionGate(world,getattr(decoder,'items',None))
        self.received_packets = 0
        self.on_events = None
        self._receiving = False
        self.send_lock = asyncio.Lock()
        self.last_received = time.monotonic()
        self.pings = {}
        self.latencies = []
        self.local_budget=RateLimit(2.5,3)
        self.global_budget=None

    @classmethod
    async def connect(cls,host,port,credentials,modulus,decoder):
        reader,writer = await deadline(asyncio.open_connection(host,port,limit=1048576),10,'connect')
        key = struct.unpack('<IIII',secrets.token_bytes(16))
        try:
            writer.write(credentials.packet(key,modulus))
            await deadline(writer.drain(),5,'login_write')
        except BaseException:
            writer.close()
            await writer.wait_closed()
            raise
        return cls(reader,writer,key,World(),decoder)

    async def send(self, packet, control=False):
        # Control bypass is narrowly restricted to protocol keepalive and logout.
        if control:
            if packet not in (b'\x14',b'\x1e',b'\x1d',b'\xbe'):
                raise ValueError('invalid control packet')
        else:
            await self.local_budget.acquire()
            if self.global_budget:
                await self.global_budget.acquire()
            if not self.gate.permit(packet):
                return False
        async with self.send_lock:
            self.writer.write(self.codec.encode(packet))
            await deadline(self.writer.drain(),5,'write')
        return True

    async def receive(self):
        if self._receiving:
            raise RuntimeError('session already has a reader')
        self._receiving = True
        try:
            while True:
                incoming = await deadline(self.reader.read(65536),90,'read')
                if not incoming:
                    raise EOFError('game connection closed')
                for payload in self.codec.feed(incoming):
                    self.received_packets += 1
                    events = self.decoder.feed_payload(payload,self.world)
                    self.last_received = time.monotonic()
                    for event in events:
                        if event.kind == 'ping':
                            await self.send(b'\x1e',control=True)
                        elif event.kind == 'latency' and event.data in self.pings:
                            self.latencies.append((time.monotonic()-self.pings.pop(event.data))*1000)
                            del self.latencies[:-60]
                        elif event.kind in ('error','update_required'):
                            raise ProtocolError('server rejected session')
                    if self.on_events:
                        await self.on_events(events)
        finally:
            self.world.valid = False
            self._receiving = False

    async def ping(self):
        from .wire import Writer
        if len(self.pings) >= 3:
            raise SessionTimeout('ping_ack')
        identifier = secrets.randbits(32)
        self.pings[identifier] = time.monotonic()
        return await self.send(Writer().u8(0x40).u32(identifier).u16(0).u16(0).data)

    async def close(self):
        self.gate.suspended = True
        try:
            await self.send(b'\xbe',control=True)
            await self.send(b'\x14',control=True)
        finally:
            self.writer.close()
            await self.writer.wait_closed()
