#include "otpch.h"
#include "game.h"
#include "configmanager.h"
#include "npc.h"
#include "scheduler.h"
#include "databasetasks.h"
#include "rsa.h"
#include <new>
#include <cstring>
#include <type_traits>
#include <stdexcept>

DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;

struct NpcInitializationTestAccess {
	static void check(unsigned char pattern) {
		std::aligned_storage<sizeof(Npc), alignof(Npc)>::type storage;
		std::memset(&storage, pattern, sizeof(storage));
		auto* npc = new (&storage) Npc("isolated-initialization-probe");
		const bool valid = npc->spectators.empty() && npc->lastTalkCreature == 0 &&
			npc->focusCreature == 0 && npc->conversationStartTime == 0 &&
			npc->conversationEndTime == 0 && npc->isIdle && !npc->loaded &&
			npc->behaviourDatabase == nullptr;
		npc->lastTalkCreature = 123;
		npc->conversationStartTime = 456;
		npc->isIdle = false;
		npc->reset();
		const bool resetPreserved = npc->lastTalkCreature == 123 &&
			npc->conversationStartTime == 456 && !npc->isIdle;
		npc->~Npc();
		if (!valid) throw std::runtime_error("NPC state depends on uninitialized allocation bytes");
		if (!resetPreserved) throw std::runtime_error("constructor hardening changed existing reset semantics");
	}
};

int main()
{
	try {
		// Constructor must establish state independently of recycled allocator bytes.
		for (unsigned char pattern : {0x00, 0x01, 0xA5, 0xFF}) {
			NpcInitializationTestAccess::check(pattern);
		}
		std::cout << "PASS: NPC construction initializes idle/conversation state for four memory patterns; reset semantics preserved." << std::endl;
		return 0;
	} catch (const std::exception& error) {
		std::cerr << "FAIL: " << error.what() << std::endl;
		return 1;
	}
}
