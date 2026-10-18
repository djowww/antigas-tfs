import unittest
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


class _IdleAgent:
    def priority(self, now):
        return False

    def step(self, now):
        return [b'agent']


class AppLearningTests(unittest.TestCase):
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

    def test_wait_intent_can_hold_when_progression_is_not_busy(self):
        from tools.autonomous_players.app import choose_actions_with_learning
        intent = LearningIntent('A', 'wait', {}, 1, 5)
        self.assertEqual(choose_actions_with_learning(_IdleAgent(), _Progression(), 2, intent), [])


if __name__ == '__main__':
    unittest.main()
