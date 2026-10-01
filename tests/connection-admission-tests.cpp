#include "connectionadmission.h"
#include "connectionattemptlimiter.h"
#include "connectionratelimit.h"

#include <atomic>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <thread>
#include <vector>

namespace {
void require(bool condition, const char* message)
{
	if (!condition) {
		std::cerr << "FAIL: " << message << std::endl;
		std::exit(1);
	}
}

void testPerAddressAndGlobalLimits()
{
	ConnectionAdmission admission(3, 2);
	require(admission.tryAcquire(10), "first connection from an address should fit");
	require(admission.tryAcquire(10), "second connection from an address should fit");
	require(!admission.tryAcquire(10), "per-address limit should reject another connection");
	require(admission.tryAcquire(20), "another address should use remaining global capacity");
	require(!admission.tryAcquire(30), "global limit should reject an additional address");
	require(admission.getActiveConnections() == 3, "rejections must not change the active count");
	require(admission.getConnectionsForIP(10) == 2, "per-address count should match acquisitions");
	require(!admission.release(30), "release for an unknown address must not change counts");
	require(admission.release(10), "release should free an acquired address slot");
	require(admission.tryAcquire(30), "released global capacity should be reusable");
	require(admission.getActiveConnections() == 3, "global count should remain bounded after reuse");

	admission.clear();
	require(admission.getActiveConnections() == 0, "clear should reset the global count");
	require(admission.getConnectionsForIP(10) == 0, "clear should reset per-address counts");
	require(!admission.tryAcquire(0), "an invalid address must not consume capacity");
}

void testLoweredLimitsDoNotForgetExistingConnections()
{
	ConnectionAdmission admission(8, 8);
	require(admission.tryAcquire(10), "setup acquisition should succeed");
	require(admission.tryAcquire(10), "setup acquisition should succeed");
	admission.setLimits(2, 1);
	require(!admission.tryAcquire(10), "lowered per-address limit should reject new connections");
	require(!admission.tryAcquire(20), "lowered global limit should reject new connections while full");
	require(admission.getActiveConnections() == 2, "lowering limits must not discard active reservations");
	require(admission.release(10), "existing reservation should still release after a limit change");
	require(admission.tryAcquire(20), "capacity should become available after existing connections close");
}

void testConcurrentPerAddressLimit()
{
	ConnectionAdmission admission(64, 16);
	std::atomic<std::size_t> acquired(0);
	std::vector<std::thread> workers;
	for (std::size_t i = 0; i < 32; ++i) {
		workers.emplace_back([&admission, &acquired]() {
			for (std::size_t attempt = 0; attempt < 100; ++attempt) {
				if (admission.tryAcquire(42)) {
					++acquired;
				}
			}
		});
	}
	for (auto& worker : workers) {
		worker.join();
	}
	require(acquired.load() == 16, "concurrent acquisitions must respect the per-address limit");
	require(admission.getActiveConnections() == 16, "concurrent acquisitions must preserve the global count");

	std::atomic<std::size_t> released(0);
	workers.clear();
	for (std::size_t i = 0; i < 32; ++i) {
		workers.emplace_back([&admission, &released]() {
			for (std::size_t attempt = 0; attempt < 2; ++attempt) {
				if (admission.release(42)) {
					++released;
				}
			}
		});
	}
	for (auto& worker : workers) {
		worker.join();
	}
	require(released.load() == 16, "concurrent releases must not underflow the address count");
	require(admission.getActiveConnections() == 0, "all acquired capacity should be released");
}

void testDefaultLimitsPreserveConfiguredPlayers()
{
	require(ConnectionAdmissionSettings::defaultMaxConnections(2000) == 2256,
	        "default should preserve maxPlayers with 256 login slots");
	require(ConnectionAdmissionSettings::defaultMaxConnections(0) == 4096,
	        "unlimited maxPlayers should still receive a finite connection ceiling");
	require(ConnectionAdmissionSettings::defaultMaxConnections(2147483647) == 2147483647,
	        "default calculation must not overflow int32");
}

void testConnectionAttemptLimiterHasBoundedExpiringState()
{
	ConnectionAttemptLimiter limiter(2, 1);
	require(limiter.allow(10, 100), "first source address should be tracked");
	require(limiter.allow(20, 100), "second source address should fit the bounded table");
	require(limiter.getTrackedCount() == 2, "tracking state must not exceed its capacity");
	require(!limiter.allow(30, 101), "new addresses should be rejected when no slot is available");
	require(limiter.getTrackedCount() == limiter.getCapacity(), "rejections must not grow tracking state");
	require(limiter.allow(30, 5101), "an expired slot should be reclaimed for a new source address");
	require(limiter.getTrackedCount() == limiter.getCapacity(), "reclaimed tracking state should remain bounded");
	require(!limiter.allow(0, 5101), "invalid source addresses must not consume limiter state");
}

void testConnectionAttemptLimiterClockIsMonotonic()
{
	const uint64_t first = ConnectionAttemptLimiter::getMonotonicTimeMs();
	const uint64_t second = ConnectionAttemptLimiter::getMonotonicTimeMs();
	require(second >= first, "limiter clock must not move backwards");
}

void testConnectionAttemptLimiterDelaysRapidReconnects()
{
	ConnectionAttemptLimiter limiter(8, 2);
	require(limiter.allow(10, 1000), "first connection attempt should pass");
	for (uint64_t timestamp = 1100; timestamp <= 1400; timestamp += 100) {
		require(limiter.allow(10, timestamp), "first five rapid attempts should pass");
	}
	require(!limiter.allow(10, 1500), "sixth rapid attempt should start a temporary block");
	require(!limiter.allow(10, 2000), "attempt during the temporary block should remain rejected");
	require(limiter.allow(10, 4751), "attempt after the block should pass again");
}

void testPacketRateLimitConfigurationIsValid()
{
	require(ConnectionRateLimitSettings::isValidMaxPacketsPerSecond(1), "minimum positive packet rate should be valid");
	require(ConnectionRateLimitSettings::isValidMaxPacketsPerSecond(50), "ordinary packet rate should be valid");
	require(ConnectionRateLimitSettings::isValidMaxPacketsPerSecond(std::numeric_limits<int32_t>::max()),
	        "largest representable packet rate should remain configurable");
	require(!ConnectionRateLimitSettings::isValidMaxPacketsPerSecond(0), "zero packet rate should be rejected");
	require(!ConnectionRateLimitSettings::isValidMaxPacketsPerSecond(-1), "negative packet rate should be rejected");
	require(!ConnectionRateLimitSettings::isValidMaxPacketsPerSecond(1.5), "fractional packet rate should be rejected");
	require(!ConnectionRateLimitSettings::isValidMaxPacketsPerSecond(std::numeric_limits<double>::infinity()),
	        "infinite packet rate should be rejected");
	require(!ConnectionRateLimitSettings::isValidMaxPacketsPerSecond(std::numeric_limits<double>::quiet_NaN()),
	        "NaN packet rate should be rejected");
	require(!ConnectionRateLimitSettings::isValidMaxPacketsPerSecond(static_cast<double>(std::numeric_limits<int32_t>::max()) + 1),
	        "packet rate outside the stored integer range should be rejected");
}
}

int main()
{
	testPerAddressAndGlobalLimits();
	testLoweredLimitsDoNotForgetExistingConnections();
	testConcurrentPerAddressLimit();
	testDefaultLimitsPreserveConfiguredPlayers();
	testConnectionAttemptLimiterHasBoundedExpiringState();
	testConnectionAttemptLimiterDelaysRapidReconnects();
	testConnectionAttemptLimiterClockIsMonotonic();
	testPacketRateLimitConfigurationIsValid();
	std::cout << "Connection admission tests passed." << std::endl;
	return 0;
}
