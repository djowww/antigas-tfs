import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "data" / "talkactions" / "scripts"


class StaffBanCommandTests(unittest.TestCase):
    def test_account_ban_verifies_group_and_duration_before_write(self):
        source = (SCRIPTS / "ban.lua").read_text(encoding="utf-8-sig")
        self.assertIn("SELECT `account_id`, `group_id` FROM `players`", source)
        self.assertIn("local targetGroup = target:getGroup()", source)
        self.assertIn("local targetGroup = Group(result.getDataInt(resultId, \"group_id\"))", source)
        self.assertIn("SELECT `players`.`group_id`, `accounts`.`type` AS `account_type`", source)
        self.assertIn("until not result.next(accountResultId)", source)
        self.assertIn("accountType >= ACCOUNT_TYPE_TUTOR", source)
        self.assertIn("if accountHasStaff then", source)
        self.assertLess(source.index("accountType >= ACCOUNT_TYPE_TUTOR"), source.index("SELECT 1 FROM `account_bans`"))
        self.assertLess(source.index("if accountHasStaff then"), source.index("SELECT 1 FROM `account_bans`"))
        self.assertIn("banDays == math.huge or banDays ~= math.floor(banDays)", source)
        insert = source.index("if not db.query(\"INSERT INTO `account_bans`")
        remove = source.index("target:remove()")
        self.assertLess(insert, remove)

    def test_ip_ban_checks_target_staff_and_inserts_before_kicking(self):
        source = (SCRIPTS / "ipban.lua").read_text(encoding="utf-8-sig")
        self.assertIn("SELECT `players`.`lastip`, `players`.`group_id`, `players`.`account_id`, `accounts`.`type` AS `account_type`", source)
        self.assertIn("targetGroup:getAccess()", source)
        self.assertIn("if targetGroup == nil then", source)
        self.assertIn("targetAccountType >= ACCOUNT_TYPE_TUTOR", source)
        self.assertIn("SELECT `group_id` FROM `players` WHERE `account_id` = ", source)
        self.assertIn("until not result.next(accountGroupResultId)", source)
        self.assertIn("if accountGroupUnverified then", source)
        self.assertIn("if accountHasStaff then", source)
        self.assertIn("if not targetIp or targetIp == 0 then", source)
        self.assertIn("DELETE FROM `ip_bans` WHERE `ip` = ", source)
        self.assertIn("`expires_at` != 0 AND `expires_at` <= ", source)
        self.assertIn("db.storeQueryChecked(\"SELECT 1 FROM `ip_bans`", source)
        insert = source.index("if not db.query(\"INSERT INTO `ip_bans`")
        remove = source.index("targetPlayer:remove()")
        account_staff_check = source.index("if accountHasStaff then")
        self.assertLess(account_staff_check, insert)
        self.assertLess(insert, remove)

    def test_ip_ban_behavioral_harness_runs_in_ci(self):
        root = Path(__file__).resolve().parents[1]
        harness = root / "tests" / "ipban-security-tests.lua"
        workflow = (root / ".github" / "workflows" / "security-build.yml").read_text(encoding="utf-8")
        self.assertTrue(harness.is_file())
        self.assertIn("luajit tests/ipban-security-tests.lua", workflow)


if __name__ == "__main__":
    unittest.main()
