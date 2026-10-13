#include "otpch.h"
#include "actions.h"
#include "configmanager.h"
#include "creatureevent.h"
#include "databasetasks.h"
#include "events.h"
#include "game.h"
#include "monster.h"
#include "movement.h"
#include "outputmessage.h"
#include "protocolgame.h"
#include "rsa.h"
#include "scheduler.h"
#include "spawn.h"
#include "spells.h"
#include <boost/filesystem.hpp>
#include <fstream>
#include <stdexcept>

// Real server core. No sockets, SQL, worker threads, player saves or live map.
DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;
extern LuaEnvironment g_luaEnvironment;
extern Events* g_events;
extern MoveEvents* g_moveEvents;
extern CreatureEvents* g_creatureEvents;

static unsigned checks = 0;
static void require(bool value, const char* message)
{
	++checks;
	if (!value) throw std::runtime_error(message);
}

// Only fixture/session setup and access to the actual private consumers.
// No visibility, packet parsing, cooldown, spawn or AI rule is reimplemented.
struct ViewportCoreTestAccess {
	static void bind(ProtocolGame& protocol, Player* player, uint8_t width, uint8_t height)
	{
		protocol.player = player;
		protocol.acceptPackets = true;
		protocol.otclientV8 = true;
		protocol.mapViewport.set(width, height);
		protocol.lastMapRangeChange = OTSYS_TIME() - 1000;
	}
	static void detach(ProtocolGame& protocol) { protocol.player = nullptr; protocol.acceptPackets = false; }
	static MapViewport viewport(const ProtocolGame& protocol) { return protocol.mapViewport; }
	static void cooldown(ProtocolGame& protocol, int64_t time) { protocol.lastMapRangeChange = time; }
	static void change(ProtocolGame& protocol, uint8_t width, uint8_t height) { protocol.changeMapAwareRange(width, height); }
	static void parse(ProtocolGame& protocol, NetworkMessage& message) { protocol.parseChangeMapAwareRange(message); }
	static bool spawnBlocked(const Position& position) { return Spawn::findPlayer(position); }
	static std::vector<uint8_t> compatibility(ProtocolGame& protocol, bool v8, OperatingSystem_t operatingSystem)
	{
		protocol.otclientV8 = v8;
		protocol.getCurrentBuffer().reset();
		protocol.sendClientCompatibility(operatingSystem);
		const auto& output = protocol.getCurrentBuffer();
		if (!output) return {};
		const auto* begin = output->getBuffer() + NetworkMessage::INITIAL_BUFFER_POSITION;
		return {begin, begin + output->getLength()};
	}
};

class IncomingRange : public NetworkMessage {
	public:
		IncomingRange(uint16_t length, uint8_t width, uint8_t height)
		{
			std::fill(buffer, buffer + sizeof(buffer), uint8_t(0));
			info.length = length;
			info.position = INITIAL_BUFFER_POSITION;
			buffer[INITIAL_BUFFER_POSITION] = width;
			buffer[INITIAL_BUFFER_POSITION + 1] = height;
		}
};

// Run the actual queued task synchronously; the dispatcher worker is never
// started. Malformed requests must not enqueue a task in the first place.
struct DispatcherProbe : Dispatcher {
	static void running(Dispatcher& dispatcher, bool value)
	{
		auto setter = &DispatcherProbe::setState;
		(dispatcher.*setter)(value ? THREAD_STATE_RUNNING : THREAD_STATE_TERMINATED);
	}
	static void drain(Dispatcher& dispatcher)
	{
		auto tasksMember = &DispatcherProbe::taskList;
		auto metricsMember = &DispatcherProbe::queueMetrics;
		auto& tasks = dispatcher.*tasksMember;
		while (!tasks.empty()) {
			std::unique_ptr<Task> task(tasks.front());
			tasks.pop_front();
			(dispatcher.*metricsMember).taskDequeued(task->getTrackedPayloadBytes());
			(*task)();
		}
	}
};

struct DispatcherScope {
	DispatcherScope() { DispatcherProbe::running(g_dispatcher, true); }
	~DispatcherScope() { DispatcherProbe::running(g_dispatcher, false); DispatcherProbe::drain(g_dispatcher); }
};

static void loadConfig()
{
	const auto original = boost::filesystem::current_path();
	const auto scratch = boost::filesystem::temp_directory_path() /
		boost::filesystem::unique_path("antigas-viewport-%%%%-%%%%");
	boost::filesystem::create_directory(scratch);
	{
		std::ofstream config((scratch / "config.lua").string());
		config << "freePremium = false\n";
		require(config.good(), "isolated fixture config must be writable");
	}
	boost::filesystem::current_path(scratch);
	const bool loaded = g_config.load();
	boost::filesystem::current_path(original);
	boost::filesystem::remove_all(scratch);
	require(loaded, "real ConfigManager must load the isolated fixture");
}

