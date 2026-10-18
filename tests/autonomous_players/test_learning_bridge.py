import asyncio
import tempfile
import unittest
from pathlib import Path
from tools.autonomous_players.learning_bridge import LearningAgent, LearningBridge
from tools.autonomous_players.learning_protocol import LearningObservation
from tools.autonomous_players.world import Position, Stats, World


class LearningBridgeTests(unittest.TestCase):
    def test_stale_socket_falls_back_without_an_intent(self):
        with tempfile.TemporaryDirectory() as d:
            bridge = LearningBridge(Path(d) / 'missing.sock')
            world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
            self.assertIsNone(bridge.publish(LearningObservation.from_world('A', world, 'hunt', 0)))
            self.assertIsNone(bridge.poll_intent(999))

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
                self.assertEqual(agent.handle(LearningObservation.from_world('A', healthy, 'hunt', 0)).kind, 'hunt')
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

    def test_restart_restores_last_policy_context(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'learning.db'
            first = LearningAgent(path)
            world = World(position=Position(1, 1, 7), stats=Stats(150, 150, 400, 0, 1))
            first.handle(LearningObservation.from_world('A', world, 'hunt', 0))
            first.close()
            second = LearningAgent(path)
            try:
                next_world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
                second.handle(LearningObservation.from_world('A', next_world, 'hunt', 0))
                self.assertEqual(second.store.summary('A')['transitions'], 1)
            finally:
                second.close()

    def test_observed_floor_transition_updates_learned_region_graph(self):
        with tempfile.TemporaryDirectory() as d:
            agent = LearningAgent(Path(d) / 'learning.db')
            try:
                first = World(position=Position(1, 1, 7), stats=Stats(150, 150, 400, 0, 1))
                second = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
                agent.handle(LearningObservation.from_world('A', first, 'hunt', 0))
                agent.handle(LearningObservation.from_world('A', second, 'hunt', 0))
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


if __name__ == '__main__':
    unittest.main()
