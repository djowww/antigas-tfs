#pragma once

#include <cmath>
#include <cstdint>
#include <limits>

class ConnectionRateLimitSettings {
public:
	static bool isValidMaxPacketsPerSecond(double value)
	{
		return std::isfinite(value) && value >= 1 && value <= std::numeric_limits<int32_t>::max() && std::floor(value) == value;
	}
};
