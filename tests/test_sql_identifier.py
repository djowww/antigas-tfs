import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SqlIdentifierTests(unittest.TestCase):
    def test_table_metadata_is_quoted_by_identifier_helper(self):
        source = (ROOT / "src" / "databasemanager.cpp").read_text(encoding="utf-8")
        optimize = source.split("bool DatabaseManager::optimizeTables()", 1)[1].split(
            "bool DatabaseManager::tableExists(", 1
        )[0]
        self.assertIn('quoteSqlIdentifier(tableName)', optimize)
        self.assertNotIn('"OPTIMIZE TABLE `" << tableName', optimize)

    def test_native_identifier_regression_is_wired_into_cmake_and_ci(self):
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "security-build.yml").read_text(encoding="utf-8")
        self.assertIn("TFS_BUILD_SQL_IDENTIFIER_TESTS", cmake)
        self.assertIn("sql-identifier-tests", cmake)
        self.assertIn("-DTFS_BUILD_SQL_IDENTIFIER_TESTS=ON", workflow)


if __name__ == "__main__":
    unittest.main()
