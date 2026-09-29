/**
 * Tibia GIMUD Server - a free and open-source MMORPG server emulator
 * Copyright (C) 2017  Alejandro Mujica <alejandrodemujica@gmail.com>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 */

#ifndef FS_SQL_IDENTIFIER_H_79DD191B735F4890B0C9DC8350766619
#define FS_SQL_IDENTIFIER_H_79DD191B735F4890B0C9DC8350766619

#include <string>

inline std::string quoteSqlIdentifier(const std::string& identifier)
{
	std::string quoted;
	quoted.reserve(identifier.size() + 2);
	quoted.push_back('`');
	for (char character : identifier) {
		if (character == '`') {
			quoted.push_back('`');
		}
		quoted.push_back(character);
	}
	quoted.push_back('`');
	return quoted;
}

#endif
