from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate-retired-items.py"


class RetiredItemGeneratorTests(unittest.TestCase):
    def run_generator(self, manifest, output, check=False):
        args = [sys.executable, str(GENERATOR), "--manifest", str(manifest), "--output", str(output)]
        if check:
            args.append("--check")
        return subprocess.run(args, text=True, capture_output=True)

    def test_generated_ids_preserve_sorted_numeric_identity(self):
        with tempfile.TemporaryDirectory() as scratch:
            manifest = Path(scratch) / "items.json"
            output = Path(scratch) / "ids.h"
            manifest.write_text(json.dumps({"ids": [{"id": 3157}, {"id": 2775}, {"id": 5364}]}), encoding="utf-8")
            result = self.run_generator(manifest, output)
            self.assertEqual(result.returncode, 0, result.stderr)
            header = output.read_text(encoding="utf-8")
            self.assertIn("2775, 3157, 5364", header)
            self.assertEqual(self.run_generator(manifest, output, check=True).returncode, 0)
            manifest.write_text(json.dumps({"ids": [{"id": 2775}, {"id": 5364}]}), encoding="utf-8")
            self.assertNotEqual(self.run_generator(manifest, output, check=True).returncode, 0,
                                "stale generated IDs must fail the check")

    def test_duplicate_or_invalid_ids_fail_without_overwriting_header(self):
        for ids in ([2775, 2775], [0], [65536], [True], ["3157"]):
            with self.subTest(ids=ids), tempfile.TemporaryDirectory() as scratch:
                manifest = Path(scratch) / "items.json"
                output = Path(scratch) / "ids.h"
                manifest.write_text(json.dumps({"ids": [{"id": item_id} for item_id in ids]}), encoding="utf-8")
                output.write_text("preserved", encoding="utf-8")
                result = self.run_generator(manifest, output)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(output.read_text(encoding="utf-8"), "preserved")


if __name__ == "__main__":
    unittest.main()
