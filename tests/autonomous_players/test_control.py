import random
import tempfile
import unittest
from pathlib import Path

from tools.autonomous_players.learning import Policy
from tools.autonomous_players.store import Store
from tools.autonomous_players.supervisor import HealthSample, Supervisor


class LearningTests(unittest.TestCase):
    def test_real_update_mask_and_resume(self):
        with tempfile.TemporaryDirectory() as directory:
            with Store(Path(directory) / 'state.db') as store:
                policy = Policy(store, 'Sim One', random.Random(7), epsilon=0)
                self.assertEqual(policy.choose('safe', ['explore']), 'explore')
                policy.update('safe', 'hunt', 10, 'safe', ['hunt', 'explore'], terminal=True)
                self.assertEqual(policy.choose('safe', ['hunt', 'explore']), 'hunt')
                self.assertEqual(policy.choose('safe', ['retreat']), 'retreat')
                self.assertGreater(store.values('Sim One', 'safe')['hunt'], 0)
                store.checkpoint('Sim One', {'experience': 4, 'intent': 'hunt'})
            with Store(Path(directory) / 'state.db') as store:
                self.assertEqual(store.restore('Sim One')['experience'], 4)
                self.assertEqual(Policy(store, 'Sim One', random.Random(7), epsilon=0).choose('safe', ['explore', 'hunt']), 'hunt')

    def test_no_allowed_action_and_nonfinite_rewards(self):
        with tempfile.TemporaryDirectory() as directory, Store(Path(directory) / 's.db') as store:
            policy = Policy(store, 'x', random.Random(0))
            with self.assertRaises(ValueError):
                policy.choose('s', [])
            with self.assertRaises(ValueError):
                policy.update('s', 'hunt', float('nan'), 's', ['hunt'])

    def test_corrupt_checkpoint_version_rejected(self):
        with tempfile.TemporaryDirectory() as directory, Store(Path(directory) / 's.db') as store:
            store.checkpoint('x', {'level': 1})
            store.db.execute('UPDATE checkpoints SET version=999')
            with self.assertRaises(ValueError):
                store.restore('x')


def sample(now, **kwargs):
    return HealthSample(now=now, measured_at=now, memory_mib=1024, cpu_percent=20,
                        latency_ms=50, server_pid=123, **kwargs)


class SupervisorTests(unittest.TestCase):
    def test_baseline_ramp_and_no_unmeasured_admission(self):
        guard = Supervisor()
        self.assertEqual(guard.observe(sample(0)).target, 0)
        self.assertEqual(guard.observe(sample(299)).target, 0)
        self.assertEqual(guard.observe(sample(300)).target, 1)
        self.assertEqual(guard.observe(sample(900), functional=True).target, 5)
        self.assertEqual(guard.observe(sample(1500), functional=False).target, 5)
        self.assertEqual(guard.observe(sample(1501), functional=True).target, 10)
        self.assertEqual(guard.observe(sample(2101), functional=True).target, 25)
        self.assertEqual(guard.observe(sample(2701), functional=True).target, 25)
        self.assertEqual(guard.observe(sample(3301), functional=True).target, 50)

    def test_stale_critical_restart_and_persisted_latch(self):
        for changes in ({'memory_mib': 383}, {'measured_at': -121}, {'sql_age_seconds': 2.01},
                        {'oom': True}, {'latency_ms': 1001}, {'server_pid': 124}, {'counter_anomaly': True}):
            guard = Supervisor()
            guard.observe(sample(0))
            guard.observe(sample(300))
            params = dict(now=301, measured_at=301, memory_mib=1024, cpu_percent=20,
                          latency_ms=50, server_pid=123)
            params.update(changes)
            decision = guard.observe(HealthSample(**params))
            self.assertEqual(decision.target, 0, changes)
            self.assertTrue(decision.suspended)
            restored = Supervisor(guard.snapshot())
            self.assertEqual(restored.observe(sample(302)).target, 0)

    def test_memory_and_cpu_duration_and_admission_boundary(self):
        for metric, value, seconds in [('memory_mib', 511, 30), ('cpu_percent', 86, 60)]:
            guard = Supervisor()
            guard.observe(sample(0))
            guard.observe(sample(300))
            params = dict(now=301, measured_at=301, memory_mib=1024, cpu_percent=20,
                          latency_ms=50, server_pid=123)
            params[metric] = value
            self.assertEqual(guard.observe(HealthSample(**params)).target, 1)
            params.update(now=301+seconds, measured_at=301+seconds)
            self.assertEqual(guard.observe(HealthSample(**params)).target, 0)
        guard = Supervisor()
        guard.observe(sample(0))
        self.assertEqual(guard.observe(HealthSample(300, 300, 767, 20, 50, 123)).target, 0)
        self.assertEqual(guard.observe(HealthSample(301, 301, 768, 20, 50, 123)).target, 1)

    def test_recovery_requires_continuous_health(self):
        guard = Supervisor()
        guard.observe(sample(0))
        guard.observe(HealthSample(1, 1, 300, 20, 50, 123))
        self.assertEqual(guard.observe(sample(2)).target, 0)
        self.assertEqual(guard.observe(sample(301)).target, 0)
        self.assertEqual(guard.observe(sample(302)).target, 1)


if __name__ == '__main__':
    unittest.main()