static Tile& tileAt(const Position& position)
{
	Tile* tile = g_game.map.getTile(position);
	if (!tile) {
		tile = new DynamicTile(position.x, position.y, position.z);
		g_game.map.setTile(position, tile);
		tile->addThing(Item::CreateItem(102));
	}
	return *tile;
}

struct CountingSpell : BaseSpell {
	unsigned casts = 0;
	bool castSpell(Creature*) override { ++casts; return true; }
	bool castSpell(Creature*, Creature*) override { ++casts; return true; }
};

struct Fixture {
	Group group = {};
	ProtocolGame_ptr protocol = std::make_shared<ProtocolGame>(nullptr);
	Player player {protocol};
	CountingSpell spell;
	MonsterType type;
	Monster monster {&type};
	const Position origin {1000, 1000, 7};
	bool monsterPlaced = false, playerPlaced = false;

	Fixture(uint8_t width, uint8_t height)
	{
		group.flags = PlayerFlag_NotGainSkill;
		player.setGroup(&group);
		player.setName("Viewport Offline Target");
		player.setID();
		require(player.setVocation(0), "ordinary fixture vocation must exist");
		// Stack-owned creatures keep one fixture reference so native list cleanup
		// never deletes a stack object. All additional native references drain.
		player.incrementReferenceCounter();
		monster.incrementReferenceCounter();
		monster.setID();
		type.name = "Viewport Offline Ranger";
		type.info.targetDistance = 7;
		type.info.attackSpells.emplace_back();
		type.info.attackSpells.back().spell = &spell;
		type.info.attackSpells.back().range = 7;
		type.info.attackSpells.back().chance = 0; // Deterministic native chance gate.
		for (uint16_t x = 980; x <= 1020; ++x) {
			for (uint16_t y = 980; y <= 1020; ++y) tileAt(Position(x, y, 7));
		}
		tileAt(Position(1000, 1000, 8));
		ViewportCoreTestAccess::bind(*protocol, &player, width, height);
		monsterPlaced = g_game.map.placeCreature(origin, &monster, false, true);
		require(monsterPlaced, "real Map must place the isolated monster");
		playerPlaced = g_game.map.placeCreature(Position(1013, 1000, 7), &player, false, true);
		require(playerPlaced, "real Map must place the isolated ordinary player");
		monster.onCreatureAppear(&monster, false); // Actual bootstrap scan.
	}
	~Fixture()
	{
		if (monsterPlaced && playerPlaced) monster.onRemoveCreature(&player, true);
		Game::removeCreatureCheck(&monster);
		Game::removeCreatureCheck(&player);
		for (size_t index = 0; index < EVENT_CREATURECOUNT; ++index) g_game.checkCreatures(index);
		if (playerPlaced) player.getTile()->removeCreature(&player);
		if (monsterPlaced) monster.getTile()->removeCreature(&monster);
		g_game.map.clearSpectatorCache();
		ViewportCoreTestAccess::detach(*protocol);
		g_game.cleanup(true);
	}
	void movePlayer(const Position& position)
	{
		g_game.map.moveCreature(player, tileAt(position), true);
		g_game.map.clearSpectatorCache();
	}
	bool acquired() const
	{
		const auto& targets = monster.getTargetList();
		return std::find(targets.begin(), targets.end(), &player) != targets.end();
	}
};

static void sightAndNotifications(Fixture& fixture)
{
	require(!fixture.acquired(), "bootstrap scan must reject a player thirteen tiles away");
	for (int distance : {9, 12, 13}) {
		for (int sign : {-1, 1}) {
			for (bool vertical : {false, true}) {
				const Position target(1000 + (vertical ? 0 : sign*distance),
				                      1000 + (vertical ? sign*distance : 0), 7);
				fixture.movePlayer(target);
				require(fixture.monster.canSee(target) == (distance <= 12), "actual Monster sight boundary must stay twelve on each axis");
				require(fixture.acquired() == (distance <= 12), "actual Map movement audience must acquire/lose targets at twelve/thirteen");
				SpectatorVec audience;
				g_game.map.getMonsterSpectators(audience, target, false);
				require(audience.count(&fixture.monster) == (distance <= 12), "monster-only event audience must match actual sight");
				require(audience.count(&fixture.player) == 0, "extended monster audience must never include player observers");
			}
		}
	}
	fixture.movePlayer(Position(1012, 1000, 7));
	require(fixture.acquired(), "thirteen-to-twelve entry must acquire a target");
	fixture.monster.onRemoveCreature(&fixture.player, true);
	require(!fixture.acquired(), "logout/removal notification must remove the distant target");
	fixture.monster.onCreatureAppear(&fixture.player, true);
	require(fixture.acquired(), "login/appearance notification must acquire the same distant target");
	fixture.movePlayer(Position(1000, 1000, 8));
	require(!fixture.monster.isTarget(&fixture.player), "a different-floor player must never be an attack target");
	fixture.movePlayer(Position(1013, 1000, 7));
	require(!fixture.acquired(), "teleport outside sight must leave no stale target");
}

