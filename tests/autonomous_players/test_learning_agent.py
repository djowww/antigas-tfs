import unittest
import tempfile
from pathlib import Path
from tools.autonomous_players.learning_protocol import decode_message, encode_message
from tools.autonomous_players.learning_bridge import LearningAgent
from tools.autonomous_players.learning_protocol import LearningObservation
from tools.autonomous_players.world import Position, Stats, World


class LearningAgentCodecContractTests(unittest.TestCase):
    def test_intent_message_uses_only_safe_high_level_fields(self):
        message = {'schema': 1, 'type': 'intent', 'agent': 'A', 'kind': 'hunt',
                   'payload': {'reason': 'healthy'}, 'issued_at': 1.0, 'ttl': 2.0}
        decoded = decode_message(encode_message(message))
        self.assertEqual(decoded['kind'], 'hunt')
        self.assertNotIn('packet', decoded)

    def test_status_is_written_without_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            status = Path(d) / 'status.json'
            agent = LearningAgent(Path(d) / 'learning.db', status_path=status)
            try:
                world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
                agent.handle(LearningObservation.from_world('A', world, 'hunt', 0))
                text = status.read_text()
                self.assertIn('A', text)
                self.assertNotIn('password', text.lower())
            finally:
                agent.close()


if __name__ == '__main__':
    unittest.main()
