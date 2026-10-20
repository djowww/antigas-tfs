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

    def test_repeated_route_failures_increase_cooldown_with_a_cap(self):
        graph=RegionGraph(cooldown=10)
        source,target=Position(1,1,8),Position(4,4,8)
        graph.record_failure('A',source,target,'blocked',0)
        self.assertTrue(graph.is_blocked('A',source,target,9))
        self.assertFalse(graph.is_blocked('A',source,target,10))

        graph.record_failure('A',source,target,'blocked',11)
        self.assertTrue(graph.is_blocked('A',source,target,30))
        self.assertFalse(graph.is_blocked('A',source,target,31))

        graph.record_failure('A',source,target,'blocked',32)
        self.assertTrue(graph.is_blocked('A',source,target,71))
        self.assertFalse(graph.is_blocked('A',source,target,72))

        for attempt in range(4,20):
            at=72+attempt
            graph.record_failure('A',source,target,'blocked',at)
            edge=next(edge for key,edge in graph._edges.items() if key[0]=='A')
            self.assertLessEqual(edge.cooldown_until-at,graph.MAX_FAILURE_COOLDOWN)

    def test_observed_success_resets_failure_backoff_for_same_route(self):
        graph=RegionGraph(cooldown=10)
        source,destination=Position(1,1,7),Position(1,1,8)
        graph.record_failure('A',source,destination,'blocked',0)
        graph.record_failure('A',source,destination,'blocked',11)
        graph.record_stair_observation('A',source,1947,destination)

        self.assertTrue(graph.observe_transition('A',source,destination,1947,22))
        self.assertTrue(all(edge.failures==0 for edge in graph._edges.values()))
        graph.record_failure('A',source,destination,'blocked',30)

        self.assertTrue(graph.is_blocked('A',source,destination,39))
        self.assertFalse(graph.is_blocked('A',source,destination,40))

    def test_navigation_memory_survives_restart_with_remaining_cooldown(self):
        source=Position(1,1,8)
        verified=Position(2,1,7)
        blocked=Position(1,2,8)
        graph=RegionGraph(cooldown=120)
        graph.record_stair_observation('A',source,428,verified)
        self.assertTrue(graph.observe_transition('A',source,verified,428,1))
        graph.record_failure('A',source,blocked,'blocked',10)

        snapshot=graph.snapshot('A',now=20)
        restored=RegionGraph(cooldown=120)
        restored.restore('A',snapshot,now=100)

        self.assertTrue(restored.can_use('A',source,verified,100,428))
        self.assertTrue(restored.is_blocked('A',source,blocked,209))
        self.assertFalse(restored.is_blocked('A',source,blocked,210))

    def test_route_failure_history_is_bounded_per_agent(self):
        graph = RegionGraph()
        target=Position(60000,60000,8)
        for index in range(2049):
            graph.record_failure('A',Position(index,0,8),target,'blocked',index)
        self.assertEqual(len(graph._edges),2048)
        self.assertNotIn(('A',Position(0,0,8),target,-1),graph._edges)
        self.assertIn(('A',Position(2048,0,8),target,-1),graph._edges)

    def test_unconfirmed_stair_candidates_are_bounded_per_agent(self):
        graph = RegionGraph()
        for index in range(257):
            graph.record_stair_observation('A',Position(index,0,7),1947,Position(index,0,8))
        self.assertEqual(len(graph._candidates),256)
        self.assertNotIn(('A',Position(0,0,7),1947),graph._candidates)
        self.assertIn(('A',Position(256,0,7),1947),graph._candidates)

    def test_curriculum_requires_health_food_and_retreat(self):
        curriculum = Curriculum()
        world = World(position=Position(1, 1, 8), stats=Stats(150, 150, 400, 5, 2))
        self.assertFalse(curriculum.ready_for('A', 'cave', world, has_food=False, has_retreat=True))
        self.assertTrue(curriculum.ready_for('A', 'cave', world, has_food=True, has_retreat=True))
        wounded = World(position=Position(1, 1, 8), stats=Stats(50, 150, 400, 5, 2))
        self.assertFalse(curriculum.ready_for('A', 'cave', wounded, has_food=True, has_retreat=True))

    def test_curriculum_bounds_long_running_outcome_history(self):
        curriculum = Curriculum()
        for index in range(300):
            curriculum.record('A', {'floor': index})
        self.assertEqual(len(curriculum._outcomes['A']), 128)
        self.assertEqual(curriculum._outcomes['A'][0], {'floor': 172})
        self.assertEqual(curriculum._outcomes['A'][-1], {'floor': 299})


if __name__ == '__main__':
    unittest.main()
