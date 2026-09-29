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
 * with this program. If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef FS_WALKPATHPARSER_H_5AA5969B48A84BCF835E41AB8EF0420C
#define FS_WALKPATHPARSER_H_5AA5969B48A84BCF835E41AB8EF0420C

#include <cmath>
#include <cstdint>
#include <list>

#include "networkmessage.h"
#include "position.h"

inline bool parseNewWalkingPath(NetworkMessage& msg, uint16_t numdirs, std::list<Direction>& path)
{
	const uint32_t packetEnd = static_cast<uint32_t>(msg.getLength()) + NetworkMessage::INITIAL_BUFFER_POSITION;
	const uint32_t position = msg.getBufferPosition();
	if (msg.isOverrun() || numdirs == 0 || numdirs > 4096 || position > packetEnd || numdirs > packetEnd - position) {
		return false;
	}

	for (uint16_t i = 0; i < numdirs; ++i) {
		const uint8_t rawdir = msg.getByte();
		switch (rawdir) {
			case 1: path.push_back(DIRECTION_EAST); break;
			case 2: path.push_back(DIRECTION_NORTHEAST); break;
			case 3: path.push_back(DIRECTION_NORTH); break;
			case 4: path.push_back(DIRECTION_NORTHWEST); break;
			case 5: path.push_back(DIRECTION_WEST); break;
			case 6: path.push_back(DIRECTION_SOUTHWEST); break;
			case 7: path.push_back(DIRECTION_SOUTH); break;
			case 8: path.push_back(DIRECTION_SOUTHEAST); break;
			default: break;
		}
	}

	if (msg.isOverrun() || path.empty()) {
		path.clear();
		return false;
	}

	return true;
}

#endif // FS_WALKPATHPARSER_H_5AA5969B48A84BCF835E41AB8EF0420C
