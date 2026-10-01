import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]


class LampStateParserSourceTests(unittest.TestCase):
    def test_persisted_state_parser_does_not_evaluate_and_bounds_reads(self):
        source = (ROOT / "data" / "lib" / "lamp_states.lua").read_text(encoding="utf-8")

        self.assertNotIn("loadstring(", source)
        self.assertIn("local maxBytes = 8 * 1024 * 1024", source)
        self.assertIn("local maxEntries = 100000", source)
        self.assertIn("file:read(8 * 1024 * 1024 + 1)", source)
        self.assertNotIn("body:sub(token)", source)
        self.assertIn("lampTransformIds[itemId]", source)
        self.assertIn("reverseLampTransformIds[itemId]", source)

    def test_legacy_analyzer_unserializer_is_not_reintroduced(self):
        analyzer = (ROOT / "data" / "lib" / "core" / "analyzersLib.lua").read_text(encoding="utf-8")
        bootstrap = (ROOT / "data" / "lib" / "lib.lua").read_text(encoding="utf-8")
        lamp_states = (ROOT / "data" / "lib" / "lamp_states.lua").read_text(encoding="utf-8")

        self.assertNotIn("function unserialize(", analyzer)
        self.assertNotIn("function serialize(", analyzer)
        self.assertNotIn("loadstring", analyzer)
        self.assertLess(
            bootstrap.index("dofile('data/lib/core/core.lua')"),
            bootstrap.index("dofile('data/lib/lamp_states.lua')"),
        )
        self.assertIn("function unserialize(str)", lamp_states)
        self.assertIn("msg:addString(serialize(res))", analyzer)

    def test_lamp_house_action_uses_same_tile_and_invitation_policy(self):
        action = (ROOT / "data" / "actions" / "scripts" / "others" / "lamp_states.lua").read_text(encoding="utf-8")
        library = (ROOT / "data" / "lib" / "lamp_states.lua").read_text(encoding="utf-8")
        interface = (ROOT / "src" / "luascript.cpp").read_text(encoding="utf-8")
        header = (ROOT / "src" / "luascript.h").read_text(encoding="utf-8")

        self.assertIn("if fromPosition ~= toPosition then", action)
        self.assertIn("house:isInvited(player)", action)
        self.assertIn("configKeys.ONLY_INVITED_CAN_MOVE_HOUSE_ITEMS", action)
        self.assertLess(action.index("house:isInvited(player)"), action.index("item:transform(transformId)"))
        self.assertLess(action.index("fromPosition ~= toPosition"), action.index("storeLampState(toPosition, transformId)"))
        self.assertIn("MAX_LAMP_STATE_ENTRIES = 100000", library)
        self.assertIn("MAX_LAMP_STATE_FILE_BYTES = 8 * 1024 * 1024", library)
        self.assertIn("if not canStoreLampState(toPosition) then", action)
        self.assertLess(action.index("not canStoreLampState(toPosition)"), action.index("item:transform(transformId)"))
        self.assertIn('registerMethod("House", "isInvited", LuaScriptInterface::luaHouseIsInvited);', interface)
        self.assertIn('registerEnumIn("configKeys", ConfigManager::ONLY_INVITED_CAN_MOVE_HOUSE_ITEMS)', interface)
        self.assertIn("static int luaHouseIsInvited(lua_State* L);", header)
        self.assertIn("house && player && house->isInvited(player)", interface)


if __name__ == "__main__":
    unittest.main()
