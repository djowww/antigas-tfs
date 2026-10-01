import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
XML_PATH = ROOT / "data" / "talkactions" / "talkactions.xml"
SCRIPT_ROOT = ROOT / "data" / "talkactions" / "scripts"

EXPECTED_POLICIES = {
    "/storage": ("access", None), "/ban": ("access", None), "/ipban": ("access", None),
    "/unban": ("access", None), "/up": ("access", None), "/down": ("access", None),
    "/c": ("access", None), "/goto": ("access", None), "/gotopos": ("access", None),
    "/owner": ("access", "god"), "/t": ("access", None), "/town": ("access", None),
    "/a": ("access", None), "/pos": ("public", None), "/r": ("access", None),
    "/kick": ("access", None), "/openserver": ("access", "god"),
    "/closeserver": ("access", "god"), "/B": ("broadcast", None),
    "/m": ("access", "god"), "/i": ("access", "god"), "/s": ("access", "god"),
    "/addtutor": ("account", "senior-tutor"), "/removetutor": ("account", "senior-tutor"),
    "/looktype": ("access", None), "/summon": ("access", "god"),
    "/chameleon": ("access", "god"), "/addskill": ("access", "god"),
    "/addatk": ("access", "god"), "/resetatk": ("access", "god"),
    "/mccheck": ("access", "god"), "/ghost": ("access", "gamemaster"),
    "/clean": ("access", "god"), "/storagevalue": ("access", None),
    "/globalboost": ("access", "god"), "/mute": ("account", "tutor"),
    "!buyhouse": ("public", None), "!leavehouse": ("public", None),
    "!frags": ("public", None), "!share": ("public", None),
    "!uptime": ("public", None), "!serverinfo": ("public", None),
    "!online": ("access", None), "!spells": ("public", None),
    "!deathlist": ("public", None), "!pz": ("public", None),
    "!z": ("access", None), "!x": ("access", None),
}


class TalkActionAuthorizationTests(unittest.TestCase):
    def test_all_active_commands_have_the_reviewed_policy(self):
        root = ET.parse(XML_PATH).getroot()
        actual = {}
        for action in root.findall("talkaction"):
            command = action.get("words", "")
            if not command.startswith(("/", "!")):
                continue
            self.assertNotIn(command, actual, f"duplicate active command: {command}")
            policy = action.get("permission")
            minimum = action.get("minaccounttype")
            actual[command] = (policy, minimum)
            script = action.get("script")
            self.assertTrue(script, f"missing script for {command}")
            self.assertTrue((SCRIPT_ROOT / script).is_file(), f"missing script for {command}: {script}")

            source = (SCRIPT_ROOT / script).read_text(encoding="utf-8-sig")
            if policy == "access":
                self.assertIn("getGroup():getAccess()", source, f"retain script-side access check for {command}")
            elif policy == "account":
                self.assertIn("getAccountType()", source, f"retain script-side account check for {command}")
            elif policy == "broadcast":
                self.assertIn("PlayerFlag_CanBroadcast", source, f"retain broadcast flag check for {command}")
            elif command == "/pos":
                self.assertIn("getGroup():getAccess() and param ~= \"\"", source,
                              "only staff may use /pos to teleport; public position lookup remains available")

        self.assertEqual(actual, EXPECTED_POLICIES)

    def test_dispatcher_applies_explicit_policies_to_both_command_prefixes(self):
        source = (ROOT / "src" / "talkaction.cpp").read_text(encoding="utf-8-sig")
        self.assertIn("talkactionWords.front() == '/' || talkactionWords.front() == '!'", source)
        self.assertIn("words.front() == '/' || words.front() == '!'", source)
        self.assertNotIn("Player-facing bang commands are reserved for staff", source)


if __name__ == "__main__":
    unittest.main()
