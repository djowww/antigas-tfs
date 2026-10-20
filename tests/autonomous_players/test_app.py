import unittest
import asyncio
from tools.autonomous_players.app import (validate_config, functional_population, admission_available,
                                          occupancy_ids, owned_food_count, connection_failure_payload,
                                          death_event_payload)
from tools.autonomous_players.wire import ProtocolError


class ReconnectBackoffTests(unittest.TestCase):
    def test_route_confidence_uses_only_confirmed_movement_evidence(self):
        from tools.autonomous_players.app import observed_route_confidence

        self.assertEqual(observed_route_confidence('move',10,11),1.0)
        self.assertEqual(observed_route_confidence('move',10,10),0.0)
        self.assertEqual(observed_route_confidence('hunt',10,11),0.5)
        self.assertEqual(observed_route_confidence('move',11,10),0.5)
        self.assertEqual(observed_route_confidence('move',None,10),0.5)

    def test_learning_session_ids_are_unique_across_runner_restarts(self):
        from tools.autonomous_players.app import new_learning_session_id

        first=new_learning_session_id()
        second=new_learning_session_id()

        self.assertEqual(len(first),32)
        self.assertNotEqual(first,second)

    def test_backoff_grows_to_a_cap(self):
        from tools.autonomous_players import app
        self.assertTrue(callable(getattr(app, 'reconnect_delay', None)))
        self.assertEqual([app.reconnect_delay(n) for n in range(1, 9)],
                         [10, 20, 40, 80, 160, 300, 300, 300])

    def test_stable_online_session_clears_only_consecutive_failures(self):
        from tools.autonomous_players import app
        self.assertTrue(callable(getattr(app, 'reset_failure_streak', None)))
        self.assertEqual(app.reset_failure_streak(6, 59.9), 6)
        self.assertEqual(app.reset_failure_streak(6, 60), 0)
        self.assertEqual(app.reset_failure_streak(0, 60), 0)


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
    def test_observation_gap_diagnostic_separates_sample_delay_from_controller_delay(self):
        from tools.autonomous_players.app import observation_gap_payload
        from tools.autonomous_players.supervisor import HealthSample

        sample=HealthSample(now=121,measured_at=120.5,memory_mib=1500,
                            cpu_percent=30,latency_ms=25,server_pid=42)

        payload=observation_gap_payload(100,sample,controller_loop_gap=2,now=121.2)

        self.assertEqual(payload['sample_gap_seconds'],21)
        self.assertEqual(payload['sample_age_seconds'],0.7)
        self.assertEqual(payload['controller_loop_gap_seconds'],2)
        self.assertEqual(payload['server_pid'],42)
        self.assertEqual(payload['dispatcher_queued'],0)

    def test_observation_gap_diagnostic_records_blocking_controller_stage(self):
        from tools.autonomous_players.app import observation_gap_payload
        from tools.autonomous_players.supervisor import HealthSample

        sample=HealthSample(now=121,measured_at=120.5,memory_mib=1500,
                            cpu_percent=30,latency_ms=25,server_pid=42)

        payload=observation_gap_payload(100,sample,controller_loop_gap=21,now=121.2,
                                        controller_stage='persist_status',controller_stage_seconds=20.4)

        self.assertEqual(payload['controller_stage'],'persist_status')
        self.assertEqual(payload['controller_stage_seconds'],20.4)

    def test_kill_event_and_checkpoint_commit_or_rollback_together(self):
        import sqlite3
        import tempfile
        from pathlib import Path
        from tools.autonomous_players.app import sync_confirmed_kills
        from tools.autonomous_players.store import Store

        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'state.db') as store:
            store.checkpoint('Sim Test',{'confirmed_kills':3,'confirmed_kill_types':{'Rat':3}})
            store.db.execute("CREATE TRIGGER reject_kill BEFORE INSERT ON events BEGIN SELECT RAISE(ABORT,'disk simulation'); END")
            status={'confirmed_kills':3,'confirmed_kill_types':{'Rat':3}}
            reported={}

            with self.assertRaises(sqlite3.IntegrityError):
                sync_confirmed_kills(store,'Sim Test',{'Rat':1},reported,{'Rat':3},status,100,
                                     {'edges':['preserve']})

            self.assertEqual(store.restore('Sim Test'),
                             {'confirmed_kills':3,'confirmed_kill_types':{'Rat':3}})
            self.assertEqual(store.db.execute('SELECT count(*) FROM events').fetchone()[0],0)
            self.assertEqual(reported,{})
            self.assertEqual(status,{'confirmed_kills':3,'confirmed_kill_types':{'Rat':3}})

    def test_confirmed_kill_status_sync_is_immediate_and_idempotent(self):
        import json
        import tempfile
        from pathlib import Path
        from tools.autonomous_players.app import sync_confirmed_kills
        from tools.autonomous_players.store import Store

        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'state.db') as store:
            status={}
            reported={}
            baseline={'Rat':3}
            current={'Rat':1}
            navigation={'edges':['preserve']}
            sync_confirmed_kills(store,'Sim Test',current,reported,baseline,status,100,navigation)
            self.assertEqual(status,{'confirmed_kill_types':{'Rat':4},'confirmed_kills':4})
            sync_confirmed_kills(store,'Sim Test',current,reported,baseline,status,101,navigation)
            rows=store.db.execute('SELECT kind,payload FROM events ORDER BY id').fetchall()

            self.assertEqual(rows,[('kill_confirmed',json.dumps(
                {'creature':'Rat','count':1,'total':4},separators=(',',':')))])
            self.assertEqual(store.restore('Sim Test'),{
                'confirmed_kill_types':{'Rat':4},'confirmed_kills':4,'learned_navigation':navigation})

            current={'Rat':2,'Cave Rat':1}
            sync_confirmed_kills(store,'Sim Test',current,reported,baseline,status,102,navigation)
            self.assertEqual(status,{'confirmed_kill_types':{'Rat':5,'Cave Rat':1},
                                    'confirmed_kills':6})
            self.assertEqual(store.db.execute('SELECT count(*) FROM events').fetchone()[0],3)

    def test_player_runner_restores_and_saves_learned_navigation_with_status(self):
        import tempfile
        import time
        from pathlib import Path
        from tools.autonomous_players.app import PlayerRunner
        from tools.autonomous_players.learned_navigation import RegionGraph
        from tools.autonomous_players.store import Store
        from tools.autonomous_players.world import Position

        source,target=Position(100,100,8),Position(103,100,8)
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'state.db') as store:
            learned=RegionGraph()
            learned.record_failure('Sim Test',source,target,'blocked',10)
            store.checkpoint('Sim Test',{'learned_navigation':learned.snapshot('Sim Test',now=20)})
            profile=dict(account=1,character='Sim Test',password='qa',vocation='knight',city='thais')
            runner=PlayerRunner(profile,dict(host='127.0.0.1',game_port=1,modulus='1'),{},store,{'Sim Test'})

            self.assertTrue(runner.learned_graph.is_blocked('Sim Test',source,target,time.monotonic()+100))
            runner.status['moves']=9
            runner.status['confirmed_kills']=2
            runner.status['confirmed_kill_types']={'Rat':1,'Cave Rat':1}
            runner.save_checkpoint()
            saved=store.restore('Sim Test')
            resumed=PlayerRunner(profile,dict(host='127.0.0.1',game_port=1,modulus='1'),{},store,{'Sim Test'})

            self.assertEqual(saved['moves'],9)
            self.assertEqual(len(saved['learned_navigation']['edges']),1)
            self.assertEqual(resumed.status['confirmed_kills'],2)
            self.assertEqual(resumed.status['confirmed_kill_types'],{'Rat':1,'Cave Rat':1})

    def test_confirmed_floor_transition_is_checkpointed_immediately(self):
        import tempfile
        from pathlib import Path
        from tools.autonomous_players.app import PlayerRunner
        from tools.autonomous_players.store import Store
        from tools.autonomous_players.world import Position

        source,destination=Position(32109,32245,7),Position(32110,32246,8)
        profile=dict(account=1,character='Sim Test',password='qa',vocation='knight',city='thais')
        with tempfile.TemporaryDirectory() as d, Store(Path(d)/'state.db') as store:
            runner=PlayerRunner(profile,dict(host='127.0.0.1',game_port=1,modulus='1'),{},store,{'Sim Test'})

            recorded=runner.record_learned_transition(source,destination,428,100)

            self.assertTrue(recorded)
            checkpoint=store.restore('Sim Test')
            self.assertTrue(checkpoint['learned_navigation']['edges'][0]['verified'])

    def test_food_receipt_counts_owned_items_without_open_corpse_contents(self):
        from pathlib import Path
        from tools.autonomous_players.world import World,Thing,Container
        from tools.autonomous_players.definitions import load_items
        items=load_items(Path(__file__).resolve().parents[2]/'data/items/items.srv')
        w=World()
        w.containers[0]=Container(0,2853,'bag',20,False,[Thing(3577,2)])
        w.containers[1]=Container(1,4173,'dead rabbit',10,False,[Thing(3577,1)])
        self.assertEqual(owned_food_count(w,items),2)
        w.containers[0].items.append(Thing(3577,1))
        w.containers[1].items.clear()
        self.assertEqual(owned_food_count(w,items),3)

    def test_food_receipt_does_not_count_food_in_unrelated_open_corpses(self):
        from pathlib import Path
        from tools.autonomous_players.world import World,Thing,Container
        from tools.autonomous_players.definitions import load_items
        items=load_items(Path(__file__).resolve().parents[2]/'data/items/items.srv')
        w=World()
        w.containers[0]=Container(0,2853,'backpack',20,False,[Thing(3577,2)])
        w.containers[1]=Container(1,4173,'dead rabbit',10,False,[Thing(3577,1)])
        w.containers[2]=Container(2,3994,'dead rat',10,False,[Thing(3607,1)])

        self.assertEqual(owned_food_count(w,items),2)

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
class ConnectionFailureTests(unittest.TestCase):
    def test_protocol_failure_payload_keeps_only_bounded_printable_diagnostic(self):
        payload=connection_failure_payload(ProtocolError('unsupported server opcode 0x99\n'))
        self.assertEqual(payload['kind'],'ProtocolError')
        self.assertEqual(payload['detail'],'unsupported server opcode 0x99')
        self.assertLessEqual(len(payload['detail']),160)

    def test_non_protocol_failure_does_not_expose_exception_text(self):
        self.assertEqual(connection_failure_payload(OSError('private connection detail')),
                         {'kind':'OSError'})

