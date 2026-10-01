import subprocess
import unittest
from pathlib import Path
from unittest.mock import Mock

from staging_recovery import RECOVERY_COMMANDS, record_recovery, recover_staging


class StagingRecoveryTests(unittest.TestCase):
    def test_success_requires_all_commands_and_expected_final_states(self):
        run = Mock(return_value=subprocess.CompletedProcess([], 0))
        show = Mock(side_effect=["active\n", "inactive\n"])

        result = recover_staging(run, show)

        self.assertTrue(result["recovery_ok"])
        self.assertEqual(result["recovery_codes"], [0, 0, 0])
        self.assertEqual(run.call_count, 3)
        self.assertEqual(show.call_count, 2)

    def test_every_recovery_step_is_attempted_after_nonzero_exit(self):
        for failed_step in range(len(RECOVERY_COMMANDS)):
            with self.subTest(failed_step=failed_step):
                outcomes = [subprocess.CompletedProcess([], 0) for _ in RECOVERY_COMMANDS]
                outcomes[failed_step] = subprocess.CompletedProcess([], 7)
                run = Mock(side_effect=outcomes)
                show = Mock(side_effect=["active", "inactive"])

                result = recover_staging(run, show)

                expected_codes = [0, 0, 0]
                expected_codes[failed_step] = 7
                self.assertFalse(result["recovery_ok"])
                self.assertEqual(result["recovery_codes"], expected_codes)
                self.assertEqual(run.call_count, len(RECOVERY_COMMANDS))

    def test_command_exception_is_recorded_and_remaining_steps_run(self):
        run = Mock(side_effect=[
            subprocess.TimeoutExpired("systemctl stop", 55),
            subprocess.CompletedProcess([], 0),
            subprocess.CompletedProcess([], 0),
        ])
        show = Mock(side_effect=["active", "inactive"])

        result = recover_staging(run, show)

        self.assertFalse(result["recovery_ok"])
        self.assertEqual(result["recovery_codes"], [-1, 0, 0])
        self.assertEqual(run.call_count, len(RECOVERY_COMMANDS))

    def test_unexpected_final_states_fail_recovery(self):
        run = Mock(return_value=subprocess.CompletedProcess([], 0))
        show = Mock(side_effect=["inactive", "active"])

        result = recover_staging(run, show)

        self.assertFalse(result["recovery_ok"])
        self.assertEqual(result["production"], "inactive")
        self.assertEqual(result["staging"], "active")

    def test_state_query_failure_fails_recovery(self):
        run = Mock(return_value=subprocess.CompletedProcess([], 0))
        show = Mock(side_effect=[OSError("systemctl unavailable"), "inactive"])

        result = recover_staging(run, show)

        self.assertFalse(result["recovery_ok"])
        self.assertEqual(result["production"], "unknown")

    def test_recording_failed_recovery_downgrades_a_passed_report(self):
        report = {"status": "passed"}
        recovery = {"recovery_ok": False, "production": "inactive", "staging": "inactive"}

        result = record_recovery(report, recovery, ended=123.0)

        self.assertFalse(result)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(report["production"], "inactive")
        self.assertEqual(report["ended"], 123.0)

    def test_recording_success_preserves_passed_report(self):
        report = {"status": "passed"}
        recovery = {"recovery_ok": True, "production": "active", "staging": "inactive"}

        result = record_recovery(report, recovery, recovery=[0, 0, 0])

        self.assertTrue(result)
        self.assertEqual(report["status"], "passed")
        self.assertEqual(report["recovery"], [0, 0, 0])

    def test_legacy_runner_checks_staging_guard_before_stopping_production(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "tests" / "staging-maintenance.py").read_text(encoding="utf-8")
        self.assertLess(source.index("require_staging_target()"), source.index("run('systemctl', 'stop', 'imperium772')"))

    def test_both_runners_validate_staging_service_isolation_before_stopping_production(self):
        root = Path(__file__).resolve().parents[1]
        for filename in ("security-staging-run.py", "staging-maintenance.py"):
            with self.subTest(filename=filename):
                source = (root / "tests" / filename).read_text(encoding="utf-8")
                self.assertLess(source.index("require_isolated_staging_service(value)"),
                                source.index("systemctl', 'stop', 'imperium772"))

    def test_both_runners_write_recovery_report_before_nonzero_exit(self):
        root = Path(__file__).resolve().parents[1]
        for filename, report_write in (
            ("security-staging-run.py", "write_text(json.dumps(report, indent=2))"),
            ("staging-maintenance.py", "write_text(json.dumps(result, indent=2))"),
        ):
            with self.subTest(filename=filename):
                source = (root / "tests" / filename).read_text(encoding="utf-8")
                self.assertIn("record_recovery(", source)
                self.assertLess(source.index(report_write), source.index("if not recovery_ok:"))


if __name__ == "__main__":
    unittest.main()
