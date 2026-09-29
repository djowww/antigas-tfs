import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CoinPageCacheTests(unittest.TestCase):
    def test_authenticated_order_and_pix_responses_are_not_cacheable(self):
        source = (ROOT / "deploy" / "site-public" / "coins.php").read_text(encoding="utf-8")

        web_start = source.index("webStart();")
        i18n_start = source.index("require __DIR__.'/i18n.php';")
        cache_headers = [
            "header('Cache-Control: private, no-store, max-age=0');",
            "header('Pragma: no-cache');",
            "header('Expires: 0');",
        ]
        for header in cache_headers:
            self.assertIn(header, source[web_start:i18n_start])

        qr_route = source.split("if(isset($_GET['qr']))", 1)[1].split("\n            }", 1)[0]
        self.assertIn("$png=pixQr($selected['payload'])", qr_route)
        self.assertIn("echo $png", qr_route)
