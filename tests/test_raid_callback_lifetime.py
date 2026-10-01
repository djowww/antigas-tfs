import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class RaidCallbackLifetimeTests(unittest.TestCase):
    def test_scheduler_callbacks_resolve_raid_after_generation_guard(self):
        source = (ROOT / "src" / "raids.cpp").read_text(encoding="utf-8")

        schedule = source.split("uint32_t Raids::scheduleRaidEvent(", 1)[1]
        schedule = schedule.split("void Raids::executeRaidEvent(", 1)[0]
        self.assertIn("callbackGeneration.guard(generation", schedule)
        self.assertIn("[this, raidName, eventIndex, generation]", schedule)
        self.assertNotIn("Raid*", schedule)
        self.assertNotIn("RaidEvent*", schedule)

        execute = source.split("void Raids::executeRaidEvent(", 1)[1]
        execute = execute.split("Raid::~Raid()", 1)[0]
        self.assertLess(execute.index("generation != callbackGeneration.snapshot()"), execute.index("getRunning()"))
        self.assertIn("raid->executeRaidEvent(eventIndex);", execute)

    def test_raid_event_chain_schedules_indices_instead_of_raw_pointers(self):
        source = (ROOT / "src" / "raids.cpp").read_text(encoding="utf-8")
        start = source.split("void Raid::startRaid()", 1)[1]
        start = start.split("void Raid::executeRaidEvent(uint32_t eventIndex)", 1)[0]
        self.assertIn("scheduleRaidEvent(name, nextEvent, raidEvent->getDelay())", start)
        self.assertNotIn("std::bind", start)

        execute = source.split("void Raid::executeRaidEvent(uint32_t eventIndex)", 1)[1]
        execute = execute.split("void Raid::resetRaid()", 1)[0]
        self.assertIn("eventIndex != nextEvent", execute)
        self.assertIn("raidEvents[eventIndex]", execute)
        self.assertIn("scheduleRaidEvent(name, nextEvent, ticks)", execute)
        self.assertNotIn("std::bind", execute)

    def test_reload_invalidates_queued_callbacks_before_deleting_raid_objects(self):
        source = (ROOT / "src" / "raids.cpp").read_text(encoding="utf-8")
        clear = source.split("void Raids::clear()", 1)[1]
        clear = clear.split("bool Raids::reload()", 1)[0]
        self.assertLess(clear.index("callbackGeneration.invalidate();"), clear.index("delete raid;"))
        self.assertIn("activeRaidIsOwned", clear)
        self.assertIn("delete activeRaid;", clear)
        self.assertIn("oneShotRaidList.clear();", clear)

    def test_non_repeating_raid_remains_owned_after_leaving_repeatable_list(self):
        source = (ROOT / "src" / "raids.cpp").read_text(encoding="utf-8")
        check = source.split("void Raids::checkRaids(uint64_t generation)", 1)[1]
        check = check.split("void Raids::clear()", 1)[0]
        self.assertIn("oneShotRaidList.splice(oneShotRaidList.end(), raidList, it);", check)

        destructor = source.split("Raids::~Raids()", 1)[1]
        destructor = destructor.split("bool Raids::loadFromXml()", 1)[0]
        self.assertIn("for (Raid* raid : oneShotRaidList)", destructor)
        self.assertIn("oneShotRaidList.begin()", destructor)

    def test_scheduler_removes_event_id_before_dispatching_callback(self):
        source = (ROOT / "src" / "scheduler.cpp").read_text(encoding="utf-8")
        worker = source.split("void Scheduler::threadMain()", 1)[1]
        worker = worker.split("uint32_t Scheduler::addEvent(", 1)[0]
        timeout_branch = worker.split("if (ret == std::cv_status::timeout)", 1)[1]
        timeout_branch = timeout_branch.split("\n\t\t} else {", 1)[0]
        erased = timeout_branch.index("eventIds.erase(it);")
        unlocked_after_erase = timeout_branch.index("eventLockUnique.unlock();", erased)
        dispatched = timeout_branch.index("g_dispatcher.addTask(task, true);")
        self.assertLess(erased, unlocked_after_erase)
        self.assertLess(unlocked_after_erase, dispatched)

        stop = source.split("bool Scheduler::stopEvent(uint32_t eventid)", 1)[1]
        stop = stop.split("void Scheduler::shutdown()", 1)[0]
        self.assertIn("if (it == eventIds.end())", stop)
        self.assertIn("return false;", stop)

    def test_periodic_raid_checker_is_generation_guarded(self):
        source = (ROOT / "src" / "raids.cpp").read_text(encoding="utf-8")
        schedule = source.split("void Raids::scheduleCheckRaids(", 1)[1]
        schedule = schedule.split("void Raids::checkRaids(", 1)[0]
        self.assertIn("callbackGeneration.guard(generation", schedule)
        check = source.split("void Raids::checkRaids(uint64_t generation)", 1)[1]
        check = check.split("void Raids::clear()", 1)[0]
        self.assertIn("generation != callbackGeneration.snapshot()", check)
        self.assertIn("scheduleCheckRaids(generation);", check)

    def test_manual_raid_command_uses_guarded_raid_scheduler(self):
        source = (ROOT / "src" / "commands.cpp").read_text(encoding="utf-8")
        force_raid = source.split("void Commands::forceRaid(", 1)[1]
        force_raid = force_raid.split("void Commands::", 1)[0]
        self.assertIn("raid->startRaid();", force_raid)
        self.assertNotIn("std::bind", force_raid)
        self.assertNotIn("createSchedulerTask", force_raid)


if __name__ == "__main__":
    unittest.main()
