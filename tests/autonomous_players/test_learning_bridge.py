import asyncio
import tempfile
import unittest
from pathlib import Path
from tools.autonomous_players.learning_bridge import LearningAgent, LearningBridge, recv_line
from tools.autonomous_players.learning_protocol import LearningObservation
from tools.autonomous_players.world import Position, Stats, World


class LearningBridgeTests(unittest.TestCase):
    def test_neural_canary_controls_only_selected_agent_after_training(self):
        from unittest.mock import Mock,patch
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db',neural_mode='active',neural_agents=('A',))
            try:
                agent.neural.choose=Mock(return_value='hunt')
                world=World(position=Position(100,100,8),stats=Stats(150,150,400,0,1))
                with patch('tools.autonomous_players.learning_bridge.Policy.choose',return_value='move'):
                    self.assertEqual(agent.handle(LearningObservation.from_world('A',world,'hunt',0)).kind,'move')
                    agent.neural.choose.assert_not_called()
                    agent.neural.updates=1000
                    self.assertEqual(agent.handle(LearningObservation.from_world('B',world,'hunt',0)).kind,'move')
                    agent.neural.choose.assert_not_called()
                    self.assertEqual(agent.handle(LearningObservation.from_world('A',world,'hunt',0)).kind,'hunt')
                    self.assertEqual(agent.neural_decisions,{'A':1})
                    agent.handle(LearningObservation.from_world('A',world,'hunt',0,executed_action='hunt'))
                    self.assertEqual(agent.neural_confirmed,{'A':1})
            finally:
                agent.close()

    def test_learner_cli_passes_canary_and_exits_cleanly_after_interrupt(self):
        from unittest.mock import patch
        from tools.autonomous_learning_agent import main
        with patch('tools.autonomous_learning_agent.serve',side_effect=KeyboardInterrupt) as server:
            self.assertEqual(main(['--socket','test.sock','--state','test.db',
                                  '--neural-mode','active','--neural-agent','A']),0)
            self.assertEqual(server.call_args.kwargs['neural_agents'],['A'])

    def test_neural_shadow_trains_only_confirmed_actions_without_controlling_player(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db',neural_mode='shadow')
            try:
                world=World(position=Position(100,100,8),stats=Stats(150,150,400,0,1))
                first=LearningObservation.from_world('A',world,'hunt',0,session_id='one')
                with patch('tools.autonomous_players.learning_bridge.Policy.choose',return_value='hunt'):
                    self.assertEqual(agent.handle(first).kind,'hunt')
                    rejected=LearningObservation.from_world('A',world,'hunt',0,
                        executed_action='move',session_id='one')
                    agent.handle(rejected)
                    self.assertEqual(len(agent.neural.replay),0)
                    confirmed=LearningObservation.from_world('A',world,'hunt',0,
                        executed_action='hunt',session_id='one')
                    self.assertEqual(agent.handle(confirmed).kind,'hunt')
                    self.assertEqual(len(agent.neural.replay),1)
                agent.close()
                self.assertTrue((Path(d)/'learning.neural.json').exists())
            finally:
                agent.store.close()

    def test_corrupt_neural_checkpoint_falls_back_to_tabular_policy(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d)/'learning.neural.json').write_text('{"broken":true}',encoding='utf-8')
            agent=LearningAgent(Path(d)/'learning.db',neural_mode='active')
            try:
                self.assertIsNone(agent.neural)
                world=World(position=Position(100,100,8),stats=Stats(150,150,400,0,1))
                self.assertIn(agent.handle(LearningObservation.from_world('A',world,'hunt',0)).kind,
                              ('move','hunt'))
            finally:
                agent.close()

    def test_active_neural_cannot_override_required_retreat(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db',neural_mode='active')
            try:
                agent.neural.updates=1000
                agent.neural.choose=Mock(return_value='hunt')
                world=World(position=Position(100,100,8),stats=Stats(30,150,400,0,1))
                observation=LearningObservation.from_world('A',world,'retreat',0,
                                                           retreat_required=True)
                self.assertEqual(agent.handle(observation).kind,'retreat')
                agent.neural.choose.assert_not_called()
            finally:
                agent.close()

    def test_active_neural_invalid_choice_falls_back_to_tabular(self):
        from unittest.mock import Mock,patch
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db',neural_mode='active')
            try:
                agent.neural.updates=1000
                agent.neural.choose=Mock(return_value='retreat')
                world=World(position=Position(100,100,7),stats=Stats(150,150,400,0,1))
                observation=LearningObservation.from_world('A',world,'hunt',0)
                with patch('tools.autonomous_players.learning_bridge.Policy.choose',return_value='move'):
                    self.assertEqual(agent.handle(observation).kind,'move')
            finally:
                agent.close()

    def test_policy_key_generalizes_position_but_distinguishes_threat_context(self):
        from tools.autonomous_players.world import Creature
        first_world=World(position=Position(100,100,8),stats=Stats(150,150,400,0,1))
        next_world=World(position=Position(101,100,8),stats=Stats(150,150,400,100,4))
        threat_world=World(position=Position(102,100,8),stats=Stats(150,150,400,100,1))
        threat_world.creatures[0x40000001]=Creature(0x40000001,'Rat',Position(104,100,8))
        first=LearningObservation.from_world('A',first_world,'hunt',0)
        next_tile=LearningObservation.from_world('A',next_world,'hunt',0)
        threat=LearningObservation.from_world('A',threat_world,'hunt',0)

        self.assertTrue(callable(getattr(LearningAgent,'policy_key',None)))
        self.assertEqual(LearningAgent.policy_key(first.state),LearningAgent.policy_key(next_tile.state))
        self.assertNotEqual(LearningAgent.policy_key(next_tile.state),LearningAgent.policy_key(threat.state))
        fed=LearningObservation.from_world('A',next_world,'hunt',0,food_available=True,retreat_available=True)
        hungry=LearningObservation.from_world('A',next_world,'hunt',0,food_available=False,retreat_available=True)
        self.assertNotEqual(LearningAgent.policy_key(fed.state),LearningAgent.policy_key(hungry.state))
        no_prey=LearningObservation.from_world('A',next_world,'hunt',0,prey_available=False,
                                               food_prey_available=False)
        passive_prey=LearningObservation.from_world('A',next_world,'hunt',0,prey_available=True,
                                                    food_prey_available=True)
        self.assertNotEqual(LearningAgent.policy_key(no_prey.state),
                            LearningAgent.policy_key(passive_prey.state))

    def test_learned_action_value_is_reused_on_another_tile_in_same_context(self):
        from unittest.mock import patch
        first_world=World(position=Position(100,100,8),stats=Stats(150,150,400,0,1))
        next_world=World(position=Position(101,100,8),stats=Stats(150,150,400,0,1))
        first=LearningObservation.from_world('A',first_world,'hunt',0)
        next_tile=LearningObservation.from_world('A',next_world,'hunt',0)
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db')
            try:
                self.assertTrue(callable(getattr(LearningAgent,'policy_key',None)))
                key=LearningAgent.policy_key(first.state)
                agent.store.set_value('A',key,'move',10.0)
                agent.store.set_value('A',key,'hunt',-1.0)
                policy=agent._policy('A')
                policy.epsilon=0
                policy.rng.choice=lambda actions:actions[0]
                with patch.object(LearningAgent,'_policy',return_value=policy):
                    self.assertEqual(agent.handle(next_tile).kind,'move')
            finally:
                agent.close()

    def test_policy_chooses_hunt_only_in_context_with_available_food_prey(self):
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db')
            world=World(position=Position(100,100,7),stats=Stats(70,150,400,0,1))
            no_prey=LearningObservation.from_world('A',world,'hunt',0,
                prey_available=False,food_prey_available=False)
            rabbit=LearningObservation.from_world('A',world,'hunt',0,
                prey_available=True,food_prey_available=True)
            try:
                no_prey_key=LearningAgent.policy_key(no_prey.state)
                rabbit_key=LearningAgent.policy_key(rabbit.state)
                agent.store.set_value('A',no_prey_key,'move',1.0)
                agent.store.set_value('A',rabbit_key,'hunt',1.0)
                policy=agent._policy('A')
                policy.epsilon=0

                self.assertEqual(agent.handle(no_prey).kind,'move')
                self.assertEqual(agent.handle(rabbit).kind,'hunt')
            finally:
                agent.close()

    def test_policy_context_revision_preserves_values_from_previous_schema(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db')
            try:
                world=World(position=Position(100,100,7),stats=Stats(100,150,400,0,1))
                observation=LearningObservation.from_world('A',world,'hunt',0,
                    food_available=False,retreat_available=True,retreat_required=False,
                    prey_available=False,food_prey_available=False)
                old_context_v1=json.dumps({
                    'policy_schema':1,'floor':7,'level_band':0,'health_band':'healthy',
                    'nearby_threats':0,'goal':'hunt','route_confidence':0.0,
                    'food_available':False,'retreat_available':True,
                },sort_keys=True,separators=(',',':'))
                old_context_v2=json.dumps({
                    'policy_schema':2,'floor':7,'level_band':0,'health_band':'healthy',
                    'nearby_threats':0,'goal':'hunt','retreat_required':False,
                    'route_confidence':0.0,'food_available':False,'retreat_available':True,
                },sort_keys=True,separators=(',',':'))
                agent.store.set_value('A',old_context_v1,'hunt',2.5)
                agent.store.set_value('A',old_context_v2,'move',3.5)

                agent.handle(observation)

                new_context=LearningAgent.policy_key(observation.state)
                self.assertEqual(agent.store.values('A',new_context),{'hunt':2.5,'move':3.5})
                self.assertEqual(agent.store.values('A',old_context_v1)['hunt'],2.5)
                self.assertEqual(agent.store.values('A',old_context_v2)['move'],3.5)
                self.assertEqual(json.loads(new_context)['policy_schema'],3)
            finally:
                agent.close()

    def test_observed_outcome_updates_the_generalized_policy_state(self):
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db')
            try:
                first_world=World(position=Position(100,100,8),stats=Stats(150,150,400,0,1))
                next_world=World(position=Position(101,100,8),stats=Stats(150,150,400,20,1))
                first=LearningObservation.from_world('A',first_world,'hunt',0)
                next_tile=LearningObservation.from_world('A',next_world,'hunt',0,executed_action='move')
                agent.handle(first)
                agent.handle(next_tile)
                key=LearningAgent.policy_key(first.state)
                self.assertIn('move',agent.store.values('A',key))
            finally:
                agent.close()

    def test_policy_does_not_learn_from_an_intent_the_runner_did_not_execute(self):
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db')
            try:
                world=World(position=Position(100,100,8),stats=Stats(150,150,400,0,1))
                first=LearningObservation.from_world('A',world,'hunt',0)
                intended=agent.handle(first).kind
                policy=agent._policy('A')
                policy.update=Mock(wraps=policy.update)
                mismatch='hunt' if intended=='move' else 'move'
                later=LearningObservation.from_world('A',world,'hunt',0,executed_action=mismatch)

                agent.handle(later)

                policy.update.assert_not_called()
            finally:
                agent.close()

    def test_failed_move_without_observed_displacement_gets_a_small_negative_reward(self):
        previous={'floor':8,'x':100,'y':100,'experience':20,'health':100,'max_health':150}
        current=dict(previous,executed_action='move')
        self.assertEqual(LearningAgent._reward(previous,current),-0.25)

    def test_combat_stall_penalizes_executed_hunt_even_after_cancel_packet(self):
        previous={'floor':8,'x':100,'y':100,'experience':20,'health':100,'max_health':150,
                  'combat_stalls':0}
        current=dict(previous,combat_stalls=1,executed_action='none')

        self.assertLess(LearningAgent._reward(previous,current,previous_action='hunt'),0)
        self.assertEqual(LearningAgent._reward(previous,current,previous_action='move'),0)

    def test_combat_stall_updates_q_value_for_hunt_after_cancel_packet(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db')
            try:
                world=World(position=Position(100,100,8),stats=Stats(150,150,400,20,1))
                first=LearningObservation.from_world('A',world,'hunt',0,combat_stalls=0)
                stalled=LearningObservation.from_world('A',world,'hunt',0,
                    executed_action='none',combat_stalls=1)
                with patch('tools.autonomous_players.learning_bridge.Policy.choose',return_value='hunt'):
                    agent.handle(first)
                    agent.handle(stalled)

                key=LearningAgent.policy_key(first.state)
                self.assertLess(agent.store.values('A',key)['hunt'],0)
            finally:
                agent.close()

    def test_confirmed_passive_kill_rewards_hunt_without_xp(self):
        previous={'floor':8,'x':100,'y':100,'experience':20,'health':100,'max_health':150,
                  'hunt_kills':0}
        current=dict(previous,hunt_kills=1,executed_action='none')

        self.assertGreater(LearningAgent._reward(previous,current,previous_action='hunt'),0)
        self.assertEqual(LearningAgent._reward(previous,current,previous_action='move'),0)

    def test_confirmed_kill_updates_q_value_for_hunt_even_if_actor_priority_sent_it(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db')
            try:
                world=World(position=Position(100,100,8),stats=Stats(150,150,400,20,1))
                first=LearningObservation.from_world('A',world,'hunt',0,hunt_kills=0)
                killed=LearningObservation.from_world('A',world,'hunt',0,
                    executed_action='none',hunt_kills=1)
                with patch('tools.autonomous_players.learning_bridge.Policy.choose',return_value='hunt'):
                    agent.handle(first)
                    agent.handle(killed)

                key=LearningAgent.policy_key(first.state)
                self.assertGreater(agent.store.values('A',key)['hunt'],0)
            finally:
                agent.close()

    def test_move_returning_to_sampled_position_is_not_penalized_if_steps_were_observed(self):
        previous={'floor':8,'x':100,'y':100,'experience':20,'health':100,'max_health':150,
                  'move_count':12}
        current=dict(previous,executed_action='move',move_count=14)

        self.assertEqual(LearningAgent._reward(previous,current),0)

    def test_move_counter_reset_does_not_fall_back_to_false_stall_penalty(self):
        previous={'floor':8,'x':100,'y':100,'experience':20,'health':100,'max_health':150,
                  'move_count':120}
        current=dict(previous,executed_action='move',move_count=1)

        self.assertEqual(LearningAgent._reward(previous,current),0)

    def test_successful_move_does_not_receive_the_failed_move_penalty(self):
        previous={'floor':8,'x':100,'y':100,'experience':20,'health':100,'max_health':150}
        current=dict(previous,x=101,executed_action='move')
        self.assertEqual(LearningAgent._reward(previous,current),0)

    def test_food_acquisition_rewards_a_real_observed_inventory_change(self):
        previous={'floor':8,'x':100,'y':100,'experience':20,'health':100,'max_health':150,
                  'food_available':False}
        current=dict(previous,food_available=True)
        self.assertGreater(LearningAgent._reward(previous,current),0)

    def test_successful_healing_rewards_observed_health_recovery(self):
        previous={'floor':8,'x':100,'y':100,'experience':20,'health':50,'max_health':150}
        current=dict(previous,health=80)
        self.assertGreater(LearningAgent._reward(previous,current),0)

    def test_food_consumption_is_not_a_negative_reward(self):
        previous={'floor':8,'x':100,'y':100,'experience':20,'health':100,'max_health':150,
                  'food_available':True}
        current=dict(previous,food_available=False)
        self.assertEqual(LearningAgent._reward(previous,current),0)

    def test_food_receipt_reward_reaches_the_character_policy(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db')
            try:
                start=World(position=Position(100,100,8),stats=Stats(100,150,400,20,1))
                fed=World(position=Position(100,100,8),stats=Stats(100,150,400,20,1))
                first=LearningObservation.from_world('A',start,'hunt',0,food_available=False)
                second=LearningObservation.from_world('A',fed,'hunt',0,executed_action='hunt',food_available=True)
                with patch('tools.autonomous_players.learning_bridge.Policy.choose',return_value='hunt'):
                    agent.handle(first)
                    agent.handle(second)
                state=LearningAgent.policy_key(first.state)
                self.assertGreater(agent.store.values('A',state)['hunt'],0)
            finally:
                agent.close()

    def test_untrained_agent_does_not_choose_wait_without_a_reason(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            agent = LearningAgent(Path(d) / 'learning.db')
            world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
            def choose_wait_if_offered(policy, state, allowed_actions):
                return 'wait' if 'wait' in allowed_actions else allowed_actions[0]
            try:
                with patch('tools.autonomous_players.learning_bridge.Policy.choose',
                           choose_wait_if_offered):
                    intent = agent.handle(LearningObservation.from_world('A', world, 'roam', 0))
                self.assertNotEqual(intent.kind, 'wait')
            finally:
                agent.close()

    def test_q_update_ignores_retreat_value_when_hunt_state_disallows_it(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db')
            world=World(position=Position(100,100,8),stats=Stats(100,150,400,20,1))
            first=LearningObservation.from_world('A',world,'hunt',0,
                retreat_required=False,prey_available=True)
            second=LearningObservation.from_world('A',world,'hunt',0,
                executed_action='hunt',retreat_required=False,prey_available=True)
            state=LearningAgent.policy_key(first.state)
            try:
                agent.store.set_value('A',state,'retreat',50.0)
                with patch('tools.autonomous_players.learning_bridge.Policy.choose',return_value='hunt'):
                    agent.handle(first)
                    agent.handle(second)

                self.assertEqual(agent.store.values('A',state)['hunt'],0.0)
            finally:
                agent.close()

    def test_wounded_surface_agent_can_choose_food_hunt_instead_of_forced_retreat(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db')
            world=World(position=Position(100,100,7),stats=Stats(50,100,400,0,1))
            observation=LearningObservation.from_world('A',world,'hunt',0,
                food_available=False,retreat_required=False)
            try:
                with patch('tools.autonomous_players.learning_bridge.Policy.choose',return_value='hunt') as choose:
                    intent=agent.handle(observation)
                self.assertEqual(intent.kind,'hunt')
                self.assertEqual(choose.call_args.args[1],('hunt','move'))
            finally:
                agent.close()

    def test_wounded_agent_with_actual_retreat_requirement_keeps_safety_override(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db')
            world=World(position=Position(100,100,8),stats=Stats(50,100,400,0,1))
            observation=LearningObservation.from_world('A',world,'retreat',0,retreat_required=True)
            try:
                with patch('tools.autonomous_players.learning_bridge.Policy.choose') as choose:
                    intent=agent.handle(observation)
                self.assertEqual(intent.kind,'retreat')
                choose.assert_not_called()
            finally:
                agent.close()

    def test_stream_reader_reassembles_fragmented_json_line(self):
        class Fragmented:
            def __init__(self):
                self.parts = [b'{"schema":1,', b'"type":"intent"}\n']
            def recv(self, size):
                return self.parts.pop(0) if self.parts else b''
        self.assertEqual(recv_line(Fragmented()), b'{"schema":1,"type":"intent"}\n')

    def test_stale_socket_falls_back_without_an_intent(self):
        with tempfile.TemporaryDirectory() as d:
            bridge = LearningBridge(Path(d) / 'missing.sock')
            world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
            self.assertIsNone(bridge.publish(LearningObservation.from_world('A', world, 'hunt', 0)))
            self.assertIsNone(bridge.poll_intent(999))

    def test_bridge_rejects_intent_for_a_different_character(self):
        import json
        import time
        from unittest.mock import patch

        class SocketReply:
            def __init__(self, response):
                self.response = response
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def settimeout(self, _):
                pass
            def connect(self, _):
                pass
            def sendall(self, _):
                pass
            def recv(self, _):
                response, self.response = self.response, b''
                return response

        response = (json.dumps({'schema': 1, 'type': 'intent', 'agent': 'Sim B',
                                'kind': 'hunt', 'payload': {'source': 'learner'},
                                'issued_at': time.time(), 'ttl': 2}) + '\n').encode()
        world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
        observation = LearningObservation.from_world('Sim A', world, 'hunt', 0)
        bridge = LearningBridge('unused.sock')
        with patch('tools.autonomous_players.learning_bridge.socket.AF_UNIX', 1, create=True), \
             patch('tools.autonomous_players.learning_bridge.socket.socket',
                   return_value=SocketReply(response)):
            self.assertIsNone(bridge.publish(observation))
        self.assertIsNone(bridge.poll_intent())

    def test_failed_publish_clears_an_unpolled_previous_intent(self):
        import json
        import time
        from unittest.mock import patch

        class SocketReply:
            def __init__(self, response):
                self.response = response
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def settimeout(self, _):
                pass
            def connect(self, _):
                pass
            def sendall(self, _):
                pass
            def recv(self, _):
                response, self.response = self.response, b''
                return response

        def intent(agent, kind):
            return (json.dumps({'schema': 1, 'type': 'intent', 'agent': agent,
                                'kind': kind, 'payload': {'source': 'learner'},
                                'issued_at': time.time(), 'ttl': 2}) + '\n').encode()

        world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
        observation = LearningObservation.from_world('Sim A', world, 'hunt', 0)
        bridge = LearningBridge('unused.sock')
        with patch('tools.autonomous_players.learning_bridge.socket.AF_UNIX', 1, create=True), \
             patch('tools.autonomous_players.learning_bridge.socket.socket',
                   side_effect=[SocketReply(intent('Sim A', 'move')),
                                SocketReply(intent('Sim B', 'hunt'))]):
            self.assertIsNotNone(bridge.publish(observation))
            self.assertIsNone(bridge.publish(observation))
        self.assertIsNone(bridge.poll_intent())

    def test_shadow_agent_records_decision_but_emits_no_intent(self):
        with tempfile.TemporaryDirectory() as d:
            agent = LearningAgent(Path(d) / 'learning.db', shadow=True)
            world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
            observation = LearningObservation.from_world('A', world, 'hunt', 0)
            self.assertIsNone(agent.handle(observation))
            self.assertEqual(agent.store.summary('A')['transitions'], 0)
            agent.close()

    def test_active_agent_keeps_character_policies_independent(self):
        with tempfile.TemporaryDirectory() as d:
            agent = LearningAgent(Path(d) / 'learning.db')
            try:
                healthy = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
                wounded = World(position=Position(1, 1, 8), stats=Stats(50, 150, 400, 0, 1))
                self.assertIn(agent.handle(LearningObservation.from_world('A', healthy, 'hunt', 0)).kind, ('hunt', 'move'))
                self.assertEqual(agent.handle(LearningObservation.from_world('B', wounded, 'retreat', 0)).kind, 'retreat')
            finally:
                agent.close()

    def test_floor_transition_records_positive_observed_reward(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            agent = LearningAgent(Path(d) / 'learning.db')
            try:
                first = World(position=Position(1, 1, 7), stats=Stats(150, 150, 400, 0, 1))
                second = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
                agent.handle(LearningObservation.from_world('A', first, 'hunt', 0))
                agent.handle(LearningObservation.from_world('A', second, 'hunt', 0))
                reward = agent.store.db.execute('SELECT reward FROM transitions WHERE agent=?', ('A',)).fetchone()[0]
                self.assertEqual(reward, 1.0)
            finally:
                agent.close()

    def test_wrong_way_floor_transition_updates_hunt_policy_negatively(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db')
            try:
                upper=World(position=Position(1,1,8),stats=Stats(150,150,400,0,1))
                lower=World(position=Position(1,1,7),stats=Stats(150,150,400,0,1))
                first=LearningObservation.from_world('A',upper,'hunt',0)
                second=LearningObservation.from_world('A',lower,'hunt',0,executed_action='hunt')
                with patch('tools.autonomous_players.learning_bridge.Policy.choose',return_value='hunt'):
                    agent.handle(first)
                    agent.handle(second)

                state=LearningAgent.policy_key(first.state)
                self.assertLess(agent.store.values('A',state)['hunt'],0)
                reward=agent.store.db.execute(
                    'SELECT reward FROM transitions WHERE agent=? ORDER BY id DESC LIMIT 1',('A',)).fetchone()[0]
                self.assertEqual(reward,-1.0)
            finally:
                agent.close()

    def test_floor_transition_reward_follows_goal_direction(self):
        from tools.autonomous_players.learning_bridge import LearningAgent
        cases = [
            ({'floor': 8, 'goal': 'hunt'}, {'floor': 9}, 1.0),
            ({'floor': 8, 'goal': 'retreat'}, {'floor': 7}, 1.0),
            ({'floor': 8, 'goal': 'hunt'}, {'floor': 7}, -1.0),
            ({'floor': 8, 'goal': 'retreat'}, {'floor': 9}, -1.0),
        ]
        for previous, current, expected in cases:
            with self.subTest(previous=previous, current=current):
                self.assertEqual(LearningAgent._reward(previous, current), expected)

    def test_wrong_way_floor_transition_is_negative_learning_evidence(self):
        from tools.autonomous_players.learning_bridge import LearningAgent
        previous={'floor':8,'goal':'hunt','experience':20,'health':100,'max_health':150}
        current=dict(previous,floor=7)

        self.assertLess(LearningAgent._reward(previous,current),0)

    def test_restart_discards_unmatched_pre_restart_transition(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'learning.db'
            first = LearningAgent(path)
            start = World(position=Position(1, 1, 7), stats=Stats(150, 150, 400, 0, 1))
            first.handle(LearningObservation.from_world('A', start, 'hunt', 0))
            first.close()
            second = LearningAgent(path)
            try:
                next_world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 50, 1))
                intent = second.handle(LearningObservation.from_world(
                    'A', next_world, 'hunt', 0, transition_id=428, executed_action='move'))
                self.assertEqual(second.store.summary('A')['transitions'], 0)
                self.assertFalse(second.graph.can_use(
                    'A', Position(1, 1, 7), Position(1, 1, 8), 3, transition_id=428))

                after_intent = World(position=Position(2, 1, 8), stats=Stats(150, 150, 400, 50, 1))
                second.handle(LearningObservation.from_world(
                    'A', after_intent, 'hunt', 0, executed_action=intent.kind))
                self.assertEqual(second.store.summary('A')['transitions'], 1)
            finally:
                second.close()

    def test_reconnect_does_not_train_across_game_sessions(self):
        with tempfile.TemporaryDirectory() as d:
            agent=LearningAgent(Path(d)/'learning.db')
            try:
                start=World(position=Position(1,1,7),stats=Stats(150,150,400,0,1))
                first=LearningObservation.from_world('A',start,'hunt',0,session_id='session-1')
                first_intent=agent.handle(first)

                reconnected=World(position=Position(1,1,8),stats=Stats(150,150,400,50,1))
                second=LearningObservation.from_world('A',reconnected,'hunt',0,
                    executed_action=first_intent.kind,session_id='session-2')
                second_intent=agent.handle(second)

                self.assertEqual(agent.store.summary('A')['transitions'],0)

                later=World(position=Position(2,1,8),stats=Stats(150,150,400,50,1))
                third=LearningObservation.from_world('A',later,'hunt',0,
                    executed_action=second_intent.kind,session_id='session-2')
                agent.handle(third)
                self.assertEqual(agent.store.summary('A')['transitions'],1)
            finally:
                agent.close()

    def test_observed_floor_transition_updates_learned_region_graph(self):
        with tempfile.TemporaryDirectory() as d:
            agent = LearningAgent(Path(d) / 'learning.db')
            try:
                first = World(position=Position(1, 1, 7), stats=Stats(150, 150, 400, 0, 1))
                second = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
                agent.handle(LearningObservation.from_world('A', first, 'hunt', 0))
                agent.handle(LearningObservation.from_world('A', second, 'hunt', 0, transition_id=1947))
                self.assertTrue(agent.graph.can_use('A', Position(1, 1, 7), Position(1, 1, 8), 3))
            finally:
                agent.close()

    def test_async_publish_does_not_block_event_loop(self):
        async def run():
            with tempfile.TemporaryDirectory() as d:
                bridge = LearningBridge(Path(d) / 'missing.sock')
                world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
                return await bridge.publish_async(LearningObservation.from_world('A', world, 'hunt', 0))
        self.assertIsNone(asyncio.run(run()))

    def test_corrupt_checkpoint_is_quarantined_by_learner(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'learning.db'
            first = LearningAgent(path)
            first.store.checkpoint('A', {'previous_state': '{"floor":7,"x":1,"y":1}', 'previous_action': 'hunt', 'updated_at': 1})
            first.store.db.execute("UPDATE checkpoints SET payload='broken' WHERE agent='A'")
            first.store.db.commit()
            first.close()
            second = LearningAgent(path)
            try:
                world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
                second.handle(LearningObservation.from_world('A', world, 'hunt', 0))
                self.assertTrue((path.parent / 'learning.db.A.corrupt').exists())
            finally:
                second.close()

    def test_floor_change_without_observed_stair_is_not_learned(self):
        with tempfile.TemporaryDirectory() as d:
            agent = LearningAgent(Path(d) / 'learning.db')
            try:
                first = World(position=Position(1, 1, 7), stats=Stats(150, 150, 400, 0, 1))
                second = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
                agent.handle(LearningObservation.from_world('A', first, 'hunt', 0))
                agent.handle(LearningObservation.from_world('A', second, 'hunt', 0))
                self.assertFalse(agent.graph.can_use('A', Position(1, 1, 7), Position(1, 1, 8), 3))
            finally:
                agent.close()

    def test_xp_gain_without_floor_change_does_not_create_stair_edge(self):
        with tempfile.TemporaryDirectory() as d:
            agent = LearningAgent(Path(d) / 'learning.db')
            try:
                first = World(position=Position(1, 1, 7), stats=Stats(150, 150, 400, 0, 1))
                second = World(position=Position(1, 1, 7), stats=Stats(150, 150, 400, 100, 1))
                agent.handle(LearningObservation.from_world('A', first, 'hunt', 0))
                agent.handle(LearningObservation.from_world('A', second, 'hunt', 0, transition_id=1947))
                self.assertFalse(agent.graph.can_use('A', Position(1, 1, 7), Position(1, 1, 7), 3))
            finally:
                agent.close()

    def test_observations_do_not_append_unbounded_checkpoints(self):
        with tempfile.TemporaryDirectory() as d:
            agent = LearningAgent(Path(d) / 'learning.db')
            try:
                for _ in range(6):
                    world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
                    agent.handle(LearningObservation.from_world('A', world, 'hunt', 0))
                count = agent.store.summary('A')['checkpoints']
                self.assertLessEqual(count, 2)
            finally:
                agent.close()

    def test_persisted_policy_value_can_select_a_safe_movement_action(self):
        import json
        with tempfile.TemporaryDirectory() as d:
            agent = LearningAgent(Path(d) / 'learning.db')
            try:
                world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
                observation = LearningObservation.from_world('A', world, 'hunt', 0)
                state = json.dumps(observation.state, sort_keys=True, separators=(',', ':'))
                agent.store.set_value('A', state, 'move', 10.0)
                self.assertEqual(agent.handle(observation).kind, 'move')
            finally:
                agent.close()

    def test_real_xp_rewards_learning_and_unconfirmed_action_is_not_used(self):
        with tempfile.TemporaryDirectory() as d:
            agent = LearningAgent(Path(d) / 'learning.db')
            try:
                first = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
                second = World(position=Position(1, 1, 8), stats=Stats(140, 150, 400, 100, 1))
                agent.handle(LearningObservation.from_world('A', first, 'hunt', 0, executed_action='reactive'))
                agent.handle(LearningObservation.from_world('A', second, 'hunt', 0, executed_action='hunt'))
                reward = agent.store.db.execute('SELECT reward FROM transitions WHERE agent=?', ('A',)).fetchone()[0]
                self.assertGreater(reward, 0)
                outcome = agent.store.db.execute('SELECT outcome FROM transitions WHERE agent=?', ('A',)).fetchone()[0]
                self.assertIn('"executed_action":"hunt"', outcome)
            finally:
                agent.close()


if __name__ == '__main__':
    unittest.main()
