import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class ConnectionShutdownSerializationTests(unittest.TestCase):
    def test_close_all_swaps_registry_before_locking_each_connection(self):
        source = (ROOT / "src" / "connection.cpp").read_text(encoding="utf-8")
        method = source.split("void ConnectionManager::closeAll()", 1)[1].split("// Connection", 1)[0]

        self.assertRegex(method, re.compile(
            r"std::unordered_set<Connection_ptr> connectionsToClose;\s*"
            r"\{\s*std::lock_guard<std::mutex> lockClass\(connectionManagerLock\);\s*"
            r"connectionsToClose\.swap\(connections\);\s*\}\s*"
            r"for \(const auto& connection : connectionsToClose\)"
        ))
        self.assertIn("std::lock_guard<std::recursive_mutex> lockClass(connection->connectionLock);", method)
        self.assertIn("connection->connectionState = Connection::CONNECTION_STATE_CLOSED;", method)
        self.assertIn("connection->closeSocket();", method)

    def test_listener_and_connection_closes_run_in_one_io_handler(self):
        source = (ROOT / "src" / "server.cpp").read_text(encoding="utf-8")
        method = source.split("void ServiceManager::stop()", 1)[1].split("ServicePort::~ServicePort()", 1)[0]

        self.assertIn("io_service.post([this, ports]()", method)
        self.assertLess(method.index("servicePort->onStopServer();"), method.index("ConnectionManager::getInstance().closeAll();"))
        self.assertLess(method.index("ConnectionManager::getInstance().closeAll();"), method.index("death_timer.expires_from_now"))
        self.assertIn("acceptors.clear();", method)

        service_port_accept = source.split("void ServicePort::accept()", 1)[1].split("void ServicePort::onAccept", 1)[0]
        self.assertIn("if (!acceptor || !acceptor->is_open())", service_port_accept)
        on_accept = source.split("void ServicePort::onAccept", 1)[1].split("Protocol_ptr ServicePort::make_protocol", 1)[0]
        self.assertIn("services.empty() || !acceptor || !acceptor->is_open()", on_accept)

        game = (ROOT / "src" / "game.cpp").read_text(encoding="utf-8")
        shutdown = game.split("void Game::shutdown()", 1)[1].split("void Game::cleanup()", 1)[0]
        self.assertNotIn("ConnectionManager::getInstance().closeAll()", shutdown)
        self.assertIn("serviceManager->stop();", shutdown)


if __name__ == "__main__":
    unittest.main()
