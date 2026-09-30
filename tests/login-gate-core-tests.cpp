#include "otpch.h"
#include "game.h"
#include "configmanager.h"
#include "databasetasks.h"
#include "scheduler.h"
#include "rsa.h"
#include "protocollogin.h"
#include "protocolgame.h"
#include "outputmessage.h"
#include <boost/filesystem.hpp>
#include <atomic>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <future>
#include <stdexcept>

// Real core/parser/dispatcher/scheduler, synthetic credentials and RSA key.
// No listener, open socket, live config, world or database is used.
DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;

static std::atomic<unsigned> databaseConnections{0};

// Executable-level link seam: even an unpatched login cannot reach MySQL.
extern "C" MYSQL* STDCALL mysql_real_connect(MYSQL*, const char*, const char*, const char*,
                                              const char*, unsigned int, const char*, unsigned long)
{
	++databaseConnections;
	return nullptr;
}

static void require(bool ok, const char* message)
{
	if (!ok) throw std::runtime_error(message);
}

static void onDispatcher(const std::function<void()>& action)
{
	auto completion = std::make_shared<std::promise<void>>();
	auto ready = completion->get_future();
	g_dispatcher.addTask(createTask([completion, action]() {
		try { action(); completion->set_value(); }
		catch (...) { completion->set_exception(std::current_exception()); }
	}));
	require(ready.wait_for(std::chrono::seconds(3)) == std::future_status::ready, "isolated dispatcher must finish the test action");
	ready.get();
}

static uint64_t dispatcherCycle()
{
	uint64_t cycle = 0;
	onDispatcher([&cycle]() { cycle = g_dispatcher.getDispatcherCycle(); });
	return cycle;
}

static void config(bool blocked)
{
	std::ofstream file("config.lua");
	file << "blockLogin=" << (blocked ? "true" : "false")
	     << "\nblockLoginText='Synthetic login maintenance.'\nreplaceKickOnLogin=true\n"
	     << "mysqlHost='127.0.0.1'\nmysqlPort=1\nmysqlDatabase='synthetic_unused'\n";
	file.close();
	require(g_config.load(), "isolated login config must load");
}

struct TestRSA {
	mpz_t p, q, modulus, exponent;
	TestRSA() {
		mpz_inits(p, q, modulus, exponent, nullptr);
		mpz_set_ui(p, 3);
		mpz_mul_2exp(p, p, 510);
		mpz_add_ui(p, p, 123);
		mpz_nextprime(p, p);
		mpz_add_ui(q, p, 1000000);
		mpz_nextprime(q, q);
		mpz_mul(modulus, p, q);
		mpz_set_ui(exponent, 65537);
		char* pText = mpz_get_str(nullptr, 10, p);
		char* qText = mpz_get_str(nullptr, 10, q);
		g_RSA.setKey(pText, qText);
		std::free(pText);
		std::free(qText);
	}
	~TestRSA() { mpz_clears(p, q, modulus, exponent, nullptr); }
	void encrypt(std::vector<uint8_t>& plain) const {
		plain.resize(128, 0);
		mpz_t value;
		mpz_init(value);
		mpz_import(value, 128, 1, 1, 0, 0, plain.data());
		mpz_powm(value, value, exponent, modulus);
		const size_t count = (mpz_sizeinbase(value, 2) + 7) / 8;
		std::fill(plain.begin(), plain.end(), 0);
		mpz_export(plain.data() + 128 - count, nullptr, 1, 1, 0, 0, value);
		mpz_clear(value);
	}
};

static void word(std::vector<uint8_t>& out, uint16_t value)
{
	out.push_back(static_cast<uint8_t>(value));
	out.push_back(static_cast<uint8_t>(value >> 8));
}

static void number(std::vector<uint8_t>& out, uint32_t value)
{
	word(out, static_cast<uint16_t>(value));
	word(out, static_cast<uint16_t>(value >> 16));
}

