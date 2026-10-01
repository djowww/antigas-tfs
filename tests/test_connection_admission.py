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
        self.assertLess(handler.index("tryAdmitConnection"), handler.index("g_bans.acceptConnection"))
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

    def test_packet_rate_limit_is_validated_before_config_is_applied(self):
        config = (ROOT / "src" / "configmanager.cpp").read_text(encoding="utf-8")
        self.assertLess(
            config.index('lua_getglobal(L, "maxPacketsPerSecond")'),
            config.index("//parse config"),
        )
        self.assertIn("ConnectionRateLimitSettings::isValidMaxPacketsPerSecond", config)
        self.assertIn('integer[MAX_PACKETS_PER_SECOND] = maxPacketsPerSecond;', config)

        limiter = (ROOT / "src" / "connection.cpp").read_text(encoding="utf-8")
        self.assertIn("static_cast<uint32_t>(g_config.getNumber(ConfigManager::MAX_PACKETS_PER_SECOND))", limiter)

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
        accept = implementation.split("bool Ban::acceptConnection", 1)[1].split("BanLookupResult", 1)[0]
        self.assertIn("ConnectionAttemptLimiter::getMonotonicTimeMs()", accept)
        self.assertIn("getMonotonicTimeMs()", limiter)
        self.assertIn("std::chrono::steady_clock::now()", limiter)
        self.assertNotIn("OTSYS_TIME()", accept)
        self.assertIn("cleanupExpired(currentTime)", limiter)
        self.assertIn("capacity(capacity == 0 ? 1 : capacity)", limiter)

    def test_listener_and_source_limiter_share_ipv4_only_address_model(self):
        server = (ROOT / "src" / "server.cpp").read_text(encoding="utf-8")
        listener = server.split("void ServicePort::open(uint16_t port)", 1)[1].split(
            "void ServicePort::", 1
        )[0]
        self.assertIn("address_v4::from_string", listener)
        self.assertIn("address_v4(INADDR_ANY)", listener)
        self.assertNotIn("address_v6", server)
        self.assertNotIn("tcp::v6", server)

        connection = (ROOT / "src" / "connection.cpp").read_text(encoding="utf-8")
        get_ip = connection.split("uint32_t Connection::getIP()", 1)[1].split(
            "void Connection::onWriteOperation", 1
        )[0]
        self.assertIn("if (error)", get_ip)
        self.assertIn("return 0;", get_ip)
        self.assertIn("endpoint.address().to_v4().to_ulong()", get_ip)


if __name__ == "__main__":
    unittest.main()
