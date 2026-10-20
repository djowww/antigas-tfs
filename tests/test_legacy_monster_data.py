import unittest, pathlib, json, re, xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).resolve().parents[1]
class AuditedMonsterData(unittest.TestCase):
 def test_dragon_exact_probability_divisors(self):
  x=ET.parse(ROOT/'data/monster/dragon.xml').getroot()
  attacks=x.findall('./attacks/attack')+x.findall('./defenses/defense')
  fire=[a for a in attacks if a.get('name')=='fire']
  self.assertEqual(sorted(int(a.get('legacychance','0')) for a in fire),[7,9])
 def test_demon_has_audited_mana_drain(self):
  x=ET.parse(ROOT/'data/monster/demon.xml').getroot()
  attack=x.find('./attacks/attack[@name="manadrain"]')
  self.assertIsNotNone(attack)
  self.assertEqual((attack.get('min'),attack.get('max'),attack.get('legacychance')),('-40','-100','8'))
 def test_circle_native_offset(self):
  old=json.loads((ROOT/'tests/fixtures/audited-circle-labels.json').read_text())
  source=(ROOT/'src/combat.cpp').read_text(encoding='utf-8-sig')
  block=re.search(r'int32_t area\[13\]\[13\] = \{(.*?)\n\s*\};',source,re.S).group(1)
  matrix=[[int(n) for n in re.findall(r'\d+',row)] for row in re.findall(r'\{([^}]+)\}',block)]
  self.assertEqual(len(matrix),13)
  for y in range(13):
   for x in range(13):self.assertEqual(matrix[y][x],0 if old[y+4][x+4]==99 else old[y+4][x+4]+1)
 def test_all_origin_areas_preserved(self):
  data=json.loads((ROOT/'tests/fixtures/audited-monster-rules.json').read_text())
  names={1:'physical',2:'earth',4:'fire',8:'energy',32:'poisoncondition',64:'firecondition',128:'energycondition',256:'lifedrain',512:'manadrain'}
  for row in data['monsters']:
   if row['status']!='mapped':continue
   nodes=ET.parse(ROOT/row['file']).getroot().findall('./attacks/attack')
   for spell in row['spells']:
    if spell['form']!='Origin' or not isinstance(spell['type'],int):continue
    matches=[n for n in nodes if n.get('name')==names[spell['type']] and n.get('legacychance')==str(spell['divisor'])]
    self.assertTrue(any(n.get('radius')==str(spell['geometry'][0]+1) and n.get('target')=='0' for n in matches),row['file'])
 def test_registry_canonical_names(self):
  for name in ['orc','orcwarlord','larva','skeleton','poisonspider','slime']:
   self.assertEqual(ET.parse(ROOT/('data/monster/'+name+'.xml')).getroot().get('legacyreference'),'1',name)
if __name__=='__main__':unittest.main()
