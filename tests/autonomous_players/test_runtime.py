import asyncio
import unittest

from tools.autonomous_players.runtime import Session, ActionGate, RateLimit
from tools.autonomous_players.world import World, Creature, Position
from tools.autonomous_players.wire import FrameCodec, ProtocolError
from tools.autonomous_players.protocol import say


class GateTests(unittest.TestCase):
    def test_normal_follow_mode_is_allowed_without_secure_pvp(self):
        gate=ActionGate(World(position=Position(100,100,7)))
        self.assertTrue(gate.permit(b'\xa0\x01\x01\x00'))
        self.assertFalse(gate.permit(b'\xa0\x01\x01\x01'))

    def test_speech_needs_live_nearby_npc_and_one_confirmation_token(self):
        world=World(position=Position(100,100,7))
        world.creatures[0x80000001]=Creature(0x80000001,'The Oracle',Position(101,100,7))
        gate=ActionGate(world)
        self.assertFalse(gate.permit(say('yes')))
        gate.authorize_speech(0x80000001,'yes',100)
        self.assertTrue(gate.permit(say('yes'),now=99))
        self.assertFalse(gate.permit(say('yes'),now=99))

    def test_invalid_or_disappeared_targets_never_send(self):
        world = World(self_id=0x10000001,position=Position(100,100,7))
        monster = Creature(0x40000001,'Rat',Position(101,100,7))
        world.creatures[monster.id] = monster
        gate = ActionGate(world)
        packet = b'\xa1\x01\x00\x00\x40'
        self.assertTrue(gate.permit(packet))
        monster.position = None
        self.assertFalse(gate.permit(packet))
        world.valid = False
        self.assertFalse(gate.permit(b'\x65'))
        self.assertTrue(gate.permit(b'\x14'))
        self.assertFalse(gate.permit(b'\xa1\x02\x00\x00\x10'))


class SessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_lost_ping_acks_do_not_disconnect_a_session_with_live_receive_loop(self):
        class Writer:
            def __init__(self):self.sent=[]
            def write(self,data):self.sent.append(data)
            async def drain(self):pass
        writer=Writer()
        session=Session(None,writer,(1,2,3,4),World(position=Position(100,100,7)),object())
        session.local_budget=RateLimit(100,10)
        for _ in range(4):
            await session.ping()
        self.assertEqual(len(writer.sent),4)
        self.assertEqual(len(session.pings),3)

    async def test_shared_connection_budget_spaces_reconnecting_clients(self):
        state=[0.0]
        async def sleep(delay):state[0]+=delay
        budget=RateLimit(.1,1,clock=lambda:state[0],sleep=sleep)
        admitted=[]
        for _ in range(20):
            await budget.acquire();admitted.append(state[0])
        self.assertEqual(admitted,list(range(0,200,10)))

    async def test_deadline_reports_only_fixed_stage_and_cancels_operation(self):
        from tools.autonomous_players.runtime import deadline, SessionTimeout
        cancelled=[]
        async def blocked():
            try:await asyncio.Future()
            finally:cancelled.append(True)
        with self.assertRaises(SessionTimeout) as failure:
            await deadline(blocked(),.01,'read')
        self.assertEqual(failure.exception.stage,'read')
        self.assertEqual(cancelled,[True])

    async def test_rate_budget_waits_without_dropping_actions(self):
        state=[0.0]
        async def sleep(delay):
            state[0]+=delay
        limit=RateLimit(2,2,clock=lambda:state[0],sleep=sleep)
        await limit.acquire();await limit.acquire()
        self.assertEqual(state[0],0)
        await limit.acquire()
        self.assertEqual(state[0],.5)

    async def test_single_reader_dispatches_coalesced_frames_and_pings(self):
        key = (1,2,3,4)
        codec = FrameCodec(key)
        reader = asyncio.StreamReader()
        reader.feed_data(codec.encode(b'\x1d')+codec.encode(b'\x1e'))
        reader.feed_eof()
        class Writer:
            def __init__(self):
                self.sent = []
            def write(self,data):
                self.sent.append(data)
            async def drain(self):
                pass
        class Decoder:
            def feed_payload(self,payload,world):
                from tools.autonomous_players.world import Event
                return [Event('ping' if payload == b'\x1d' else 'pong')]
        writer = Writer()
        session = Session(reader,writer,key,World(),Decoder())
        with self.assertRaises(EOFError):
            await session.receive()
        self.assertEqual(codec.feed(b''.join(writer.sent)),[b'\x1e'])
        self.assertEqual(session.received_packets,2)


if __name__ == '__main__':
    unittest.main()
