#include "otpch.h"
#include "loot.h"
#include "game.h"
#include "player.h"
#include "container.h"
#include "party.h"
#include "tools.h"

extern Game g_game;

namespace {
constexpr uint8_t LOOT_OPCODE = 128;
constexpr uint16_t LOOT_CHANNEL = 10;
constexpr size_t MAX_TRACKED = 4096;
constexpr size_t MAX_VISIBLE = 256;
constexpr int64_t MAX_AGE = 30 * 60 * 1000;

struct TrackedCorpse {
	uint64_t id;
	int64_t created;
	uint8_t tier;
	std::vector<uint32_t> recipients;
};

std::map<const Container*, TrackedCorpse>& corpses()
{
	// Container destructors can run during global shutdown. Keep the index alive.
	static auto* index = new std::map<const Container*, TrackedCorpse>();
	return *index;
}

uint64_t nextToken()
{
	static uint64_t counter = 0;
	return ++counter;
}

std::string quoted(const std::string& value, size_t limit)
{
	std::ostringstream out;
	out << '"';
	const char* hex = "0123456789abcdef";
	for (size_t i = 0; i < value.size() && i < limit; ++i) {
		const unsigned char c = value[i];
		if (c == '"' || c == '\\') {
			out << '\\' << c;
		} else if (c < 32 || c >= 127) {
			// Game item names are Latin-1, while the JSON transport is UTF-8.
			out << "\\u00" << hex[c >> 4] << hex[c & 15];
		} else {
			out << c;
		}
	}
	out << '"';
	return out.str();
}

uint16_t clientId(const Item& item)
{
	const ItemType& type = Item::items[item.getID()];
	return type.disguise ? type.disguiseId : type.id;
}

void send(Player& player, const std::string& json)
{
	if (json.size() > 8192) {
		return;
	}
	NetworkMessage message;
	message.addByte(0x32);
	message.addByte(LOOT_OPCODE);
	message.addString(json);
	player.sendNetworkMessage(message);
}

std::string identity(const Container& corpse, const TrackedCorpse& tracked, const Player& player)
{
	const Tile* tile = dynamic_cast<const Tile*>(corpse.getParent());
	const Position& position = corpse.getPosition();
	const int32_t stack = tile && player.canSee(position) ? tile->getStackposOfItem(&player, &corpse) : -1;
	std::ostringstream out;
	out << "\"id\":\"" << tracked.id << "\",\"position\":{\"x\":" << position.x
		<< ",\"y\":" << position.y << ",\"z\":" << unsigned(position.z)
		<< "},\"corpseId\":" << clientId(corpse) << ",\"stackpos\":" << stack
		<< ",\"tier\":" << unsigned(tracked.tier) << ",\"unopened\":" << (stack >= 0 ? "true" : "false");
	return out.str();
}

void prune()
{
	const int64_t now = OTSYS_TIME();
	for (auto it = corpses().begin(); it != corpses().end();) {
		if (now - it->second.created >= MAX_AGE) {
			it = corpses().erase(it);
		} else {
			++it;
		}
	}
}
}

LootContents LootTracker::collect(const Container& corpse)
{
	LootContents result;
	for (ContainerIterator it = corpse.iterator(); it.hasNext(); it.advance()) {
		const Item* item = *it;
		const Container* child = item->getContainer();
		if (child && !child->empty()) {
			continue;
		}
		const uint8_t tier = item->hasRarity() ? static_cast<uint8_t>(item->getRarityTier()) : 0;
		result.tier = std::max(result.tier, tier);
		if (result.items.size() == 128) {
			++result.omitted;
			continue;
		}
		result.items.push_back({clientId(*item), item->getItemCount(), tier, item->getNameDescription()});
	}
	return result;
}

uint64_t LootTracker::track(Container& corpse, const std::vector<uint32_t>& recipients, uint8_t tier)
{
	const auto existing = corpses().find(&corpse);
	if (existing != corpses().end()) {
		return existing->second.id;
	}
	prune();
	if (corpses().size() >= MAX_TRACKED) {
		auto oldest = std::min_element(corpses().begin(), corpses().end(), [](const std::pair<const Container* const, TrackedCorpse>& a, const std::pair<const Container* const, TrackedCorpse>& b) {
			return a.second.id < b.second.id;
		});
		corpses().erase(oldest);
	}
	TrackedCorpse tracked = {nextToken(), OTSYS_TIME(), tier, recipients};
	corpses().emplace(&corpse, tracked);
	return tracked.id;
}

