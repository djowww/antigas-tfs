import tempfile
import unittest
from pathlib import Path
from tools.autonomous_learning_simulation import run_simulation


class LearningSimulationTests(unittest.TestCase):
    def test_twenty_agents_make_independent_observed_progress(self):
        with tempfile.TemporaryDirectory() as d:
            result = run_simulation(Path(d) / 'learning.db', agents=20, steps=40, seed=7)
            self.assertEqual(result['agents'], 20)
            self.assertEqual(result['floor_transitions'], 20)
            self.assertEqual(result['fixture_xp_observations'], 20)
            self.assertEqual(result['deaths_restored'], 0)
            self.assertTrue(result['checkpoint_reloaded'])

    def test_simulation_never_uses_a_production_endpoint(self):
        with tempfile.TemporaryDirectory() as d:
            result = run_simulation(Path(d) / 'learning.db', agents=2, steps=5, seed=1)
            self.assertEqual(result['network_connections'], 0)
            self.assertLess(result['max_events'], 1000)


if __name__ == '__main__':
    unittest.main()
