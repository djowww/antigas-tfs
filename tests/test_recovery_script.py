import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "systemd" / "staging-maintenance-recovery.sh"


def shell_executable():
    shell = shutil.which("sh")
    if shell:
        return shell
    if os.name == "nt":
        candidate = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git" / "usr" / "bin" / "sh.exe"
        if candidate.is_file():
            return str(candidate)
    return None


class RecoveryScriptTests(unittest.TestCase):
    def run_with_fake_systemctl(self, fail_first=False):
        shell = shell_executable()
        if not shell:
            self.skipTest("POSIX shell is not installed")
        with tempfile.TemporaryDirectory(prefix="antigas-recovery-test-") as directory:
            temp = Path(directory)
            log = temp / "calls.txt"
            fake = temp / ("systemctl.exe" if os.name == "nt" else "systemctl")
            fake.write_text(
                "#!/bin/sh\n"
                'echo "$*" >> "$STUB_LOG"\n'
                + ('[ "$1" = stop ] && exit 7\n' if fail_first else "")
                + "exit 0\n",
                encoding="utf-8",
            )
            if os.name != "nt":
                fake.chmod(0o755)
            env = os.environ.copy()
            env["PATH"] = directory + os.pathsep + env.get("PATH", "")
            env["STUB_LOG"] = str(log)
            result = subprocess.run([shell, str(SCRIPT)], cwd=ROOT, env=env, capture_output=True, text=True, timeout=15)
            calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
            return result, calls

    def test_recovery_attempts_all_steps_after_first_step_fails(self):
        result, calls = self.run_with_fake_systemctl(fail_first=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, [
            "stop imperium772-staging",
            "set-property --runtime imperium772-staging MemoryMax=1G",
            "start imperium772",
        ])

    def test_successful_recovery_runs_all_steps(self):
        result, calls = self.run_with_fake_systemctl()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(calls), 3)
        self.assertTrue(calls[-1].startswith("start imperium772"))


if __name__ == "__main__":
    unittest.main()