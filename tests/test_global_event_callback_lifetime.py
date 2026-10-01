import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class GlobalEventCallbackLifetimeTests(unittest.TestCase):
    def test_reload_invalidates_old_callbacks_before_clearing_event_maps(self):
        source = (ROOT / "src" / "globalevent.cpp").read_text(encoding="utf-8")
        clear = source.split("void GlobalEvents::clear()", 1)[1].split("Event* GlobalEvents::getEvent", 1)[0]
        self.assertLess(clear.index("callbackGeneration.invalidate();"), clear.index("clearMap(thinkMap);"))
        self.assertLess(clear.index("callbackGeneration.invalidate();"), clear.index("clearMap(timerMap);"))

        base = (ROOT / "src" / "baseevents.cpp").read_text(encoding="utf-8")
        reload_method = base.split("bool BaseEvents::reload()", 1)[1].split("Event::Event(", 1)[0]
        self.assertLess(reload_method.index("clear();"), reload_method.index("loadFromXml();"))

    def test_initial_timer_and_think_callbacks_capture_a_generation_guard(self):
        source = (ROOT / "src" / "globalevent.cpp").read_text(encoding="utf-8")
        register = source.split("bool GlobalEvents::registerEvent(", 1)[1].split("void GlobalEvents::startup()", 1)[0]
        self.assertEqual(register.count("callbackGeneration.guard(generation"), 2)
        self.assertIn("timer(generation);", register)
        self.assertIn("think(generation);", register)

    def test_expired_timer_ids_reset_and_reschedules_keep_the_same_generation(self):
        source = (ROOT / "src" / "globalevent.cpp").read_text(encoding="utf-8")
        for method, event_id in (("timer", "timerEventId"), ("think", "thinkEventId")):
            body = source.split(f"void GlobalEvents::{method}(uint64_t generation)", 1)[1]
            body = body.split("void GlobalEvents::", 1)[0]
            guard = "generation != callbackGeneration.snapshot()"
            self.assertLess(body.index(guard), body.index(f"{event_id} = 0;"))
            self.assertIn("callbackGeneration.guard(generation", body)
            self.assertIn(f"{method}(generation);", body)


if __name__ == "__main__":
    unittest.main()
