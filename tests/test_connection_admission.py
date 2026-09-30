import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ConnectionAdmissionIntegrationTests(unittest.TestCase):
    def test_admission_limits_are_applied_before_protocol_creation(self):
        server = (ROOT / "src" / "server.cpp").read_text(encoding="utf-8")
        handler = server.split("void ServicePort::onAccept", 1)[1].split(
            "Protocol_ptr ServicePort::make_protocol", 1
        )[0]
        self.assertLess(handler.index("tryAdmitConnection"), handler.index("make_protocol"))
        self.assertRegex(
            handler,
            re.compile(r"else\s*\{\s*connection->close\(Connection::FORCE_CLOSE\);\s*\}\s*accept\(\);"),
        )

    def test_admission_slot_survives_graceful_close_until_socket_close(self):
        connection = (ROOT / "src" / "connection.cpp").read_text(encoding="utf-8")
        close = connection.split("void Connection::close(bool force)", 1)[1].split(
            "void Connection::closeSocket", 1
        )[0]
        self.assertLess(close.index("closeSocket();"), close.index("releaseConnection(shared_from_this())"))
        self.assertIn("Keep the admission slot until the queued response is written or times out", close)

        write = connection.split("void Connection::onWriteOperation", 1)[1].split(
            "void Connection::handleTimeout", 1
        )[0]
        self.assertRegex(write, re.compile(r"closeSocket\(\);\s*ConnectionManager::getInstance\(\)\.releaseConnection"))

    def test_manager_releases_counts_and_resets_them_during_shutdown(self):
        connection = (ROOT / "src" / "connection.cpp").read_text(encoding="utf-8")
        release = connection.split("void ConnectionManager::releaseConnection", 1)[1].split(
            "void ConnectionManager::closeAll", 1
        )[0]
        self.assertIn("connectionAdmission.release(connection->remoteIP)", release)
        self.assertIn("if (connection->admitted)", release)
        close_all = connection.split("void ConnectionManager::closeAll", 1)[1].split(
            "// Connection", 1
        )[0]
        self.assertIn("connectionAdmission.clear()", close_all)

    def test_limits_are_configurable_and_default_above_max_players(self):
        config = (ROOT / "src" / "configmanager.cpp").read_text(encoding="utf-8")
        example = (ROOT / "config.example.lua").read_text(encoding="utf-8")
        self.assertIn('"maxConnections", 0', config)
        self.assertIn('"maxConnectionsPerIP", 128', config)
        self.assertIn("integer[MAX_CONNECTIONS] < integer[MAX_PLAYERS]", config)
        self.assertIn("maxConnections = 0", example)
        self.assertIn("maxConnectionsPerIP = 128", example)

    def test_service_configures_limits_before_running_accept_callbacks(self):
        server = (ROOT / "src" / "server.cpp").read_text(encoding="utf-8")
        run = server.split("void ServiceManager::run()", 1)[1].split("void ServiceManager::stop", 1)[0]
        self.assertLess(run.index("configureAdmission"), run.index("io_service.run()"))

    def test_ban_rate_limit_state_is_bounded_and_expires(self):
        ban = (ROOT / "src" / "ban.h").read_text(encoding="utf-8")
        implementation = (ROOT / "src" / "ban.cpp").read_text(encoding="utf-8")
        limiter = (ROOT / "src" / "connectionattemptlimiter.h").read_text(encoding="utf-8")
        self.assertIn("ConnectionAttemptLimiter connectionAttempts", ban)
        self.assertNotIn("ipConnectMap", ban)
        self.assertIn("connectionAttempts.allow(clientip, OTSYS_TIME())", implementation)
        self.assertIn("cleanupExpired(currentTime)", limiter)
        self.assertIn("capacity(capacity == 0 ? 1 : capacity)", limiter)


if __name__ == "__main__":
    unittest.main()
