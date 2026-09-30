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

#include "configmanager.h"
#include "connection.h"
#include "connectionqueue.h"
#include "outputmessage.h"
#include "protocol.h"
#include "scheduler.h"
#include "server.h"

#include <iterator>

extern ConfigManager g_config;

Connection_ptr ConnectionManager::createConnection(boost::asio::io_service& io_service, ConstServicePort_ptr servicePort)
{
	std::lock_guard<std::mutex> lockClass(connectionManagerLock);

	auto connection = std::make_shared<Connection>(io_service, servicePort);
	connections.insert(connection);
	return connection;
}

bool ConnectionManager::tryAdmitConnection(const Connection_ptr& connection, uint32_t remoteIP)
{
	std::lock_guard<std::mutex> lockClass(connectionManagerLock);
	if (connections.find(connection) == connections.end() || connection->admitted || !connectionAdmission.tryAcquire(remoteIP)) {
		return false;
	}

	connection->remoteIP = remoteIP;
	connection->admitted = true;
	return true;
}

void ConnectionManager::configureAdmission(std::size_t maxConnections, std::size_t maxConnectionsPerIP)
{
	connectionAdmission.setLimits(maxConnections, maxConnectionsPerIP);
}

void ConnectionManager::releaseConnection(const Connection_ptr& connection)
{
	std::lock_guard<std::mutex> lockClass(connectionManagerLock);
	if (connection->admitted) {
		connectionAdmission.release(connection->remoteIP);
		connection->remoteIP = 0;
		connection->admitted = false;
	}

	connections.erase(connection);
}

void ConnectionManager::closeAll()
{
	std::unordered_set<Connection_ptr> connectionsToClose;
	{
		std::lock_guard<std::mutex> lockClass(connectionManagerLock);
		for (const auto& connection : connections) {
			connection->remoteIP = 0;
			connection->admitted = false;
		}
		connectionAdmission.clear();
		connectionsToClose.swap(connections);
	}

	for (const auto& connection : connectionsToClose) {
		std::lock_guard<std::recursive_mutex> lockClass(connection->connectionLock);
		connection->clearPendingOutputMessages();
		connection->connectionState = Connection::CONNECTION_STATE_CLOSED;
		connection->closeSocket();
	}
}

// Connection

void Connection::close(bool force)
{
	bool releaseFromManager = false;
	{
		std::lock_guard<std::recursive_mutex> lockClass(connectionLock);
		if (connectionState != CONNECTION_STATE_OPEN) {
			if (!force) {
				return;
			}
			clearPendingOutputMessages();
			closeSocket();
			releaseFromManager = true;
		} else {
			connectionState = CONNECTION_STATE_CLOSED;

			if (protocol) {
				g_dispatcher.addTask(
					createTask(std::bind(&Protocol::release, protocol)));
			}

			if (messageQueue.empty() || force) {
				if (force) {
					clearPendingOutputMessages();
				}
				closeSocket();
				releaseFromManager = true;
			} else {
				//Keep the admission slot until the queued response is written or times out.
			}
		}
	}

	if (releaseFromManager) {
		ConnectionManager::getInstance().releaseConnection(shared_from_this());
	}
}

void Connection::closeSocket()
{
	if (socket.is_open()) {
		try {
			readTimer.cancel();
			writeTimer.cancel();
			boost::system::error_code error;
			socket.shutdown(boost::asio::ip::tcp::socket::shutdown_both, error);
			socket.close(error);
		} catch (boost::system::system_error& e) {
			std::cout << "[Network error - Connection::closeSocket] " << e.what() << std::endl;
		}
	}
}

void Connection::clearPendingOutputMessages()
{
	const std::size_t keepInFlight = writeInProgress && !messageQueue.empty() ? 1 : 0;
	const std::size_t discarded = messageQueue.size() - keepInFlight;
	if (discarded == 0) {
		return;
	}

	if (keepInFlight != 0) {
		messageQueue.erase(std::next(messageQueue.begin()), messageQueue.end());
	} else {
		messageQueue.clear();
	}
	ConnectionOutputQueue::release(discarded);
}

Connection::~Connection()
{
	ConnectionOutputQueue::release(messageQueue.size());
	messageQueue.clear();
	closeSocket();
}

void Connection::accept(Protocol_ptr protocol)
{
	this->protocol = protocol;
	g_dispatcher.addTask(createTask(std::bind(&Protocol::onConnect, protocol)));

	accept();
}

void Connection::accept()
{
	std::lock_guard<std::recursive_mutex> lockClass(connectionLock);
	try {
		readTimer.expires_from_now(boost::posix_time::seconds(static_cast<long>(Connection::read_timeout)));
		readTimer.async_wait(std::bind(&Connection::handleTimeout, std::weak_ptr<Connection>(shared_from_this()), std::placeholders::_1));

		// Read size of the first packet
		boost::asio::async_read(socket,
		                        boost::asio::buffer(msg.getBuffer(), NetworkMessage::HEADER_LENGTH),
		                        std::bind(&Connection::parseHeader, shared_from_this(), std::placeholders::_1));
	} catch (boost::system::system_error& e) {
		std::cout << "[Network error - Connection::accept] " << e.what() << std::endl;
		close(FORCE_CLOSE);
	}
}

