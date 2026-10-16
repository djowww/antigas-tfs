import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RELEASE_VERSION = 76


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

    def test_homepage_leads_with_coin_restoration_release_news(self):
        home = (ROOT / "deploy/site-public/index.php").read_text(encoding="utf-8")
        title = "Antigas Coins return in client v75"

        self.assertIn('href="#coins-v75"', home)
        self.assertIn('id="coins-v75"', home)
        self.assertLess(home.index('href="#coins-v75"'), home.index('href="#client-v72"'))
        self.assertIn(title, home)
        self.assertIn("Client v75 restores the classic Antigas Coin item and its artwork, keeping its ID.", home)
        self.assertIn("Antigas Coins are back in the Store and Market for in-game trades.", home)
        self.assertIn("After manual payment approval, collect website Coins through the Market.", home)

    def test_coin_restoration_release_news_is_translated(self):
        translations = (ROOT / "deploy/site-public/i18n-extra.php").read_text(encoding="utf-8")
        for translation in (
            "Antigas Coins retornam no cliente v75",
            "Las Antigas Coins vuelven en el cliente v75",
            "Antigas Coins wracają w kliencie v75",
            "O cliente v75 restaura o item clássico Antigas Coin e sua arte, preservando seu ID.",
            "El cliente v75 restaura el objeto clásico Antigas Coin y su arte, conservando su ID.",
            "Klient v75 przywraca klasyczny przedmiot Antigas Coin i jego grafikę, zachowując jego ID.",
        ):
            with self.subTest(translation=translation):
                self.assertIn(translation, translations)


if __name__ == "__main__":
    unittest.main()
