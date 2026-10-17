import unittest
from tools.autonomous_players.app import validate_config, functional_population, admission_available, occupancy_ids


class AppTests(unittest.TestCase):
    def test_requires_explicit_target_and_maximum_twenty(self):
        config = dict(identity='test-world',public_authorized=True,max_players=20,host='127.0.0.1',game_port=7186,
                      manifest='private.json',state_dir='state',health_file='health.json',items='items.srv',modulus='1')
        self.assertEqual(validate_config(config)['max_players'],20)
        for changed in ({'max_players':21},{'public_authorized':False},{'identity':''}):
            with self.assertRaises(ValueError):
                validate_config(dict(config,**changed))

    def test_progress_and_sql_online_required_for_ramp(self):
        own = {1:dict(online=True,moves=10,xp_gain=5,last_progress_at=100,last_xp_at=100),
               2:dict(online=True,moves=10,xp_gain=0,last_progress_at=100,last_xp_at=100)}
        sql = dict(players=[[1,1,5,150,0,100,100,7,1],[2,1,0,150,0,101,100,7,1]])
        self.assertFalse(functional_population(own,sql,2,now=101))
        own[2]['xp_gain']=5
        self.assertTrue(functional_population(own,sql,2,now=101))
        self.assertFalse(functional_population(own,sql,2,now=1000))
        sql['players'][1][-1]=0
        self.assertFalse(functional_population(own,sql,2,now=101))

    def test_draining_sessions_still_consume_capacity(self):
        self.assertFalse(admission_available(0,1,1))
        self.assertFalse(admission_available(10,20,20))
        self.assertTrue(admission_available(0,0,1))

    def test_disconnected_player_waits_for_fresh_sql_offline_confirmation(self):
        self.assertEqual(occupancy_ids(set(),{1:101},[[1,1]],100),{1})
        self.assertEqual(occupancy_ids(set(),{1:101},[[1,0]],100),{1})
        self.assertEqual(occupancy_ids(set(),{1:101},[[1,0]],102),set())
        self.assertEqual(occupancy_ids({2},{1:101},[[1,1],[2,1]],102),{1,2})

    def test_combat_priority_does_not_advance_npc_dialogue(self):
        from tools.autonomous_players.app import choose_actions
        class Agent:
            def priority(self,now):return True
            def step(self,now):return [b'\xa1']
        class Progression:
            def step(self,now):raise AssertionError('urgent combat must precede NPC state transition')
        self.assertEqual(choose_actions(Agent(),Progression(),1),[b'\xa1'])
