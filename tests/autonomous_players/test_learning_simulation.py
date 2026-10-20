import tempfile
import unittest
from pathlib import Path
from tools.autonomous_learning_simulation import main, run_simulation


class LearningSimulationTests(unittest.TestCase):
    def test_neural_shadow_learns_from_twenty_realistic_offline_agents(self):
        with tempfile.TemporaryDirectory() as d:
            result=run_simulation(Path(d)/'learning.db',agents=20,steps=60,
                                  seed=17,prey_name='Cave Rat',neural_mode='shadow')
            self.assertEqual(result['sewer_entries'],20)
            self.assertEqual(result['rats_killed'],20)
            self.assertEqual(result['xp_gain'],200)
            self.assertEqual(result['food_received'],20)
            self.assertGreater(result['neural_updates'],0)
            self.assertTrue((Path(d)/'learning.neural.json').exists())

    def test_twenty_agents_really_descend_hunt_and_collect_food_in_closed_world(self):
        with tempfile.TemporaryDirectory() as d:
            result = run_simulation(Path(d) / 'learning.db', agents=20, steps=40, seed=7)
            self.assertEqual(result['agents'], 20)
            self.assertEqual(result['sewer_entries'], 20)
            self.assertEqual(result['rats_killed'], 20)
            self.assertEqual(result['xp_gain'], 100)
            self.assertEqual(result['food_received'], 20)
            self.assertEqual(len(result['agents_detail']),20)
            self.assertTrue(all(agent['sewer_entries']==1 and agent['rats_killed']==1 and
                                agent['xp_gain']==5 and agent['food_received']==1
                                for agent in result['agents_detail']))
            self.assertEqual(result['food_eaten'],20)
            self.assertEqual(sum(agent['food_eaten'] for agent in result['agents_detail']),20)
            self.assertTrue(all(agent['food_eaten']==1 for agent in result['agents_detail']))
            self.assertLessEqual(result['steps_run'],20*40)
            self.assertTrue(all(agent['steps_run']<40 for agent in result['agents_detail']))
            self.assertEqual(result['learned_agents'],20)
            self.assertTrue(result['checkpoint_reloaded'])

    def test_twenty_agents_loot_rat_food_when_another_corpse_already_uses_container_one(self):
        with tempfile.TemporaryDirectory() as d:
            result = run_simulation(Path(d) / 'learning.db', agents=20, steps=40, seed=13,
                                    unrelated_open_corpse=True)
            self.assertEqual(result['rats_killed'],20)
            self.assertEqual(result['xp_gain'],100)
            self.assertEqual(result['food_received'],20)
            self.assertEqual(result['food_eaten'],20)
            self.assertEqual(result['unowned_food_uses'],0)
            self.assertTrue(all(agent['rats_killed']==1 and agent['food_received']==1 and
                                agent['food_eaten']==1 for agent in result['agents_detail']))

    def test_twenty_agents_hunt_cave_rats_and_receive_real_definition_xp_and_food(self):
        with tempfile.TemporaryDirectory() as d:
            for seed in (17,41,73):
                with self.subTest(seed=seed):
                    result = run_simulation(Path(d) / f'learning-{seed}.db', agents=20, steps=60,
                                            seed=seed,prey_name='Cave Rat')
                    self.assertEqual(result['sewer_entries'],20)
                    self.assertEqual(result['rats_killed'],20)
                    self.assertEqual(result['xp_gain'],200)
                    self.assertEqual(result['food_received'],20)
                    self.assertEqual(result['food_eaten'],20)
                    self.assertTrue(all(agent['xp_gain']==10 and agent['rats_killed']==1 and
                                        agent['food_received']==1 and agent['food_eaten']==1
                                        for agent in result['agents_detail']))

    def test_command_line_can_select_cave_rat_fixture(self):
        import contextlib
        import io
        import json
        with tempfile.TemporaryDirectory() as d,contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['--agents','1','--duration','60','--seed','29',
                                   '--state',str(Path(d)/'learning.db'),
                                   '--prey-name','Cave Rat']),0)
        result=json.loads(output.getvalue())
        self.assertEqual(result['prey_name'],'Cave Rat')
        self.assertEqual(result['prey_experience'],10)
        self.assertEqual(result['rats_killed'],1)
        self.assertEqual(result['xp_gain'],10)

    def test_simulation_never_uses_a_production_endpoint(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            with patch('socket.socket',side_effect=AssertionError('simulation must stay offline')):
                result = run_simulation(Path(d) / 'learning.db', agents=2, steps=5, seed=1)
            self.assertEqual(result['network_connections'], 0)
            self.assertLess(result['max_events'], 1000)


if __name__ == '__main__':
    unittest.main()
