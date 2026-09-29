#ifndef FS_STATUS_QUERY_RATE_LIMITER_H
#define FS_STATUS_QUERY_RATE_LIMITER_H

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <map>
#include <mutex>
#include <utility>

class StatusQueryRateLimiter
{
public:
	using Clock = std::chrono::steady_clock;
	enum { MAX_TRACKED_IPS = 65536, MAX_EXPIRATIONS_PER_CALL = 256 };

	bool allow(std::uint32_t ip, Clock::time_point now, std::chrono::milliseconds timeout)
	{
		if (timeout.count() < 0) {
			timeout = std::chrono::milliseconds::zero();
		}

		std::lock_guard<std::mutex> lock(mutex);
		std::size_t expiredCount = 0;
		// Process only a bounded prefix so one status packet cannot trigger a full-cache sweep.
		while (expiredCount < MAX_EXPIRATIONS_PER_CALL && !expiryOrder.empty() && expiryOrder.front().second + timeout <= now) {
			const auto expired = expiryOrder.front();
			expiryOrder.pop_front();

			auto lastSeenIt = lastSeen.find(expired.first);
			if (lastSeenIt != lastSeen.end() && lastSeenIt->second == expired.second) {
				lastSeen.erase(lastSeenIt);
			}
			++expiredCount;
		}

		auto lastSeenIt = lastSeen.find(ip);
		if (lastSeenIt != lastSeen.end() && now < lastSeenIt->second + timeout) {
			return false;
		}
		if (lastSeenIt == lastSeen.end() && lastSeen.size() >= static_cast<std::size_t>(MAX_TRACKED_IPS)) {
			return false;
		}

		lastSeen[ip] = now;
		expiryOrder.emplace_back(ip, now);
		return true;
	}

	std::size_t size() const
	{
		std::lock_guard<std::mutex> lock(mutex);
		return lastSeen.size();
	}

private:
	mutable std::mutex mutex;
	std::map<std::uint32_t, Clock::time_point> lastSeen;
	std::deque<std::pair<std::uint32_t, Clock::time_point>> expiryOrder;
};

#endif
