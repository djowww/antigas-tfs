"""Conservative normal actions; strategies are selected by the persistent policy."""
from collections import Counter
import time
from .world import Position
from .navigation import find_path, walkable, walk_packet
from .protocol import attack, use_item, move_item
from .creature_rules import (HUNTABLE_ROOK_PREY, PASSIVE_CORPSES,
                             PASSIVE_CORPSE_NAMES, PASSIVE_FOOD_CREATURES)


class Agent:
    DESTINATION_STALL_SECONDS = 10
    DESTINATION_COOLDOWN_SECONDS = 15
    MAX_UNREACHABLE_DESTINATIONS = 256
    MAX_UNREACHABLE_PREY_POSITIONS = 128
    WALK_RETRY_SECONDS = 1
    ATTACK_STALL_SECONDS = 12
    MAX_PREY_COOLDOWN_SECONDS = 300

    def __init__(self, name, world, items, policy):
        self.name,self.world,self.items,self.policy = name,world,items,policy
        self.next_action,self.next_food,self.next_strategy = 0,0,0
        self.visits = Counter()
        self.strategy,self.transition,self.target = 'explore',None,0
        self.strategy_hint_applied = False
        self.home = None
        self.next_attack = 0
        self.last_experience = world.stats.experience
        self.target_position = None
        self.attack_progress = None
        self.combat_stalls = 0
        self.allowed_corpses = {}
        self.own_names = {name}
        self.loot_pending = None
        self.loot_container_id = None
        self.loot_open_requested = False
        self.loot_retry = 0
        self.loot_transfer_retry = 0
        self.destination = None
        self.destination_progress_position = None
        self.destination_progress_at = None
        self.last_walk_source = self.last_walk_step = None
        self.last_walk_at = None
        self.unreachable_destinations = {}
        self.pending_loot = None
        self.pending_xp_loot = None
        self.loot_open_attempts = 0
        self.attack_evidence = None
        self.unreachable_prey = {}
        self.unreachable_prey_failures = {}
        self.unreachable_prey_positions = {}
        self.unreachable_prey_position_failures = {}
        self.escape = None
        self.retreat_routes = None
        self.retreat_goal = None
        self.forage = None
        self.passive_attack = None
        self.passive_corpse_claims = 0
        self.confirmed_kills = 0
        self.confirmed_kill_types = Counter()

    def food(self):
        for slot,item in self.world.inventory.items():
            if self.items[item.id].attributes.get('nutrition',0)>0:
                yield Position(65535,slot,0),item.id,0
        for cid,container in self.world.containers.items():
            container_name = container.name.lower()
            item_name = self.items[container.item_id].name.lower()
            if ('dead' in container_name or 'dead' in item_name or
                    (self.loot_pending and container.item_id==self.loot_pending[1])):
                continue  # Loot the corpse into the backpack before treating its contents as carried food.
            for slot,item in enumerate(container.items):
                if self.items[item.id].attributes.get('nutrition',0)>0:
                    yield Position(65535,64+cid,slot),item.id,slot

    def prey(self):
        w=self.world
        current=time.monotonic()
        retained={}
        for cid,(position,health,expiry) in self.unreachable_prey.items():
            creature=w.creatures.get(cid)
            if (creature and creature.position and creature.health==health and
                    position.distance(creature.position)<=1):
                retained[cid]=(position,health,expiry)
            else:
                self.unreachable_prey_failures.pop(cid,None)
                if creature is not None:
                    self.unreachable_prey_positions.pop(position,None)
                    self.unreachable_prey_position_failures.pop(position,None)
        self.unreachable_prey=retained
        self.unreachable_prey_positions={position:expiry for position,expiry in
                                          self.unreachable_prey_positions.items()
                                          if expiry>current}
        humans=[c for c in w.creatures.values() if c.kind=='player' and c.id!=w.self_id and
                c.name not in self.own_names and c.position]
        return [c for c in w.creatures.values() if c.kind=='monster' and c.position and c.health>0 and
                not (c.id in self.unreachable_prey and self.unreachable_prey[c.id][2]>current) and
                c.position.distance(w.position)<=7 and
                c.name.lower() in HUNTABLE_ROOK_PREY and
                c.position not in self.unreachable_prey_positions and
                (w.stats.health >= w.stats.max_health*.65 or c.name.lower() in PASSIVE_CORPSES) and
                not any(h.position.distance(c.position)<=3 for h in humans)]

    def _mark_unreachable_prey(self,creature,cooldown):
        # A failed route and a stalled melee attack are both observed hunt
        # failures. Report either outcome to the learner exactly once.
        self.combat_stalls+=1
        if len(self.unreachable_prey)>=128 and creature.id not in self.unreachable_prey:
            oldest=next(iter(self.unreachable_prey))
            self.unreachable_prey.pop(oldest)
            self.unreachable_prey_failures.pop(oldest,None)
        previous=self.unreachable_prey_failures.get(creature.id)
        same_blocked_area=(previous and previous[1]==creature.health and
                           previous[0].distance(creature.position)<=1)
        failures=(previous[2]+1 if same_blocked_area else 1)
        if len(self.unreachable_prey_failures)>=128 and creature.id not in self.unreachable_prey_failures:
            self.unreachable_prey_failures.pop(next(iter(self.unreachable_prey_failures)))
        self.unreachable_prey_failures[creature.id]=(creature.position,creature.health,failures)
        position_failures=self.unreachable_prey_position_failures.get(creature.position,0)+1
        self.unreachable_prey_position_failures[creature.position]=position_failures
        attempt=max(failures,position_failures)
        delay=min(float(cooldown)*(2**min(attempt-1,8)),self.MAX_PREY_COOLDOWN_SECONDS)
        expiry=time.monotonic()+delay
        self.unreachable_prey[creature.id]=(creature.position,creature.health,expiry)
        self.unreachable_prey_positions[creature.position]=max(
            expiry,self.unreachable_prey_positions.get(creature.position,0))
        while len(self.unreachable_prey_positions)>self.MAX_UNREACHABLE_PREY_POSITIONS:
            oldest=next(iter(self.unreachable_prey_positions))
            self.unreachable_prey_positions.pop(oldest,None)
            self.unreachable_prey_position_failures.pop(oldest,None)

    def retreat_needed(self):
        w=self.world
        if not w.position:return False
        near=[c for c in w.creatures.values() if c.kind=='monster' and c.position and
              c.health>0 and c.position.distance(w.position)<=3]
        aggressive=[c for c in near if c.name.lower() not in PASSIVE_FOOD_CREATURES]
        wounded=w.stats.health<w.stats.max_health*.65
        manageable_cave_rats=(w.position.z>7 and len(aggressive)==2 and not wounded and
                              all(c.name.lower() in ('rat','cave rat') for c in aggressive))
        return (w.stats.health<w.stats.max_health*.35 or
                (len(aggressive)>=2 and not manageable_cave_rats) or
                (wounded and (bool(aggressive) or w.position.z>7)))

    def _loot_targets(self,now):
        w=self.world
        if not w.position:
            return set()
        humans=[c for c in w.creatures.values()
                if c.kind=='player' and c.id!=w.self_id and c.name not in self.own_names and c.position]
        return {(location,item_id) for (location,item_id),expiry in self.allowed_corpses.items()
                if expiry>now and location.distance(w.position)<=7 and location in w.tiles and
                any(t.id==item_id and not t.creature_id for t in w.tiles[location]) and
                not any(h.position.distance(location)<=7 for h in humans)}

    def _corpse_counts(self,location):
        counts={}
        for thing in self.world.tiles.get(location,[]):
            definition=self.items.get(thing.id)
            if definition is None:
                continue
            if (not thing.creature_id and definition.container and
                    'dead' in definition.name.lower()):
                counts[thing.id]=counts.get(thing.id,0)+1
        return counts

    def _mark_unreachable_destination(self,destination,now):
        if destination is None:
            return
        if len(self.unreachable_destinations)>=self.MAX_UNREACHABLE_DESTINATIONS:
            oldest=next(iter(self.unreachable_destinations))
            del self.unreachable_destinations[oldest]
        self.unreachable_destinations[destination]=now+self.DESTINATION_COOLDOWN_SECONDS

    def priority(self,now):
        w=self.world
        if not w.valid or not w.position or not w.stats.level:
            return False
        return (self.retreat_needed() or w.stats.health<w.stats.max_health*.65 or
                self.withdraw_target() or
                (3 in w.inventory and 0 not in w.containers) or
                (now>=self.next_food and next(self.food(),None) is not None) or
                bool(self._loot_targets(now)) or
                (self.loot_pending and self.loot_container_id in w.containers and
                 w.containers[self.loot_container_id].item_id==self.loot_pending[1]) or
                any(c.position.distance(w.position)<=7 for c in self.prey()))

    def withdraw_target(self):
        current=self.world.creatures.get(self.target)
        return bool(current and current.position and current.health>0 and
                    all(c.id!=self.target for c in self.prey()))

    def observe(self, events, now):
        w = self.world
        target = w.creatures.get(self.target)
        if target and target.position:
            self.target_position = target.position
            if self.attack_evidence and self.attack_evidence[0]==target.id:
                baseline=(self.attack_evidence[3] if target.position==self.attack_evidence[1]
                          else self._corpse_counts(target.position))
                self.attack_evidence=(target.id,target.position,self.attack_evidence[2],baseline,target.name)
        humans = [c for c in w.creatures.values() if c.kind == 'player' and c.name not in self.own_names and c.position]
        if self.passive_attack:
            cid,location,corpse_id,baseline,at=self.passive_attack
            victim=w.creatures.get(cid)
            if victim and victim.position and victim.health>0:
                location=victim.position
                # A moving target cannot inherit a corpse from a previous tile.
                if location != self.passive_attack[1]:
                    baseline=sum(t.id==corpse_id and not t.creature_id for t in w.tiles.get(location,[]))
                self.passive_attack=(cid,location,corpse_id,baseline,at)
            elif (now-at<=10 and location in w.tiles and
                  sum(t.id==corpse_id and not t.creature_id for t in w.tiles[location])>baseline and
                  not any(c.position.distance(location)<=7 for c in humans)):
                self.allowed_corpses[(location,corpse_id)]=now+120
                self.passive_corpse_claims += 1
                victim=w.creatures.get(cid)
                name=victim.name if victim else PASSIVE_CORPSE_NAMES.get(corpse_id,'Unknown')
                self.confirmed_kills += 1
                self.confirmed_kill_types[name] += 1
                self.passive_attack=None
            if now-at>10:
                self.passive_attack=None
        if (w.stats.experience > self.last_experience and self.attack_evidence and
            now-self.attack_evidence[2]<=10):
            # XP can precede creature removal in the server's death sequence.
            # Correlate it briefly to this exact victim before trusting a corpse
            # at the same tile; loot eligibility is checked separately below.
            target_id, location, _, baseline, name = self.attack_evidence
            self.pending_xp_loot = (target_id, location, now+2, now+5, False, baseline, name)
            self.attack_evidence=None
        if self.pending_xp_loot:
            target_id, location, correlation_deadline, expiry, confirmed, baseline, name = self.pending_xp_loot
            victim = w.creatures.get(target_id)
            if not confirmed and (not victim or not victim.position or victim.health <= 0):
                confirmed = now <= correlation_deadline
                if confirmed:
                    self.confirmed_kills += 1
                    self.confirmed_kill_types[name] += 1
                self.pending_xp_loot = (target_id, location, correlation_deadline, expiry, confirmed, baseline, name)
            if not confirmed and now > correlation_deadline:
                self.pending_xp_loot = None
            elif confirmed and now <= expiry:
                self.pending_xp_loot = (target_id, location, correlation_deadline, expiry, True, baseline, name)
                for thing in w.tiles.get(location,[]):
                    if (not thing.creature_id and self.items[thing.id].container and
                            'dead' in self.items[thing.id].name.lower() and
                            self._corpse_counts(location).get(thing.id,0)>baseline.get(thing.id,0)):
                        if not any(c.position.distance(location) <= 7 for c in humans):
                            self.allowed_corpses[(location,thing.id)] = now+120
                        self.pending_xp_loot = None
                        break
            elif now > expiry:
                self.pending_xp_loot = None
        self.last_experience = w.stats.experience
        self.allowed_corpses = {key:expiry for key,expiry in self.allowed_corpses.items() if expiry > now}
        for event in events:
            if (event.kind == 'container_open' and self.loot_pending and
                    self.loot_open_requested and isinstance(event.data,tuple) and len(event.data)==2):
                container_id,item_id=event.data
                if (item_id==self.loot_pending[1] and
                        self.allowed_corpses.get(self.loot_pending,0)>now):
                    self.loot_container_id=container_id
                    self.loot_open_requested=False
                    self.loot_open_attempts=0
            elif (event.kind == 'container_closed' and event.data==self.loot_container_id):
                self.loot_container_id=None
            elif event.kind == 'move' and event.data[0]==w.self_id and self.last_walk_source==event.data[1]:
                self.last_walk_source=self.last_walk_step=None
                self.last_walk_at=None
            elif event.kind == 'cancel_attack':
                self.target = 0
                self.attack_progress=None
            elif event.kind == 'walk_cancel':
                failed_step=self.last_walk_step if self.last_walk_source==w.position else None
                if self.last_walk_source==w.position:
                    self.last_walk_source=self.last_walk_step=None
                    self.last_walk_at=None
                followed=self.world.creatures.get(self.target)
                if followed and followed.name.lower() in PASSIVE_CORPSES:
                    # Server follow was cancelled for a fleeing food animal;
                    # release its id so the next cycle computes a fresh path.
                    self.target=0
                    self.attack_progress=None
                if self.destination:
                    # Avoid resending a cancelled exploration route until its
                    # short cooldown expires and select another destination.
                    self._mark_unreachable_destination(self.destination,now)
                    self.destination=None
                    self.destination_progress_position=self.destination_progress_at=None
                elif failed_step:
                    # Last-resort adjacent exploration has no long-range goal;
                    # blacklist its cancelled step itself to avoid retry loops.
                    self._mark_unreachable_destination(failed_step,now)

    def _walk_actions(self,p,destination,now,prefix=()):
        if (self.last_walk_source,self.last_walk_step)!=(p,destination):
            self.last_walk_source,self.last_walk_step=p,destination
            self.last_walk_at=None
        if (self.last_walk_at is not None and
                now-self.last_walk_at<self.WALK_RETRY_SECONDS):
            return list(prefix)
        self.last_walk_at=now
        return list(prefix)+[walk_packet(p,destination)]

    def _retreat_walk(self,p,destination,now):
        self.destination=destination
        self.destination_progress_position,self.destination_progress_at=p,now
        return self._walk_actions(p,destination,now)

    def step(self, now, strategy_hint=None):
        w = self.world
        self.strategy_hint_applied=False
        if not w.valid or not w.position or not w.stats.level or now < self.next_action:
            return []
        self.next_action = now+0.6
        p = w.position
        self.home = self.home or p
        self.visits[p] += 1
        if len(self.visits) > 4096:
            self.visits = Counter(dict(self.visits.most_common(2048)))
        self.unreachable_destinations={goal:expiry for goal,expiry in self.unreachable_destinations.items()
                                       if expiry>now and goal in w.tiles}
        if self.destination and self.destination!=p:
            if self.destination_progress_position!=p:
                self.destination_progress_position,self.destination_progress_at=p,now
            elif now-self.destination_progress_at>=self.DESTINATION_STALL_SECONDS:
                self._mark_unreachable_destination(self.destination,now)
                self.destination=None
                self.destination_progress_position=self.destination_progress_at=None
        health = w.stats.health / max(1,w.stats.max_health)
        monsters = [c for c in w.creatures.values() if c.kind == 'monster' and c.position and c.health > 0 and c.position.distance(p) <= 7]
        # Only weak known Rook prey; stronger targets require explicit progression rules.
        prey = self.prey()
        if self.withdraw_target():
            self.target=0
            self.target_position=None
            self.attack_evidence=None
            self.passive_attack=None
            self.attack_progress=None
            return [b'\xbe']
        if now >= self.next_food:
            food=next(self.food(),None)
            if food:
                self.next_food = now+90
                return [use_item(*food)]
        if self.retreat_needed():
            self.strategy = 'retreat'
            if self.target:
                self.target = 0
                return [b'\xbe']
            if self.escape:
                route=self.escape(now)
                if route:
                    return route
            candidates = [n for n in w.tiles if n.z == p.z and p.distance(n) == 1 and
                          walkable(w,n,self.items) and n not in self.unreachable_destinations]
            if candidates and getattr(self.retreat_routes,'tiles',None) and self.retreat_goal:
                blocked={c.position for c in w.creatures.values()
                         if c.id!=w.self_id and c.position is not None}
                blocked.add(p)  # Reject a fallback that only routes back through this stuck tile.
                connected=[]
                for candidate in candidates:
                    step=self.retreat_routes.next_step(candidate,self.retreat_goal,blocked=blocked)
                    if candidate==self.retreat_goal or (step and candidate.distance(step)==1):
                        connected.append(candidate)
                if connected:
                    candidates=connected
                else:
                    candidates=[]
            if candidates and monsters:
                best = max(candidates,key=lambda n:min(n.distance(c.position) for c in monsters))
                return self._retreat_walk(p,best,now)
            if candidates and not monsters and self.retreat_routes and self.retreat_goal:
                best = min(candidates,key=lambda n:(self.visits[n],p.distance(n)))
                return self._retreat_walk(p,best,now)
            if (candidates and not monsters and
                    not getattr(self.retreat_routes,'tiles',None)):
                # With no route graph and no visible stair, a safe observed
                # step reveals more of the map so recovery can replan next tick.
                best=min(candidates,key=lambda n:(self.visits[n],p.distance(n)))
                return self._retreat_walk(p,best,now)
            return []
        if 3 in w.inventory and 0 not in w.containers:
            return [use_item(Position(65535,3,0),w.inventory[3].id,0,0)]
        pending_corpse = ((self.loot_container_id,w.containers[self.loot_container_id])
                          if self.loot_pending and self.loot_container_id in w.containers and
                          w.containers[self.loot_container_id].item_id==self.loot_pending[1] else None)
        if pending_corpse and now>=self.loot_transfer_retry:
            self.loot_open_attempts=0
            corpse_id,corpse = pending_corpse
            for slot,item in enumerate(corpse.items):
                definition = self.items[item.id]
                if item.id == 3031 or definition.attributes.get('nutrition',0) > 0:
                    backpack=w.containers.get(0)
                    if not backpack or len(backpack.items)>=backpack.capacity:
                        self.loot_transfer_retry=now+30
                        break
                    self.loot_transfer_retry=now+5
                    return [move_item(Position(65535,64+corpse_id,slot),item.id,slot,Position(65535,64,0),min(100,item.count))]
            else:
                self.allowed_corpses.pop(self.loot_pending,None)
                self.loot_pending = None
                self.loot_container_id=None
                self.loot_open_requested=False
                self.loot_open_attempts=0
        if now >= self.loot_retry:
            loot_targets=self._loot_targets(now)
            for (location,item_id),expiry in self.allowed_corpses.items():
                if (location,item_id) not in loot_targets:
                    continue
                if 1 < p.distance(location) < 8 and now < expiry:
                    paths = [path for dx,dy in ((0,1),(1,0),(0,-1),(-1,0))
                             if (path:=find_path(w,p,location.shift(dx,dy),self.items))]
                    if paths:
                        return self._walk_actions(p,min(paths,key=len)[0],now)
                if p.distance(location) <= 1 and now < expiry:
                    if (any(container.item_id==item_id for container in w.containers.values()) and
                            self.loot_pending==(location,item_id)):
                        continue
                    for stack,thing in enumerate(w.tiles.get(location,[])):
                        if thing.id == item_id:
                            if self.loot_pending!=(location,item_id):
                                self.loot_open_attempts=0
                                self.loot_container_id=None
                            self.loot_pending = (location,item_id)
                            self.loot_open_requested=True
                            retry_delay=min(5*(2**min(self.loot_open_attempts,3)),30)
                            self.loot_open_attempts+=1
                            self.loot_retry = now+retry_delay
                            return [use_item(location,item_id,stack,1)]
        if health < .65 and not prey and self.forage and next(self.food(),None) is None:
            route=self.forage(now)
            if route:
                self.strategy='forage'
                return route
        state = f'l{min(w.stats.level,30)//3}:h{int(health*3)}:m{min(len(prey),3)}'
        if prey and health < .65:
            # Wounded characters prioritize safe food prey over learned roaming.
            allowed = ['hunt']
        elif prey and strategy_hint == 'explore':
            # Let an explicit learned decision escape a repeatedly unproductive
            # hunt while preserving the normal visible-prey preference otherwise.
            allowed = ['explore','hunt']
        elif prey:
            allowed = ['hunt']
        else:
            allowed = ['explore']
        if strategy_hint in allowed:
            if self.transition:
                old_state,old_action,old_exp,old_health = self.transition
                reward = (w.stats.experience-old_exp)/10 - max(0,old_health-w.stats.health)/10
                self.policy.update(old_state,old_action,reward,state,allowed)
            self.strategy = strategy_hint
            self.transition = None
            self.strategy_hint_applied=True
            self.next_strategy = now+15
        elif now >= self.next_strategy or self.strategy not in allowed:
            if self.transition:
                old_state,old_action,old_exp,old_health = self.transition
                reward = (w.stats.experience-old_exp)/10 - max(0,old_health-w.stats.health)/10
                self.policy.update(old_state,old_action,reward,state,allowed)
            self.strategy = self.policy.choose(state,allowed)
            self.transition = state,self.strategy,w.stats.experience,w.stats.health
            self.next_strategy = now+15
        walk_prefix=[]
        if prey and self.strategy == 'hunt':
            creature = next((c for c in prey if c.id==self.target),None) or min(prey,key=lambda c:p.distance(c.position))
            self.target_position = creature.position
            if p.distance(creature.position) > 1:
                self.attack_progress=None
                if self.target==creature.id and creature.name.lower() in PASSIVE_CORPSES:
                    return []  # The normal follow mode continues after a fleeing animal.
                adjacent = [creature.position.shift(dx,dy) for dx,dy in ((0,1),(1,0),(0,-1),(-1,0))]
                paths = [path for goal in adjacent if (path:=find_path(w,p,goal,self.items))]
                if paths:
                    packets = [b'\xbe'] if self.target else []
                    self.target = 0
                    self.passive_attack = None
                    self.attack_evidence = None
                    return self._walk_actions(p,min(paths,key=len)[0],now,packets)
                self._mark_unreachable_prey(creature,15)
                walk_prefix=[b'\xbe'] if self.target else []
                self.target=0
                self.passive_attack=None
                self.attack_evidence=None
            else:
                progress=self.attack_progress
                if (progress is None or progress[0]!=creature.id or
                        progress[1]!=creature.position or progress[2]!=creature.health):
                    self.attack_progress=(creature.id,creature.position,creature.health,now)
                elif now-progress[3]>=self.ATTACK_STALL_SECONDS:
                    self._mark_unreachable_prey(creature,30)
                    self.target=0
                    self.target_position=None
                    self.attack_evidence=None
                    self.passive_attack=None
                    self.attack_progress=None
                    return [b'\xbe']
                if self.target != creature.id or now >= self.next_attack:
                    self.target = creature.id
                    self.next_attack = now+3
                    self.attack_evidence=(creature.id,creature.position,now,
                                         self._corpse_counts(creature.position),creature.name)
                    corpse_id=PASSIVE_CORPSES.get(creature.name.lower())
                    if corpse_id:
                        tracked=self.passive_attack
                        baseline=(tracked[3] if tracked and tracked[0]==creature.id and
                                  tracked[1]==creature.position and tracked[2]==corpse_id else
                                  sum(t.id==corpse_id and not t.creature_id
                                      for t in w.tiles.get(creature.position,[])))
                        # Keep the corpse correlation alive while attacks continue;
                        # passive prey award no XP, so a long fight has no XP event
                        # to provide the alternate loot correlation.
                        self.passive_attack=(creature.id,creature.position,corpse_id,baseline,now)
                    mode=b'\xa0\x01\x01\x00' if corpse_id else b'\xa0\x01\x00\x00'
                    return [mode,attack(creature)]
                return []
        self.target = 0
        self.attack_progress=None
        if self.destination and self.destination != p:
            path = find_path(w,p,self.destination,self.items)
            if path:
                return self._walk_actions(p,path[0],now,walk_prefix)
        self.destination = None
        self.destination_progress_position=self.destination_progress_at=None
        candidates = [n for n in w.tiles if n.z == p.z and p.distance(n) > 1 and walkable(w,n,self.items)]
        candidates = [goal for goal in candidates if goal not in self.unreachable_destinations]
        self.policy.rng.shuffle(candidates)
        candidates.sort(key=lambda n:(self.visits[n],p.distance(n)))
        for goal in candidates[:20]:
            path = find_path(w,p,goal,self.items)
            if path:
                self.destination = goal
                self.destination_progress_position,self.destination_progress_at=p,now
                return self._walk_actions(p,path[0],now,walk_prefix)
        adjacent = [n for n in w.tiles if n.z == p.z and p.distance(n) == 1 and
                    walkable(w,n,self.items) and n not in self.unreachable_destinations]
        if adjacent:
            return self._walk_actions(p,min(adjacent,key=lambda n:self.visits[n]),now,walk_prefix)
        return walk_prefix
