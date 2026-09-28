#ifndef ANTIGAS_LOOT_H
#define ANTIGAS_LOOT_H

#include <cstdint>
#include <string>
#include <vector>

class Container;
class Item;
class Player;

struct LootEntry {
	uint16_t id;
	uint16_t count;
	uint8_t tier;
	std::string name;
};

struct LootContents {
	std::vector<LootEntry> items;
	uint32_t omitted = 0;
	uint8_t tier = 0;
};

// Dispatcher-only, transient corpse state. Never serialized into an item or database.
class LootTracker {
	public:
		static LootContents collect(const Container& corpse);
		static std::string notification(const Container& corpse, const LootContents& contents, const std::string& monsterName, uint64_t id, const Player& player);
		static uint64_t track(Container& corpse, const std::vector<uint32_t>& recipients, uint8_t tier);
		static uint64_t token(const Container* corpse);
		static bool eligible(const Container* corpse, uint32_t guid);
		static size_t size();
		static void forget(const Container* corpse);
		static void publish(Container& corpse, const std::string& monsterName);
		static void handleRequest(Player& player, const std::string& request);
		static void resetSession(Player& player);
		static void sync(Player& player, bool force = false);
		static void invalidate(Player& player, const Item* item);
		static void opened(Container& corpse);
};

#endif
