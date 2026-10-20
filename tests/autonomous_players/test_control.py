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

    def test_store_budgets_keys_and_agents(self):
        with tempfile.TemporaryDirectory() as directory, Store(Path(directory)/'s.db',max_agents=2,max_states=3) as store:
            store.set_value('a','s1','hunt',1)
            store.set_value('a','s2','hunt',2)
            store.set_value('a','s3','hunt',3)
            with self.assertRaises(ValueError):
                store.set_value('a','s4','hunt',4)
            with self.assertRaises(ValueError):
                store.set_value('a','x'*257,'hunt',4)
            store.checkpoint('a',{'level':1})
            store.checkpoint('b',{'level':1})
            with self.assertRaises(ValueError):
                store.checkpoint('c',{'level':1})
            self.assertEqual(store.restore('a'),{'level':1})


def sample(now, **kwargs):
    return HealthSample(now=now, measured_at=now, memory_mib=1024, cpu_percent=20,
                        latency_ms=50, server_pid=123, **kwargs)


class SupervisorTests(unittest.TestCase):
    def test_recent_complete_preflight_can_start_one_but_sparse_or_old_cannot(self):
        samples=[sample(t) for t in range(0,301,5)]
        guard=Supervisor.from_preflight(samples,sample(334))
        self.assertEqual(guard.state['target'],1)
        with self.assertRaises(ValueError):
            Supervisor.from_preflight([sample(0),sample(300)],sample(334))
        with self.assertRaises(ValueError):
            Supervisor.from_preflight(samples,sample(500))

    def advance(self, guard, start, end, functional=False):
        result = None
        for t in range(start, end+1, 5):
            result = guard.observe(sample(t),functional=functional)
        return result

    def test_baseline_ramp_and_no_unmeasured_admission(self):
        guard = Supervisor()
        self.assertEqual(guard.observe(sample(0)).target, 0)
        self.assertEqual(self.advance(guard,5,295).target,0)
        self.assertEqual(guard.observe(sample(300)).target,1)
        self.assertEqual(self.advance(guard,305,900,True).target,5)
        self.assertEqual(self.advance(guard,905,1500).target,5)
        self.assertEqual(guard.observe(sample(1505),functional=True).target,10)
        self.assertEqual(self.advance(guard,1510,2105,True).target,20)
        self.assertEqual(self.advance(guard,2110,3305,True).target,20)

    def test_sparse_observations_never_establish_health(self):
        guard = Supervisor()
        guard.observe(sample(0))
        self.assertEqual(guard.observe(sample(300)).target,0)
        restored = Supervisor(guard.snapshot())
        self.assertEqual(restored.observe(sample(2000),functional=True).target,0)

    def test_negative_metrics_rejected(self):
        for key,value in [('cpu_percent',-1),('cpu_percent',101),('sql_age_seconds',-1),('dispatcher_queued',-1)]:
            params = dict(now=0,measured_at=0,memory_mib=1024,cpu_percent=20,latency_ms=50,server_pid=123)
            params[key] = value
            self.assertTrue(Supervisor().observe(HealthSample(**params)).suspended)

    def test_stale_critical_restart_and_persisted_latch(self):
        for changes in ({'memory_mib': 383}, {'measured_at': -121}, {'sql_age_seconds': 2.01},
                        {'oom': True}, {'latency_ms': 1001}, {'server_pid': 124}, {'counter_anomaly': True}):
            guard = Supervisor()
            self.advance(guard,0,300)
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
            self.advance(guard,0,300)
            params = dict(now=301, measured_at=301, memory_mib=1024, cpu_percent=20,
                          latency_ms=50, server_pid=123)
            params[metric] = value
            self.assertEqual(guard.observe(HealthSample(**params)).target, 1)
            for t in range(306,302+seconds,5):
                params.update(now=t,measured_at=t)
                result = guard.observe(HealthSample(**params))
            self.assertEqual(result.target,0)
        guard = Supervisor()
        self.advance(guard,0,295)
        self.assertEqual(guard.observe(HealthSample(300, 300, 767, 20, 50, 123)).target, 0)
        self.assertEqual(guard.observe(HealthSample(301, 301, 1023, 20, 50, 123)).target, 0)
        self.assertEqual(self.advance(guard,306,601).target,0)
        self.assertEqual(guard.observe(sample(606)).target,1)

    def test_recovery_requires_continuous_health(self):
        guard = Supervisor()
        guard.observe(sample(0))
        guard.observe(HealthSample(1, 1, 300, 20, 50, 123))
        self.assertEqual(guard.observe(sample(2)).target, 0)
        self.assertEqual(self.advance(guard,7,297).target, 0)
        self.assertEqual(guard.observe(sample(302)).target, 1)


if __name__ == '__main__':
    unittest.main()
