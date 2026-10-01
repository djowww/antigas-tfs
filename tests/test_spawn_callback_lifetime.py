import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SpawnCallbackLifetimeTests(unittest.TestCase):
    def test_spawn_timer_is_generation_guarded_before_using_spawn(self):
        source = (ROOT / "src" / "spawn.cpp").read_text(encoding="utf-8")
        schedule = source.split("void Spawn::scheduleSpawnCheck(", 1)[1]
        schedule = schedule.split("Spawn::~Spawn()", 1)[0]
        self.assertIn("callbackGeneration.guard(generation", schedule)
        self.assertIn("[this, generation]", schedule)
        self.assertIn("checkSpawn(generation);", schedule)

        check = source.split("void Spawn::checkSpawn(uint64_t generation)", 1)[1]
        check = check.split("void Spawn::cleanup()", 1)[0]
        self.assertLess(check.index("generation != callbackGeneration.snapshot()"), check.index("checkSpawnEvent = 0;"))
        self.assertIn("scheduleSpawnCheck(getInterval(), generation);", check)

    def test_spawn_destruction_invalidates_before_cancellation_and_release(self):
        source = (ROOT / "src" / "spawn.cpp").read_text(encoding="utf-8")
        destructor = source.split("Spawn::~Spawn()", 1)[1].split("bool Spawn::findPlayer", 1)[0]
        self.assertLess(destructor.index("stopEvent();"), destructor.index("for (const auto& it : spawnedMap)"))

        stop = source.split("void Spawn::stopEvent()", 1)[1]
        self.assertLess(stop.index("callbackGeneration.invalidate();"), stop.index("g_scheduler.stopEvent(checkSpawnEvent)"))

    def test_shutdown_clears_spawns_after_dispatcher_sentinel_is_queued(self):
        spawn_source = (ROOT / "src" / "spawn.cpp").read_text(encoding="utf-8")
        clear = spawn_source.split("void Spawns::clear()", 1)[1]
        clear = clear.split("bool Spawns::isInZone", 1)[0]
        self.assertLess(clear.index("spawn.stopEvent();"), clear.index("spawnList.clear();"))

        game = (ROOT / "src" / "game.cpp").read_text(encoding="utf-8")
        shutdown = game.split("void Game::shutdown()", 1)[1].split("void Game::cleanup", 1)[0]
        self.assertLess(shutdown.index("g_scheduler.shutdown();"), shutdown.index("g_dispatcher.shutdown();"))
        self.assertLess(shutdown.index("g_dispatcher.shutdown();"), shutdown.index("map.spawns.clear();"))


if __name__ == "__main__":
    unittest.main()