static void string(std::vector<uint8_t>& out, const std::string& value)
{
	word(out, static_cast<uint16_t>(value.size()));
	out.insert(out.end(), value.begin(), value.end());
}

static NetworkMessage packet(const TestRSA& rsa, bool game, unsigned malformed = 0)
{
	std::vector<uint8_t> prefix{static_cast<uint8_t>(game ? 0x0A : 0x01)}, plain{0};
	word(prefix, CLIENTOS_OTCLIENT_WINDOWS);
	word(prefix, 772);
	if (!game) {
		prefix.resize(prefix.size() + 12, 0);
		string(prefix, "Antigas-26");
	}
	for (uint32_t key = 1; key <= 4; ++key) number(plain, key);
	if (game) plain.push_back(0);
	number(plain, 42);
	if (game) string(plain, "Synthetic Character");
	if (malformed == 1) {
		// Old canRead tolerates undeclared bytes. A nonempty password + trailer
		// finish at rawEnd+4, which the XTEA-specific cursor helper still accepts.
		word(plain, 107);
		plain.resize(128, 'p');
	} else if (malformed == 2) {
		string(plain, std::string(100, 'p'));
		word(plain, 5);
		plain.push_back('O'); plain.push_back('T'); plain.push_back('C');
		// The rest of OTCv8 and its version will reside in unreceived slack.
	} else {
		string(plain, "synthetic-password");
		word(plain, 0); // legacy client without an OTCv8 extension
	}
	rsa.encrypt(plain);
	prefix.insert(prefix.end(), plain.begin(), plain.end());
	NetworkMessage msg;
	std::memset(msg.getBuffer(), 0, NETWORKMESSAGE_MAXSIZE);
	std::memcpy(msg.getBodyBuffer(), prefix.data(), prefix.size());
	msg.setLength(static_cast<NetworkMessage::MsgSize_t>(prefix.size() + NetworkMessage::HEADER_LENGTH));
	require(msg.getByte() == (game ? 0x0A : 0x01), "fixture must consume the protocol ID exactly as Connection does");
	if (malformed == 2) {
		msg.getBuffer()[msg.getLength()] = 'v';
		msg.getBuffer()[msg.getLength() + 1] = '8';
		msg.getBuffer()[msg.getLength() + 2] = 253;
	}
	return msg;
}

struct LoginFixture : ProtocolLogin {
	using ProtocolLogin::ProtocolLogin;
	using ProtocolLogin::getCharacterList;
};

struct PlayerFixture : Player {
	PlayerFixture() : Player(nullptr) {}
	void setClient(ProtocolGame_ptr protocol) { client = std::move(protocol); }
	bool connecting() const { return isConnecting; }
	bool hasClient() const { return client != nullptr; }
};

