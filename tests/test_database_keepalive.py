"""Check that both game database connections get a bounded idle heartbeat."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class DatabaseKeepaliveRegistration(unittest.TestCase):
    def test_idle_connections_have_a_periodic_event(self):
        events = ET.parse(ROOT / 'data/globalevents/globalevents.xml').getroot()
        matches = [e for e in events if e.get('name') == 'DatabaseKeepalive']
        self.assertEqual(len(matches), 1, 'Database connections must not expire during an empty world')
        self.assertEqual(matches[0].get('script'), 'database_keepalive.lua')
        self.assertEqual(int(matches[0].get('interval')), 60000)


if __name__ == '__main__':
    unittest.main()
