#include "otpch.h"
#include "groundrarity.h"
#include "game.h"
#include "player.h"
#include "tools.h"

extern Game g_game;

namespace {
constexpr uint8_t GROUND_RARITY_OPCODE = 129;
constexpr size_t MAX_VISIBLE_TILES = 256;
constexpr int64_t GROUND_RARITY_REQUEST_COOLDOWN_MS = 5000;

uint64_t tileKey(const Position& position)
{
	return (uint64_t(position.z) << 32) | (uint64_t(position.y) << 16) | position.x;
}

Position tilePosition(uint64_t key)
{
	return Position(uint16_t(key), uint16_t(key >> 16), uint8_t(key >> 32));
}
}

std::vector<GroundRarityEntry> GroundRarity::collect(const Tile& tile, const Player& player)
{
	std::vector<GroundRarityEntry> result;
	unsigned slots = 0;
	auto append = [&](const Item* item) {
		if (!item || slots >= 10) return;
		++slots;
		const unsigned tier = static_cast<unsigned>(item->getRarityTier());
		if (item->getParent() != &tile || !item->hasRarity() || tier < 1 || tier > 5) return;
		const int32_t stack = tile.getStackposOfItem(&player, item);
		if (stack < 0 || stack >= 10) return;
		const ItemType& type = Item::items[item->getID()];
		result.push_back({type.disguise ? type.disguiseId : type.id, uint8_t(stack), uint8_t(tier)});
	};
	// Match ProtocolGame::GetTileDescription's ten-item wire limit. Never walk
	// container contents or the unbounded tail of an overfilled ground stack.
	append(tile.getGround());
	const TileItemVector* items = tile.getItemList();
	if (items) {
		for (auto it = items->getBeginTopItem(); it != items->getEndTopItem() && slots < 10; ++it) append(*it);
	}
	if (const CreatureVector* creatures = tile.getCreatures()) {
		for (const Creature* creature : *creatures) {
			if (slots >= 10) break;
			if (player.canSeeCreature(creature)) ++slots;
		}
	}
	if (items) {
		for (auto it = items->getBeginDownItem(); it != items->getEndDownItem() && slots < 10; ++it) append(*it);
	}
	return result;
}

std::string GroundRarity::describe(const Position& position, const std::vector<GroundRarityEntry>& items)
{
	std::ostringstream out;
	out << "\"position\":{\"x\":" << position.x << ",\"y\":" << position.y << ",\"z\":" << unsigned(position.z) << "},\"items\":[";
	bool first = true;
	for (size_t i = 0; i < items.size() && i < 10; ++i) {
		const GroundRarityEntry& item = items[i];
		if (item.stackpos >= 10 || item.tier < 1 || item.tier > 5 || item.itemId == 0) continue;
		if (!first) out << ',';
		first = false;
		out << "{\"itemId\":" << item.itemId << ",\"stackpos\":" << unsigned(item.stackpos) << ",\"tier\":" << unsigned(item.tier) << '}';
	}
	out << ']';
	return out.str();
}

std::vector<Position> GroundRarity::stripPositions(const std::vector<GroundRarityMapStrip>& strips)
{
	std::set<Position> positions;
	// A walking packet has at most a horizontal and a vertical strip. Restrict
	// this path to their native dimensions instead of scanning the whole viewport.
	for (size_t i = 0; i < strips.size() && i < 2; ++i) {
		const GroundRarityMapStrip& strip = strips[i];
		if (strip.z < 0 || strip.z >= MAP_MAX_LAYERS || strip.width < 1 || strip.height < 1 ||
			strip.width > 2 * (MapViewport::maxRangeX + 1) || strip.height > 2 * (MapViewport::maxRangeY + 1) ||
			(strip.width != 1 && strip.height != 1)) continue;
		// Exactly the same floors and perspective offset as GetMapDescription.
		const int32_t first = strip.z > 7 ? strip.z - 2 : 7;
		const int32_t last = strip.z > 7 ? std::min<int32_t>(MAP_MAX_LAYERS - 1, strip.z + 2) : 0;
		const int32_t step = strip.z > 7 ? 1 : -1;
		for (int32_t z = first; z != last + step; z += step) {
			const int32_t offset = strip.z - z;
			for (int32_t nx = 0; nx < strip.width; ++nx) {
				for (int32_t ny = 0; ny < strip.height; ++ny) {
					const int64_t x = int64_t(strip.x) + nx + offset;
					const int64_t y = int64_t(strip.y) + ny + offset;
					if (x < 0 || x > 65535 || y < 0 || y > 65535) continue;
					positions.emplace(uint16_t(x), uint16_t(y), uint8_t(z));
				}
			}
		}
	}
	return {positions.begin(), positions.end()};
}

std::string GroundRarity::replaceTile(std::map<uint64_t, std::string>& cache, const Position& position, const std::vector<GroundRarityEntry>& items)
{
	const uint64_t key = tileKey(position);
	const auto previous = cache.find(key);
	if (items.empty()) {
		if (previous == cache.end()) return {};
		cache.erase(previous);
		return describe(position, {});
	}
	if (previous == cache.end() && cache.size() >= MAX_VISIBLE_TILES) return {};
	const std::string description = describe(position, items);
	cache[key] = description;
	// Native map strips recreate client Item objects even if their serialized
	// identity is unchanged. A fresh native frame always needs a fresh binding.
	return description;
}

