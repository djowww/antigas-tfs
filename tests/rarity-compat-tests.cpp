#include "otpch.h"
#include "game.h"
#include "configmanager.h"
#include "scheduler.h"
#include "databasetasks.h"
#include "rsa.h"
#include <stdexcept>

// Compile only against Git HEAD plus deploy/rarity-rollback-compat.patch.
// This fixture does not require or call the new rarity APIs.
DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;

static unsigned checks = 0;
static void require(bool success, const char* message)
{
	++checks;
	if (!success) {
		throw std::runtime_error(message);
	}
}

static uint16_t findType(const std::function<bool(const ItemType&)>& predicate)
{
	for (size_t id = 1; id < Item::items.size(); ++id) {
		const ItemType& type = Item::items[id];
		if (type.id && type.group != ITEM_GROUP_DEPRECATED && predicate(type)) {
			return type.id;
		}
	}
	throw std::runtime_error("missing item fixture category");
}

int main()
{
	try {
		require(Item::items.loadItems(), "item definitions must load");
		const uint16_t swordId = findType([](const ItemType& t) { return t.weaponType == WEAPON_SWORD && !t.stackable; });
		const uint16_t otherId = findType([swordId](const ItemType& t) { return t.id != swordId && t.weaponType == WEAPON_SWORD && !t.stackable; });
		const uint16_t bagId = findType([](const ItemType& t) { return t.isContainer() && (t.slotPosition & SLOTP_BACKPACK); });
		const uint32_t packedRarity = 5 | (6 << 8) | (5 << 16);
		Item* item = Item::CreateItem(swordId);
		item->setIntAttr(ITEM_ATTRIBUTE_RARITY, static_cast<int32_t>(packedRarity));
		item->setIntAttr(ITEM_ATTRIBUTE_ATTACK, 47);
		require(item->getAttack() == 47, "fallback must retain pre-rarity attack semantics");
		PropWriteStream written;
		item->serializeAttr(written);
		size_t size;
		const char* bytes = written.getStream(size);
		PropStream source;
		source.init(bytes, size);
		Item* restored = Item::CreateItem(swordId);
		require(restored->unserializeAttr(source), "fallback must accept persisted attribute 39");
		require(static_cast<uint32_t>(restored->getIntAttr(ITEM_ATTRIBUTE_RARITY)) == packedRarity, "opaque rarity payload must survive read");
		require(restored->getAttack() == 47, "reading rarity must not apply new gameplay effects");
		Item* cloned = restored->clone();
		require(cloned->equals(restored), "clone must preserve opaque rarity");
		delete cloned;
		delete restored;

		Container* bag = Item::CreateItem(bagId)->getContainer();
		bag->internalAddThing(item);
		ItemType& otherType = Item::items.getItemType(otherId);
		const ItemTypes_t originalType = otherType.type;
		otherType.type = ITEM_TYPE_KEY;
		Item* replacement = g_game.transformItem(item, otherId);
		require(replacement && replacement != item, "fixture must replace item instance");
		require(static_cast<uint32_t>(replacement->getIntAttr(ITEM_ATTRIBUTE_RARITY)) == packedRarity, "replacement transform must preserve opaque rarity");
		otherType.type = originalType;

		Item* charged = Item::CreateItem(swordId);
		charged->setIntAttr(ITEM_ATTRIBUTE_RARITY, static_cast<int32_t>(packedRarity));
		charged->setCharges(1);
		bag->internalAddThing(charged);
		ItemType& chargedType = Item::items.getItemType(swordId);
		const int32_t originalDecay = chargedType.decayTo;
		chargedType.decayTo = otherId;
		Item* expired = g_game.transformItem(charged, swordId, 0);
		require(expired && expired != charged, "zero charges fixture must replace item instance");
		require(static_cast<uint32_t>(expired->getIntAttr(ITEM_ATTRIBUTE_RARITY)) == packedRarity, "charge exhaustion must preserve opaque rarity");
		chargedType.decayTo = originalDecay;
		g_game.cleanup();
		delete bag;
		std::cout << "PASS: " << checks << " opaque rarity compatibility checks." << std::endl;
		return 0;
	} catch (const std::exception& error) {
		std::cerr << "FAIL: " << error.what() << std::endl;
		return 1;
	}
}
