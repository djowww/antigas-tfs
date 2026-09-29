import ast
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPTS = (
    "deploy/deploy-ground-rarity-scroll-fix.py",
    "deploy/deploy-ground-rarity-v46.py",
    "deploy/deploy-loot-v45.py",
    "deploy/deploy-rarity-container-v47.py",
    "deploy/deploy-rarity-v44.py",
)
ATOMIC_DEPLOY_SCRIPTS = (
    ("deploy/deploy-rarity-v44.py", "atomic", ".v44-new"),
    ("deploy/deploy-loot-v45.py", "atomic", ".v45-new"),
    ("deploy/deploy-ground-rarity-v46.py", "atomic", ".v46-new"),
    ("deploy/deploy-rarity-container-v47.py", "atomic_copy", ".v47-new"),
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

    def test_atomic_deploy_helpers_replace_from_source_and_preserve_contents(self):
        for relative, function_name, _ in ATOMIC_DEPLOY_SCRIPTS:
            with self.subTest(script=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                destination_dir = root / "destination"
                destination_dir.mkdir()
                source = root / "staged-file"
                target = destination_dir / "release-file"
                source.write_bytes(b"new verified release contents")
                target.write_bytes(b"old contents")
                namespace = runpy.run_path(str(ROOT / relative), run_name="deployment_atomic_test")

                # These deployment utilities target Linux. Mock ownership/mode syscalls
                # unavailable on Windows while still exercising copy, fsync and replace.
                with patch.object(os, "fchown", return_value=None, create=True), patch.object(
                    os, "fchmod", return_value=None, create=True
                ):
                    namespace[function_name](source, target, uid=123, gid=456, mode=0o640)

                self.assertEqual(target.read_bytes(), source.read_bytes())
                self.assertEqual(sorted(path.name for path in destination_dir.iterdir()), ["release-file"])

    def test_atomic_deploy_helpers_flush_before_fsync(self):
        for relative, function_name, _ in ATOMIC_DEPLOY_SCRIPTS:
            with self.subTest(script=relative):
                tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"), filename=relative)
                function = next(
                    node for node in tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == function_name
                )
                flush_line = next(
                    node.lineno for node in ast.walk(function)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "flush"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "output"
                )
                fsync_line = next(
                    node.lineno for node in ast.walk(function)
                    if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "fsync"
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "os"
                )
                self.assertLess(flush_line, fsync_line)

    def test_atomic_deploy_helpers_do_not_follow_preplanted_temp_symlinks(self):
        for relative, function_name, legacy_suffix in ATOMIC_DEPLOY_SCRIPTS:
            with self.subTest(script=relative), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                destination_dir = root / "destination"
                destination_dir.mkdir()
                source = root / "staged-file"
                target = destination_dir / "release-file"
                victim = root / "outside-victim"
                legacy_temp = destination_dir / (target.name + legacy_suffix)
                source.write_bytes(b"new verified release contents")
                target.write_bytes(b"old contents")
                victim.write_bytes(b"do not overwrite")
                try:
                    os.symlink(victim, legacy_temp)
                except (NotImplementedError, OSError):
                    # Windows may deny symlink creation without Developer Mode. A
                    # hardlink still proves that the old predictable path is ignored.
                    if legacy_temp.exists() or legacy_temp.is_symlink():
                        legacy_temp.unlink()
                    try:
                        os.link(victim, legacy_temp)
                    except OSError as error:
                        self.skipTest(f"Cannot create a symlink/hardlink regression fixture: {error}")

                namespace = runpy.run_path(str(ROOT / relative), run_name="deployment_atomic_test")
                with patch.object(os, "fchown", return_value=None, create=True), patch.object(
                    os, "fchmod", return_value=None, create=True
                ):
                    namespace[function_name](source, target, uid=123, gid=456, mode=0o640)

                self.assertEqual(victim.read_bytes(), b"do not overwrite")
                self.assertEqual(target.read_bytes(), source.read_bytes())
                self.assertEqual(legacy_temp.read_bytes(), b"do not overwrite")


if __name__ == "__main__":
    unittest.main()
