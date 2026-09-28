#ifndef ANTIGAS_GROUNDRARITY_H
#define ANTIGAS_GROUNDRARITY_H

#include <cstdint>
#include <functional>
#include <map>
#include <string>
#include <vector>
#include "position.h"

class Player;
class Tile;

struct GroundRarityEntry {
	uint16_t itemId;
	uint8_t stackpos;
	uint8_t tier;
};

struct GroundRarityMapStrip {
	int32_t x;
	int32_t y;
	int32_t z;
	int32_t width;
	int32_t height;
};

// All state belongs to the current player connection. Tile frames refer only to
// top-level native wire slots; no item pointers survive a dispatcher callback.
class GroundRarity {
	public:
		static std::vector<GroundRarityEntry> collect(const Tile& tile, const Player& player);
		static std::string describe(const Position& position, const std::vector<GroundRarityEntry>& items);
		static std::vector<Position> stripPositions(const std::vector<GroundRarityMapStrip>& strips);
		static std::string replaceTile(std::map<uint64_t, std::string>& cache, const Position& position, const std::vector<GroundRarityEntry>& items);
		static std::vector<Position> pruneCache(std::map<uint64_t, std::string>& cache, const std::function<bool(const Position&)>& visible);
		static void handleRequest(Player& player, const std::string& request);
		static void resetSession(Player& player);
		static void resetMap(Player& player);
		static void sync(Player& player, bool force = false);
		static void updateTile(Player& player, const Position& position);
		static void refreshMapStrips(Player& player, const std::vector<GroundRarityMapStrip>& strips);
	private:
		static void send(Player& player, const std::string& fields);
};

#endif
