#pragma once

#include "remotelogratelimiter.h"

#include <cstddef>
#include <cstdint>

class ClientAssertionPolicy {
public:
	static bool getPayloadBytes(std::size_t assertLine, std::size_t date, std::size_t description, std::size_t comment,
	                            std::uint64_t& payloadBytes)
	{
		const std::size_t sizes[] = {assertLine, date, description, comment};
		std::size_t total = 0;
		for (std::size_t size : sizes) {
			if (size > maxPayloadBytes() - total) {
				return false;
			}
			total += size;
		}
		if (total == 0) {
			return false;
		}
		payloadBytes = total;
		return true;
	}

	static bool canAppend(std::uint64_t currentFileBytes, std::uint64_t payloadBytes)
	{
		const std::uint64_t maximumFileBytes = 16 * 1024 * 1024;
		const std::uint64_t maximumRecordOverheadBytes = 256;
		if (payloadBytes == 0 || payloadBytes > maxPayloadBytes() || currentFileBytes > maximumFileBytes - maximumRecordOverheadBytes) {
			return false;
		}
		const std::uint64_t maximumEncodedPayloadBytes = payloadBytes * 2;
		return maximumEncodedPayloadBytes <= maximumFileBytes - maximumRecordOverheadBytes - currentFileBytes;
	}

private:
	static std::size_t maxPayloadBytes()
	{
		return 8 * 1024;
	}
};

inline RemoteLogRateLimiter& clientAssertionWriteRateLimiter()
{
	static RemoteLogRateLimiter limiter(10, std::chrono::seconds(60));
	return limiter;
}
