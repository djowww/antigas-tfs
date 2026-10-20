import unittest
from tools.autonomous_players.health import parse_queue, parse_meminfo, cpu_usage


class HealthTests(unittest.TestCase):
    def test_uses_available_memory_and_normalized_cpu(self):
        self.assertEqual(parse_meminfo('MemFree: 100 kB\nMemAvailable: 786432 kB\n'),768)
        self.assertEqual(cpu_usage((10,0,10,80,0,0,0,0),(20,0,20,160,0,0,0,0)),20)
        with self.assertRaises(ValueError):
            parse_meminfo('MemFree: 100 kB')

    def test_queue_sections_are_not_confused(self):
        text = '[QueueMetrics] dispatcher queued=3 counter_anomaly=0; scheduler active_events=6 counter_anomaly=0; database queued=1 oldest_queued_age_ms=250 counter_anomaly=0'
        queue = parse_queue(text)
        self.assertEqual(queue['dispatcher_queued'],3)
        self.assertEqual(queue['sql_age_seconds'],.25)
        self.assertFalse(queue['counter_anomaly'])
        self.assertTrue(parse_queue(text.replace('active_events=6 counter_anomaly=0','active_events=6 counter_anomaly=1'))['counter_anomaly'])
        with self.assertRaises(ValueError):
            parse_queue('missing metrics')

    def test_queue_reading_skips_newer_login_messages(self):
        import json
        from tools.autonomous_players.health import latest_queue_entry
        metric = '[QueueMetrics] dispatcher queued=0 counter_anomaly=0; scheduler active_events=6 counter_anomaly=0; database queued=0 oldest_queued_age_ms=0 counter_anomaly=0'
        rows = [dict(__REALTIME_TIMESTAMP='100000000',MESSAGE=metric),dict(__REALTIME_TIMESTAMP='101000000',MESSAGE='Sim Aster has logged in.')]
        self.assertEqual(latest_queue_entry('\n'.join(map(json.dumps,rows)),102)['MESSAGE'],metric)
        with self.assertRaises(ValueError):
            latest_queue_entry('\n'.join(map(json.dumps,rows)),221)
        with self.assertRaises(ValueError):
            latest_queue_entry(json.dumps(rows[-1]),102)

    def test_command_failure_publishes_failed_lease_without_secret_arguments(self):
        import subprocess
        from tools.autonomous_players.health import collect_once
        class Broken:
            def sample(self):
                raise subprocess.CalledProcessError(1,['mysql','PRIVATE_ARGUMENT'])
        result=collect_once(Broken())
        self.assertEqual(result['error'],'CalledProcessError')
        self.assertNotIn('sample',result)
        self.assertNotIn('PRIVATE_ARGUMENT',str(result))

    def test_failed_sample_identifies_stage_without_echoing_arbitrary_messages(self):
        from tools.autonomous_players.health import collect_once
        class Broken:
            stage='cpu'
            def sample(self):raise ValueError('invalid CPU sample')
        result=collect_once(Broken())
        self.assertEqual(result['stage'],'cpu')
        self.assertEqual(result['detail'],'invalid CPU sample')

    def test_startup_cpu_measurement_has_a_real_interval(self):
        from unittest.mock import patch
        from tools.autonomous_players.health import Collector
        c=Collector.__new__(Collector)
        c.previous_cpu=(10,0,10,80,0,0,0,0);c.previous_cpu_at=10
        with patch('tools.autonomous_players.health.time.monotonic',side_effect=[10.05,11]), patch('tools.autonomous_players.health.time.sleep') as sleep, patch.object(c,'_cpu',return_value=(20,0,20,160,0,0,0,0)):
            self.assertEqual(c._cpu_percent(),20)
            self.assertAlmostEqual(sleep.call_args.args[0],.95)

    def test_queue_emitted_during_collection_is_not_mistaken_for_future_data(self):
        import json
        from unittest.mock import patch
        from tools.autonomous_players.health import Collector
        c=Collector.__new__(Collector)
        c.service='test.service';c.last_sql=1000;c.population={};c.oom_count=0;c.port=7173
        message='[QueueMetrics] dispatcher queued=0 counter_anomaly=0; scheduler active_events=6 counter_anomaly=0; database queued=0 oldest_queued_age_ms=0 counter_anomaly=0'
        entry=json.dumps(dict(__REALTIME_TIMESTAMP='1002500000',MESSAGE=message))
        with patch.object(c,'_cpu_percent',return_value=20),patch.object(c,'_oom',return_value=0),patch('tools.autonomous_players.health.time.time',side_effect=[1002,1003,1004]),patch('tools.autonomous_players.health.command',side_effect=['123',entry]),patch('tools.autonomous_players.health.Path.read_text',return_value='MemAvailable: 1048576 kB\n'),patch('tools.autonomous_players.health.status_latency',return_value=1):
            sample=c.sample()['sample']
        self.assertEqual(sample['now'],1004)
        self.assertEqual(sample['dispatcher_queued'],0)
