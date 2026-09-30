/*
 * Tibia GIMUD Server - a free and open-source MMORPG server emulator
 * Copyright (C) 2017  Alejandro Mujica <alejandrodemujica@gmail.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#ifndef FS_CONNECTION_ADMISSION_H_6B8918B2041742138BC9E3C83977A21F
#define FS_CONNECTION_ADMISSION_H_6B8918B2041742138BC9E3C83977A21F

#include <cstddef>
#include <cstdint>
#include <limits>
#include <mutex>
#include <unordered_map>

namespace ConnectionAdmissionSettings {
	inline int32_t defaultMaxConnections(int32_t maxPlayers)
	{
		if (maxPlayers <= 0) {
			return 4096;
		}

		const int64_t withHeadroom = static_cast<int64_t>(maxPlayers) + 256;
		return withHeadroom > std::numeric_limits<int32_t>::max()
		       ? maxPlayers
		       : static_cast<int32_t>(withHeadroom);
	}
}

class ConnectionAdmission
{
	public:
		explicit ConnectionAdmission(std::size_t maxConnections = 4096,
		                             std::size_t maxConnectionsPerIP = 128) :
			maxConnections(maxConnections),
			maxConnectionsPerIP(maxConnectionsPerIP > maxConnections ? maxConnections : maxConnectionsPerIP) {}

		bool tryAcquire(uint32_t ip)
		{
			if (ip == 0) {
				return false;
			}

			std::lock_guard<std::mutex> lockClass(mutex);
			if (activeConnections >= maxConnections) {
				return false;
			}

			auto found = connectionsByIP.find(ip);
			if (found != connectionsByIP.end() && found->second >= maxConnectionsPerIP) {
				return false;
			}

			if (found == connectionsByIP.end()) {
				found = connectionsByIP.emplace(ip, 0).first;
			}

			++found->second;
			++activeConnections;
			return true;
		}

		bool release(uint32_t ip)
		{
			std::lock_guard<std::mutex> lockClass(mutex);
			auto found = connectionsByIP.find(ip);
			if (found == connectionsByIP.end() || found->second == 0 || activeConnections == 0) {
				return false;
			}

			--found->second;
			--activeConnections;
			if (found->second == 0) {
				connectionsByIP.erase(found);
			}
			return true;
		}

		void setLimits(std::size_t newMaxConnections, std::size_t newMaxConnectionsPerIP)
		{
			std::lock_guard<std::mutex> lockClass(mutex);
			maxConnections = newMaxConnections;
			maxConnectionsPerIP = newMaxConnectionsPerIP > newMaxConnections ? newMaxConnections : newMaxConnectionsPerIP;
		}

		void clear()
		{
			std::lock_guard<std::mutex> lockClass(mutex);
			activeConnections = 0;
			connectionsByIP.clear();
		}

		std::size_t getActiveConnections() const
		{
			std::lock_guard<std::mutex> lockClass(mutex);
			return activeConnections;
		}

		std::size_t getConnectionsForIP(uint32_t ip) const
		{
			std::lock_guard<std::mutex> lockClass(mutex);
			auto found = connectionsByIP.find(ip);
			return found == connectionsByIP.end() ? 0 : found->second;
		}

	private:
		mutable std::mutex mutex;
		std::unordered_map<uint32_t, std::size_t> connectionsByIP;
		std::size_t activeConnections = 0;
		std::size_t maxConnections;
		std::size_t maxConnectionsPerIP;
};

#endif
