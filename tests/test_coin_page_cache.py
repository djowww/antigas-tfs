import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CoinPageCacheTests(unittest.TestCase):
    def test_retired_get_post_and_qr_routes_are_not_cacheable(self):
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

        self.assertIn("http_response_code(410);", source[web_start:i18n_start])
        for producer in ("webDb(", "pixOrder(", "pixQr(", "pixQuote("):
            self.assertNotIn(producer, source, "Retired page must not invoke a payment producer")
        for payment_control in ('<form', 'pix-code', 'pix-qr', 'PIX_KEY'):
            self.assertNotIn(payment_control, source)
        self.assertIn('Antigas Coins are unavailable. This item was retired from the test environment.', source)
