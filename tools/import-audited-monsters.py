"""Import confirmed monster numerical rules from the audited .mon datapack."""
import argparse,json,pathlib,re,xml.etree.ElementTree as ET

def norm(s):return re.sub('[^a-z0-9]','',s.lower())
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--source',type=pathlib.Path,required=True);ap.add_argument('--repo',type=pathlib.Path,default=pathlib.Path(__file__).resolve().parents[1]);args=ap.parse_args()
 repo=args.repo;root=repo/'data/monster';used=set();catalog=ET.parse(root/'monsters.xml').getroot();dest={}
 for n in catalog.findall('monster'):
  p=root/n.get('file','');
  if p.is_file():
   try:x=ET.parse(p).getroot();dest[norm(n.get('name',''))]=p
   except ET.ParseError:pass
 rows=[];mapped=0;damagecount=0
 types={1:'physical',2:'earth',4:'fire',8:'energy',32:'poisoncondition',64:'firecondition',128:'energycondition',256:'lifedrain',512:'manadrain'}
 canonical=set(types.values())|{'poison','healing'}
 for p in sorted(args.source.glob('*.mon')):
  text=p.read_text(encoding='latin1');name=re.search(r'^Name\s*=\s*"([^"]+)"',text,re.M).group(1);out=dest.get(norm(p.stem)) or dest.get(norm(name))
  if not out:rows.append({'source':p.name,'name':name,'status':'not-present-in-enabled-datapack'});continue
  if out in used:rows.append({'source':p.name,'name':name,'status':'duplicate-display-name-with-distinct-race'});continue
  used.add(out)
  tree=ET.parse(out,parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True)));x=tree.getroot();x.set('legacyreference','1')
  fist=re.search(r'\(FistFighting,\s*(-?\d+),\s*(-?\d+)',text);skill=max(int(fist[1]),int(fist[2])) if fist else 10;x.set('legacyfistskill',str(skill))
  scalar=lambda key,default=0:int(re.search(r'^'+key+r'\s*=\s*(-?\d+)',text,re.M).group(1)) if re.search(r'^'+key+r'\s*=',text,re.M) else default
  x.set('experience',str(scalar('Experience')))
  defense=x.find('defenses')
  if defense is None:defense=ET.SubElement(x,'defenses')
  defense.set('defense',str(scalar('Defend')));defense.set('armor',str(scalar('Armor')))
  attacks=x.find('attacks')
  if attacks is None:attacks=ET.SubElement(x,'attacks')
  existing=list(attacks)+list(defense);melee=next((a for a in attacks if a.get('name')=='melee'),None)
  if melee is None:melee=ET.SubElement(attacks,'attack',{'name':'melee','interval':'2000','chance':'0'})
  melee.set('attack',str(scalar('Attack')));melee.set('skill',str(skill));poison=scalar('Poison')
  if poison:melee.set('poison',str(poison))
  elif 'poison'in melee.attrib:del melee.attrib['poison']
  for section in [attacks,defense]:
   for n in list(section):
    if n.get('name','').lower() in canonical:section.remove(n)
  block=re.search(r'Spells\s*=\s*\{(.*?)\}',text,re.S);spellrows=[]
  if block:
   pattern=r'(Actor|Victim|Destination|Angle|Origin)\s*\(([^)]*)\)\s*->\s*(Damage|Healing)\s*\(([^)]*)\)\s*:\s*(\d+)'
   for form,raw,impact,values,delay in re.findall(pattern,block.group(1)):
    geom=[int(v.strip()) for v in raw.split(',') if v.strip()];v=[int(z.strip()) for z in values.split(',')];typ=types.get(v[0]) if impact=='Damage' else 'healing'
    if not typ:continue
    base,var=(v[1],v[2]) if impact=='Damage' else(v[0],v[1]);old=next((a for a in existing if a.get('name')==typ and bool(a.get('length'))==(form=='Angle')),None)
    attrs={'name':typ,'legacychance':delay,'interval':old.get('interval','2000') if old is not None else '2000','chance':'0','min':str(base-var if impact=='Healing' else -(base-var)),'max':str(base+var if impact=='Healing' else -(base+var))}
    section=defense if impact=='Healing' and form=='Actor' else attacks;node=ET.SubElement(section,'defense' if section is defense else 'attack',attrs)
    if form=='Angle':node.set('length',str(geom[1]));node.set('spread','0' if geom[0]==0 else (old.get('spread','3') if old is not None else '3'))
    elif form=='Destination':node.set('range',str(geom[0]));node.set('radius',str(geom[1]+1));node.set('target','1')
    elif form=='Victim':node.set('range',str(geom[0]));node.set('target','1')
    elif form=='Origin':node.set('radius',str(geom[0]+1));node.set('target','0')
    if old is not None:
     for attr in old:
      if attr.tag=='attribute':node.append(ET.fromstring(ET.tostring(attr)))
    spellrows.append({'form':form,'geometry':geom,'type':v[0] if impact=='Damage' else'healing','base':base,'variation':var,'divisor':int(delay)});damagecount+=impact=='Damage'
  ET.indent(tree,space='\t');tree.write(out,encoding='utf-8',xml_declaration=True);mapped+=1
  rows.append({'source':p.name,'name':name,'file':out.relative_to(repo).as_posix(),'status':'mapped','attack':scalar('Attack'),'defend':scalar('Defend'),'armor':scalar('Armor'),'fist':skill,'poison':poison,'spells':spellrows})
 target=repo/'tests/fixtures/audited-monster-rules.json';target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps({'reference_sha256':'61ec3c56da0a2e328834e94fb0bb5aa87ed9211ab26eb7d8c11d508060112b69','mapped':mapped,'damage_entries':damagecount,'monsters':rows},indent=2),encoding='utf-8');print(mapped,'mapped monsters;',damagecount,'damage entries')
if __name__=='__main__':main()
