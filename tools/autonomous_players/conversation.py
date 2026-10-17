"""Small local dialogue policy over observed player speech and current game state.

Input is conversation data only. No commands, generated packets, remote calls or
privileged actions can be requested through chat. This is not an LLM.
"""
import re
import unicodedata


def normalized(text):
    return ''.join(c for c in unicodedata.normalize('NFKD',text.lower()) if not unicodedata.combining(c))


class ReplyBudget:
    def __init__(self):
        self.next_reply=0

    def reserve(self,now):
        if now<self.next_reply:
            return False
        self.next_reply=now+4
        return True


class Conversation:
    def __init__(self,name,world,profile,own_names):
        self.name,self.world,self.profile,self.own_names=name,world,profile,own_names
        self.pending=None
        self.next_reply=0
        self.contacts={}
        self.replies=0

    def observe(self,events,now,strategy):
        if self.pending or now<self.next_reply or not self.world.valid or not self.world.position:
            return
        for event in events:
            if event.kind!='speech':
                continue
            data=event.data
            author=data['author']
            if author in self.own_names or data['type'] not in (1,2,3):
                continue
            speaker=next((c for c in self.world.creatures.values() if c.kind=='player' and
                          c.name==author and c.id!=self.world.self_id and c.position),None)
            if not speaker or self.world.position.distance(speaker.position)>7:
                continue
            if data.get('context')!=speaker.position or now-self.contacts.get(author,-1000)<25:
                continue
            text=normalized(data['text'][:255])
            words=set(re.findall(r'[a-z0-9]+',text))
            addressed=bool(words.intersection(normalized(self.name).split()[1:]))
            recipients={name for name in self.own_names if words.intersection(normalized(name).split()[1:])}
            if recipients and self.name!=min(recipients):
                continue
            near=self.world.position.distance(speaker.position)<=3
            greeting=bool(words.intersection({'oi','ola','hello','hi','eai','salve'})) and len(words)<=5
            ongoing=author in self.contacts and now-self.contacts[author]<90
            if not addressed and not (near and (greeting or '?' in text or ongoing)):
                continue
            if not recipients:
                candidates=[(self.world.position.distance(speaker.position),self.name)]
                candidates.extend((c.position.distance(speaker.position),c.name) for c in self.world.creatures.values()
                                  if c.name in self.own_names and c.position and c.kind=='player' and
                                  c.position.distance(speaker.position)<=3)
                if min(candidates)[1]!=self.name:
                    continue
            response=self.answer(text,words,strategy)
            self.pending=(speaker.id,response,now+1.5,now+8)
            return

    def answer(self,text,words,strategy):
        w=self.world
        if words.intersection({'bot','ia','robo','robot','inteligencia'}):
            return 'Sou um jogador simulado de teste. Exploro, caco e aprendo com minhas tentativas.'
        if words.intersection({'level','nivel','lvl','upar','experiencia','xp'}):
            return f'Estou no level {w.stats.level}, com {w.stats.experience} de experiencia. Quero evoluir por aqui!'
        if words.intersection({'vida','hp','saude','ferido','machucado'}):
            return f'Tenho {w.stats.health}/{w.stats.max_health} de vida. Se apertar, recuo para me recuperar.'
        if words.intersection({'vocacao','profissao','knight','druid','paladin','sorcerer'}):
            voc=self.profile.get('vocation','knight')
            return f'Meu plano e seguir como {voc}. Primeiro preciso evoluir e falar com o Oracle.'
        if words.intersection({'cidade','thais','venore','carlin','rook','rookgaard'}):
            return f'Estou explorando Rookgaard. Depois quero conhecer {self.profile.get("city","thais").capitalize()}.'
        if words.intersection({'pt','party','grupo','juntos'}):
            return 'Pode me convidar para a party. Por enquanto prefiro cacar criaturas fracas em Rook.'
        if words.intersection({'cacar','caca','rat','ratos','monstro','monstros','ataca','ataque','atacar'}):
            return 'Procuro ratos e outras criaturas fracas. Quando vejo um alvo seguro, me aproximo e ataco.'
        if words.intersection({'fazendo','objetivo','planos','plano','vai','indo'}):
            if w.stats.health<.45*max(1,w.stats.max_health):
                return 'Estou ferido; vou recuar e recuperar a vida antes de continuar.'
            return ('Estou cacando e tentando ganhar experiencia.' if strategy=='hunt' else
                    'Estou explorando caminhos novos e procurando uma caca segura.')
        if words.intersection({'obrigado','obrigada','valeu','vlw'}):
            return 'Por nada! Boa aventura por aqui.'
        if words.intersection({'tchau','bye','flw','ate'}):
            return 'Ate mais! Vou continuar minha exploracao.'
        if words.intersection({'oi','ola','hello','hi','eai','salve'}):
            return ('Ola! Sou o '+self.name+'. Estou conhecendo Rook. Como vai?' if self.replies%2==0 else
                    'Opa! Estou procurando uma caca tranquila por aqui. Tudo bem?')
        return 'Ainda estou aprendendo a conversar. Pode perguntar sobre minha caca, vida, level ou planos.'

    def step(self,now,budget=None):
        if not self.pending:
            return None
        cid,text,due,expires=self.pending
        if now<due:
            return None
        if now<=expires and budget and not budget.reserve(now):
            return None
        self.pending=None
        c=self.world.creatures.get(cid)
        if (now>expires or not self.world.valid or not self.world.position or not c or
            c.kind!='player' or not c.position or self.world.position.distance(c.position)>7):
            return None
        self.contacts[c.name]=now
        if len(self.contacts)>128:
            self.contacts.pop(min(self.contacts,key=self.contacts.get))
        self.next_reply=now+8
        self.replies+=1
        return cid,text
