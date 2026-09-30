#include "connectionqueue.h"

#include <atomic>
#include <stdexcept>
#include <thread>
#include <vector>

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

void testAggregateOutputQueueLimit()
{
	require(ConnectionOutputQueue::totalPendingMessages().load() == 0,
				"aggregate queue should begin empty");
	for (std::size_t pending = 0; pending < ConnectionOutputQueue::MAX_PENDING_MESSAGES; ++pending) {
		require(ConnectionOutputQueue::tryReserve(pending),
				"a connection should reserve every available per-connection slot");
	}
	require(!ConnectionOutputQueue::tryReserve(ConnectionOutputQueue::MAX_PENDING_MESSAGES),
				"the per-connection limit should be enforced while reserving globally");
	ConnectionOutputQueue::release(ConnectionOutputQueue::MAX_PENDING_MESSAGES);

	for (std::size_t i = 0; i < ConnectionOutputQueue::MAX_TOTAL_PENDING_MESSAGES; ++i) {
		require(ConnectionOutputQueue::tryReserve(0),
				"aggregate reservations should fill exactly to their configured limit");
	}
	require(!ConnectionOutputQueue::tryReserve(0),
				"aggregate queue should reject a reservation at its configured limit");
	ConnectionOutputQueue::release(1);
	require(ConnectionOutputQueue::tryReserve(0),
				"released aggregate capacity should be reusable");
	require(ConnectionOutputQueue::totalPendingMessages().load() ==
				ConnectionOutputQueue::MAX_TOTAL_PENDING_MESSAGES,
				"aggregate count should stay at its hard upper bound");
	ConnectionOutputQueue::release(ConnectionOutputQueue::MAX_TOTAL_PENDING_MESSAGES);
	require(ConnectionOutputQueue::totalPendingMessages().load() == 0,
				"releasing all aggregate reservations should return the count to zero");
}

void testAggregateOutputQueueReservationsAreThreadSafe()
{
	std::atomic<std::size_t> acquired(0);
	std::vector<std::thread> workers;
	for (std::size_t i = 0; i < 32; ++i) {
		workers.emplace_back([&acquired]() {
			for (std::size_t attempt = 0; attempt < 1024; ++attempt) {
				if (ConnectionOutputQueue::tryReserve(0)) {
					++acquired;
				}
			}
		});
	}
	for (auto& worker : workers) {
		worker.join();
	}
	require(acquired.load() == ConnectionOutputQueue::MAX_TOTAL_PENDING_MESSAGES,
	        "concurrent reservations must stop exactly at the aggregate limit");
	require(ConnectionOutputQueue::totalPendingMessages().load() ==
	        ConnectionOutputQueue::MAX_TOTAL_PENDING_MESSAGES,
	        "concurrent reservations must preserve the aggregate count");
	ConnectionOutputQueue::release(ConnectionOutputQueue::MAX_TOTAL_PENDING_MESSAGES);
}
}

int main()
{
	try {
		testOutputQueueLimit();
		testAggregateOutputQueueLimit();
		testAggregateOutputQueueReservationsAreThreadSafe();
		return 0;
	} catch (const std::exception&) {
		return 1;
	}
}
