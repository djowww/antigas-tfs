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
