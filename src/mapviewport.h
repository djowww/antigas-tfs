#ifndef ANTIGAS_MAPVIEWPORT_H
#define ANTIGAS_MAPVIEWPORT_H

#include <algorithm>
#include <cstdint>

// OTCv8 range excludes the extra east/south row. Visible odd dimensions are
// wire range - 1; the transmitted map includes a margin for walking/floors.
struct MapViewport {
	static constexpr int32_t maxRangeX = 15; // at most 29 visible columns
	static constexpr int32_t maxRangeY = 8;  // at most 15 visible rows
	int32_t x = 8;
	int32_t y = 6;

	int32_t width() const { return 2 * (x + 1); }
	int32_t height() const { return 2 * (y + 1); }
	void set(uint8_t requestedX, uint8_t requestedY) {
		x = std::max<int32_t>(8, std::min<int32_t>(int32_t(maxRangeX), requestedX / 2));
		y = std::max<int32_t>(6, std::min<int32_t>(int32_t(maxRangeY), requestedY / 2));
	}
};

#endif
