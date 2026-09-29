import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ConnectionOutputQueueTests(unittest.TestCase):
    def test_overflow_guard_precedes_queue_append_and_forces_close(self):
        source = (ROOT / "src" / "connection.cpp").read_text(encoding="utf-8")
        send = source.split("void Connection::send(", 1)[1].split("void Connection::internalSend(", 1)[0]
        guard = send.index("ConnectionOutputQueue::canQueue(messageQueue.size())")
        close = send.index("close(FORCE_CLOSE);", guard)
        append = send.index("messageQueue.emplace_back(msg)")
        self.assertLess(guard, close)
        self.assertLess(close, append)

    def test_queue_limit_is_covered_by_native_ctest_target(self):
        cmake = (ROOT / "CMakeLists.txt").read_text(encoding="utf-8")
        workflow = (ROOT / ".github" / "workflows" / "security-build.yml").read_text(encoding="utf-8")
        self.assertIn("TFS_BUILD_CONNECTION_OUTPUT_QUEUE_TESTS", cmake)
        self.assertIn("connection-output-queue-tests", cmake)
        self.assertIn("-DTFS_BUILD_CONNECTION_OUTPUT_QUEUE_TESTS=ON", workflow)


if __name__ == "__main__":
    unittest.main()
