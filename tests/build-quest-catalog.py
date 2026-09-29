"""Generate a reviewed, read-only quest catalog from the audited current map.

Generated files are mechanical output. Edit this manifest, not player storages.
Unknown map rewards retain descriptive names rather than guessed quest names.
"""

if not __debug__:
    raise SystemExit('Python optimization (-O) disables validation assertions; refusing to run this tool.')

import argparse
from collections import defaultdict
import json
from pathlib import Path
import re


def step(key, target, name):
    return dict(key=key,target=target,name=name)


def npc(id, name, region, description, steps, complete=None):
    return dict(id=id,name=name,region=region,kind='story',description=description,
                steps=[step(*s) for s in steps],complete=complete or [])


STORIES = [
    npc('banshee','The Banshee Quest','Ghostlands',
        'Pass the seals and speak to the Banshee Queen. Reward chests are listed separately. Access can also be unlocked by an existing server scroll.',
        [(4,1,'Seal of sacrifice'),(5,1,'Hidden seal'),
         (6,1,'Plague seal'),(7,1,'Demonrage seal'),(9,1,'Seal of the true path'),
         (10,1,'Seal of logic'),(11,1,"The Banshee Queen's kiss")], [[11,1]]),
    npc('postman','The Postman Missions','Kevin / mail guild',
        'Ask Kevin for missions and advancement. The log reads the existing guild ranks; a Postman Scroll can also unlock these privileges.',
        [(249,1,'Assistant postofficer requirements'),(249,2,'Postman requirements'),
         (249,3,'Grand postman requirements'),(249,4,'Special operations requirements'),
         (249,5,'Final delivery requirements'),(250,5,'Archpostman privileges')], [[250,5]]),
    npc('blue-djinn','Blue Djinn - Marid','Ashta\'daramai',
        "Work with Bo'ques, Fa'hradin and Gabel. Trading permission is recorded independently of earlier missions and can also come from a scroll.",
        [(280,2,'The dwarven cookbook'),(281,2,'The spy report'),(283,3,'Gabel: trading permission')], [[283,3]]),
    npc('green-djinn','Green Djinn - Efreet',"Mal'ouquah",
        "Work with Baa'leal, Alesar and Malor. Trading permission can also come from a scroll; the two allegiances are not interchangeable.",
        [(286,3,"Baa'leal's mission"),(287,3,'The Tear of Daraman'),(288,3,'Malor: trading permission')], [[288,3]]),
    npc('ape-city','The Ape City','Banuta / Hairycles',
        'Help Hairycles and report back after each task. Progress comes from the existing mission record.',
        [(293,n,name) for n,name in [(2,'Whisper moss'),(4,'The cough syrup'),
         (6,'The lizard parchment'),(8,'The ancient signs'),(10,'The hydra egg'),(12,'The charm of life'),
         (14,'The rotten casks'),(16,'The holy hair'),(18,'The final mission')]], [[293,18]]),
    npc('explorers','The Explorer Society','Port Hope / Northport',
        'Join the Explorer Society through Angus or Mortimer, finish research missions and report your discoveries.',
        [(300,1,'Join the society'),(304,6,'Butterfly hunt'),(305,6,'Plant collection'),
         (306,2,'Ice delivery'),(308,2,'Lizard urn'),(309,2,'Beholder secrets'),
         (310,2,'Orc powder'),(311,2,'Elven poetry'),(313,2,'Memory stone'),
         (315,2,'Rune writings'),(317,2,'Ectoplasm'),(318,2,'Spectral dress'),
         (323,1,'Astral travel')], [[323,1]]),
    npc('explorer-skull',"Explorer Society - Ratha's Skull",'Explorer bases',
        'Return the lost skull to a member of the Explorer Society.',[(302,1,"Return Ratha's skull")]),
    npc('explorer-hammer','Explorer Society - Giant Smithhammer','Explorer bases',
        'Bring the giant smithhammer to a member of the Explorer Society.',[(303,1,'Deliver the smithhammer')]),
    npc('sam-backpack',"Sam's Old Backpack",'Thais / Kazordoon',
        'Return the old backpack to Sam, speak with Kroox and recover the dwarven armor.',
        [(289,1,'Return the backpack to Sam'),(289,2,'Speak with Kroox'),(290,1,'Recover the dwarven armor')]),
    npc('white-raven','White Raven Monastery','Isle of the Kings',
        'Speak to Costello about the monastery and its catacombs. Recover the diary and return it to him.',
        [(63,1,'Catacomb permission'),(219,2,"Return Brother Fugio's diary")]),
    npc('windtrouser',"Windtrouser's Passage",'Isle of the Kings',
        'Help Windtrouser to earn passage as a friend.',[(62,2,'Gain the friendship of Windtrouser')]),
    npc('old-dragon','The Old Dragon','Dragon cemetery',
        'Bring the requested mushroom to the old dragon.',[(66,1,'Help the old dragon')]),
    npc('paradox-clues','Paradox Tower - The Tale of Hugo','Mainland',
        'Follow the existing clues from Oldrak, Zoltan, Padreia and Lubo. These clues are not the completion record of the tower treasure.',
        [(211,1,'Oldrak: the tale'),(211,2,'Zoltan: the druids'),
         (211,3,"Padreia: Crunor's Cottage"),(211,4,"Lubo: the old cottage")]),
]

