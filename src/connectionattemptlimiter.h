/*
 * Tibia GIMUD Server - a free and open-source MMORPG server emulator
 * Copyright (C) 2017  Alejandro Mujica <alejandrodemujica@gmail.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#ifndef FS_CONNECTION_ATTEMPT_LIMITER_H_3EE0F57B392A4BEB9AAEF014BB688156
#define FS_CONNECTION_ATTEMPT_LIMITER_H_3EE0F57B392A4BEB9AAEF014BB688156

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <mutex>
#include <unordered_map>
#include <vector>

class ConnectionAttemptLimiter
{
	public:
		explicit ConnectionAttemptLimiter(std::size_t capacity = 65536, std::size_t cleanupBudget = 256) :
			capacity(capacity == 0 ? 1 : capacity),
			cleanupBudget(std::min(cleanupBudget == 0 ? std::size_t(1) : cleanupBudget, this->capacity)),
			entries(this->capacity)
		{
			freeSlots.reserve(this->capacity);
			for (std::size_t slot = 0; slot < this->capacity; ++slot) {
				freeSlots.push_back(slot);
			}
		}

		bool allow(uint32_t ip, uint64_t currentTime)
		{
			if (ip == 0) {
				return false;
			}

			std::lock_guard<std::mutex> lockClass(mutex);
			auto found = indexByIP.find(ip);
			if (found != indexByIP.end()) {
				return allowExisting(entries[found->second], currentTime);
			}

			if (freeSlots.empty()) {
				cleanupExpired(currentTime);
			}
			if (freeSlots.empty()) {
				return false;
			}

			const std::size_t slot = freeSlots.back();
			freeSlots.pop_back();
			Entry& entry = entries[slot];
			entry.ip = ip;
			entry.lastAttempt = currentTime;
			entry.blockTime = 0;
			entry.count = 1;
			entry.occupied = true;
			indexByIP.emplace(ip, slot);
			return true;
		}

		std::size_t getTrackedCount() const
		{
			std::lock_guard<std::mutex> lockClass(mutex);
			return indexByIP.size();
		}

		std::size_t getCapacity() const
		{
			return capacity;
		}

	private:
		struct Entry {
			uint32_t ip = 0;
			uint64_t lastAttempt = 0;
			uint64_t blockTime = 0;
			uint32_t count = 0;
			bool occupied = false;
		};

		static bool allowExisting(Entry& entry, uint64_t currentTime)
		{
			if (entry.blockTime > currentTime) {
				entry.blockTime += 250;
				return false;
			}

			const uint64_t timeDiff = currentTime >= entry.lastAttempt ? currentTime - entry.lastAttempt : 0;
			entry.lastAttempt = currentTime;
			if (timeDiff <= 5000) {
				if (++entry.count > 5) {
					entry.count = 0;
					if (timeDiff <= 500) {
						entry.blockTime = currentTime + 3000;
						return false;
					}
				}
			} else {
				entry.count = 1;
			}
			return true;
		}

		static bool expired(const Entry& entry, uint64_t currentTime)
		{
			return entry.occupied && currentTime >= entry.blockTime &&
			       currentTime >= entry.lastAttempt && currentTime - entry.lastAttempt > 5000;
		}

		void cleanupExpired(uint64_t currentTime)
		{
			for (std::size_t scanned = 0; scanned < cleanupBudget; ++scanned) {
				const std::size_t slot = cleanupCursor;
				cleanupCursor = (cleanupCursor + 1) % capacity;
				Entry& entry = entries[slot];
				if (!expired(entry, currentTime)) {
					continue;
				}

				indexByIP.erase(entry.ip);
				entry.occupied = false;
				freeSlots.push_back(slot);
			}
		}

		mutable std::mutex mutex;
		const std::size_t capacity;
		const std::size_t cleanupBudget;
		std::unordered_map<uint32_t, std::size_t> indexByIP;
		std::vector<Entry> entries;
		std::vector<std::size_t> freeSlots;
		std::size_t cleanupCursor = 0;
};

#endif
