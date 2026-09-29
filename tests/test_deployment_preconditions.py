import ast
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPTS = (
    "deploy/deploy-ground-rarity-scroll-fix.py",
    "deploy/deploy-ground-rarity-v46.py",
    "deploy/deploy-loot-v45.py",
    "deploy/deploy-rarity-container-v47.py",
    "deploy/deploy-rarity-v44.py",
)
OPTIMIZED_CHECK = r'''
import runpy
import sys

module = runpy.run_path(sys.argv[1])
try:
    module["require"](False, "sentinel precondition failure")
except RuntimeError as error:
    if str(error) != "sentinel precondition failure":
        raise SystemExit(2)
else:
    raise SystemExit(3)
'''


class DeploymentPreconditionTests(unittest.TestCase):
    def test_production_deploy_scripts_do_not_use_optimizable_asserts(self):
        for relative in DEPLOY_SCRIPTS:
            path = ROOT / relative
            with self.subTest(script=relative):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
                self.assertFalse(
                    any(isinstance(node, ast.Assert) for node in ast.walk(tree)),
                    f"{relative} contains an assert that Python -O can remove",
                )

    def test_require_rejects_failed_preconditions_under_python_optimization(self):
        for relative in DEPLOY_SCRIPTS:
            path = ROOT / relative
            with self.subTest(script=relative):
                result = subprocess.run(
                    [sys.executable, "-O", "-c", OPTIMIZED_CHECK, str(path)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_assert_using_validation_scripts_refuse_optimized_python(self):
        harness = "import runpy, sys; runpy.run_path(sys.argv[1])"
        for path in sorted((ROOT / "tests").glob("*.py")):
            if path.name.startswith("test_"):
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if not any(isinstance(node, ast.Assert) for node in ast.walk(tree)):
                continue
            with self.subTest(script=path.name):
                result = subprocess.run(
                    [sys.executable, "-O", "-c", harness, str(path)],
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    timeout=15,
                )
                self.assertNotEqual(result.returncode, 0, "Optimized validation script was allowed to start")
                self.assertIn(
                    "Python optimization (-O) disables validation assertions",
                    result.stdout + result.stderr,
                )


if __name__ == "__main__":
    unittest.main()
