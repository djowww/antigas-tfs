#include "connectionqueue.h"

#include <stdexcept>

namespace {
void require(bool condition, const char* message)
{
	if (!condition) {
		throw std::runtime_error(message);
	}
}

void testOutputQueueLimit()
{
	require(ConnectionOutputQueue::canQueue(0), "an empty connection queue should accept output");
	require(ConnectionOutputQueue::canQueue(ConnectionOutputQueue::MAX_PENDING_MESSAGES - 1),
	        "the last available queue slot should accept output");
	require(!ConnectionOutputQueue::canQueue(ConnectionOutputQueue::MAX_PENDING_MESSAGES),
	        "the queue should reject output at its configured bound");
	require(!ConnectionOutputQueue::canQueue(ConnectionOutputQueue::MAX_PENDING_MESSAGES + 1),
	        "the queue should remain rejected beyond its configured bound");
}
}

int main()
{
	try {
		testOutputQueueLimit();
		return 0;
	} catch (const std::exception&) {
		return 1;
	}
}
