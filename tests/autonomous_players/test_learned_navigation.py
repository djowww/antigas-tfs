import unittest
from tools.autonomous_players.learned_navigation import Curriculum, RegionGraph
from tools.autonomous_players.world import Position, Stats, World


class LearnedNavigationTests(unittest.TestCase):
    def test_floor_edge_requires_observed_transition_and_can_be_reused(self):
        graph = RegionGraph()
        self.assertFalse(graph.observe_transition('A', Position(1, 1, 7), Position(1, 1, 8), 1947, 1))
        graph.record_stair_observation('A', Position(1, 1, 7), 1947, Position(1, 1, 8))
        self.assertTrue(graph.observe_transition('A', Position(1, 1, 7), Position(1, 1, 8), 1947, 2))
        self.assertTrue(graph.can_use('A', Position(1, 1, 7), Position(1, 1, 8), 3))

    def test_blocked_edge_cools_down_and_alternate_goal_is_selected(self):
        graph = RegionGraph()
        bad = Position(3, 3, 8)
        good = Position(4, 4, 8)
        graph.record_failure('A', Position(1, 1, 8), bad, 'blocked', 10)
        self.assertNotEqual(graph.next_goal('A', Position(1, 1, 8), (bad, good), 11), bad)
        self.assertEqual(graph.next_goal('A', Position(1, 1, 8), (bad, good), 200), bad)

    def test_curriculum_requires_health_food_and_retreat(self):
        curriculum = Curriculum()
        world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 5, 2))
        self.assertFalse(curriculum.ready_for('A', 'cave', world, has_food=False, has_retreat=True))
        self.assertTrue(curriculum.ready_for('A', 'cave', world, has_food=True, has_retreat=True))
        wounded = World(position=Position(1, 1, 8), stats=Stats(50, 150, 400, 5, 2))
        self.assertFalse(curriculum.ready_for('A', 'cave', wounded, has_food=True, has_retreat=True))


if __name__ == '__main__':
    unittest.main()
