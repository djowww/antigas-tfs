/**
 * Tibia GIMUD Server - a free and open-source MMORPG server emulator
 * Copyright (C) 2017  Alejandro Mujica <alejandrodemujica@gmail.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#ifndef FS_CONNECTION_QUEUE_H_6A1312FC77F647B0A4D4E7A5F478E803
#define FS_CONNECTION_QUEUE_H_6A1312FC77F647B0A4D4E7A5F478E803

#include <cstddef>
#include <atomic>

namespace ConnectionOutputQueue {
	// OutputMessage owns a fixed 65,500-byte buffer, so bound queued objects,
	// not just their serialized lengths. The active write is part of the queue.
	// The process-wide cap limits retained queue buffers to about 512 MiB.
	enum : std::size_t {
		MAX_PENDING_MESSAGES = 64,
		MAX_TOTAL_PENDING_MESSAGES = 8192
	};

	inline bool canQueue(std::size_t pendingMessages)
	{
		return pendingMessages < MAX_PENDING_MESSAGES;
	}

	inline std::atomic<std::size_t>& totalPendingMessages()
	{
		static std::atomic<std::size_t> pendingMessages(0);
		return pendingMessages;
	}

	inline bool tryReserve(std::size_t connectionPendingMessages)
	{
		if (!canQueue(connectionPendingMessages)) {
			return false;
		}

		auto& total = totalPendingMessages();
		std::size_t current = total.load(std::memory_order_relaxed);
		while (current < MAX_TOTAL_PENDING_MESSAGES) {
			if (total.compare_exchange_weak(current, current + 1,
								std::memory_order_acq_rel,
								std::memory_order_relaxed)) {
				return true;
			}
		}
		return false;
	}

	inline void release(std::size_t count = 1)
	{
		if (count != 0) {
			totalPendingMessages().fetch_sub(count, std::memory_order_acq_rel);
		}
	}
}

#endif
