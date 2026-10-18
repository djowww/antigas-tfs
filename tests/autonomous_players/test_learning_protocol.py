import unittest
from tools.autonomous_players.learning_protocol import (
    LearningIntent, LearningObservation, decode_message, encode_message,
)
from tools.autonomous_players.world import Position, Stats, World


class LearningProtocolTests(unittest.TestCase):
    def test_observation_round_trips_abstract_world_facts(self):
        world = World(position=Position(10, 11, 8), stats=Stats(90, 150, 400, 5, 2))
        obs = LearningObservation.from_world('Sim Aster', world, 'hunt', 0.75)
        value = decode_message(encode_message(obs.to_message()))
        self.assertEqual(value['type'], 'observation')
        self.assertEqual(value['agent'], 'Sim Aster')
        self.assertEqual(value['state']['floor'], 8)
        self.assertEqual(value['state']['goal'], 'hunt')
        self.assertEqual(value['state']['experience'], 5)

    def test_unknown_schema_is_rejected(self):
        with self.assertRaises(ValueError):
            decode_message(b'{"schema":999,"type":"observation"}\n')

    def test_intent_expiry_is_enforced(self):
        intent = LearningIntent('Sim Aster', 'wait', {}, 10.0, 2.0)
        self.assertFalse(intent.expired(11.9))
        self.assertTrue(intent.expired(12.0))

    def test_message_size_is_bounded(self):
        with self.assertRaises(ValueError):
            encode_message({'schema': 1, 'type': 'observation', 'payload': 'x' * 40000})

    def test_transition_id_is_optional_and_explicit(self):
        world = World(position=Position(10, 11, 8), stats=Stats(90, 150, 400, 5, 2))
        obs = LearningObservation.from_world('A', world, 'hunt', 0, transition_id=1947)
        self.assertEqual(obs.state['transition_id'], 1947)


if __name__ == '__main__':
    unittest.main()