std::vector<Position> GroundRarity::pruneCache(std::map<uint64_t, std::string>& cache, const std::function<bool(const Position&)>& visible)
{
	std::vector<Position> removed;
	for (auto it = cache.begin(); it != cache.end();) {
		const Position position = tilePosition(it->first);
		if (!visible(position)) {
			removed.push_back(position);
			it = cache.erase(it);
		} else {
			++it;
		}
	}
	return removed;
}

void GroundRarity::send(Player& player, const std::string& fields)
{
	const std::string json = "{\"seq\":" + std::to_string(++player.groundRaritySequence) + ',' + fields + '}';
	if (json.size() > 8192) return;
	NetworkMessage message;
	message.addByte(0x32);
	message.addByte(GROUND_RARITY_OPCODE);
	message.addString(json);
	player.sendNetworkMessage(message);
}

void GroundRarity::resetSession(Player& player)
{
	player.groundRarityProtocol = false;
	player.groundRaritySequence = 0;
	player.lastGroundRaritySync = 0;
	player.lastGroundRarityReplay = 0;
	player.lastGroundRarityRequest = 0;
	player.groundRarityTiles.clear();
}

void GroundRarity::resetMap(Player& player)
{
	if (!player.groundRarityProtocol) return;
	player.groundRarityTiles.clear();
	send(player, "\"event\":\"reset\"");
	sync(player, true);
}

void GroundRarity::handleRequest(Player& player, const std::string& request)
{
	if (request == "H|1" && !player.groundRarityProtocol) {
		player.groundRarityProtocol = true;
		send(player, "\"event\":\"ready\",\"version\":1");
		resetMap(player);
	} else if (request == "S|1" && player.groundRarityProtocol) {
		const int64_t now = OTSYS_TIME();
		if (now - player.lastGroundRarityRequest < GROUND_RARITY_REQUEST_COOLDOWN_MS) return;
		player.lastGroundRarityRequest = now;
		// The client asks for this replay when a native map refresh replaces an
		// Item object but preserves the same rare item on the same tile.
		sync(player, true);
	}
}

void GroundRarity::updateTile(Player& player, const Position& position)
{
	if (!player.groundRarityProtocol || !player.canSee(position)) return;
	const Tile* tile = g_game.map.getTile(position);
	const auto entries = tile ? collect(*tile, player) : std::vector<GroundRarityEntry>();
	const std::string description = replaceTile(player.groundRarityTiles, position, entries);
	if (!description.empty()) send(player, "\"event\":\"tile\"," + description);
}

void GroundRarity::refreshMapStrips(Player& player, const std::vector<GroundRarityMapStrip>& strips)
{
	if (!player.groundRarityProtocol) return;
	// Free slots before adding entering tiles, including a rapid out-and-back
	// movement that occurs before the periodic one-second housekeeping.
	for (const Position& position : pruneCache(player.groundRarityTiles, [&](const Position& pos) { return player.canSee(pos); })) {
		send(player, "\"event\":\"tile\"," + describe(position, {}));
	}
	for (const Position& position : stripPositions(strips)) updateTile(player, position);
}

void GroundRarity::sync(Player& player, bool force)
{
	const int64_t now = OTSYS_TIME();
	if (!player.groundRarityProtocol || !player.client || (!force && now - player.lastGroundRaritySync < 1000)) return;
	player.lastGroundRaritySync = now;
	const bool replay = force || now - player.lastGroundRarityReplay >= 5000;
	if (replay) player.lastGroundRarityReplay = now;
	std::map<uint64_t, std::string> visible;
	const Position& center = player.getPosition();
	const MapViewport& viewport = player.client->mapViewport;
	const int32_t first = center.z > 7 ? center.z - 2 : 7;
	const int32_t last = center.z > 7 ? std::min<int32_t>(MAP_MAX_LAYERS - 1, center.z + 2) : 0;
	const int32_t step = center.z > 7 ? 1 : -1;
	for (int32_t z = first; z != last + step && visible.size() < MAX_VISIBLE_TILES; z += step) {
		const int32_t offset = center.z - z;
		for (int32_t x = int32_t(center.x) - viewport.x + offset; x <= int32_t(center.x) + viewport.x + 1 + offset && visible.size() < MAX_VISIBLE_TILES; ++x) {
			for (int32_t y = int32_t(center.y) - viewport.y + offset; y <= int32_t(center.y) + viewport.y + 1 + offset && visible.size() < MAX_VISIBLE_TILES; ++y) {
				if (x < 0 || x > 65535 || y < 0 || y > 65535) continue;
				const Position position{uint16_t(x), uint16_t(y), uint8_t(z)};
				if (!player.canSee(position)) continue;
				const Tile* tile = g_game.map.getTile(position);
				if (!tile) continue;
				const auto entries = collect(*tile, player);
				if (!entries.empty()) visible.emplace(tileKey(position), describe(position, entries));
			}
		}
	}
	for (const auto& previous : player.groundRarityTiles) {
		if (visible.find(previous.first) == visible.end()) send(player, "\"event\":\"tile\"," + describe(tilePosition(previous.first), {}));
	}
	for (const auto& frame : visible) {
		const auto previous = player.groundRarityTiles.find(frame.first);
		if (replay || previous == player.groundRarityTiles.end() || previous->second != frame.second) send(player, "\"event\":\"tile\"," + frame.second);
	}
	player.groundRarityTiles.swap(visible);
}
