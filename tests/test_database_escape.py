import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DatabaseEscapeSafetyTests(unittest.TestCase):
    def test_native_escape_checks_connection_and_result_before_append(self):
        source = (ROOT / "src" / "database.cpp").read_text(encoding="utf-8")
        self.assertIn("if (!connected || !handle || !databaseEscape::getOutputCapacity", source)
        self.assertIn("mysql_real_escape_string(handle", source)
        self.assertIn("if (!databaseEscape::isValidOutputLength(escapedLength, outputCapacity))", source)
        self.assertLess(
            source.index("if (!databaseEscape::isValidOutputLength(escapedLength, outputCapacity))"),
            source.index("escaped.append(output.data()"),
        )

    def test_escape_api_propagates_failure_to_lua_without_sql_text_fallback(self):
        header = (ROOT / "src" / "database.h").read_text(encoding="utf-8")
        binding = (ROOT / "src" / "luascript.cpp").read_text(encoding="utf-8")
        self.assertIn("bool escapeString(const std::string& s, std::string& escaped) const;", header)
        self.assertNotIn("std::string escapeString(const std::string& s)", header)
        function = binding.split("int LuaScriptInterface::luaDatabaseEscapeString(lua_State* L)", 1)[1].split("\n}", 1)[0]
        self.assertIn("if (!Database::getInstance()->escapeString(getString(L, -1), escaped))", function)
        self.assertIn("lua_pushnil(L);", function)

    def test_table_exists_error_is_not_reported_as_missing_schema_to_lua(self):
        source = (ROOT / "src" / "luascript.cpp").read_text(encoding="utf-8")
        function = source.split("int LuaScriptInterface::luaDatabaseTableExists(lua_State* L)", 1)[1].split("\n}", 1)[0]
        self.assertIn("DatabaseManager::tableExists(tableName, &querySucceeded)", function)
        self.assertIn("if (!querySucceeded)", function)
        self.assertIn("luaL_error(L, \"Database table existence check failed.\")", function)

    def test_native_mock_uses_checked_api_and_preserves_expired_ban_on_escape_error(self):
        source = (ROOT / "tests" / "ban-lookup-tests.cpp").read_text(encoding="utf-8")
        self.assertIn("bool Database::escapeString(const std::string& value, std::string& escaped) const", source)
        self.assertIn("failed reason escaping must not enqueue history or delete the original ban", source)

    def test_database_escape_native_regression_is_wired_into_cmake_and_ci(self):
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "security-build.yml").read_text(encoding="utf-8")
        self.assertIn("TFS_BUILD_DATABASE_ESCAPE_TESTS", cmake)
        self.assertIn("database-escape-tests", cmake)
        self.assertIn("-DTFS_BUILD_DATABASE_ESCAPE_TESTS=ON", workflow)
        self.assertIn("test_database_escape", workflow)


if __name__ == "__main__":
    unittest.main()
