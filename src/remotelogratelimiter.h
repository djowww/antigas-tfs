#pragma once

#include <algorithm>
#include <chrono>
#include <cstdint>
#include <limits>
#include <mutex>

class RemoteLogRateLimiter {
public:
	using Clock = std::chrono::steady_clock;

	RemoteLogRateLimiter(std::uint64_t maxMessagesPerWindow, Clock::duration refillWindow) :
		maxMessagesPerWindow(maxMessagesPerWindow),
		refillWindow(refillWindow > Clock::duration::zero() ? refillWindow : Clock::duration::max()),
		tokens(static_cast<double>(maxMessagesPerWindow)) {}

	bool allow(std::uint64_t& suppressedSincePreviousLog)
	{
		return allowAt(Clock::now(), suppressedSincePreviousLog);
	}

	bool allowAt(Clock::time_point now, std::uint64_t& suppressedSincePreviousLog)
	{
		std::lock_guard<std::mutex> lock(mutex);
		suppressedSincePreviousLog = 0;
		if (!initialized) {
			lastRefill = now;
			initialized = true;
		} else if (now > lastRefill) {
			const std::chrono::duration<double> elapsed(now - lastRefill);
			const std::chrono::duration<double> window(refillWindow);
			tokens = std::min(static_cast<double>(maxMessagesPerWindow),
			                  tokens + elapsed.count() * static_cast<double>(maxMessagesPerWindow) / window.count());
			lastRefill = now;
		}

		if (tokens < 1.0) {
			if (suppressedMessages != std::numeric_limits<std::uint64_t>::max()) {
				++suppressedMessages;
			}
			return false;
		}

		tokens -= 1.0;
		suppressedSincePreviousLog = suppressedMessages;
		suppressedMessages = 0;
		return true;
	}

private:
	const std::uint64_t maxMessagesPerWindow;
	const Clock::duration refillWindow;
	std::mutex mutex;
	Clock::time_point lastRefill;
	double tokens;
	std::uint64_t suppressedMessages = 0;
	bool initialized = false;
};

inline RemoteLogRateLimiter& remoteDiagnosticLogRateLimiter()
{
	static RemoteLogRateLimiter limiter(10, std::chrono::seconds(60));
	return limiter;
}
