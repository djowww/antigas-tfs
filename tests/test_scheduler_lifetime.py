import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class SchedulerLifetimeTests(unittest.TestCase):
    def test_add_event_returns_copied_id_after_publishing_task(self):
        source = (ROOT / "src" / "scheduler.cpp").read_text(encoding="utf-8")
        add_event = source.split("uint32_t Scheduler::addEvent(SchedulerTask* task)", 1)[1]
        add_event = add_event.split("bool Scheduler::stopEvent(uint32_t eventid)", 1)[0]

        publish_position = add_event.index("eventList.push(task);")
        unlock_position = add_event.rindex("eventLock.unlock();")
        return_position = add_event.index("return eventId;", unlock_position)

        self.assertLess(add_event.index("eventId = task->getEventId();"), publish_position)
        self.assertGreater(return_position, unlock_position)
        self.assertNotIn("task->getEventId()", add_event[unlock_position:])


if __name__ == "__main__":
    unittest.main()
