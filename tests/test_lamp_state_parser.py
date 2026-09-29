import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class LampStateParserSourceTests(unittest.TestCase):
    def test_persisted_state_parser_does_not_evaluate_and_bounds_reads(self):
        source = (ROOT / "data" / "lib" / "lamp_states.lua").read_text(encoding="utf-8")

        self.assertNotIn("loadstring(", source)
        self.assertIn("local maxBytes = 8 * 1024 * 1024", source)
        self.assertIn("local maxEntries = 100000", source)
        self.assertIn("file:read(8 * 1024 * 1024 + 1)", source)
        self.assertNotIn("body:sub(token)", source)
        self.assertIn("lampTransformIds[itemId]", source)
        self.assertIn("reverseLampTransformIds[itemId]", source)


if __name__ == "__main__":
    unittest.main()
