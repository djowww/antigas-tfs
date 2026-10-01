#include "remotelogratelimiter.h"
#include "clientassertionpolicy.h"

#include <atomic>
#include <cstdint>
#include <iostream>
#include <limits>
#include <stdexcept>
#include <thread>
#include <vector>

RemoteLogRateLimiter& remoteLogRateLimiterFromSecondTranslationUnit();

namespace {
using Clock = RemoteLogRateLimiter::Clock;

Clock::time_point at(std::int64_t milliseconds)
{
	return Clock::time_point(std::chrono::milliseconds(milliseconds));
}

void require(bool condition, const char* message)
{
	if (!condition) {
		throw std::runtime_error(message);
	}
}

void testBurstAndRefill()
{
	RemoteLogRateLimiter limiter(2, std::chrono::seconds(1));
	std::uint64_t suppressed = 0;
	require(limiter.allowAt(at(0), suppressed) && suppressed == 0, "first log should be allowed without suppressed count");
	require(limiter.allowAt(at(0), suppressed) && suppressed == 0, "burst capacity should allow the second log");
	require(!limiter.allowAt(at(0), suppressed), "burst beyond capacity should be suppressed");
	require(!limiter.allowAt(at(100), suppressed), "logs should remain suppressed before token refill");
	require(limiter.allowAt(at(600), suppressed) && suppressed == 2, "refilled token should report suppressed logs");
	require(!limiter.allowAt(at(600), suppressed), "consumed token should not be reused");
	require(limiter.allowAt(at(1200), suppressed) && suppressed == 1, "limiter should refill at the configured rate");
}

void testConcurrentCallsStayWithinBurstCapacity()
{
	RemoteLogRateLimiter limiter(64, std::chrono::minutes(1));
	std::atomic<std::uint64_t> allowed(0);
	std::vector<std::thread> workers;
	for (std::size_t i = 0; i < 16; ++i) {
		workers.emplace_back([&limiter, &allowed]() {
			for (std::size_t attempt = 0; attempt < 100; ++attempt) {
				std::uint64_t suppressed = 0;
				if (limiter.allowAt(at(0), suppressed)) {
					++allowed;
				}
			}
		});
	}
	for (auto& worker : workers) {
		worker.join();
	}
	require(allowed.load() == 64, "concurrent writers must not exceed the shared log burst capacity");
}

void testProcessLimiterIsSharedAcrossTranslationUnits()
{
	RemoteLogRateLimiter& first = remoteDiagnosticLogRateLimiter();
	RemoteLogRateLimiter& second = remoteLogRateLimiterFromSecondTranslationUnit();
	require(&first == &second, "inline accessor must return one process-wide limiter across translation units");

	std::uint64_t suppressed = 0;
	for (std::size_t i = 0; i < 10; ++i) {
		require(first.allowAt(at(0), suppressed), "global limiter should allow its configured initial burst");
	}
	require(!second.allowAt(at(0), suppressed), "second translation unit must share the consumed burst capacity");
}

void testClientAssertionPayloadAndFileLimits()
{
	std::uint64_t payloadBytes = 0;
	require(ClientAssertionPolicy::getPayloadBytes(2048, 2048, 2048, 2048, payloadBytes) && payloadBytes == 8192,
	        "payload at the aggregate byte limit should be accepted");
	require(!ClientAssertionPolicy::getPayloadBytes(2049, 2048, 2048, 2048, payloadBytes),
	        "payload above the aggregate byte limit should be rejected");
	require(!ClientAssertionPolicy::getPayloadBytes(0, 0, 0, 0, payloadBytes), "empty assertion should be rejected");

	const std::uint64_t fileLimit = 16 * 1024 * 1024;
	const std::uint64_t reservedOverhead = 256;
	const std::uint64_t encodedPayload = payloadBytes * 2;
	require(ClientAssertionPolicy::canAppend(0, payloadBytes), "valid report should fit in an empty assertion log");
	require(ClientAssertionPolicy::canAppend(fileLimit - reservedOverhead - encodedPayload, payloadBytes),
	        "report should fit exactly within the file-size budget");
	require(!ClientAssertionPolicy::canAppend(fileLimit - reservedOverhead - encodedPayload + 1, payloadBytes),
	        "report should be rejected if it would exceed the file-size budget");
	require(!ClientAssertionPolicy::canAppend(std::numeric_limits<std::uint64_t>::max(), payloadBytes),
	        "invalidly large existing file size should be rejected");
}
}

int main()
{
	testBurstAndRefill();
	testConcurrentCallsStayWithinBurstCapacity();
	testProcessLimiterIsSharedAcrossTranslationUnits();
	testClientAssertionPayloadAndFileLimits();
	std::cout << "Remote log rate limiter tests passed." << std::endl;
	return 0;
}
