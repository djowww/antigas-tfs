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


if __name__ == '__main__':
    unittest.main()