void Connection::parseHeader(const boost::system::error_code& error)
{
	std::lock_guard<std::recursive_mutex> lockClass(connectionLock);
	readTimer.cancel();

	if (error) {
		close(FORCE_CLOSE);
		return;
	} else if (connectionState != CONNECTION_STATE_OPEN) {
		return;
	}

	uint32_t timePassed = std::max<uint32_t>(1, (time(nullptr) - timeConnected) + 1);
	if ((++packetsSent / timePassed) > static_cast<uint32_t>(g_config.getNumber(ConfigManager::MAX_PACKETS_PER_SECOND))) {
		std::cout << convertIPToString(getIP()) << " disconnected for exceeding packet per second limit." << std::endl;
		close();
		return;
	}

	if (timePassed > 2) {
		timeConnected = time(nullptr);
		packetsSent = 0;
	}

	uint16_t size = msg.getLengthHeader();
	if (size == 0 || size >= NETWORKMESSAGE_MAXSIZE - 16) {
		close(FORCE_CLOSE);
		return;
	}

	try {
		readTimer.expires_from_now(boost::posix_time::seconds(static_cast<long>(Connection::read_timeout)));
		readTimer.async_wait(std::bind(&Connection::handleTimeout, std::weak_ptr<Connection>(shared_from_this()),
		                                    std::placeholders::_1));

		// Read packet content
		msg.setLength(size + NetworkMessage::HEADER_LENGTH);
		boost::asio::async_read(socket, boost::asio::buffer(msg.getBodyBuffer(), size),
		                        std::bind(&Connection::parsePacket, shared_from_this(), std::placeholders::_1));
	} catch (boost::system::system_error& e) {
		std::cout << "[Network error - Connection::parseHeader] " << e.what() << std::endl;
		close(FORCE_CLOSE);
	}
}

void Connection::parsePacket(const boost::system::error_code& error)
{
	std::lock_guard<std::recursive_mutex> lockClass(connectionLock);
	readTimer.cancel();

	if (error) {
		close(FORCE_CLOSE);
		return;
	} else if (connectionState != CONNECTION_STATE_OPEN) {
		return;
	}

	if (!receivedFirst) {
		// First message received
		receivedFirst = true;

		if (!protocol) {
			// Game protocol has already been created at this point
			protocol = service_port->make_protocol(msg, shared_from_this());
			if (!protocol) {
				close(FORCE_CLOSE);
				return;
			}
		} else {
			msg.skipBytes(1);    // Skip protocol ID
		}

		protocol->onRecvFirstMessage(msg);
	} else {
		protocol->onRecvMessage(msg);    // Send the packet to the current protocol
	}

	try {
		readTimer.expires_from_now(boost::posix_time::seconds(static_cast<long>(Connection::read_timeout)));
		readTimer.async_wait(std::bind(&Connection::handleTimeout, std::weak_ptr<Connection>(shared_from_this()),
		                                    std::placeholders::_1));

		// Wait to the next packet
		boost::asio::async_read(socket,
		                        boost::asio::buffer(msg.getBuffer(), NetworkMessage::HEADER_LENGTH),
		                        std::bind(&Connection::parseHeader, shared_from_this(), std::placeholders::_1));
	} catch (boost::system::system_error& e) {
		std::cout << "[Network error - Connection::parsePacket] " << e.what() << std::endl;
		close(FORCE_CLOSE);
	}
}

void Connection::send(const OutputMessage_ptr& msg)
{
	std::lock_guard<std::recursive_mutex> lockClass(connectionLock);
	if (connectionState != CONNECTION_STATE_OPEN) {
		return;
	}
	if (!ConnectionOutputQueue::tryReserve(messageQueue.size())) {
		close(FORCE_CLOSE);
		return;
	}

	bool noPendingWrite = messageQueue.empty();
	try {
		messageQueue.emplace_back(msg);
	} catch (...) {
		ConnectionOutputQueue::release();
		close(FORCE_CLOSE);
		return;
	}
	if (noPendingWrite) {
		internalSend(msg);
	}
}

void Connection::internalSend(const OutputMessage_ptr& msg)
{
	protocol->onSendMessage(msg);
	try {
		writeTimer.expires_from_now(boost::posix_time::seconds(static_cast<long>(Connection::write_timeout)));
		writeTimer.async_wait(std::bind(&Connection::handleTimeout, std::weak_ptr<Connection>(shared_from_this()),
		                                     std::placeholders::_1));

		boost::asio::async_write(socket,
		                         boost::asio::buffer(msg->getOutputBuffer(), msg->getLength()),
		                         std::bind(&Connection::onWriteOperation, shared_from_this(), std::placeholders::_1));
		writeInProgress = true;
	} catch (boost::system::system_error& e) {
		writeInProgress = false;
		std::cout << "[Network error - Connection::internalSend] " << e.what() << std::endl;
		close(FORCE_CLOSE);
	}
}

uint32_t Connection::getIP()
{
	std::lock_guard<std::recursive_mutex> lockClass(connectionLock);

	// IP-address is expressed in network byte order
	boost::system::error_code error;
	const boost::asio::ip::tcp::endpoint endpoint = socket.remote_endpoint(error);
	if (error) {
		return 0;
	}

	return htonl(endpoint.address().to_v4().to_ulong());
}

void Connection::onWriteOperation(const boost::system::error_code& error)
{
	std::lock_guard<std::recursive_mutex> lockClass(connectionLock);
	writeTimer.cancel();
	writeInProgress = false;
	if (!messageQueue.empty()) {
		messageQueue.pop_front();
		ConnectionOutputQueue::release();
	}

	if (error) {
		clearPendingOutputMessages();
		close(FORCE_CLOSE);
		return;
	}

	if (!messageQueue.empty()) {
		internalSend(messageQueue.front());
	} else if (connectionState == CONNECTION_STATE_CLOSED) {
		closeSocket();
		ConnectionManager::getInstance().releaseConnection(shared_from_this());
	}
}

void Connection::handleTimeout(ConnectionWeak_ptr connectionWeak, const boost::system::error_code& error)
{
	if (error == boost::asio::error::operation_aborted) {
		//The timer has been manually cancelled
		return;
	}

	if (auto connection = connectionWeak.lock()) {
		connection->close(FORCE_CLOSE);
	}
}
