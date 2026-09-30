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
        self.assertIn("SELECT `group_id` FROM `players` WHERE `account_id` = ", source)
        self.assertIn("until not result.next(accountResultId)", source)
        self.assertIn("if accountHasStaff then", source)
        self.assertLess(source.index("if accountHasStaff then"), source.index("SELECT 1 FROM `account_bans`"))
        self.assertIn("banDays == math.huge or banDays ~= math.floor(banDays)", source)
        insert = source.index("if not db.query(\"INSERT INTO `account_bans`")
        remove = source.index("target:remove()")
        self.assertLess(insert, remove)

    def test_ip_ban_checks_target_staff_and_inserts_before_kicking(self):
        source = (SCRIPTS / "ipban.lua").read_text(encoding="utf-8-sig")
        self.assertIn("SELECT `lastip`, `group_id` FROM `players`", source)
        self.assertIn("targetGroup:getAccess()", source)
        self.assertIn("if targetGroup == nil then", source)
        self.assertIn("if not targetIp or targetIp == 0 then", source)
        self.assertIn("db.storeQueryChecked(\"SELECT 1 FROM `ip_bans`", source)
        insert = source.index("if not db.query(\"INSERT INTO `ip_bans`")
        remove = source.index("targetPlayer:remove()")
        self.assertLess(insert, remove)


if __name__ == "__main__":
    unittest.main()
