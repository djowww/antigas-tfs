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
