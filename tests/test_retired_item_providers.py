"""Inventory real static providers; no server/database is contacted."""
import json
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
RETIRED = {entry['id'] for entry in json.loads((ROOT / 'data/items/retired-items.json').read_text(encoding='utf-8'))['ids']}

def ids_for_element(element):
    ids = set()
    for name in ('itemid', 'id'):
        if name in element.attrib:
            ids.update(int(part) for part in re.findall(r'\d+', element.attrib[name]))
    if 'fromid' in element.attrib and 'toid' in element.attrib:
        ids.update(range(int(element.attrib['fromid']), int(element.attrib['toid']) + 1))
    return ids

class RetiredProviderDefinitions(unittest.TestCase):
    def test_antigas_coin_has_one_registered_redemption_action(self):
        actions = ET.parse(ROOT / 'data/actions/actions.xml').getroot()
        matches = [a for a in actions if 5130 in ids_for_element(a)]
        self.assertEqual(len(matches), 1, 'Physical Antigas Coins must have exactly one use action')
        self.assertEqual(matches[0].get('script'), 'others/olderac.lua')

    def test_antigas_coin_is_active_while_ticket_stays_retired(self):
        self.assertNotIn(5130, RETIRED, 'Antigas Coin must be available to the Store and Market')
        self.assertIn(5128, RETIRED, 'Antigas Ticket must remain retired')

    def test_retired_loot_is_not_offered_by_monster_definitions(self):
        found = []
        for file in (ROOT / 'data/monster').rglob('*.xml'):
            doc = ET.fromstring(file.read_bytes())
            for element in doc.findall('.//loot//item'):
                for item_id in ids_for_element(element) & RETIRED:
                    found.append((str(file.relative_to(ROOT)), item_id))
        self.assertEqual(found, [], 'Retired items must not remain in static loot providers')

    def test_retired_npc_trade_and_creation_rules_are_absent(self):
        found = []
        for file in (ROOT / 'data/npc').rglob('*'):
            if file.suffix.lower() not in ('.npc', '.ndb'):
                continue
            for line_number, line in enumerate(file.read_text(encoding='latin1').splitlines(), 1):
                if line.lstrip().startswith('#'):
                    continue
                for match in re.finditer(r'\b(?:Type\s*=\s*|Create(?:Inventory|Container)?\s*\(\s*)(\d+)', line, re.I):
                    if int(match[1]) in RETIRED:
                        found.append((str(file.relative_to(ROOT)), line_number, int(match[1])))
        self.assertEqual(found, [], 'NPCs must not quote, sell, buy or create retired goods')

    def test_monster_outfit_attacks_do_not_display_retired_item_sprites(self):
        found = []
        for file in (ROOT / 'data/monster').rglob('*.xml'):
            doc = ET.fromstring(file.read_bytes())
            for element in doc.findall('.//attack'):
                if int(element.attrib.get('item', '0')) in RETIRED:
                    found.append((str(file.relative_to(ROOT)), int(element.attrib['item'])))
        self.assertEqual(found, [], 'A retired item cannot remain as an outfit disguise')

    def test_retired_item_actions_and_weapons_are_not_registered(self):
        found = []
        for relative in ('data/actions/actions.xml', 'data/movements/movements.xml', 'data/weapons/weapons.xml'):
            file = ROOT / relative
            doc = ET.fromstring(file.read_bytes())
            for element in doc:
                for item_id in ids_for_element(element) & RETIRED:
                    found.append((relative, element.tag, item_id))
        self.assertEqual(found, [], 'Retired item IDs must have no usable action/weapon registrations')

if __name__ == '__main__':
    unittest.main()
