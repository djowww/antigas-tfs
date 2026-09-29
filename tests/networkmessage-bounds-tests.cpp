#include "otpch.h"
#include "networkmessage.h"

#include <stdexcept>

namespace {
void require(bool condition, const char* message)
{
	if (!condition) {
		throw std::runtime_error(message);
	}
}

void testValidSkipAndBacktrack()
{
	NetworkMessage message;
	message.setLength(16);
	message.getBuffer()[4] = 0xA5;

	message.skipBytes(1);
	require(message.getBufferPosition() == 5, "valid skip should advance the cursor");
	require(!message.isOverrun(), "valid skip should not mark overrun");
	require(message.getPreviousByte() == 0xA5, "backtracking should read the last skipped byte");
	require(message.getBufferPosition() == 4, "backtracking should restore the prior cursor");
	require(!message.isOverrun(), "valid backtracking should not mark overrun");
}

void testInvalidSkipsFailClosed()
{
	NetworkMessage negative;
	negative.setLength(16);
	negative.skipBytes(-1);
	require(negative.isOverrun(), "negative skip should mark overrun");
	require(negative.getBufferPosition() == NetworkMessage::INITIAL_BUFFER_POSITION, "negative skip must leave the cursor unchanged");

	NetworkMessage truncated;
	truncated.setLength(0);
	truncated.skipBytes(9);
	require(truncated.isOverrun(), "skip beyond available packet bytes should mark overrun");
	require(truncated.getBufferPosition() == NetworkMessage::INITIAL_BUFFER_POSITION, "truncated skip must leave the cursor unchanged");
}

void testInvalidBacktrackingFailsClosed()
{
	NetworkMessage message;
	message.setLength(16);
	require(message.getPreviousByte() == 0, "backtracking before the body should return zero");
	require(message.isOverrun(), "backtracking before the body should mark overrun");
	require(message.getBufferPosition() == NetworkMessage::INITIAL_BUFFER_POSITION, "invalid backtracking must not underflow the cursor");
}
}

int main()
{
	try {
		testValidSkipAndBacktrack();
		testInvalidSkipsFailClosed();
		testInvalidBacktrackingFailsClosed();
		return 0;
	} catch (const std::exception&) {
		return 1;
	}
}
