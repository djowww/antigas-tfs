import unittest
from dataclasses import replace
from tools.autonomous_players.supervisor import Supervisor, HealthSample


class DirectAdmissionTests(unittest.TestCase):
    def sample(self, now=0, **changes):
        return replace(HealthSample(now,now,1024,100,10,123),**changes)

    def test_explicit_ten_bypasses_cpu_and_tier_wait_only(self):
        guard=Supervisor(immediate_target=10)
        for t in range(0,125,5):
            self.assertEqual(guard.observe(self.sample(t)).target,10)

    def test_critical_and_delayed_non_cpu_failures_still_suspend(self):
        for changed in ({'memory_mib':300},{'oom':True},{'sql_age_seconds':3},
                        {'latency_ms':1100},{'counter_anomaly':True}):
            guard=Supervisor(immediate_target=10)
            self.assertTrue(guard.observe(self.sample(**changed)).suspended)
        guard=Supervisor(immediate_target=10)
        guard.observe(self.sample())
        for t in range(5,40,5):
            result=guard.observe(self.sample(t,memory_mib=500))
        self.assertEqual(result.target,0)
        self.assertTrue(result.suspended)

    def test_insufficient_admission_memory_cannot_start_ten(self):
        self.assertEqual(Supervisor(immediate_target=10).observe(self.sample(memory_mib=700)).target,0)

    def test_cpu_latch_can_recover_but_other_failure_cannot_be_cleared(self):
        for reason,expected in [('cpu',10),('SQL delay',0),('client protocol fault',0)]:
            guard=Supervisor(immediate_target=10)
            guard._suspend(reason)
            self.assertEqual(guard.observe(self.sample()).target,expected)

    def test_restart_rechecks_current_health_and_invalid_targets_rejected(self):
        saved=Supervisor().snapshot()
        self.assertEqual(Supervisor(saved,immediate_target=10).observe(self.sample()).target,10)
        failed=Supervisor()
        failed._suspend('client protocol fault')
        self.assertEqual(Supervisor(failed.snapshot(),immediate_target=10).observe(self.sample()).target,0)
        for target in (1,21,True,'10'):
            with self.assertRaises(ValueError):Supervisor(immediate_target=target)

    def test_config_requires_matching_ten_cap(self):
        from tools.autonomous_players.app import validate_config
        config=dict(identity='qa',public_authorized=True,max_players=10,host='127.0.0.1',game_port=7186,
                    manifest='private',state_dir='state',health_file='health',items='items',modulus='1',immediate_target=10)
        self.assertEqual(validate_config(config)['immediate_target'],10)
        for changed in ({'max_players':20},{'immediate_target':True},{'immediate_target':20}):
            with self.assertRaises(ValueError):validate_config(dict(config,**changed))

    def test_explicit_twenty_and_matching_cap(self):
        from tools.autonomous_players.app import validate_config
        guard=Supervisor(immediate_target=20)
        for t in range(0,125,5):
            self.assertEqual(guard.observe(self.sample(t)).target,20)
        config=dict(identity='qa',public_authorized=True,max_players=20,host='127.0.0.1',game_port=7186,
                    manifest='private',state_dir='state',health_file='health',items='items',modulus='1',immediate_target=20)
        self.assertEqual(validate_config(config)['immediate_target'],20)
        self.assertEqual(guard.observe(self.sample(125,memory_mib=300)).target,0)
