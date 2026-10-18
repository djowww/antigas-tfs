import unittest
from tools.autonomous_players.learning_protocol import decode_message, encode_message


class LearningAgentCodecContractTests(unittest.TestCase):
    def test_intent_message_uses_only_safe_high_level_fields(self):
        message = {'schema': 1, 'type': 'intent', 'agent': 'A', 'kind': 'hunt',
                   'payload': {'reason': 'healthy'}, 'issued_at': 1.0, 'ttl': 2.0}
        decoded = decode_message(encode_message(message))
        self.assertEqual(decoded['kind'], 'hunt')
        self.assertNotIn('packet', decoded)


if __name__ == '__main__':
    unittest.main()
