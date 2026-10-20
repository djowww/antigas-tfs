"""Closed-world simulation of bot decisions using Rat or Cave Rat definitions.

The fixture has a Rook sewer grate, observed cave tiles, and one prey per
agent. It never opens a network or production connection.
"""
import argparse
import random
from pathlib import Path

from .autonomous_players.app import classify_learning_action, select_actions_with_learning
from .autonomous_players.behaviour import Agent
from .autonomous_players.definitions import load_items
from .autonomous_players.learning_bridge import LearningAgent
from .autonomous_players.learning_protocol import LearningObservation
from .autonomous_players.learning_store import LearningStore
from .autonomous_players.learning import Policy
from .autonomous_players.progression import Progression
from .autonomous_players.routes import RouteGraph
from .autonomous_players.runtime import ActionGate
from .autonomous_players.store import Store
from .autonomous_players.world import Container, Creature, Event, Position, Stats, Thing, World
from .autonomous_players.navigation import DIRECTIONS


def _world_for(index, items, prey_profile, unrelated_open_corpse=False):
    start=Position(32109,32245,7)
    grate=Position(32110,32245,7)
    below=Position(32110,32246,8)
    middle=Position(32111,32246,8)
    goal=Position(32112,32246,8)
    world=World(self_id=0x10000001+index,position=start,
                stats=Stats(150,150,400,0,1))
    world.tiles[start]=[Thing(102)]
    world.tiles[grate]=[Thing(428)]
    for x in range(32110,32115):
        for y in range(32244,32249):
            tile=Position(x,y,8)
            world.tiles[tile]=[Thing(102)]
    world.creatures[0x40000001+index]=Creature(0x40000001+index,prey_profile['name'],
                                               goal.shift(x=1),health=prey_profile['health'])
    world.containers[0]=Container(0,2853,'backpack',20,False,[])
    if unrelated_open_corpse:
        world.containers[1]=Container(1,4173,'dead rabbit',10,False,
                                      [Thing(prey_profile['food'],1)])
    routes=RouteGraph({start:None,grate:below,below:None,middle:None,goal:None})
    profile=dict(account=index+1,character=f'Sim-{index+1:02d}',city='thais',vocation='knight')
    progression=Progression(profile,world,items,routes,rook_bounds=(32000,32000,32200,32350),
                            hunting_points=[(goal.x,goal.y,goal.z)])
    return world,profile,progression,goal


