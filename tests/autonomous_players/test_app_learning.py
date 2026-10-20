import unittest
import asyncio
from tools.autonomous_players.app import apply_learning_intent
from tools.autonomous_players.learning_protocol import LearningIntent


class _Progression:
    busy = False
    authorization = None
    floor_authorization = None

    def recover(self, now):
        return [b'recover']

    def step(self, now):
        return []


class _PriorityAgent:
    def priority(self, now):
        return True

    def step(self, now):
        return [b'priority']


class _PriorityGuidedAgent:
    def __init__(self, applies_hint=True):
        self.applies_hint=applies_hint
        self.strategy_hint_applied=False
        self.hint=None

    def priority(self, now):
        return True

    def step(self, now, strategy_hint=None):
        self.hint=strategy_hint
        self.strategy_hint_applied=self.applies_hint and strategy_hint=='hunt'
        return [b'\xa0',b'\xa1']


class _IdleAgent:
    def priority(self, now):
        return False

    def step(self, now):
        return [b'agent']


class _GuidedAgent:
    def __init__(self):
        self.strategy_hint = None

    def priority(self, now):
        return False

    def step(self, now, strategy_hint=None):
        self.strategy_hint = strategy_hint
        return [b'guided']


class AppLearningTests(unittest.TestCase):
    def test_npc_speech_is_not_misreported_as_a_successful_move(self):
        from tools.autonomous_players.app import classify_learning_action
        intent=LearningIntent('A','move',{},1,5)
        self.assertEqual(classify_learning_action(intent,False,False,[b'\x96hello'],True),'none')

    def test_walk_packet_is_reported_as_a_move(self):
        from tools.autonomous_players.app import classify_learning_action
        intent=LearningIntent('A','move',{},1,5)
        self.assertEqual(classify_learning_action(intent,False,False,[b'\x66'],True,'move'),'move')

    def test_progression_walk_is_not_mislearned_as_move_without_matching_control(self):
        from tools.autonomous_players.app import classify_learning_action
        intent=LearningIntent('A','move',{},1,5)
        packet=[b'\x66']
        self.assertEqual(classify_learning_action(intent,False,False,packet,packet,None),'none')
        self.assertEqual(classify_learning_action(intent,False,False,packet,packet,'hunt'),'none')

    def test_accepted_cancel_does_not_count_as_rejected_move(self):
        from tools.autonomous_players.app import classify_learning_action
        intent=LearningIntent('A','move',{},1,5)
        self.assertEqual(classify_learning_action(
            intent,False,False,[b'\xbe',b'\x66'],[b'\xbe']),'none')

    def test_priority_reaction_is_not_used_as_a_learning_action(self):
        from tools.autonomous_players.app import classify_learning_action
        intent=LearningIntent('A','hunt',{},1,5)
        self.assertEqual(classify_learning_action(intent,True,False,[b'\xa1'],True),'none')

    def test_priority_hunt_is_attributed_only_when_agent_applied_learner_hint(self):
        from tools.autonomous_players.app import classify_learning_action
        intent=LearningIntent('A','hunt',{},1,5)
        self.assertEqual(classify_learning_action(intent,True,False,[b'\xa0',b'\xa1'],
                                                  [b'\xa0',b'\xa1'],'hunt'),'hunt')
        self.assertEqual(classify_learning_action(intent,True,False,[b'\xa0',b'\xa1'],
                                                  [b'\xa0',b'\xa1'],None),'none')

    def test_priority_strategy_passes_hunt_hint_to_agent_and_marks_applied_action(self):
        from tools.autonomous_players.app import select_actions_with_learning
        agent=_PriorityGuidedAgent()
        intent=LearningIntent('A','hunt',{},1,5)

        actions,controlled_kind=select_actions_with_learning(agent,_Progression(),2,intent)

        self.assertEqual(agent.hint,'hunt')
        self.assertEqual(actions,[b'\xa0',b'\xa1'])
        self.assertEqual(controlled_kind,'hunt')

    def test_priority_strategy_that_agent_rejects_is_not_attributed(self):
        from tools.autonomous_players.app import select_actions_with_learning
        agent=_PriorityGuidedAgent(applies_hint=False)
        intent=LearningIntent('A','hunt',{},1,5)

        _,controlled_kind=select_actions_with_learning(agent,_Progression(),2,intent)

        self.assertIsNone(controlled_kind)

    def test_stale_wait_intent_is_not_recorded_as_an_action(self):
        from tools.autonomous_players.app import classify_learning_action
        intent=LearningIntent('A','wait',{},1,5)
        self.assertEqual(classify_learning_action(intent,False,False,[],False),'none')

    def test_busy_progression_is_not_attributed_to_the_learning_intent(self):
        from tools.autonomous_players.app import classify_learning_action
        intent=LearningIntent('A','move',{},1,5)
        self.assertEqual(classify_learning_action(intent,False,True,[b'\x66'],True),'none')

    def test_retreat_intent_uses_existing_recovery_path(self):
        intent = LearningIntent('A', 'retreat', {}, 1, 5)
        self.assertEqual(apply_learning_intent(intent, _Progression(), 2, [b'normal']), [b'recover'])

    def test_non_retreat_intent_keeps_existing_actions(self):
        intent = LearningIntent('A', 'hunt', {}, 1, 5)
        self.assertEqual(apply_learning_intent(intent, _Progression(), 2, [b'normal']), [b'normal'])

    def test_priority_agent_action_is_not_replaced_by_learning_intent(self):
        from tools.autonomous_players.app import choose_actions_with_learning
        intent = LearningIntent('A', 'retreat', {}, 1, 5)
        self.assertEqual(choose_actions_with_learning(_PriorityAgent(), _Progression(), 2, intent), [b'priority'])

    def test_stale_wait_intent_falls_back_to_normal_agent_actions(self):
        from tools.autonomous_players.app import choose_actions_with_learning
        intent = LearningIntent('A', 'wait', {}, 1, 5)
        self.assertEqual(choose_actions_with_learning(_IdleAgent(), _Progression(), 2, intent), [b'agent'])

    def test_move_intent_guides_exploration_instead_of_being_ignored(self):
        from tools.autonomous_players.app import choose_actions_with_learning
        agent = _GuidedAgent()
        intent = LearningIntent('A', 'move', {}, 1, 5)

        self.assertEqual(choose_actions_with_learning(agent, _Progression(), 2, intent), [b'guided'])
        self.assertEqual(agent.strategy_hint, 'explore')

    def test_hunt_intent_uses_configured_hunt_route_before_local_fallback(self):
        from tools.autonomous_players.app import select_actions_with_learning
        agent = _GuidedAgent()
        progression = _Progression()
        progression.step = lambda now: [b'hunt-route']
        intent = LearningIntent('A', 'hunt', {}, 1, 5)

        actions, controlled_kind = select_actions_with_learning(agent, progression, 2, intent)
        self.assertEqual(actions, [b'hunt-route'])
        self.assertIsNone(controlled_kind)
        self.assertIsNone(agent.strategy_hint)

    def test_hunt_intent_is_attributed_when_progression_confirms_hunt_route(self):
        from tools.autonomous_players.app import select_actions_with_learning

        class HuntProgression(_Progression):
            strategy_hint_applied=False
            def step_with_intent(self,now,intent):
                self.strategy_hint_applied=(intent=='hunt')
                return [b'hunt-route'] if self.strategy_hint_applied else []

        intent=LearningIntent('A','hunt',{},1,5)
        progression=HuntProgression()
        actions,controlled_kind=select_actions_with_learning(
            _GuidedAgent(),progression,2,intent)

        self.assertEqual(actions,[b'hunt-route'])
        self.assertEqual(controlled_kind,'hunt')

    def test_supply_travel_walk_is_not_attributed_to_hunt_intent(self):
        from tools.autonomous_players.app import select_actions_with_learning, classify_learning_action
        from tools.autonomous_players.definitions import load_items
        from tools.autonomous_players.progression import Progression
        from tools.autonomous_players.routes import RouteGraph
        from tools.autonomous_players.world import Position, Stats, Thing, World
        from pathlib import Path

        start=Position(32048,32205,7)
        step=start.shift(x=-1)
        goal=step
        world=World(position=start,stats=Stats(150,150,400,0,1))
        world.inventory[10]=Thing(3031,3)
        world.tiles[step]=[Thing(102)]
        items=load_items(Path(__file__).resolve().parents[2]/'data/items/items.srv')
        progression=Progression(dict(character='Sim One',city='thais',vocation='knight'),world,items,
                                RouteGraph({start:None,step:None}))
        intent=LearningIntent('Sim One','hunt',{},1,5)

        actions,controlled=select_actions_with_learning(_IdleAgent(),progression,2,intent)

        self.assertTrue(actions and actions[0][0] in (0x65,0x66,0x67,0x68))
        self.assertTrue(progression.busy)
        self.assertIsNone(controlled)
        self.assertEqual(classify_learning_action(intent,False,progression.busy,actions,actions,controlled),'none')

    def test_failed_hunt_route_fallback_is_not_misreported_as_hunting(self):
        from tools.autonomous_players.app import select_actions_with_learning, classify_learning_action

        intent = LearningIntent('A', 'hunt', {}, 1, 5)
        agent = _GuidedAgent()
        actions, controlled_kind = select_actions_with_learning(agent, _Progression(), 2, intent)

        self.assertEqual(actions, [b'guided'])
        self.assertIsNone(controlled_kind)
        self.assertEqual(classify_learning_action(intent, False, False, actions, True, controlled_kind), 'none')

    def test_failed_retreat_fallback_is_not_misreported_as_a_retreat(self):
        from tools.autonomous_players.app import select_actions_with_learning, classify_learning_action

        class NoRecoveryProgression(_Progression):
            def recover(self, now):
                return []

        intent = LearningIntent('A', 'retreat', {}, 1, 5)
        agent = _GuidedAgent()
        progression = NoRecoveryProgression()
        actions, controlled_kind = select_actions_with_learning(agent, progression, 2, intent)

        self.assertEqual(actions, [b'guided'])
        self.assertIsNone(controlled_kind)
        self.assertEqual(classify_learning_action(intent, False, False, actions, True, controlled_kind), 'none')

    def test_successful_retreat_is_attributed_to_the_learning_intent(self):
        from tools.autonomous_players.app import select_actions_with_learning, classify_learning_action

        intent = LearningIntent('A', 'retreat', {}, 1, 5)
        actions, controlled_kind = select_actions_with_learning(_IdleAgent(), _Progression(), 2, intent)

        self.assertEqual(actions, [b'recover'])
        self.assertEqual(controlled_kind, 'retreat')
        self.assertEqual(classify_learning_action(intent, False, False, actions, True, controlled_kind), 'retreat')


