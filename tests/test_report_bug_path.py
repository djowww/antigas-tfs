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


class CommandLogPathTests(unittest.TestCase):
    def test_command_log_uses_numeric_guid_for_path_separators(self):
        source = (ROOT / "src" / "commands.cpp").read_text(encoding="utf-8")

        self.assertIn("std::string logName = player.getName();", source)
        self.assertIn("logName.find('/') != std::string::npos", source)
        self.assertIn(r"logName.find('\\') != std::string::npos", source)
        self.assertIn("logName = std::to_string(player.getGUID());", source)
        self.assertIn('logFile << "data/logs/" << logName << " commands.log";', source)


if __name__ == "__main__":
    unittest.main()
