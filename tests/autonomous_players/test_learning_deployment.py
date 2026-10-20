import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class LearningDeploymentTests(unittest.TestCase):
    def test_unit_is_isolated_and_not_tied_to_game_service(self):
        unit = (ROOT / 'deploy/autonomous-learning/autonomous-learning-agent.service').read_text()
        self.assertIn('CPUQuota=10%', unit)
        self.assertIn('MemoryMax=128M', unit)
        self.assertIn('--neural-mode shadow', unit)
        self.assertIn('KillSignal=SIGINT', unit)
        self.assertIn('RestrictAddressFamilies=AF_UNIX', unit)
        self.assertIn('IPAddressDeny=any', unit)
        self.assertNotIn('antigas74.service', unit)

    def test_removal_script_has_dry_run_and_allowlist(self):
        script = (ROOT / 'deploy/autonomous-learning/remove-learning-agent.sh').read_text()
        self.assertIn('--dry-run', script)
        self.assertIn('--apply', script)
        self.assertIn('learning-agent.service', script)
        self.assertNotIn('learning_bridge.py', script)
        self.assertNotIn('learning_protocol.py', script)
        self.assertNotIn('learning_store.py', script)
        self.assertNotIn('/var/lib/autonomous-players/state.db', script)
        self.assertNotIn('mysql', script.lower())

    def test_removing_learner_preserves_persisted_learning_database(self):
        script = (ROOT / 'deploy/autonomous-learning/remove-learning-agent.sh').read_text()
        self.assertIn('/var/lib/autonomous-learning/learning.db', script)
        self.assertIn('/var/lib/autonomous-learning/learning.neural.json', script)
        self.assertNotIn('rm -rf /var/lib/autonomous-learning', script)
        self.assertIn('preserve', script.lower())

    def test_removal_aborts_when_service_state_cannot_be_verified(self):
        script = (ROOT / 'deploy/autonomous-learning/remove-learning-agent.sh').read_text()
        self.assertIn('unit_state=$(systemctl is-active "$unit" 2>/dev/null || true)', script)
        self.assertIn('inactive|failed)', script)
        self.assertIn('cannot verify', script.lower())
        self.assertLess(script.index('case "$unit_state"'), script.index('rm -f /etc/systemd'))


if __name__ == '__main__':
    unittest.main()
