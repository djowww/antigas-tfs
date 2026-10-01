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

    def test_database_account_type_loaders_validate_before_enum_cast(self):
        authentication_header = (ROOT / "src" / "authentication.h").read_text(encoding="utf-8-sig")
        authentication = (ROOT / "src" / "authentication.cpp").read_text(encoding="utf-8-sig")
        source = (ROOT / "src" / "iologindata.cpp").read_text(encoding="utf-8-sig")
        self.assertIn("value >= ACCOUNT_TYPE_NORMAL && value <= ACCOUNT_TYPE_GOD", authentication_header)
        self.assertIn("if (!isValidAccountTypeValue(row.type))", authentication)

        load_account = source.split("Account IOLoginData::loadAccount(", 1)[1].split("\nbool IOLoginData::saveAccount", 1)[0]
        get_account_type = source.split("AccountType_t IOLoginData::getAccountType(", 1)[1].split("\nbool IOLoginData::setAccountType", 1)[0]
        preload = source.split("bool IOLoginData::preloadPlayer(", 1)[1].split("\nbool IOLoginData::loadPlayerById", 1)[0]
        load_player = source.split("bool IOLoginData::loadPlayer(Player*", 1)[1].split("\nvoid IOLoginData::loadItems", 1)[0]

        for body, value_field in (
            (load_account, 'getNumber<int64_t>("type")'),
            (get_account_type, 'getNumber<int64_t>("type")'),
            (preload, 'getNumber<int64_t>("account_type")'),
        ):
            self.assertIn(value_field, body)
            validation = body.index("if (!isValidAccountTypeValue(rawAccountType))")
            cast = body.index("static_cast<AccountType_t>(rawAccountType)")
            self.assertLess(validation, cast)

        self.assertIn("if (acc.id != accno)", load_player)
        self.assertLess(load_player.index("if (acc.id != accno)"), load_player.index("player->accountType = acc.accountType"))

    def test_lua_binding_changes_live_sessions_only_after_successful_write(self):
        source = (ROOT / "src" / "luascript.cpp").read_text(encoding="utf-8-sig")
        body = source.split("int LuaScriptInterface::luaPlayerSetAccountType(", 1)[1]
        body = body.split("\nint LuaScriptInterface::luaPlayerGetCapacity(", 1)[0]
        validate_input = body.index("if (!isValidAccountTypeNumber(rawAccountType))")
        narrow_input = body.index("static_cast<AccountType_t>(rawAccountType)")
        persist = body.index("if (!IOLoginData::setAccountType(accountId, accountType))")
        update_sessions = body.index("for (const auto& playerEntry : g_game.getPlayers())")
        self.assertLess(validate_input, narrow_input)
        self.assertLess(narrow_input, persist)
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
        session_scan = remove_tutor.index("for _, onlinePlayer in ipairs(Game.getPlayers()) do")
        sync_account = remove_tutor.index("if not accountSession:setAccountType(ACCOUNT_TYPE_NORMAL) then")
        direct_update = remove_tutor.index("elseif not db.query(\"UPDATE `accounts`")
        self.assertLess(session_scan, sync_account)
        self.assertLess(sync_account, direct_update)
        self.assertIn("onlinePlayer:getAccountId() == accountId", remove_tutor)
        self.assertLess(remove_tutor.index("if not db.query("), remove_tutor.index("You have demoted"))
        self.assertIn("result.free(resultId)\n\t\tplayer:sendCancelMessage(\"You can only demote", remove_tutor)


if __name__ == "__main__":
    unittest.main()
