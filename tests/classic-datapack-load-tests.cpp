#include "otpch.h"
#include "game.h"
#include "configmanager.h"
#include "scheduler.h"
#include "databasetasks.h"
#include "rsa.h"
#include "npc.h"
#include <boost/filesystem.hpp>
#include <stdexcept>

// Validate native NPC/NDB parsing without placing NPCs or touching persistence.
DatabaseTasks g_databaseTasks;
Dispatcher g_dispatcher;
Scheduler g_scheduler;
Game g_game;
ConfigManager g_config;
Monsters g_monsters;
Vocations g_vocations;
RSA g_RSA;

int main()
{
    try {
        if (!Item::items.loadItems() || !g_vocations.loadFromXml())
            throw std::runtime_error("production definitions failed to load");
        unsigned loaded = 0;
        for (const auto& file : boost::filesystem::directory_iterator("data/npc")) {
            if (file.path().extension() != ".npc") continue;
            const auto name = file.path().stem().string();
            std::unique_ptr<Npc> npc(Npc::createNpc(name));
            if (!npc) throw std::runtime_error("native NPC parser rejected " + name);
            ++loaded;
        }
        if (loaded == 0) throw std::runtime_error("NPC inventory unexpectedly empty");
        std::cout << "classic datapack: " << loaded << " NPC/NDB definitions loaded\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "classic datapack failed: " << error.what() << '\n';
        return 1;
    }
}
