import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = 75


class CoinPublicReleaseTests(unittest.TestCase):
    def test_official_download_references_match_signed_release_version(self):
        manifest = json.loads((ROOT / "deploy/site-public/client-release.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["version"], RELEASE_VERSION)
        self.assertEqual(manifest["name"], f"Antigas 7.4 v{RELEASE_VERSION}")
        self.assertEqual(manifest["package"], f"Antigas-7.4-Update-v{RELEASE_VERSION}.zip")

        home = (ROOT / "deploy/site-public/index.php").read_text(encoding="utf-8")
        wiki = (ROOT / "deploy/site-public/wiki.php").read_text(encoding="utf-8")
        self.assertRegex(home, rf"Antigas-7\.4-Launcher-v{RELEASE_VERSION}\.zip\?site=[^'\"]*v{RELEASE_VERSION}")
        self.assertEqual(
            len(re.findall(rf"Antigas-7\.4-Launcher-v{RELEASE_VERSION}\.zip\?site=[^'\"]*v{RELEASE_VERSION}", wiki)),
            2,
        )

    def test_client_source_snapshot_metadata_matches_release(self):
        init = (ROOT / "deploy/client-current/init.lua").read_text(encoding="utf-8")
        marker = (ROOT / "deploy/client-current/client.version").read_text(encoding="utf-8").strip()
        readme = (ROOT / "deploy/client-current/LEIA-ME.txt").read_text(encoding="utf-8")
        match = re.search(r"(?m)^APP_VERSION\s*=\s*(\d+)\b", init)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), RELEASE_VERSION)
        self.assertEqual(marker, str(RELEASE_VERSION))
        self.assertIn(f"CLIENTE v{RELEASE_VERSION}", readme)


if __name__ == "__main__":
    unittest.main()
