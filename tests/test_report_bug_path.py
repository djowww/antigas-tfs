import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ReportBugPathTests(unittest.TestCase):
    def test_report_filename_falls_back_to_numeric_guid_for_path_separators(self):
        source = (ROOT / "data" / "events" / "scripts" / "player.lua").read_text(encoding="utf-8")
        handler = source.split("function Player:onReportBug(", 1)[1].split("\nend", 1)[0]

        self.assertIn("local reportFilename = name", handler)
        self.assertIn('if name:find("/", 1, true) or name:find("\\\\", 1, true) then', handler)
        self.assertIn("reportFilename = tostring(self:getGuid())", handler)
        self.assertIn('io.open("data/reports/bugs/" .. reportFilename .. " report.txt", "a")', handler)
        self.assertNotIn('io.open("data/reports/bugs/" .. name', handler)
        self.assertIn('file:write("Name: " .. name)', handler)


if __name__ == "__main__":
    unittest.main()
