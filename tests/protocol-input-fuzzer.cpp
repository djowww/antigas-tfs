#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <list>
#include <string>

#include "networkmessage.h"
#include "walkpathparser.h"

namespace {
class ExposedNetworkMessage : public NetworkMessage
{
	public:
		void setCursorPosition(MsgSize_t position) {
			info.position = position;
		}
};

uint16_t readU16(const uint8_t* data, size_t size, size_t offset)
{
	if (offset + 1 >= size) {
		return 0;
	}
	return static_cast<uint16_t>(static_cast<uint16_t>(data[offset])
		| static_cast<uint16_t>(data[offset + 1]) << 8);
}

void fuzzNetworkMessageBounds(const uint8_t* data, size_t size)
{
	const size_t copySize = std::min(size, static_cast<size_t>(NETWORKMESSAGE_MAXSIZE));
	const auto position = static_cast<NetworkMessage::MsgSize_t>(readU16(data, size, 2));

	ExposedNetworkMessage exposed;
	std::memset(exposed.getBuffer(), 0, NETWORKMESSAGE_MAXSIZE);
	if (copySize != 0) {
		std::memcpy(exposed.getBuffer(), data, copySize);
	}
	exposed.setLength(readU16(data, size, 0));
	exposed.setCursorPosition(position);
	(void)exposed.isReadPositionValid();
	(void)exposed.getPreviousByte();

	const int16_t skip = size > 4 ? static_cast<int8_t>(data[4]) : 0;
	exposed.skipBytes(skip);
	(void)exposed.getByte();
	(void)exposed.isReadPositionValid();
}

void fuzzWalkingPath(const uint8_t* data, size_t size)
{
	const size_t cappedSize = std::min(size, static_cast<size_t>(NETWORKMESSAGE_MAXSIZE));
	const uint16_t directionCount = readU16(data, cappedSize, 0);
	const uint8_t cursorOffset = cappedSize > 2 ? data[2] : 0;
	const size_t payloadSize = cappedSize > 3
		? std::min(cappedSize - 3, static_cast<size_t>(NETWORKMESSAGE_MAXSIZE - NetworkMessage::INITIAL_BUFFER_POSITION))
		: 0;

	ExposedNetworkMessage message;
	std::memset(message.getBuffer(), 0, NETWORKMESSAGE_MAXSIZE);
	message.setLength(static_cast<NetworkMessage::MsgSize_t>(payloadSize));
	message.setCursorPosition(static_cast<NetworkMessage::MsgSize_t>(
		NetworkMessage::INITIAL_BUFFER_POSITION + cursorOffset));
	if (payloadSize != 0) {
		std::memcpy(message.getBuffer() + NetworkMessage::INITIAL_BUFFER_POSITION, data + 3, payloadSize);
	}

	std::list<Direction> path;
	const bool accepted = parseNewWalkingPath(message, directionCount, path);
	if (accepted) {
		if (message.isOverrun() || path.empty() || path.size() > directionCount
			|| cursorOffset > payloadSize || path.size() > payloadSize - cursorOffset) {
			std::abort();
		}
		for (Direction direction : path) {
			if (direction > DIRECTION_LAST) {
				std::abort();
			}
		}
	} else if (!path.empty()) {
		std::abort();
	}
}
}

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size)
{
	fuzzNetworkMessageBounds(data, size);
	fuzzWalkingPath(data, size);
	return 0;
}
