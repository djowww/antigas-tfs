import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class LearningDeploymentTests(unittest.TestCase):
    def test_unit_is_isolated_and_not_tied_to_game_service(self):
        unit = (ROOT / 'deploy/autonomous-learning/autonomous-learning-agent.service').read_text()
        self.assertIn('CPUQuota=10%', unit)
        self.assertIn('MemoryMax=128M', unit)
        self.assertIn('RestrictAddressFamilies=AF_UNIX', unit)
        self.assertIn('IPAddressDeny=any', unit)
        self.assertNotIn('antigas74.service', unit)

    def test_removal_script_has_dry_run_and_allowlist(self):
        script = (ROOT / 'deploy/autonomous-learning/remove-learning-agent.sh').read_text()
        self.assertIn('--dry-run', script)
        self.assertIn('--apply', script)
        self.assertIn('learning-agent.service', script)
        self.assertNotIn('/var/lib/autonomous-players/state.db', script)
        self.assertNotIn('mysql', script.lower())


if __name__ == '__main__':
    unittest.main()