static void rangedAttackAndLineOfSight(Fixture& fixture)
{
	fixture.movePlayer(Position(1007, 1000, 7));
	require(fixture.monster.selectTarget(&fixture.player), "actual monster must select its acquired ordinary target");
	fixture.monster.onAttacking(2000);
	require(fixture.spell.casts == 1, "actual ranged attack must cast at the configured seven-tile reach");
	fixture.movePlayer(Position(1008, 1000, 7));
	require(fixture.acquired(), "eight-tile player must remain detected");
	fixture.monster.onAttacking(2000);
	require(fixture.spell.casts == 1, "twelve-tile sight must not expand the real seven-tile spell reach");
	fixture.movePlayer(Position(1007, 1000, 7));
	Tile& barrier = tileAt(Position(1003, 1000, 7));
	barrier.addThing(Item::CreateItem(373)); // Production stone wall, blocks projectiles.
	require(!g_game.map.isSightClear(fixture.origin, fixture.player.getPosition(), true), "production wall must block the real sight ray");
	fixture.monster.onAttacking(2000);
	require(fixture.spell.casts == 1, "actual ranged attack must not cast through the wall");
	barrier.addThing(Item::CreateItem(102));
	require(g_game.map.isSightClear(fixture.origin, fixture.player.getPosition(), true), "restoring floor must restore the actual clear ray");
	fixture.monster.onAttacking(2000);
	require(fixture.spell.casts == 2, "actual ranged attack must resume when line of sight is restored");
}

static void preservedGameplayLimits(Fixture& fixture, bool wide)
{
	fixture.movePlayer(fixture.origin);
	require(Map::maxClientViewportX == 8 && Map::maxClientViewportY == 6, "classic player/combat constants must remain unchanged");
	require(Map::maxViewportX == 11 && Map::maxViewportY == 11, "ordinary discovery and spawn limits must remain unchanged");
	require(fixture.player.canSee(Position(1009, 1000, 7)), "native protocol keeps the east walking margin visible");
	require(fixture.player.canSee(Position(1015, 1000, 7)) == wide, "only acknowledged wide protocol sees the wider map");
	require(!fixture.player.canSee(Position(1017, 1000, 7)), "maximal wide viewport must reject positions beyond its own buffer");
	Actions actions;
	for (int sign : {-1, 1}) {
		require(actions.canUseFar(&fixture.player, Position(1000+sign*7,1000+sign*5,7), false, true) == RETURNVALUE_NOERROR,
		        "real far-use must accept the classic seven-by-five edge");
		require(actions.canUseFar(&fixture.player, Position(1000+sign*8,1000,7), false, true) == RETURNVALUE_TOOFARAWAY,
		        "wide rendering must not enlarge horizontal far-use reach");
		require(actions.canUseFar(&fixture.player, Position(1000,1000+sign*6,7), false, true) == RETURNVALUE_TOOFARAWAY,
		        "wide rendering must not enlarge vertical far-use reach");
		require(g_game.map.canThrowObjectTo(fixture.origin, Position(1000+sign*8,1000+sign*6,7), false),
		        "real throw must accept the classic eight-by-six edge");
		require(!g_game.map.canThrowObjectTo(fixture.origin, Position(1000+sign*9,1000,7), false),
		        "wide rendering must not enlarge horizontal throw reach");
		require(!g_game.map.canThrowObjectTo(fixture.origin, Position(1000,1000+sign*7,7), false),
		        "wide rendering must not enlarge vertical throw reach");
	}
	const Position spawn(1011,1000,7);
	require(ViewportCoreTestAccess::spawnBlocked(spawn), "real spawn blocking must still include a player eleven tiles away");
	require(!ViewportCoreTestAccess::spawnBlocked(Position(1012,1000,7)), "expanded player packet audience must not enlarge spawn blocking to twelve");
	SpectatorVec observers;
	g_game.map.getSpectators(observers, Position(1015,1000,7), false, true);
	require(observers.count(&fixture.player) == 1, "real broad player audience must carry updates to the wide map edge");
}

