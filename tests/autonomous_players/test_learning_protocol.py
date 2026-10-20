import unittest
from tools.autonomous_players.learning_protocol import (
    LearningIntent, LearningObservation, decode_message, encode_message,
)
from tools.autonomous_players.world import Creature, Position, Stats, World


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
        self.assertEqual(value['state']['route_confidence'], 0.75)

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

    def test_executed_action_is_optional_and_bounded(self):
        world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 0, 1))
        obs = LearningObservation.from_world('A', world, 'hunt', 0, executed_action='move')
        self.assertEqual(obs.state['executed_action'], 'move')

    def test_movement_count_is_observed_and_validated(self):
        world=World(position=Position(1,1,8),stats=Stats(150,150,400,0,1))
        self.assertEqual(LearningObservation.from_world(
            'A',world,'hunt',0,move_count=12).state['move_count'],12)
        for invalid in (-1,1.5,True):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                LearningObservation.from_world('A',world,'hunt',0,move_count=invalid)

    def test_confirmed_hunt_kill_count_is_observed_and_validated(self):
        world=World(position=Position(1,1,8),stats=Stats(150,150,400,0,1))
        self.assertEqual(LearningObservation.from_world(
            'A',world,'hunt',0,hunt_kills=3).state['hunt_kills'],3)
        for invalid in (-1,1.5,True):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                LearningObservation.from_world('A',world,'hunt',0,hunt_kills=invalid)

    def test_retreat_requirement_is_observed_and_strictly_boolean(self):
        world=World(position=Position(1,1,8),stats=Stats(150,150,400,0,1))
        self.assertTrue(LearningObservation.from_world(
            'A',world,'retreat',0,retreat_required=True).state['retreat_required'])
        for invalid in (0,1,'yes'):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                LearningObservation.from_world('A',world,'hunt',0,retreat_required=invalid)

    def test_prey_availability_is_observed_and_strictly_boolean(self):
        world=World(position=Position(1,1,8),stats=Stats(150,150,400,0,1))
        observation=LearningObservation.from_world('A',world,'hunt',0,
            prey_available=True,food_prey_available=False)
        self.assertTrue(observation.state['prey_available'])
        self.assertFalse(observation.state['food_prey_available'])
        for key in ('prey_available','food_prey_available'):
            for invalid in (0,1,'yes'):
                with self.subTest(key=key,invalid=invalid),self.assertRaises(ValueError):
                    LearningObservation.from_world('A',world,'hunt',0,**{key:invalid})

    def test_passive_food_prey_are_not_counted_as_nearby_threats(self):
        world=World(position=Position(100,100,7),stats=Stats(150,150,400,0,1))
        world.creatures[0x40000001]=Creature(0x40000001,'Rabbit',Position(101,100,7))
        world.creatures[0x40000002]=Creature(0x40000002,'Rat',Position(100,101,7))

        observation=LearningObservation.from_world('A',world,'hunt',0)

        self.assertEqual(observation.state['nearby_threats'],1)


if __name__ == '__main__':
    unittest.main()