class DeathDiagnosticsTests(unittest.TestCase):
    def test_death_event_captures_bounded_live_combat_and_retreat_context(self):
        from types import SimpleNamespace
        from tools.autonomous_players.world import World,Stats,Position,Creature

        position=Position(32065,32250,8)
        target=Creature(0x40000001,'Rat',Position(32066,32250,8),health=40)
        world=World(self_id=0x10000001,position=position,stats=Stats(0,150,400,25,1),
                    creatures={target.id:target},icons=128)
        agent=SimpleNamespace(strategy='retreat',target=target.id,
                              retreat_needed=lambda:True,food=lambda:iter(()))
        previous_decision={'actions':[109], 'walkable_neighbors':1, 'tiles':126,
                           'next_action_in':0.2, 'ignored':'not persisted'}

        payload=death_event_payload(world,agent,previous_decision)

        self.assertEqual(payload['position'],[32065,32250,8])
        self.assertEqual((payload['health'],payload['max_health'],payload['experience']),(0,150,25))
        self.assertEqual(payload['strategy'],'retreat')
        self.assertTrue(payload['retreat_needed'])
        self.assertFalse(payload['food_available'])
        self.assertEqual(payload['target'],{'name':'Rat','health':40,'position':[32066,32250,8]})
        self.assertEqual(payload['nearby_monsters'],[payload['target']])
        self.assertEqual(payload['decision'],{'actions':[109],'walkable_neighbors':1,'tiles':126,
                                               'next_action_in':0.2})

    def test_death_event_never_persists_a_human_player_as_combat_target(self):
        from types import SimpleNamespace
        from tools.autonomous_players.world import World,Stats,Position,Creature

        position=Position(32065,32250,8)
        human=Creature(0x10000002,'Nearby Player',position,health=100)
        world=World(self_id=0x10000001,position=position,stats=Stats(0,150,400,25,1),
                    creatures={human.id:human})
        agent=SimpleNamespace(strategy='retreat',target=human.id,
                              retreat_needed=lambda:True,food=lambda:iter(()))

        payload=death_event_payload(world,agent,{})

        self.assertIsNone(payload['target'])
        self.assertEqual(payload['nearby_monsters'],[])
