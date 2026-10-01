import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RemoteLogRateLimiterIntegrationTests(unittest.TestCase):
    def test_unknown_packet_log_uses_global_bounded_limiter(self):
        source = (ROOT / "src" / "protocolgame.cpp").read_text(encoding="utf-8")
        default_case = source.split('case 0xF9: parseModalWindowAnswer(msg); break;', 1)[1].split(
            "default:", 1
        )[1].split("break;", 1)[0]
        self.assertLess(
            default_case.index("remoteDiagnosticLogRateLimiter().allow(suppressedMessages)"),
            default_case.index("std::cout"),
        )
        self.assertIn("remote log messages suppressed since the previous record", default_case)

        connection = (ROOT / "src" / "connection.cpp").read_text(encoding="utf-8")
        rate_violation = connection.split("if ((++packetsSent", 1)[1].split("if (timePassed > 2)", 1)[0]
        self.assertLess(
            rate_violation.index("remoteDiagnosticLogRateLimiter().allow(suppressedMessages)"),
            rate_violation.index("std::cout"),
        )

    def test_native_regression_is_wired_into_cmake_and_ci(self):
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "security-build.yml").read_text(encoding="utf-8")
        self.assertIn("TFS_BUILD_REMOTE_LOG_RATE_LIMITER_TESTS", cmake)
        self.assertIn("remote-log-rate-limiter-tests", cmake)
        self.assertIn("tests/remote-log-rate-limiter-sharing.cpp", cmake)
        self.assertIn("-DTFS_BUILD_REMOTE_LOG_RATE_LIMITER_TESTS=ON", workflow)
        self.assertIn("test_remote_log_rate_limiter", workflow)
        limiter = (ROOT / "src" / "remotelogratelimiter.h").read_text(encoding="utf-8")
        self.assertIn("RemoteLogRateLimiter limiter(10, std::chrono::seconds(60))", limiter)

    def test_client_assertion_write_is_bounded_before_open(self):
        game = (ROOT / "src" / "game.cpp").read_text(encoding="utf-8")
        handler = game.split("void Game::playerDebugAssert", 1)[1].split(
            "void Game::parsePlayerExtendedOpcode", 1
        )[0]
        self.assertLess(handler.index("ClientAssertionPolicy::getPayloadBytes"), handler.index('fopen("client_assertions.txt"'))
        self.assertLess(handler.index("clientAssertionWriteRateLimiter().allow"), handler.index('fopen("client_assertions.txt"'))
        self.assertLess(handler.index("ClientAssertionPolicy::canAppend"), handler.index("fprintf(file"))
        policy = (ROOT / "src" / "clientassertionpolicy.h").read_text(encoding="utf-8")
        self.assertIn("return 8 * 1024", policy)
        self.assertIn("16 * 1024 * 1024", policy)


if __name__ == "__main__":
    unittest.main()