class RunnerLearningInitializationTests(unittest.IsolatedAsyncioTestCase):
    async def test_controlled_action_survives_idle_loops_until_next_learning_observation(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, MagicMock, patch
        import time as real_time
        from tools.autonomous_players.app import PlayerRunner
        from tools.autonomous_players.learning_protocol import LearningIntent
        from tools.autonomous_players.world import World, Stats, Position

        class Clock:
            value = 100
            def monotonic(self):
                self.value += 1
                return self.value
            def time(self):
                return 2_000_000_000 + self.value

        profile=dict(account=1,character='Sim Test',password='qa',vocation='knight',city='thais')
        runner=PlayerRunner(profile,dict(host='127.0.0.1',game_port=1,modulus='1'),{},MagicMock(),{'Sim Test'})
        world=World(self_id=0x10000001,position=Position(100,100,7),stats=Stats(150,150,400,0,1))
        sent=[]
        session=SimpleNamespace(world=world,gate=MagicMock(),pings={},last_received=0)
        async def receive(): await asyncio.Future()
        async def send(packet,control=False): sent.append(packet); return True
        session.receive=receive
        session.send=send
        session.ping=AsyncMock()
        session.close=AsyncMock()

        class Progression:
            busy=False
            authorization=None
            floor_authorization=None
            purchase=None
            routes=None
            def __init__(self,*args,**kwargs): pass
            def observe(self,*args): pass
            def step(self,now): return []
            def recover(self,now): return []
            def forage(self,now): return []
            def in_rook(self): return True
            def healing_status(self,now): return {}
            def hunting_status(self,now): return {}

        agent=MagicMock()
        agent.priority.return_value=False
        agent.step.return_value=[b'\x66']
        agent.food.side_effect=lambda:iter(())
        agent.prey.return_value=[SimpleNamespace(name='Rabbit',position=Position(101,100,7))]
        agent.retreat_needed.return_value=False
        agent.strategy_hint_applied=True
        agent.strategy='explore'
        agent.target=0
        agent.next_action=0
        agent.allowed_corpses={}
        agent.loot_pending=None
        agent.passive_corpse_claims=0
        observations=[]

        class Learning:
            calls=0
            async def publish_async(self,observation):
                observations.append(observation)
                self.calls+=1
                if self.calls==2: runner.draining.set()
            def poll_intent(self,now):
                return LearningIntent('Sim Test','move',{},real_time.time(),30) if self.calls==1 else None
            def close(self): pass

        runner.learning=Learning()
        with patch('tools.autonomous_players.app.time',Clock()),\
             patch('tools.autonomous_players.app.Session.connect',AsyncMock(return_value=session)),\
             patch('tools.autonomous_players.app.Agent',return_value=agent),\
             patch('tools.autonomous_players.app.Progression',Progression),\
             patch('tools.autonomous_players.app.Conversation',return_value=SimpleNamespace(
                 observe=lambda *args:None,step=lambda *args:None,replies=0)):
            await asyncio.wait_for(runner.run(),2)

        self.assertEqual(len(observations),2)
        self.assertEqual(observations[0].state['executed_action'],'none')
        self.assertEqual(observations[1].state['executed_action'],'move')
        self.assertTrue(observations[0].state['prey_available'])
        self.assertTrue(observations[0].state['food_prey_available'])

    async def test_first_observation_after_reconnect_does_not_claim_a_wait_action(self):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock,MagicMock,patch
        from tools.autonomous_players.app import PlayerRunner
        from tools.autonomous_players.world import World,Stats,Position

        profile=dict(account=1,character='Sim Test',password='qa',vocation='knight',city='thais')
        runner=PlayerRunner(profile,dict(host='127.0.0.1',game_port=1,modulus='1'),{},MagicMock(),{'Sim Test'})
        observations=[]
        class Learning:
            async def publish_async(self,observation):observations.append(observation)
            def poll_intent(self,now):return None
            def close(self):pass
        runner.learning=Learning()
        async def receive():await asyncio.Future()
        async def connect(*args):
            world=World(self_id=0x10000001,position=Position(100,100,7),stats=Stats(150,150,400,0,1))
            runner.draining.set()
            return SimpleNamespace(world=world,gate=MagicMock(),receive=receive,send=AsyncMock(return_value=True),
                                  close=AsyncMock(),ping=AsyncMock(),pings={},last_received=0)

        with patch('tools.autonomous_players.app.Session.connect',side_effect=connect),\
             patch('tools.autonomous_players.app.Agent'),\
             patch('tools.autonomous_players.app.Progression'),\
             patch('tools.autonomous_players.app.Conversation'):
            await asyncio.wait_for(runner.run(),2)

        self.assertEqual(len(observations),1)
        self.assertEqual(observations[0].state['executed_action'],'none')


if __name__ == '__main__':
    unittest.main()
