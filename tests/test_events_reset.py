"""Keep all event identifiers covered by the reset, including unused declarations."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class EventResetTests(unittest.TestCase):
    def test_every_event_id_is_reset(self):
        header = (ROOT / 'src/events.h').read_text()
        source = (ROOT / 'src/events.cpp').read_text()
        fields = set(re.findall(r'int32_t\s+(\w+)\s*;', header))
        body = source.split('void Events::clear()', 1)[1].split('bool Events::load()', 1)[0]
        resets = set(re.findall(r'(\w+)\s*=\s*-1\s*;', body))
        self.assertGreater(len(fields), 15)
        self.assertEqual(fields, resets)


if __name__ == '__main__':
    unittest.main()
