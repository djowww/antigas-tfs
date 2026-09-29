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

namespace ConnectionOutputQueue {
	// OutputMessage owns a fixed 65,500-byte buffer, so bound queued objects,
	// not just their serialized lengths. The active write is part of the queue.
	enum : std::size_t { MAX_PENDING_MESSAGES = 64 };

	inline bool canQueue(std::size_t pendingMessages)
	{
		return pendingMessages < MAX_PENDING_MESSAGES;
	}
}

#endif
