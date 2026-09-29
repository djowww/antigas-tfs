import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ScriptFilenameTests(unittest.TestCase):
    def test_script_reader_uses_bounded_display_copy_without_changing_open_path(self):
        source = (ROOT / "src" / "script.h").read_text(encoding="utf-8")
        self.assertIn("copyScriptFilename(Filename[RecursionDepth], displayName)", source)
        self.assertIn('fopen(FileName.c_str(), "rb")', source)
        self.assertNotIn("strcpy(Filename[RecursionDepth]", source)

    def test_native_buffer_boundary_regression_is_wired_into_build_and_ci(self):
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "security-build.yml").read_text(encoding="utf-8")
        self.assertIn("TFS_BUILD_SCRIPT_FILENAME_TESTS", cmake)
        self.assertIn("script-filename-tests", cmake)
        self.assertIn("-DTFS_BUILD_SCRIPT_FILENAME_TESTS=ON", workflow)


if __name__ == "__main__":
    unittest.main()
