#include "otpch.h"
#include "walkpathparser.h"

#include <stdexcept>

namespace {
class ExposedNetworkMessage : public NetworkMessage
{
	public:
		void setCursorPosition(MsgSize_t position) {
			info.position = position;
		}
};

void require(bool condition, const char* message)
{
	if (!condition) {
		throw std::runtime_error(message);
	}
}

void testValidDirections()
{
	ExposedNetworkMessage message;
	message.setLength(3);
	message.setCursorPosition(NetworkMessage::INITIAL_BUFFER_POSITION + 1);
	message.getBuffer()[NetworkMessage::INITIAL_BUFFER_POSITION + 1] = 1;
	message.getBuffer()[NetworkMessage::INITIAL_BUFFER_POSITION + 2] = 8;
	std::list<Direction> path;
	require(parseNewWalkingPath(message, 2, path), "valid directions should be accepted");
	require(path.size() == 2, "valid direction count should be preserved");
	require(path.front() == DIRECTION_EAST && path.back() == DIRECTION_SOUTHEAST, "direction mapping should be preserved");
}

void testTruncatedDirections()
{
	ExposedNetworkMessage message;
	message.setLength(1);
	message.setCursorPosition(NetworkMessage::INITIAL_BUFFER_POSITION + 1);
	message.getBuffer()[NetworkMessage::INITIAL_BUFFER_POSITION + 1] = 1;
	std::list<Direction> path;
	require(!parseNewWalkingPath(message, 1, path), "truncated direction bytes should be rejected");
	require(path.empty(), "truncated paths should not be dispatched partially");
}

void testInvalidAndEmptyPaths()
{
	ExposedNetworkMessage invalid;
	invalid.setLength(2);
	invalid.setCursorPosition(NetworkMessage::INITIAL_BUFFER_POSITION + 1);
	invalid.getBuffer()[NetworkMessage::INITIAL_BUFFER_POSITION + 1] = 0;
	std::list<Direction> path;
	require(!parseNewWalkingPath(invalid, 1, path), "an all-invalid direction list should be rejected");
	require(path.empty(), "invalid directions must not produce an empty dispatched path");

	ExposedNetworkMessage empty;
	empty.setLength(0);
	empty.setCursorPosition(NetworkMessage::INITIAL_BUFFER_POSITION);
	require(!parseNewWalkingPath(empty, 0, path), "zero directions should be rejected");
}

void testDirectionCountLimit()
{
	ExposedNetworkMessage message;
	message.setLength(4097);
	message.setCursorPosition(NetworkMessage::INITIAL_BUFFER_POSITION + 1);
	std::list<Direction> path;
	require(!parseNewWalkingPath(message, 4097, path), "direction counts over 4096 should be rejected");
	require(path.empty(), "over-limit paths should remain empty");
}
}

int main()
{
	try {
		testValidDirections();
		testTruncatedDirections();
		testInvalidAndEmptyPaths();
		testDirectionCountLimit();
		return 0;
	} catch (const std::exception&) {
		return 1;
	}
}