def _apply_packet(packet,world,agent,progression,gate,now,metrics,prey_profile):
    if not packet or not gate.permit(packet):
        return False
    metrics['accepted_packets']+=1
    op=packet[0]
    if op in DIRECTIONS.values():
        dx,dy=next(delta for delta,opcode in DIRECTIONS.items() if opcode==op)
        old=world.position
        destination=old.shift(dx,dy)
        if progression.floor_authorization and progression.floor_authorization[0]==destination:
            destination=progression.routes.tiles[destination]
        world.previous_position,world.position=old,destination
        if old.z==7 and destination.z==8:
            metrics['sewer_entries']+=1
        movement=Event('move',(world.self_id,old,destination))
        agent.observe([movement],now+.01)
        progression.observe([movement],now+.01)
        return True
    if op==0xa1 and len(packet)==5:
        creature=world.creatures.get(int.from_bytes(packet[1:5],'little'))
        if not creature or not creature.position or creature.health<=0 or creature.position.distance(world.position)>1:
            return True
        creature.health-=20
        metrics['attacks']+=1
        if creature.health<=0:
            tile=creature.position
            creature.position=None
            world.stats.experience+=prey_profile['experience']
            world.tiles[tile].append(Thing(prey_profile['corpse']))
            metrics['rats_killed']+=1
            metrics['xp_gain']+=prey_profile['experience']
            agent.observe([Event('stats',world.stats),Event('tile',tile)],now+.01)
        return True
    if op==0x82 and len(packet)>=10:
        x=int.from_bytes(packet[1:3],'little')
        y=int.from_bytes(packet[3:5],'little')
        item_id=int.from_bytes(packet[6:8],'little')
        if x==65535:
            slot=y
            if slot in world.inventory and world.inventory[slot].id==item_id:
                del world.inventory[slot]
                metrics['food_eaten']+=1
            elif 64<=slot<=79:
                container=world.containers.get(slot-64)
                if container and any(item.id==item_id for item in container.items):
                    metrics['unowned_food_uses']+=1
        elif item_id==prey_profile['corpse'] and world.position.distance(Position(x,y,packet[5]))<=1:
            container_id=max(world.containers,default=-1)+1
            world.containers[container_id]=Container(container_id,prey_profile['corpse'],
                'dead '+prey_profile['name'].lower(),10,False,[Thing(prey_profile['food'],1)])
            agent.observe([Event('container_open',(container_id,item_id))],now+.01)
        return True
    if op==0x78 and len(packet)>=15:
        source_y=int.from_bytes(packet[3:5],'little')
        source_container_id=source_y-64
        item_id=int.from_bytes(packet[6:8],'little')
        if source_y>=65 and source_container_id in world.containers:
            corpse=world.containers[source_container_id]
            for slot,item in enumerate(corpse.items):
                if item.id==item_id and item.id==prey_profile['food'] and 5 not in world.inventory:
                    world.inventory[5]=item
                    del corpse.items[slot]
                    metrics['food_received']+=max(1,item.count)
                    break
        return True
    return True


