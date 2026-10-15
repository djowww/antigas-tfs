import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicReadmeTests(unittest.TestCase):
    def test_banner_is_valid_scalable_svg_with_readable_alt_text(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        banner = ROOT / "docs/assets/antigas-74-banner.svg"
        self.assertTrue(banner.is_file())
        root = ET.parse(banner).getroot()
        self.assertTrue(root.attrib.get("viewBox"))
        self.assertRegex(
            readme,
            r"!\[([^\]]*Antigas 7\.4[^\]]*)\]\(docs/assets/antigas-74-banner\.svg\)",
        )

    def test_readme_has_player_and_contributor_paths_and_public_boundary(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        required = (
            "https://tibia74.tech/",
            "https://tibia74.tech/#criar-conta",
            "https://tibia74.tech/#download",
            "https://tibia74.tech/wiki.php",
            "docs/building.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
            "cliente completo",
            "serviços privados",
            "pacotes de atualização",
            "SHA-256",
        )
        for link_or_phrase in required:
            with self.subTest(link_or_phrase=link_or_phrase):
                self.assertIn(link_or_phrase, readme)
        self.assertRegex(readme, r"\[!\[Compilação e testes\].*security-build\.yml")
        self.assertRegex(readme, r"\[!\[CodeQL\].*codeql\.yml")
        self.assertNotIn("cliente oficial assinado", readme)


if __name__ == "__main__":
    unittest.main()
