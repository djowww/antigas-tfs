import ast
from pathlib import Path
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]


class ValidationPreconditionTests(unittest.TestCase):
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