int main()
{
	const auto original = boost::filesystem::current_path();
	const auto scratch = boost::filesystem::temp_directory_path() / boost::filesystem::unique_path("antigas-login-gate-%%%%-%%%%");
	bool dispatcherStarted = false, schedulerStarted = false;
	std::shared_ptr<PlayerFixture> reconnectPlayer;
	ProtocolGame_ptr replacement;
	bool playerRegistered = false;
	int result = 0;
	try {
		boost::filesystem::create_directories(scratch);
		boost::filesystem::current_path(scratch);
		config(true);
		TestRSA rsa;
		g_dispatcher.start();
		dispatcherStarted = true;
		auto game = std::make_shared<ProtocolGame>(nullptr);
		onDispatcher([&]() {
			game->login("Synthetic Character", 42, CLIENTOS_OTCLIENT_WINDOWS);
			require(!game->getCurrentBuffer() && g_game.getPlayersOnline() == 0, "blockLogin must reject dispatcher login before features or player creation");
			LoginFixture login(nullptr);
			login.getCharacterList(42, "synthetic-password");
		});
		require(databaseConnections == 0, "queued character-list request must recheck blockLogin before authentication");
		NetworkMessage gamePacket = packet(rsa, true);
		const auto beforeBlocked = dispatcherCycle();
		static_cast<Protocol&>(*game).onRecvFirstMessage(gamePacket);
		require(dispatcherCycle() == beforeBlocked + 1 && databaseConnections == 0, "direct game entry must reject blockLogin before authentication or dispatch");

		onDispatcher([]() { config(false); });
		boost::asio::io_service io;
		for (unsigned variant : {1u, 2u}) {
			auto malformedConnection = std::make_shared<Connection>(io, nullptr);
			auto malformedLogin = std::make_shared<ProtocolLogin>(malformedConnection);
			NetworkMessage malformed = packet(rsa, false, variant);
			const auto beforeMalformed = dispatcherCycle();
			malformedLogin->onRecvFirstMessage(malformed);
			require(malformed.getBufferPosition() == malformed.getLength() + 4 && !malformed.isOverrun(), "malformed credential/trailer fixture must finish in the four-byte undeclared slack");
			require(malformed.isReadPositionValid(), "fixture must expose the different XTEA length convention");
			require(dispatcherCycle() == beforeMalformed + 1 && databaseConnections == 0, "raw login slack must not enqueue authentication");
		}

		auto legacyConnection = std::make_shared<Connection>(io, nullptr);
		auto legacyLogin = std::make_shared<ProtocolLogin>(legacyConnection);
		NetworkMessage legacy = packet(rsa, false);
		const auto beforeLegacy = dispatcherCycle();
		legacyLogin->onRecvFirstMessage(legacy);
		require(legacy.isReadPositionValid(), "complete legacy credentials must retain a valid cursor");
		require(dispatcherCycle() == beforeLegacy + 2 && databaseConnections == 1, "complete legacy login must still dispatch authentication against the fake connection seam");
		io.poll(); // drain writes against unopened sockets; there is no peer

		g_scheduler.start();
		schedulerStarted = true;
		reconnectPlayer = std::make_shared<PlayerFixture>();
		replacement = std::make_shared<ProtocolGame>(nullptr);
		onDispatcher([&]() {
			reconnectPlayer->setName("Synthetic Reconnect");
			reconnectPlayer->setID();
			reconnectPlayer->setClient(std::make_shared<ProtocolGame>(nullptr));
			g_game.addPlayer(reconnectPlayer.get());
			playerRegistered = true;
			replacement->login(reconnectPlayer->getName(), 42, CLIENTOS_OTCLIENT_WINDOWS);
			require(reconnectPlayer->connecting(), "open login must schedule the normal delayed reconnect");
			reconnectPlayer->setClient(nullptr);
			config(true); // maintenance begins after login dispatch, before connect
		});
		const auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(3);
		bool connecting = true;
		while (connecting && std::chrono::steady_clock::now() < deadline) {
			std::this_thread::sleep_for(std::chrono::milliseconds(25));
			onDispatcher([&]() { connecting = reconnectPlayer->connecting(); });
		}
		onDispatcher([&]() {
			const bool refused = !reconnectPlayer->connecting() && !reconnectPlayer->hasClient();
			require(refused, "delayed reconnect must recheck maintenance and release its connecting flag");
		});
		std::cout << "PASS: core login gates, delayed reconnect and malformed/legacy RSA credentials, with no external connection." << std::endl;
	} catch (const std::exception& error) {
		std::cerr << "FAIL: " << error.what() << std::endl;
		result = 1;
	}
	if (schedulerStarted) { g_scheduler.shutdown(); g_scheduler.join(); }
	if (dispatcherStarted && playerRegistered) {
		onDispatcher([&]() {
			OutputMessagePool::getInstance().removeProtocolFromAutosend(replacement);
			g_game.removePlayer(reconnectPlayer.get());
		});
	}
	if (dispatcherStarted) { g_dispatcher.shutdown(); g_dispatcher.join(); }
	boost::filesystem::current_path(original);
	boost::filesystem::remove_all(scratch);
	return result;
}
