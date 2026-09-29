/**
 * Tibia GIMUD Server - a free and open-source MMORPG server emulator
 * Copyright (C) 2017  Alejandro Mujica <alejandrodemujica@gmail.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#ifndef FS_SCRIPT_FILENAME_H_71B394B62D2A4B7497E2ACF905E4E060
#define FS_SCRIPT_FILENAME_H_71B394B62D2A4B7497E2ACF905E4E060

#include <cstring>
#include <string>

template <std::size_t N>
inline void copyScriptFilename(char (&destination)[N], const std::string& filename)
{
	static_assert(N > 0, "script filename buffer must not be empty");
	const std::size_t length = filename.size() < N - 1 ? filename.size() : N - 1;
	if (length != 0) {
		std::memcpy(destination, filename.data(), length);
	}
	destination[length] = '\0';
}

#endif
