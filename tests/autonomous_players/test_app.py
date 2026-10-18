import unittest
import asyncio
from tools.autonomous_players.app import validate_config, functional_population, admission_available, occupancy_ids, owned_food_count


class ConnectionAdmissionTests(unittest.IsolatedAsyncioTestCase):
    async def test_dead_session_relogs_without_ping_timeout_or_database_repair(self):
        from unittest.mock import AsyncMock,MagicMock,patch
        from types import SimpleNamespace
        from tools.autonomous_players.app import PlayerRunner
        from tools.autonomous_players.world import World,Stats,Position
        store=MagicMock()
        profile=dict(account=1,character='Sim Test',password='qa',vocation='knight',city='thais')
        runner=PlayerRunner(profile,dict(host='127.0.0.1',game_port=1,modulus='1'),{},store,{'Sim Test'})
        sessions=[]
        async def receive():await asyncio.Future()
        async def connect(*args):
            world=World(self_id=0x10000001,position=Position(100,100,7),stats=Stats(0 if not sessions else 150,150,400,0,1))
            session=SimpleNamespace(world=world,gate=MagicMock(),receive=receive,send=AsyncMock(),close=AsyncMock(),ping=AsyncMock())
            sessions.append(session)
            if len(sessions)>1:runner.draining.set()
            return session
        with patch('tools.autonomous_players.app.Session.connect',side_effect=connect),patch('tools.autonomous_players.app.Agent'),patch('tools.autonomous_players.app.Progression'),patch('tools.autonomous_players.app.Conversation'):
            await asyncio.wait_for(runner.run(),7)
        self.assertEqual(len(sessions),2)
        sessions[0].ping.assert_not_awaited()
        sessions[0].close.assert_awaited_once()
        self.assertEqual(runner.status['failures'],0)
        self.assertTrue(any(call.args[2]=='death' for call in store.event.call_args_list))

    async def test_suspension_cancels_waiting_connection_without_consuming_future_slot(self):
        from tools.autonomous_players.app import connection_admission
        from tools.autonomous_players.runtime import RateLimit
        budget=RateLimit(.1,1)
        await budget.acquire()
        draining=asyncio.Event()
        waiting=asyncio.create_task(connection_admission(budget,draining))
        await asyncio.sleep(.01)
        draining.set()
        self.assertFalse(await asyncio.wait_for(waiting,.1))
        self.assertFalse(budget.lock.locked())


class AppTests(unittest.TestCase):
    def test_food_receipt_counts_owned_items_without_open_corpse_contents(self):
        from pathlib import Path
        from tools.autonomous_players.world import World,Thing,Container
        from tools.autonomous_players.definitions import load_items
        items=load_items(Path(__file__).resolve().parents[2]/'data/items/items.srv')
        w=World()
        w.containers[0]=Container(0,2853,'bag',20,False,[Thing(3577,2)])
        w.containers[1]=Container(1,4173,'dead rabbit',10,False,[Thing(3577,1)])
        self.assertEqual(owned_food_count(w,items,True),2)
        w.containers[0].items.append(Thing(3577,1))
        w.containers[1].items.clear()
        self.assertEqual(owned_food_count(w,items,True),3)

    def test_requires_explicit_target_and_maximum_twenty(self):
        config = dict(identity='test-world',public_authorized=True,max_players=20,host='127.0.0.1',game_port=7186,
                      manifest='private.json',state_dir='state',health_file='health.json',items='items.srv',modulus='1')
        self.assertEqual(validate_config(config)['max_players'],20)
        for changed in ({'max_players':21},{'public_authorized':False},{'identity':''}):
            with self.assertRaises(ValueError):
                validate_config(dict(config,**changed))

    def test_progress_and_sql_online_required_for_ramp(self):
        own = {1:dict(online=True,moves=10,xp_gain=5,last_progress_at=100,last_xp_at=100),
               2:dict(online=True,moves=10,xp_gain=0,last_progress_at=100,last_xp_at=100)}
        sql = dict(players=[[1,1,5,150,0,100,100,7,1],[2,1,0,150,0,101,100,7,1]])
        self.assertFalse(functional_population(own,sql,2,now=101))
        own[2]['xp_gain']=5
        self.assertTrue(functional_population(own,sql,2,now=101))
        self.assertFalse(functional_population(own,sql,2,now=1000))
        sql['players'][1][-1]=0
        self.assertFalse(functional_population(own,sql,2,now=101))

    def test_draining_sessions_still_consume_capacity(self):
        self.assertFalse(admission_available(0,1,1))
        self.assertFalse(admission_available(10,20,20))
        self.assertTrue(admission_available(0,0,1))

    def test_disconnected_player_waits_for_fresh_sql_offline_confirmation(self):
        self.assertEqual(occupancy_ids(set(),{1:101},[[1,1]],100),{1})
        self.assertEqual(occupancy_ids(set(),{1:101},[[1,0]],100),{1})
        self.assertEqual(occupancy_ids(set(),{1:101},[[1,0]],102),set())
        self.assertEqual(occupancy_ids({2},{1:101},[[1,1],[2,1]],102),{1,2})

    def test_combat_priority_does_not_advance_npc_dialogue(self):
        from tools.autonomous_players.app import choose_actions
        class Agent:
            def priority(self,now):return True
            def step(self,now):return [b'\xa1']
        class Progression:
            def step(self,now):raise AssertionError('urgent combat must precede NPC state transition')
        self.assertEqual(choose_actions(Agent(),Progression(),1),[b'\xa1'])
