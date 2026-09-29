#include "statusqueryratelimiter.h"

#include <atomic>
#include <chrono>
#include <cstdint>
#include <exception>
#include <iostream>
#include <stdexcept>
#include <thread>
#include <vector>

namespace {
using Clock = StatusQueryRateLimiter::Clock;
using Milliseconds = std::chrono::milliseconds;

Clock::time_point at(std::int64_t milliseconds)
{
	return Clock::time_point(Milliseconds(milliseconds));
}

void require(bool condition, const char* message)
{
	if (!condition) {
		throw std::runtime_error(message);
	}
}

void testTimeoutBoundary()
{
	StatusQueryRateLimiter limiter;
	const Milliseconds timeout(5000);
	require(limiter.allow(7, at(100), timeout), "first status query should be accepted");
	require(!limiter.allow(7, at(5099), timeout), "query inside the timeout must be rejected");
	require(limiter.allow(7, at(5100), timeout), "query at timeout expiry should be accepted");
	require(limiter.size() == 1, "expired entry should be replaced");
}

void testExpiredEntriesAreReclaimed()
{
	StatusQueryRateLimiter limiter;
	const Milliseconds timeout(5000);
	for (std::uint32_t ip = 1; ip <= 10000; ++ip) {
		require(limiter.allow(ip, at(0), timeout), "first query for each IP should be accepted");
	}
	require(limiter.size() == 10000, "all recent IPs should be tracked");
	require(limiter.allow(10001, at(5000), timeout), "new query after expiry should be accepted");
	const std::size_t expectedAfterOneBatch = 10000u - StatusQueryRateLimiter::MAX_EXPIRATIONS_PER_CALL + 1u;
	require(limiter.size() == expectedAfterOneBatch, "one request must perform only its bounded cleanup batch");
	for (std::uint32_t request = 1; request < 40; ++request) {
		require(limiter.allow(10001 + request, at(5000), timeout), "new query after expiry should be accepted");
	}
	require(limiter.size() == 40, "expired IP entries should be reclaimed over bounded batches");
	require(limiter.allow(1, at(5000), timeout), "an expired IP should be accepted after batch cleanup");
}

void testNonpositiveTimeout()
{
	StatusQueryRateLimiter limiter;
	require(limiter.allow(1, at(0), Milliseconds(0)), "zero timeout should allow a query");
	require(limiter.allow(1, at(0), Milliseconds(0)), "zero timeout should not block repeated queries");
	require(limiter.size() == 1, "zero timeout should not retain stale duplicate entries");
	require(limiter.allow(2, at(0), Milliseconds(-1)), "negative timeout should be treated as zero");
	require(limiter.size() == 1, "negative timeout should reclaim prior entries");
}

void testCapacityIsBoundedAndRecoversAfterExpiry()
{
	StatusQueryRateLimiter limiter;
	const Milliseconds timeout(5000);
	const std::uint32_t maxTrackedIps = static_cast<std::uint32_t>(StatusQueryRateLimiter::MAX_TRACKED_IPS);
	const std::size_t maxTrackedCount = static_cast<std::size_t>(maxTrackedIps);
	for (std::uint32_t ip = 1; ip <= maxTrackedIps; ++ip) {
		require(limiter.allow(ip, at(0), timeout), "addresses below the cache cap should be accepted");
	}
	require(limiter.size() == maxTrackedCount, "the cache should stop at its fixed capacity");
	require(!limiter.allow(maxTrackedIps + 1, at(1), timeout), "a new address must be refused at capacity inside the active window");
	require(limiter.allow(1, at(5000), timeout), "expired cached addresses should be reclaimable at capacity");
	require(limiter.size() < maxTrackedCount, "bounded cleanup should free cache capacity");
	require(limiter.allow(maxTrackedIps + 1, at(5000), timeout), "a new address should be accepted after expired entries are pruned");
}

void testConcurrentAccess()
{
	StatusQueryRateLimiter limiter;
	const Milliseconds timeout(5000);
	std::atomic<std::size_t> accepted(0);
	std::vector<std::thread> workers;
	for (std::uint32_t worker = 0; worker < 8; ++worker) {
		workers.emplace_back([worker, &limiter, &accepted, timeout]() {
			for (std::uint32_t i = 0; i < 1000; ++i) {
				if (limiter.allow(worker * 1000 + i + 1, at(100), timeout)) {
					++accepted;
				}
			}
		});
	}
	for (auto& worker : workers) {
		worker.join();
	}
	require(accepted == 8000, "concurrent requests from distinct IPs should be accepted");
	require(limiter.size() == 8000, "concurrent cache updates should not be lost");
	StatusQueryRateLimiter sameAddressLimiter;
	std::atomic<std::size_t> sameAddressAccepted(0);
	workers.clear();
	for (std::uint32_t worker = 0; worker < 8; ++worker) {
		workers.emplace_back([&sameAddressLimiter, &sameAddressAccepted, timeout]() {
			if (sameAddressLimiter.allow(42, at(100), timeout)) {
				++sameAddressAccepted;
			}
		});
	}
	for (auto& worker : workers) {
		worker.join();
	}
	require(sameAddressAccepted == 1, "concurrent requests from one IP must preserve the rate limit");
	require(sameAddressLimiter.size() == 1, "one source IP must create only one cache entry");
}
}

int main()
{
	try {
		testTimeoutBoundary();
		testExpiredEntriesAreReclaimed();
		testNonpositiveTimeout();
		testCapacityIsBoundedAndRecoversAfterExpiry();
		testConcurrentAccess();
		std::cout << "Status query rate limiter tests passed." << std::endl;
		return 0;
	} catch (const std::exception& error) {
		std::cerr << error.what() << std::endl;
		return 1;
	}
}
