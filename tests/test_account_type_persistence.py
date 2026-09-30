import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AccountTypePersistenceTests(unittest.TestCase):
    def test_database_setter_reports_validation_and_sql_failures(self):
        header = (ROOT / "src" / "iologindata.h").read_text(encoding="utf-8-sig")
        source = (ROOT / "src" / "iologindata.cpp").read_text(encoding="utf-8-sig")
        self.assertIn("static bool setAccountType(uint32_t accountId, AccountType_t accountType);", header)
        setter = source.split("bool IOLoginData::setAccountType(", 1)[1].split("\n}", 1)[0]
        self.assertIn("accountType < ACCOUNT_TYPE_NORMAL || accountType > ACCOUNT_TYPE_GOD", setter)
        self.assertIn("return Database::getInstance()->executeQuery(query.str());", setter)

    def test_lua_binding_changes_live_sessions_only_after_successful_write(self):
        source = (ROOT / "src" / "luascript.cpp").read_text(encoding="utf-8-sig")
        body = source.split("int LuaScriptInterface::luaPlayerSetAccountType(", 1)[1]
        body = body.split("\nint LuaScriptInterface::luaPlayerGetCapacity(", 1)[0]
        persist = body.index("if (!IOLoginData::setAccountType(accountId, accountType))")
        update_sessions = body.index("for (const auto& playerEntry : g_game.getPlayers())")
        self.assertLess(persist, update_sessions)
        self.assertIn("pushBoolean(L, false);", body[persist:update_sessions])
        self.assertIn("onlinePlayer->getAccount() == accountId", body)
        self.assertIn("onlinePlayer->accountType = accountType;", body)

    def test_tutor_commands_do_not_report_success_after_persistence_failure(self):
        add_tutor = (ROOT / "data" / "talkactions" / "scripts" / "add_tutor.lua").read_text(encoding="utf-8-sig")
        remove_tutor = (ROOT / "data" / "talkactions" / "scripts" / "remove_tutor.lua").read_text(encoding="utf-8-sig")
        self.assertIn("if not target:setAccountType(ACCOUNT_TYPE_TUTOR) then", add_tutor)
        self.assertLess(add_tutor.index("if not target:setAccountType"), add_tutor.index("You have been promoted"))
        self.assertIn("if not target:setAccountType(ACCOUNT_TYPE_NORMAL) then", remove_tutor)
        self.assertIn("if not db.query(\"UPDATE `accounts`", remove_tutor)
        self.assertLess(remove_tutor.index("if not db.query("), remove_tutor.index("You have demoted"))
        self.assertIn("result.free(resultId)\n\t\tplayer:sendCancelMessage(\"You can only demote", remove_tutor)


if __name__ == "__main__":
    unittest.main()
