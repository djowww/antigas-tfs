"""Navigation and observed NPC dialogues for ordinary progression and supplies."""
from .world import Position
from .social import Oracle,Purchase
from .protocol import say
from .navigation import find_path,walk_packet,walkable


class Progression:
    def __init__(self,profile,world,items,routes=None,oracle_position=Position(32104,32190,6),
                 rook_bounds=(32000,32000,32200,32350),hunting_points=(),learned_graph=None):
        self.profile,self.world,self.items,self.routes = profile,world,items,routes
        self.oracle_position,self.rook_bounds = oracle_position,rook_bounds
        self.oracle = Oracle(profile['character'],profile['city'],profile['vocation'])
        self.pending,self.authorization,self.floor_authorization = [],None,None
        self.last_speech,self.dialogue_started,self.next_purchase = -10,0,0
        self.purchase = None
        self.halted = False
        self.healer_greeted = False
        self.travel_started,self.travel_position,self.travel_progress=None,None,None
        if len(hunting_points)>64:
            raise ValueError('hunting route budget exceeded')
        self.hunting_points=tuple(Position(*p) for p in hunting_points)
        self.learned_graph=learned_graph
        self.hunting_index=profile.get('account',0)%len(self.hunting_points) if self.hunting_points else 0
        self.hunting_started,self.hunting_position,self.hunting_progress=None,None,None

    def recover(self,now):
        if not self.in_rook():
            return []
        w=self.world
        temple=Position(32097,32219,7)
        possessions=list(w.inventory.values())+[i for c in w.containers.values() for i in c.items]
        gold=sum(i.count for i in possessions if i.id==3031)
        food=any(self.items[i.id].attributes.get('nutrition',0)>0 for i in possessions)
        if w.stats.health>=65 and not self.healer_greeted and not food and gold>=3:
            self.next_purchase=0
            return self.step(now)
        if w.position.distance(temple)>3:
            return self._toward(temple)
        if self._npc('Cipfried'):
            if w.stats.health<65:
                result=self._speak('Cipfried','heal' if self.healer_greeted else 'hi',now)
                if result:self.healer_greeted=True
                return result
            if self.healer_greeted:
                result=self._speak('Cipfried','bye',now)
                if result:self.healer_greeted=False
                return result
        return []

    def _patrol(self,now):
        if not self.routes or not self.hunting_points:
            return []
        p=self.world.position
        goal=self.hunting_points[self.hunting_index]
        if self.learned_graph:
            learned_goal=self.learned_graph.next_goal(self.profile['character'], p, self.hunting_points, now)
            if learned_goal is not None:
                goal=learned_goal
                self.hunting_index=self.hunting_points.index(learned_goal)
        if self.hunting_started is None:
            self.hunting_started,self.hunting_position,self.hunting_progress=now,p,now
        elif p!=self.hunting_position:
            self.hunting_position,self.hunting_progress=p,now
        if p.distance(goal)<=1 or now-self.hunting_started>180 or now-self.hunting_progress>20:
            self.hunting_index=(self.hunting_index+1)%len(self.hunting_points)
            self.hunting_started,self.hunting_position,self.hunting_progress=now,p,now
            goal=self.hunting_points[self.hunting_index]
        route = self._toward(goal)
        if route or not self.learned_graph:
            return route
        self.learned_graph.record_failure(self.profile['character'], p, goal, 'blocked', now)
        alternate = self.learned_graph.next_goal(self.profile['character'], p, self.hunting_points, now)
        if alternate is not None and alternate != goal:
            self.hunting_index = self.hunting_points.index(alternate)
            return self._toward(alternate)
        return []

    @property
    def busy(self):
        return bool(self.pending or self.purchase or (self.in_rook() and self.world.stats.level>=8 and
                    self.profile.get('observed_vocation')==0 and not self.halted))

    def in_rook(self):
        p=self.world.position
        a,b,c,d=self.rook_bounds
        return p is not None and a<=p.x<=c and b<=p.y<=d

    def observe(self,events,now):
        for event in events:
            if event.kind != 'speech':
                continue
            author,text=event.data['author'],event.data['text']
            response=self.oracle.reply(author,text,now)
            if response:
                self.pending.append((author,response))
            if self.purchase:
                response=self.purchase.reply(author,text)
                if response:
                    self.pending.append((author,response))
            if author=='The Oracle' and self.oracle.state=='confirmed' and 'SO BE IT' in text.upper():
                self.halted=True  # The new world snapshot supplies the next phase.

    def _npc(self,name):
        p=self.world.position
        return next((c for c in self.world.creatures.values() if c.kind=='npc' and c.name==name and
                     c.position and p and p.distance(c.position)<=3),None)

    def _speak(self,name,text,now):
        c=self._npc(name)
        if not c or now-self.last_speech<2:
            return []
        self.authorization=(c.id,text,now+5)
        self.last_speech=now
        return [say(text)]

    def _toward(self,goal):
        w=self.world
        p=w.position
        if self.routes:
            step=self.routes.next_step(p,goal)
            if step and p.distance(step)==1:
                if self.routes.tiles.get(step) is not None:
                    expected=self.routes.tiles[step]
                    # Pin the live stair ID/offset to the advisory map edge.
                    # Full mapping can be supplied by the route compiler later;
                    # these are the normal Rook library stair orientations.
                    offsets={1947:(0,-1,-1),1950:(1,0,-1),1952:(-1,0,-1),1954:(0,1,-1),
                             413:(0,1,1),414:(0,1,1),369:(0,0,1),370:(0,0,1),385:(0,0,1)}
                    for thing in w.tiles.get(step,[]):
                        delta=offsets.get(thing.id)
                        if delta and step.shift(*delta)==expected and walkable(w,step,self.items,True):
                            self.floor_authorization=(step,thing.id)
                            return [walk_packet(p,step)]
                    return []
                if walkable(w,step,self.items):
                    return [walk_packet(p,step)]
        path=find_path(w,p,goal,self.items)
        return [walk_packet(p,path[0])] if path else []

    def step(self,now):
        self.authorization,self.floor_authorization=None,None
        w=self.world
        if not w.valid or not w.position:
            return []
        if self.purchase and ((self.purchase.state=='confirmed' and not self.pending and now-self.last_speech>=2) or
                              now-self.dialogue_started>30):
            npc=self.purchase.npc
            self.purchase=None
            self.pending=[p for p in self.pending if p[0]!=npc]
            self.next_purchase=now+90
        if self.oracle.state not in ('idle','confirmed') and now-self.oracle.last>30:
            self.oracle=Oracle(self.profile['character'],self.profile['city'],self.profile['vocation'])
            self.pending=[p for p in self.pending if p[0]!='The Oracle']
        if self.pending:
            name,text=self.pending[0]
            result=self._speak(name,text,now)
            if result:
                self.pending.pop(0)
            return result
        if not self.in_rook():
            return []
        if w.stats.level>=8 and self.profile.get('observed_vocation')==0:
            if self.halted:
                return []
            if self.oracle.state=='confirmed':
                # Never repeat an irreversible confirmation after a timeout.
                return []
            npc=self._npc('The Oracle')
            if npc:
                if now-self.last_speech<2:
                    return []
                response=self.oracle.start(w.stats.level,now)
                return self._speak('The Oracle',response,now) if response else []
            goal=self.oracle_position.shift(y=1)
            return self._toward(goal)
        if now<self.next_purchase:
            return self._patrol(now)
        if now-self.last_speech<2:
            return []
        possessions=list(w.inventory.values())+[i for c in w.containers.values() for i in c.items]
        gold=sum(i.count for i in possessions if i.id==3031)
        food=any(self.items[i.id].attributes.get('nutrition',0)>0 for i in possessions)
        target=None
        if not food and gold>=3:
            target=('Willie','bread',3,Position(32047,32205,7))
        elif gold>=15 and not any(i.id==3412 for i in possessions):
            target=('Dixi','wooden shield',15,Position(32105,32208,6))
        elif gold>=50 and not any(i.id==3003 for i in possessions):
            target=('Dixi','rope',50,Position(32105,32208,6))
        if not target:
            self.travel_started=None
            return self._patrol(now)
        name,item,price,goal=target
        if self._npc(name):
            self.travel_started=None
            if self.purchase is None:
                self.purchase=Purchase(name,item,price)
                response=self.purchase.start(gold)
                self.dialogue_started=now
                return self._speak(name,response,now) if response else []
            if self.purchase.state=='confirmed' or now-self.dialogue_started>30:
                self.purchase=None
                self.next_purchase=now+90
            return []
        if self.travel_started is None:
            self.travel_started,self.travel_position,self.travel_progress=now,w.position,now
        elif w.position!=self.travel_position:
            self.travel_position,self.travel_progress=w.position,now
        if now-self.travel_started>=120 or now-self.travel_progress>=20:
            self.next_purchase=now+90
            self.travel_started=None
            return self._patrol(now)
        return self._toward(goal)