uint64_t LootTracker::token(const Container* corpse)
{
	const auto found = corpses().find(corpse);
	return found == corpses().end() ? 0 : found->second.id;
}

bool LootTracker::eligible(const Container* corpse, uint32_t guid)
{
	const auto found = corpses().find(corpse);
	return found != corpses().end() && std::find(found->second.recipients.begin(), found->second.recipients.end(), guid) != found->second.recipients.end();
}

size_t LootTracker::size()
{
	return corpses().size();
}

void LootTracker::forget(const Container* corpse)
{
	corpses().erase(corpse);
}

std::string LootTracker::notification(const Container& corpse, const LootContents& contents, const std::string& monsterName, uint64_t id, const Player& player)
{
	const TrackedCorpse tracked = {id, 0, contents.tier, {}};
	std::string fields = identity(corpse, tracked, player);
	if (contents.items.empty()) {
		const size_t unopened = fields.rfind("true");
		if (unopened != std::string::npos) {
			fields.replace(unopened, 4, "false");
		}
	}
	std::string result = "{\"event\":\"loot\"," + fields + ",\"name\":" + quoted(monsterName, 80) + ",\"items\":[";
	uint32_t omitted = contents.omitted;
	bool first = true;
	for (const LootEntry& entry : contents.items) {
		std::ostringstream item;
		item << "{\"id\":" << entry.id << ",\"count\":" << entry.count << ",\"tier\":" << unsigned(entry.tier)
			<< ",\"name\":" << quoted(entry.name, 160) << '}';
		const std::string encoded = item.str();
		// NetworkMessage::addString has a hard 8192 byte limit. Reserve the tail.
		if (result.size() + encoded.size() > 7900) {
			++omitted;
			continue;
		}
		if (!first) {
			result += ',';
		}
		first = false;
		result += encoded;
	}
	return result + "],\"omitted\":" + std::to_string(omitted) + '}';
}

void LootTracker::publish(Container& corpse, const std::string& monsterName)
{
	Player* owner = g_game.getPlayerByID(corpse.getCorpseOwner());
	if (!owner) {
		return;
	}
	std::vector<Player*> recipients = {owner};
	if (Party* party = owner->getParty()) {
		recipients.push_back(party->getLeader());
		recipients.insert(recipients.end(), party->getMembers().begin(), party->getMembers().end());
	}
	std::sort(recipients.begin(), recipients.end());
	recipients.erase(std::unique(recipients.begin(), recipients.end()), recipients.end());
	std::vector<uint32_t> guids;
	for (Player* recipient : recipients) {
		guids.push_back(recipient->getGUID());
	}
	const LootContents contents = collect(corpse);
	TrackedCorpse transient = {nextToken(), OTSYS_TIME(), contents.tier, guids};
	if (!contents.items.empty()) {
		track(corpse, guids, contents.tier);
		transient = corpses().at(&corpse);
	}
	for (Player* recipient : recipients) {
		if (!recipient->lootProtocol) {
			std::string text = "Loot of " + monsterName + ": " + corpse.getContentDescription();
			if (text.size() > 7500) {
				text.resize(7497);
				text += "...";
			}
			recipient->sendChannelMessage("", text, TALKTYPE_CHANNEL_Y, LOOT_CHANNEL);
			continue;
		}
		if (!contents.items.empty() && recipient->canSee(corpse.getPosition())) {
			recipient->lootMarkers[transient.id] = identity(corpse, transient, *recipient);
		}
		send(*recipient, notification(corpse, contents, monsterName, transient.id, *recipient));
		if (contents.tier > 0 && contents.tier <= 5 && recipient->canSee(corpse.getPosition())) {
			static const char* names[] = {"", "Incomum", "Raro", "Epico", "Lendario", "Mitico"};
			static const uint8_t colors[] = {0, TEXTCOLOR_LIGHTGREEN, TEXTCOLOR_LIGHTBLUE, TEXTCOLOR_PURPLE, TEXTCOLOR_YELLOW, TEXTCOLOR_RED};
			static const uint8_t effects[] = {0, CONST_ME_MAGIC_GREEN, CONST_ME_MAGIC_BLUE, CONST_ME_SOUND_PURPLE, CONST_ME_YELLOW_RINGS, CONST_ME_MAGIC_RED};
			// Send directly to this connection, so the visual never broadcasts to bystanders.
			NetworkMessage effect;
			effect.addByte(0x83);
			effect.addPosition(corpse.getPosition());
			effect.addByte(effects[contents.tier]);
			effect.addByte(0x84);
			effect.addPosition(corpse.getPosition());
			effect.addByte(colors[contents.tier]);
			effect.addString(names[contents.tier]);
			recipient->sendNetworkMessage(effect);
		}
	}
}

