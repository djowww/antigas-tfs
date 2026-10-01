/**
 * Tibia GIMUD Server - a free and open-source MMORPG server emulator
 * Copyright (C) 2017  Alejandro Mujica <alejandrodemujica@gmail.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License along
 * with this program; if not, write to the Free Software Foundation, Inc.,
 * 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
 */

#include "otpch.h"

#include "outputmessage.h"
#include "server.h"
#include "scheduler.h"
#include "configmanager.h"
#include "ban.h"
#include "game.h"

extern ConfigManager g_config;
extern Game g_game;
extern Dispatcher g_dispatcher;
Ban g_bans;

ServiceManager::ServiceManager()
{
#ifndef _WIN32
	shutdownSignals.async_wait([](const boost::system::error_code& error, int signal) {
		if (error) {
			return;
		}
		std::cout << "[Shutdown] Signal " << signal << ": saving players and world before exit." << std::endl;
		// World/database state belongs to the dispatcher, never to a signal handler.
		g_dispatcher.addTask(createTask([]() {
			g_game.setGameState(GAME_STATE_SHUTDOWN);
		}));
	});
#endif
}

ServiceManager::~ServiceManager()
{
	stop();
}

void ServiceManager::die()
{
	io_service.stop();
}

void ServiceManager::run()
{
	assert(!running);
	running = true;
	ConnectionManager::getInstance().configureAdmission(
	        static_cast<std::size_t>(g_config.getNumber(ConfigManager::MAX_CONNECTIONS)),
	        static_cast<std::size_t>(g_config.getNumber(ConfigManager::MAX_CONNECTIONS_PER_IP)));
	io_service.run();
}

void ServiceManager::stop()
{
	if (!running) {
		return;
	}

	running = false;

	std::vector<ServicePort_ptr> ports;
	ports.reserve(acceptors.size());
	for (const auto& servicePortIt : acceptors) {
		ports.push_back(servicePortIt.second);
	}
	acceptors.clear();

	try {
		io_service.post([this, ports]() {
			for (const auto& servicePort : ports) {
				servicePort->onStopServer();
			}

			ConnectionManager::getInstance().closeAll();

			death_timer.expires_from_now(boost::posix_time::seconds(3));
			death_timer.async_wait(std::bind(&ServiceManager::die, this));
		});
	} catch (const boost::system::system_error& e) {
		std::cout << "[ServiceManager::stop] Network Error: " << e.what() << std::endl;
		io_service.stop();
	}
}

ServicePort::~ServicePort()
{
	close();
}

bool ServicePort::is_single_socket() const
{
	return !services.empty() && services.front()->is_single_socket();
}

std::string ServicePort::get_protocol_names() const
{
	if (services.empty()) {
		return std::string();
	}

	std::string str = services.front()->get_protocol_name();
	for (size_t i = 1; i < services.size(); ++i) {
		str.push_back(',');
		str.push_back(' ');
		str.append(services[i]->get_protocol_name());
	}
	return str;
}

void ServicePort::accept()
{
	if (!acceptor || !acceptor->is_open()) {
		return;
	}

	auto connection = ConnectionManager::getInstance().createConnection(io_service, shared_from_this());
	acceptor->async_accept(connection->getSocket(), std::bind(&ServicePort::onAccept, shared_from_this(), connection, std::placeholders::_1));
}

void ServicePort::onAccept(Connection_ptr connection, const boost::system::error_code& error)
{
	if (!error) {
		if (services.empty() || !acceptor || !acceptor->is_open()) {
			connection->close(Connection::FORCE_CLOSE);
			return;
		}

		auto remote_ip = connection->getIP();
		// Do not consume per-IP limiter state for a socket rejected by the active-connection caps.
		if (remote_ip != 0 && ConnectionManager::getInstance().tryAdmitConnection(connection, remote_ip) &&
		        g_bans.acceptConnection(remote_ip)) {
			Service_ptr service = services.front();
			if (service->is_single_socket()) {
				connection->accept(service->make_protocol(connection));
			} else {
				connection->accept();
			}
		} else {
			connection->close(Connection::FORCE_CLOSE);
		}

		accept();
	} else {
		// The connection was registered before async_accept; release it on every
		// failed/cancelled accept so it cannot remain retained by ConnectionManager.
		connection->close(Connection::FORCE_CLOSE);

		if (error != boost::asio::error::operation_aborted && !pendingStart) {
			close();
			pendingStart = true;
			g_scheduler.addEvent(createSchedulerTask(15000,
				                     std::bind(&ServicePort::openAcceptor, std::weak_ptr<ServicePort>(shared_from_this()), serverPort)));
		}
	}
}

Protocol_ptr ServicePort::make_protocol(NetworkMessage& msg, const Connection_ptr& connection) const
{
	uint8_t protocolID = msg.getByte();
	for (auto& service : services) {
		if (protocolID != service->get_protocol_identifier()) {
			continue;
		}

		return service->make_protocol(connection);
	}
	return nullptr;
}

void ServicePort::onStopServer()
{
	close();
}

void ServicePort::openAcceptor(std::weak_ptr<ServicePort> weak_service, uint16_t port)
{
	if (auto service = weak_service.lock()) {
		service->open(port);
	}
}

void ServicePort::open(uint16_t port)
{
	close();

	serverPort = port;
	pendingStart = false;

	try {
		if (g_config.getBoolean(ConfigManager::BIND_ONLY_GLOBAL_ADDRESS)) {
			acceptor.reset(new boost::asio::ip::tcp::acceptor(io_service, boost::asio::ip::tcp::endpoint(
			            boost::asio::ip::address(boost::asio::ip::address_v4::from_string(g_config.getString(ConfigManager::IP))), serverPort)));
		} else {
			acceptor.reset(new boost::asio::ip::tcp::acceptor(io_service, boost::asio::ip::tcp::endpoint(
			            boost::asio::ip::address(boost::asio::ip::address_v4(INADDR_ANY)), serverPort)));
		}

		acceptor->set_option(boost::asio::ip::tcp::no_delay(true));

		accept();
	} catch (boost::system::system_error& e) {
		std::cout << "[ServicePort::open] Error: " << e.what() << std::endl;

		pendingStart = true;
		g_scheduler.addEvent(createSchedulerTask(15000,
		                     std::bind(&ServicePort::openAcceptor, std::weak_ptr<ServicePort>(shared_from_this()), port)));
	}
}

void ServicePort::close()
{
	if (acceptor && acceptor->is_open()) {
		boost::system::error_code error;
		acceptor->close(error);
	}
}

bool ServicePort::add_service(const Service_ptr& new_svc)
{
	if (std::any_of(services.begin(), services.end(), [](const Service_ptr& svc) {return svc->is_single_socket();})) {
		return false;
	}

	services.push_back(new_svc);
	return true;
}
