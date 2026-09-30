import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SchedulerLifetimeTests(unittest.TestCase):
    def test_add_event_returns_copied_id_after_scoped_lock_and_publish(self):
        source = (ROOT / "src" / "scheduler.cpp").read_text(encoding="utf-8")
        add_event = source.split("uint32_t Scheduler::addEvent(SchedulerTask* task)", 1)[1]
        add_event = add_event.split("bool Scheduler::stopEvent(uint32_t eventid)", 1)[0]

        lock_position = add_event.index("std::unique_lock<std::mutex> lock(eventLock);")
        publish_position = add_event.index("eventList.push(task);")
        scope_end = add_event.index("\n\t}\n\n\tif (do_signal)", publish_position)
        return_position = add_event.index("return eventId;", scope_end)

        self.assertLess(add_event.index("eventId = task->getEventId();"), publish_position)
        self.assertLess(lock_position, publish_position)
        self.assertGreater(scope_end, publish_position)
        self.assertGreater(return_position, scope_end)
        self.assertNotIn("task->", add_event[scope_end:return_position])
        self.assertNotIn("eventLock.unlock();", add_event)


if __name__ == "__main__":
    unittest.main()
