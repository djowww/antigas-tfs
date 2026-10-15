import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class CoinPageCacheTests(unittest.TestCase):
    def test_player_coin_copy_describes_the_active_flow_in_every_locale(self):
        wiki = (ROOT / "deploy" / "site-public" / "wiki.php").read_text(encoding="utf-8")
        home = (ROOT / "deploy" / "site-public" / "index.php").read_text(encoding="utf-8")
        translations = (ROOT / "deploy" / "site-public" / "i18n-extra.php").read_text(encoding="utf-8")

        stale_copy = (
            "Extra items and Antigas Coins are unavailable.",
            "Are website Coins available? No: this item was retired from the test environment.",
            "Antigas Coin sales are unavailable.",
            "The Shop and Market no longer offer retired items or Antigas Coins.",
        )
        for phrase in stale_copy:
            self.assertNotIn(phrase, wiki)
            self.assertNotIn(phrase, home)
            self.assertNotIn(phrase, translations)

        market_copy = (
            "The Market supports player offers for items and coins. Review an offer before accepting, "
            "and collect completed trades through the Market. After manual payment approval, Antigas Coins "
            "bought on the website are available for the selected character to collect through the Market "
            "in their hometown depot."
        )
        faq_copy = (
            "Where do new characters start? In Rookgaard. Where do I download the client? Use the download button "
            "on the home page. Are website Coins available? Yes. Choose a package and character on the website; "
            "payment is reviewed manually, then the selected character can collect the Coins through the Market "
            "in their hometown depot. Where can I find the full spell list? Search the client or read the Spells "
            "and runes section on this page."
        )
        news_copy = (
            "At the v72 release, retired items and Antigas Coins were unavailable in the Shop and Market. "
            "Antigas Coins are now available through website orders; after manual payment approval, collect them "
            "through the Market with the selected character."
        )
        self.assertIn(market_copy, wiki)
        self.assertIn(faq_copy, wiki)
        self.assertIn("siteT('See coin prices and create an order on the website.')", wiki)
        self.assertIn(news_copy, home)
        self.assertEqual(translations.count(market_copy), 3, "Market instructions must be translated for PT, ES and PL")
        self.assertEqual(translations.count(faq_copy), 3, "FAQ instructions must be translated for PT, ES and PL")
        self.assertEqual(translations.count(news_copy), 3, "Coin restoration news must be translated for PT, ES and PL")

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