# Names whose map positions/rewards are identified in this server. Other
# entries intentionally use reward names and approximate regions.
CHEST_NAMES = {37:'Desert Dungeon',50:'Black Knight - Crown Shield',
    154:'Black Knight - Crown Armor',137:'Crusader Helmet',146:'Devil Helmet',
    147:'Devil Helmet - Halberd',151:'Noble Armor',152:'Noble Armor - Crown Helmet',
    155:'Naginata',187:'Demon Helmet',188:'Demon Helmet - Demon Shield',
    189:'Demon Helmet - Steel Boots',200:'Orc Fortress - Knight Axe',
    201:'Orc Fortress - Knight Armor',202:'Orc Fortress - Fire Sword',
    203:'The Annihilator',290:'Dwarven Armor',
    41:'Paradox Tower - Wand',42:'Paradox Tower - Coins',
    43:'Paradox Tower - Talons',44:'Paradox Tower - Phoenix Egg',
    261:'Ancient Helmet - Ornament',262:'Ancient Helmet - Gem Holder',
    263:'Ancient Helmet - Right Horn',264:'Ancient Helmet - Left Horn',
    265:'Ancient Helmet - Damaged Helmet',266:'Ancient Helmet - Piece',
    267:'Ancient Helmet - Adornment'}


def clean(name):
    return re.sub(r'^(a|an) ', '', name).strip()


def reward(item):
    name = clean(item['name'])
    count = item['attributes'].get('15',1)
    label = (f'{count} x ' if count > 1 else '') + name
    if item['contents']:
        label += ' (' + ', '.join(reward(i) for i in item['contents']) + ')'
    return label


def build(data):
    grouped = defaultdict(list)
    for chest in data['chests']:
        assert chest['contents'], 'Empty quest chest must be reviewed'
        assert not chest['attributes'].get('4'), 'Action override must be reviewed'
        grouped[int(chest['attributes']['28'])].append(chest)
    quests = list(STORIES)
    for key,chests in sorted(grouped.items()):
        pos = chests[0]['pos']
        town = min(data['towns'],key=lambda t:(pos[0]-t['pos'][0])**2+(pos[1]-t['pos'][1])**2)
        rewards = list(dict.fromkeys(reward(c['contents'][0]) for c in chests))
        first = chests[0]['contents'][0]
        notable = first['contents'][0] if first['contents'] else first
        title = CHEST_NAMES.get(key, clean(notable['name']).title() + ' - ' + town['name'])
        if key in (193,194,195,196,197,198): title = 'Banshee - ' + clean(first['name']).title()
        description = 'Map quest reward. The original server records completion only; travel and combat are not recorded. Region is approximate.'
        if len(rewards)>1:
            description += ' These alternatives share one completion record; they are not separate rewards to claim.'
        if key == 203:
            description = 'The Annihilator trial. This server marks the record when leaving the trial as well as when taking a reward; completion does not prove which reward was taken.'
        quests.append(dict(id=f'chest-{key}',name=title,region='Near '+town['name'],
            kind='chest',description=description,rewards=' / '.join(rewards),
            steps=[step(key,1,'Completion registered by the server')],complete=[]))
    for arena,name in [(7100,'Greenhorn'),(7200,'Scrapper'),(7300,'Warlord')]:
        if str(arena) in data['movement_ids'] and data['action_ids'].get('5555'):
            quests.append(npc(f'arena-{arena}',f'Arena - {name}','Arena / Angel',
                'The arena uses its existing admission and reward flags. This log does not grant entry or prizes.',
                [(arena,1,'Arena admission'),(arena+500,1,'Reward received')],[[arena+500,1]]))
    duplicate_names = defaultdict(list)
    for q in quests: duplicate_names[q['name']].append(q)
    for group in duplicate_names.values():
        if len(group)>1:
            for q in group: q['name'] += ' ['+q['id'].split('-')[-1]+']'
    quests.sort(key=lambda q:(q['kind']=='chest',q['name'].lower()))
    assert len({q['id'] for q in quests})==len(quests)
    assert all(len(q['name'])<=100 and len(q['steps'])<=30 for q in quests)
    return quests


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('audit',type=Path)
    args=parser.parse_args()
    data=json.loads(args.audit.read_text())
    quests=build(data)
    target=Path('data/lib/custom/questCatalog.lua')
    content='-- Generated by tests/build-quest-catalog.py; read-only original storage rules.\n'
    content+='-- Source map SHA-256: '+data['map_sha256']+'\n'
    content+='return json.decode([=[\n'+json.dumps(quests,indent=2)+'\n]=])\n'
    target.write_text(content,encoding='utf-8',newline='\n')
    print(f'Generated {len(quests)} entries; {len(data["chests"])} mapped chest objects, {len({c["attributes"]["28"] for c in data["chests"]})} chest flags.')