def run_simulation(state_path, agents=20, steps=200, seed=1, unrelated_open_corpse=False,
                   prey_name='Rat', neural_mode='off'):
    if not isinstance(agents,int) or not 1<=agents<=20 or not isinstance(steps,int) or steps<1:
        raise ValueError('invalid simulation size')
    root=Path(__file__).resolve().parents[1]
    items=load_items(root/'data/items/items.srv')
    from xml.etree import ElementTree
    registry=ElementTree.parse(root/'data/monster/monsters.xml').getroot()
    entry=next((monster for monster in registry.findall('monster')
                if monster.attrib['name'].lower()==prey_name.lower()),None)
    if entry is None or prey_name.lower() not in ('rat','cave rat'):
        raise ValueError('simulation prey must be Rat or Cave Rat')
    definition=ElementTree.parse(root/'data/monster'/entry.attrib['file']).getroot()
    food=next((int(drop.attrib['id']) for drop in definition.findall('./loot/item')
               if items[int(drop.attrib['id'])].attributes.get('nutrition',0)>0),None)
    if food is None:
        raise ValueError('simulation prey has no nutritious loot')
    prey_profile=dict(name=definition.attrib['name'],health=int(definition.find('health').attrib['max']),
                      experience=int(definition.attrib['experience']),
                      corpse=int(definition.find('look').attrib['corpse']),food=food)
    behavior_path=Path(state_path).with_suffix('.behavior.db')
    learner=LearningAgent(Path(state_path),neural_mode=neural_mode)
    metrics=dict(agents=agents,prey_name=prey_profile['name'],
                 prey_experience=prey_profile['experience'],nutritious_food_id=prey_profile['food'],
                 sewer_entries=0,rats_killed=0,xp_gain=0,
                 food_received=0,food_eaten=0,unowned_food_uses=0,attacks=0,accepted_packets=0,
                 network_connections=0,steps_run=0)
    metrics['agents_detail']=[]
    try:
        with Store(behavior_path,max_agents=20) as behavior_store:
            for index in range(agents):
                world,profile,progression,_=_world_for(index,items,prey_profile,unrelated_open_corpse)
                agent=Agent(profile['character'],world,items,
                            Policy(behavior_store,profile['character'],random.Random(seed+index)))
                agent.escape=progression.recover
                agent.retreat_routes=progression.routes
                agent.retreat_goal=Position(32097,32218,7)
                agent.forage=progression.forage
                gate=ActionGate(world,items)
                last_executed='none'
                baseline={key:metrics[key] for key in
                          ('sewer_entries','rats_killed','xp_gain','food_received','food_eaten')}
                agent_steps=0
                for tick in range(steps):
                    agent_steps+=1
                    metrics['steps_run']+=1
                    now=1.0+tick*2.0
                    observation=LearningObservation.from_world(
                        profile['character'],world,
                        'retreat' if world.stats.health<world.stats.max_health*.65 else 'hunt',
                        0.0,executed_action=last_executed,
                        food_available=next(agent.food(),None) is not None,
                        retreat_available=progression.in_rook())
                    intent=learner.handle(observation)
                    priority=agent.priority(now)
                    actions,controlled=select_actions_with_learning(agent,progression,now,intent)
                    gate.floor_token=progression.floor_authorization
                    gate.allowed_corpses=set(agent.allowed_corpses)
                    accepted=[]
                    for packet in actions:
                        if _apply_packet(packet,world,agent,progression,gate,now,metrics,prey_profile):
                            accepted.append(packet)
                    classified=classify_learning_action(
                        intent,priority,progression.busy,actions,accepted,controlled)
                    if classified!='none':
                        last_executed=classified
                    elif priority or progression.busy or intent is not None:
                        last_executed='none'
                    if all(metrics[key]-baseline[key]>=minimum for key,minimum in
                           (('sewer_entries',1),('rats_killed',1),('xp_gain',prey_profile['experience']),
                            ('food_received',1),('food_eaten',1))):
                        break
                metrics['agents_detail'].append({
                    'character':profile['character'],
                    'sewer_entries':metrics['sewer_entries']-baseline['sewer_entries'],
                    'rats_killed':metrics['rats_killed']-baseline['rats_killed'],
                    'xp_gain':metrics['xp_gain']-baseline['xp_gain'],
                    'food_received':metrics['food_received']-baseline['food_received'],
                    'food_eaten':metrics['food_eaten']-baseline['food_eaten'],
                    'steps_run':agent_steps,
                    'position':[world.position.x,world.position.y,world.position.z],
                })
                learner.store.checkpoint(profile['character'],{
                    'sewer_entered':world.position.z==8,
                    'experience':world.stats.experience,
                    'food_received':metrics['food_received'],
                })
        metrics['checkpoint_reloaded']=learner.store.restore_latest('Sim-01') is not None
        metrics['max_events']=learner.store.db.execute('SELECT count(*) FROM transitions').fetchone()[0]
        metrics['learned_agents']=learner.store.db.execute(
            'SELECT count(DISTINCT agent) FROM qvalues').fetchone()[0]
        metrics['neural_updates']=learner.neural.updates if learner.neural else 0
    finally:
        learner.close()
    with LearningStore(Path(state_path)) as reopened:
        metrics['checkpoint_reloaded']=reopened.restore_latest('Sim-01') is not None
        metrics['max_events']=reopened.db.execute('SELECT count(*) FROM transitions').fetchone()[0]
        metrics['learned_agents']=reopened.db.execute(
            'SELECT count(DISTINCT agent) FROM qvalues').fetchone()[0]
    return metrics


def main(argv=None):
    parser=argparse.ArgumentParser(description='isolated autonomous-learning simulation')
    parser.add_argument('--agents',type=int,default=20)
    parser.add_argument('--duration',type=int,default=200)
    parser.add_argument('--seed',type=int,default=1)
    parser.add_argument('--state',required=True)
    parser.add_argument('--prey-name',choices=('Rat','Cave Rat'),default='Rat')
    args=parser.parse_args(argv)
    import json
    print(json.dumps(run_simulation(Path(args.state),args.agents,args.duration,args.seed,
                                    prey_name=args.prey_name),sort_keys=True))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