static void rangeParserAndCooldown(Fixture& fixture)
{
	DispatcherScope dispatcher;
	const auto before = g_dispatcher.getQueueMetrics().totalQueuedCount;
	for (uint16_t length : {0,1}) {
		IncomingRange truncated(length,30,16);
		ViewportCoreTestAccess::parse(*fixture.protocol,truncated);
		require(!truncated.isReadPositionValid(), "truncated aware-range body must be rejected by the real parser");
		require(g_dispatcher.getQueueMetrics().totalQueuedCount == before, "truncated aware-range body must never enqueue a dispatcher task");
	}
	IncomingRange valid(2,255,255);
	ViewportCoreTestAccess::parse(*fixture.protocol,valid);
	require(valid.isReadPositionValid(), "complete aware-range body must parse");
	require(g_dispatcher.getQueueMetrics().totalQueuedCount == before+1, "complete aware-range body must enqueue exactly one native task");
	ViewportCoreTestAccess::cooldown(*fixture.protocol,OTSYS_TIME()-1000);
	DispatcherProbe::drain(g_dispatcher);
	auto range = ViewportCoreTestAccess::viewport(*fixture.protocol);
	require(range.x == 15 && range.y == 8, "actual dispatched request must clamp oversized dimensions");
	const auto length = fixture.protocol->getCurrentBuffer()->getLength();
	ViewportCoreTestAccess::cooldown(*fixture.protocol,OTSYS_TIME()+1000);
	ViewportCoreTestAccess::change(*fixture.protocol,16,12);
	range = ViewportCoreTestAccess::viewport(*fixture.protocol);
	require(range.x == 15 && range.y == 8, "actual rate-limited request must leave the acknowledged viewport intact");
	require(fixture.protocol->getCurrentBuffer()->getLength() == length, "actual cooldown must not acknowledge an unapplied viewport");
	ViewportCoreTestAccess::cooldown(*fixture.protocol,OTSYS_TIME()-1000);
	ViewportCoreTestAccess::change(*fixture.protocol,0,0);
	range = ViewportCoreTestAccess::viewport(*fixture.protocol);
	require(range.x == 8 && range.y == 6, "actual later retry must apply the classic minimum safely");
	const auto& output = fixture.protocol->getCurrentBuffer();
	const auto* body = output->getBuffer()+NetworkMessage::INITIAL_BUFFER_POSITION;
	require(output->getLength() >= length+3 && body[length] == 0x42 && body[length+1] == 16 && body[length+2] == 12,
	        "accepted retry must send the exact applied classic aware-range acknowledgment");
}

static void compatibilityOrdering()
{
	auto protocol = std::make_shared<ProtocolGame>(nullptr);
	const auto v8 = ViewportCoreTestAccess::compatibility(*protocol,true,CLIENTOS_WINDOWS);
	require(v8.size() >= 7, "OTCv8 compatibility must contain opcode bootstrap and feature negotiation");
	require(v8[0] == 0x32 && v8[1] == 0 && v8[2] == 0 && v8[3] == 0,
	        "actual opcode-zero bootstrap must precede the feature-negotiation packet");
	require(v8[4] == 0x43, "actual feature negotiation must follow the four-byte opcode bootstrap");
	const auto custom = ViewportCoreTestAccess::compatibility(*protocol,false,CLIENTOS_OTCLIENT_LINUX);
	require(custom == std::vector<uint8_t>({0x32,0,0,0}), "custom OS without OTCv8 must receive only opcode-zero bootstrap");
	const auto legacy = ViewportCoreTestAccess::compatibility(*protocol,false,static_cast<OperatingSystem_t>(0));
	require(legacy.empty(), "legacy client must receive neither custom bootstrap nor OTCv8 features");
}

int main(int argc, char** argv)
{
	try {
		require(argc == 2, "select classic, wide or compatibility regression");
		const std::string mode(argv[1]);
		if (mode == "compatibility") compatibilityOrdering();
		else {
			require(mode == "classic" || mode == "wide", "unknown viewport regression");
			loadConfig();
			require(Item::items.loadItems(), "production item definitions must load");
			require(g_vocations.loadFromXml(), "production vocations must load");
			require(g_luaEnvironment.initState(), "production Lua environment must initialize");
			Events events;
			MoveEvents moves;
			CreatureEvents creatureEvents;
			g_events = &events; g_moveEvents = &moves; g_creatureEvents = &creatureEvents;
			{
				Fixture fixture(mode == "wide" ? 30 : 16, mode == "wide" ? 16 : 12);
				sightAndNotifications(fixture);
				rangedAttackAndLineOfSight(fixture);
				preservedGameplayLimits(fixture,mode == "wide");
				rangeParserAndCooldown(fixture);
			}
			g_events = nullptr; g_moveEvents = nullptr; g_creatureEvents = nullptr;
		}
		std::cout << "PASS: viewport " << mode << " (" << checks << " real-core checks)\n";
		return 0;
	} catch (const std::exception& error) {
		std::cerr << "FAIL: viewport " << error.what() << '\n';
		return 1;
	}
}
