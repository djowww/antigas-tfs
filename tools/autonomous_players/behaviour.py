"""Conservative normal actions; strategies are selected by the persistent policy."""
from collections import Counter
from .world import Position
from .navigation import find_path, walkable, walk_packet
from .protocol import attack, use_item, move_item


class Agent:
    def __init__(self, name, world, items, policy):
        self.name,self.world,self.items,self.policy = name,world,items,policy
        self.next_action,self.next_food,self.next_strategy = 0,0,0
        self.visits = Counter()
        self.strategy,self.transition,self.target = 'explore',None,0
        self.home = None
        self.next_attack = 0
        self.last_experience = world.stats.experience
        self.target_position = None
        self.allowed_corpses = {}
        self.own_names = {name}
        self.loot_pending = None
        self.loot_retry = 0
        self.destination = None
        self.pending_loot = None
        self.attack_evidence = None

    def observe(self, events, now):
        w = self.world
        target = w.creatures.get(self.target)
        if target and target.position:
            self.target_position = target.position
            if self.attack_evidence:
                self.attack_evidence=(target.id,target.position,now)
        humans = [c for c in w.creatures.values() if c.kind == 'player' and c.name not in self.own_names and c.position]
        if (w.stats.experience > self.last_experience and self.attack_evidence and
            now-self.attack_evidence[2]<=10 and
            not any(c.position.distance(self.attack_evidence[1]) <= 7 for c in humans)):
            self.pending_loot = (self.attack_evidence[1],now+5)
            self.attack_evidence=None
        if self.pending_loot and now <= self.pending_loot[1]:
            location = self.pending_loot[0]
            for thing in w.tiles.get(location,[]):
                if not thing.creature_id and self.items[thing.id].container and 'dead' in self.items[thing.id].name.lower():
                    if not any(c.position.distance(location) <= 7 for c in humans):
                        self.allowed_corpses[(location,thing.id)] = now+120
                    self.pending_loot = None
        self.last_experience = w.stats.experience
        self.allowed_corpses = {key:expiry for key,expiry in self.allowed_corpses.items() if expiry > now}
        for event in events:
            if event.kind == 'cancel_attack':
                self.target = 0

    def step(self, now):
        w = self.world
        if not w.valid or not w.position or not w.stats.level or now < self.next_action:
            return []
        self.next_action = now+0.6
        p = w.position
        self.home = self.home or p
        self.visits[p] += 1
        if len(self.visits) > 4096:
            self.visits = Counter(dict(self.visits.most_common(2048)))
        health = w.stats.health / max(1,w.stats.max_health)
        monsters = [c for c in w.creatures.values() if c.kind == 'monster' and c.position and c.health > 0 and c.position.distance(p) <= 7]
        # Only weak known Rook prey; stronger targets require explicit progression rules.
        prey = [c for c in monsters if c.name.lower() in ('rat','cave rat','rabbit','deer','sheep','pig','chicken')]
        if now >= self.next_food:
            for cid,c in w.containers.items():
                for slot,item in enumerate(c.items):
                    if self.items[item.id].attributes.get('nutrition',0) > 0:
                        self.next_food = now+90
                        return [use_item(Position(65535,64+cid,slot),item.id,slot)]
        if health < .45:
            self.strategy = 'retreat'
            if self.target:
                self.target = 0
                return [b'\xbe']
            candidates = [n for n in w.tiles if n.z == p.z and p.distance(n) == 1 and walkable(w,n,self.items)]
            if candidates and monsters:
                best = max(candidates,key=lambda n:min(n.distance(c.position) for c in monsters))
                return [walk_packet(p,best)]
            return []
        if 3 in w.inventory and 0 not in w.containers:
            return [use_item(Position(65535,3,0),w.inventory[3].id,0,0)]
        if 1 in w.containers and self.loot_pending:
            corpse = w.containers[1]
            for slot,item in enumerate(corpse.items):
                definition = self.items[item.id]
                if item.id == 3031 or definition.attributes.get('nutrition',0) > 0:
                    return [move_item(Position(65535,65,slot),item.id,slot,Position(65535,64,0),min(100,item.count))]
            self.allowed_corpses.pop(self.loot_pending,None)
            self.loot_pending = None
        if now >= self.loot_retry:
            for (location,item_id),expiry in self.allowed_corpses.items():
                if 1 < p.distance(location) < 8 and now < expiry:
                    paths = [path for dx,dy in ((0,1),(1,0),(0,-1),(-1,0))
                             if (path:=find_path(w,p,location.shift(dx,dy),self.items))]
                    if paths:
                        return [walk_packet(p,min(paths,key=len)[0])]
                if p.distance(location) <= 1 and now < expiry:
                    for stack,thing in enumerate(w.tiles.get(location,[])):
                        if thing.id == item_id:
                            self.loot_pending = (location,item_id)
                            self.loot_retry = now+5
                            return [use_item(location,item_id,stack,1)]
        state = f'l{min(w.stats.level,30)//3}:h{int(health*3)}:m{min(len(prey),3)}'
        reactive = any(p.distance(c.position) <= 2 or c.id == self.target for c in prey)
        allowed = ['hunt'] if reactive else ['explore'] + (['hunt'] if prey else [])
        if now >= self.next_strategy or self.strategy not in allowed:
            if self.transition:
                old_state,old_action,old_exp,old_health = self.transition
                reward = (w.stats.experience-old_exp)/10 - max(0,old_health-w.stats.health)/10
                self.policy.update(old_state,old_action,reward,state,allowed)
            self.strategy = self.policy.choose(state,allowed)
            self.transition = state,self.strategy,w.stats.experience,w.stats.health
            self.next_strategy = now+15
        if prey and self.strategy == 'hunt':
            creature = min(prey,key=lambda c:p.distance(c.position))
            self.target_position = creature.position
            if self.target != creature.id or now >= self.next_attack:
                self.target = creature.id
                self.next_attack = now+3
                self.attack_evidence=(creature.id,creature.position,now)
                # Stand mode; manual movement respects observed occupancy.
                return [b'\xa0\x01\x00\x00',attack(creature)]
            if p.distance(creature.position) > 1:
                adjacent = [creature.position.shift(dx,dy) for dx,dy in ((0,1),(1,0),(0,-1),(-1,0))]
                paths = [path for goal in adjacent if (path:=find_path(w,p,goal,self.items))]
                if paths:
                    return [walk_packet(p,min(paths,key=len)[0])]
            return []
        self.target = 0
        if self.destination and self.destination != p:
            path = find_path(w,p,self.destination,self.items)
            if path:
                return [walk_packet(p,path[0])]
        self.destination = None
        candidates = [n for n in w.tiles if n.z == p.z and p.distance(n) > 1 and walkable(w,n,self.items)]
        self.policy.rng.shuffle(candidates)
        candidates.sort(key=lambda n:(self.visits[n],-p.distance(n)))
        for goal in candidates[:20]:
            path = find_path(w,p,goal,self.items)
            if path:
                self.destination = goal
                return [walk_packet(p,path[0])]
        return []
