import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class NpcCallbackLifetimeTests(unittest.TestCase):
    def test_delayed_dialogue_captures_response_and_uses_generation_guard(self):
        source = (ROOT / "src" / "behaviourdatabase.cpp").read_text(encoding="utf-8")
        action = source.split("void BehaviourDatabase::checkAction(", 1)[1]
        action = action.split("bool BehaviourDatabase::", 1)[0]

        self.assertIn("const std::string response = parseResponse(player, action->string);", action)
        self.assertIn("delayedSayGeneration.guard(generation", action)
        self.assertIn("std::bind(&Npc::doSay, npc, response)", action)

    def test_reset_invalidates_callbacks_before_trying_scheduler_cancellation(self):
        source = (ROOT / "src" / "behaviourdatabase.cpp").read_text(encoding="utf-8")
        reset = source.split("void BehaviourDatabase::reset()", 1)[1]
        reset = reset.split("bool NpcBehaviourCondition::", 1)[0]

        self.assertLess(reset.index("delayedSayGeneration.invalidate();"), reset.index("g_scheduler.stopEvent(eventId);"))

    def test_destruction_resets_pending_dialogue_before_releasing_behaviour_data(self):
        source = (ROOT / "src" / "behaviourdatabase.cpp").read_text(encoding="utf-8")
        destructor = source.split("BehaviourDatabase::~BehaviourDatabase()", 1)[1]
        destructor = destructor.split("bool BehaviourDatabase::loadDatabase", 1)[0]

        self.assertLess(destructor.index("reset();"), destructor.index("delete behaviour;"))


if __name__ == "__main__":
    unittest.main()