void LootTracker::resetSession(Player& player)
{
	player.lootProtocol = false;
	player.lastLootSync = 0;
	player.lastLootFullSync = 0;
	player.lootMarkers.clear();
}

void LootTracker::handleRequest(Player& player, const std::string& request)
{
	if (request == "H|1") {
		if (player.lootProtocol) {
			return;
		}
		player.lootProtocol = true;
		send(player, "{\"event\":\"ready\",\"version\":1}");
		sync(player, true);
	} else if (request == "S|1" && player.lootProtocol) {
		sync(player);
	}
}

void LootTracker::sync(Player& player, bool force)
{
	const int64_t now = OTSYS_TIME();
	if (!player.lootProtocol || (!force && now - player.lastLootSync < 1000)) {
		return;
	}
	player.lastLootSync = now;
	// A map refresh can recreate client item objects without changing their stack.
	const bool replay = force || now - player.lastLootFullSync >= 5000;
	if (replay) {
		player.lastLootFullSync = now;
	}
	static int64_t lastPrune = 0;
	if (now - lastPrune > 5000) {
		prune();
		lastPrune = now;
	}
	std::map<uint64_t, std::string> visible;
	for (const auto& pair : corpses()) {
		const Container& corpse = *pair.first;
		const TrackedCorpse& tracked = pair.second;
		const Tile* tile = dynamic_cast<const Tile*>(corpse.getParent());
		if (!tile || !eligible(&corpse, player.getGUID()) || !player.canSee(corpse.getPosition()) || tile->getStackposOfItem(&player, &corpse) < 0) {
			continue;
		}
		visible.emplace(tracked.id, identity(corpse, tracked, player));
		if (visible.size() == MAX_VISIBLE) {
			break;
		}
	}
	for (const auto& previous : player.lootMarkers) {
		if (visible.find(previous.first) == visible.end()) {
			send(player, "{\"event\":\"removed\",\"id\":\"" + std::to_string(previous.first) + "\"}");
		}
	}
	for (const auto& marker : visible) {
		const auto previous = player.lootMarkers.find(marker.first);
		if (replay || previous == player.lootMarkers.end() || previous->second != marker.second) {
			send(player, "{\"event\":\"marker\"," + marker.second + '}');
		}
	}
	player.lootMarkers.swap(visible);
}

void LootTracker::invalidate(Player& player, const Item* item)
{
	const Container* corpse = item ? item->getContainer() : nullptr;
	const uint64_t id = token(corpse);
	if (id && player.lootMarkers.erase(id)) {
		send(player, "{\"event\":\"removed\",\"id\":\"" + std::to_string(id) + "\"}");
	}
}

void LootTracker::opened(Container& corpse)
{
	const auto found = corpses().find(&corpse);
	if (found == corpses().end()) {
		return;
	}
	const TrackedCorpse tracked = found->second;
	corpses().erase(found);
	for (uint32_t guid : tracked.recipients) {
		Player* player = g_game.getPlayerByGUID(guid);
		if (player && player->lootProtocol) {
			player->lootMarkers.erase(tracked.id);
			send(*player, "{\"event\":\"opened\",\"id\":\"" + std::to_string(tracked.id) + "\"}");
		}
	}
}
