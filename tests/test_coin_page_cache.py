import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CoinPageCacheTests(unittest.TestCase):
    def test_checkout_routes_are_private_and_never_expose_payment_secrets(self):
        source = (ROOT / "deploy" / "site-public" / "coins.php").read_text(encoding="utf-8")

        web_start = source.index("webStart();")
        i18n_start = source.index("i18n.php")
        cache_headers = [
            "header('Cache-Control: private, no-store, max-age=0');",
            "header('Pragma: no-cache');",
            "header('Expires: 0');",
        ]
        for header in cache_headers:
            self.assertIn(header, source[web_start:i18n_start])

        self.assertNotIn("Antigas Coins are unavailable. This item was retired from the test environment.", source)
        for producer in ("webDb(", "pixOrder(", "pixQr(", "pixQuote("):
            self.assertIn(producer, source, "Active checkout must use the existing private helper API")
        self.assertRegex(source, r"\$coinPackages\s*=\s*\[\s*10\s*,\s*50\s*,\s*100\s*,\s*250\s*,\s*500\s*,\s*1000\s*,\s*2500\s*,\s*5000\s*,\s*10000\s*\]")
        self.assertIn("coin_order_nonce", source)
        self.assertIn("hash_equals", source)
        self.assertIn("webLimit('pix:", source)
        self.assertIn("webLimit('pix-ip:", source)
        self.assertIn("o.account_id=?", source, "Order and QR lookups must be account-scoped")
        self.assertNotIn("PIX_KEY", source)
        self.assertNotIn("pixKey", source)
        self.assertTrue((ROOT / "tests" / "coin-page-tests.php").is_file())
