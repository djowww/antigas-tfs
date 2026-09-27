dofile('data/lib/core/json.lua')
dofile('data/creaturescripts/scripts/questlog.lua')
local now=1000
os.time=function() return now end
local function player(id,storage)
    return {storage=storage or {}, sent={},getGuid=function() return id end,
        getStorageValue=function(self,key) return self.storage[key] or -1 end,
        sendExtendedOpcode=function(self,opcode,data)
            assert(opcode==125 and #data<=48000)
            self.sent[#self.sent+1]=json.decode(data)
        end,
        setStorageValue=function() error('Quest Log must never write progress') end,
        addItem=function() error('Quest Log must never grant items') end}
end
local a,b=player(1,{[203]=1,[293]=6,[283]=3}),player(2)
local seq=0
local function request(p,data,advance)
    if advance~=false then now=now+2 end
    seq=seq+1; data.requestId=seq
    local old=#p.sent
    onExtendedOpcode(p,125,json.encode(data))
    assert(#p.sent==old+1,'Expected response')
    local response=p.sent[#p.sent]
    assert(response.requestId==seq and response.journal==2)
    return response
end
local empty=request(b,{action='list'})
assert(empty.total==0 and empty.matched==0 and #empty.entries==0 and empty.pages==1,'New player must not receive the catalog')
local denied=request(b,{action='detail',id='blue-djinn'})
assert(denied.unavailable==true and not denied.quest,'No detail enumeration')
assert(not json.encode(denied):find('cookbook',1,true))
assert(request(b,{action='list',query='Annihilator'}).total==0,'Search must not disclose unknown quests or counts')
local first=request(a,{action='list'})
assert(first.total==3 and #first.entries==3 and first.completed==2,'Only known adventures are counted')
local q=request(a,{action='detail',id='chest-203'}).quest
assert(q.status=='completed' and q.done==1 and not q.steps[1].key)
assert(q.rewards=='','Annihilator exit flag does not prove any reward was taken')
q=request(a,{action='detail',id='ape-city'}).quest
assert(q.status=='active' and q.done==3 and q.total==3,'Do not reveal future shared-storage stages')
assert(not json.encode(q):find('hydra',1,true) and not json.encode(q):find('ancient signs',1,true))
a.storage[293]=7
q=request(a,{action='detail',id='ape-city'}).quest
assert(q.total==4 and q.done==3 and q.steps[4].current==0 and q.steps[4].target==1,'Stage appears only when accepted')
q=request(a,{action='detail',id='blue-djinn'}).quest
assert(q.status=='completed' and q.done==1 and q.total==1,'Access scroll must not fabricate previous stages')
assert(not json.encode(q):find('cookbook',1,true))
a.storage[293]=18
assert(request(a,{action='detail',id='ape-city'}).quest.status=='completed','Fresh storage reads')
a.storage[203]=0
assert(request(a,{action='detail',id='chest-203'}).unavailable==true,'Storage reset removes the entry')
assert(request(a,{action='list',query='APE CITY',filter='completed'}).matched==1)
assert(request(b,{action='list',query='APE CITY',filter='completed'}).matched==0)
assert(request(a,{action='list',filter='unstarted'}).matched==0,'Legacy filter cannot expose unknown quests')
assert(request(a,{action='list',query='[.*%'}).matched==0,'Literal search')
b.storage[227]=1; b.storage[325]=1
assert(request(b,{action='detail',id='postman'}).quest.total==1,'First mail-guild mission is discovered immediately')
assert(request(b,{action='detail',id='explorers'}).quest.total==1,'Explorer initiation is discovered immediately')
b.storage={}
local c=player(3)
for _,quest in ipairs(dofile('data/lib/custom/questCatalog.lua')) do
    for _,rule in ipairs(quest.steps) do c.storage[rule.key]=math.max(c.storage[rule.key] or 0,rule.target) end
end
local full=request(c,{action='list'})
assert(full.total==242 and full.pages==7)
local seen,count={},0
for page=1,full.pages do
    for _,entry in ipairs(request(c,{action='list',page=page}).entries) do
        assert(not seen[entry.id]); seen[entry.id]=true; count=count+1
    end
end
assert(count==full.total and request(c,{action='list',page=999}).page==full.pages,'Complete pagination')
local invalid={
    {action='detail',id='unknown'}, {action='claim',id='chest-203'},
    {action='list',playerId=2},{action='detail',id='chest-203',storage=203,value=1},
    {action='list',page=-1},{action='list',page=1.5},{action='list',page='1'},
    {action='list',query=string.rep('x',49)}, {action='list',query='a\nb'},
    {action='list',filter='admin'}
}
for _,data in ipairs(invalid) do
    now=now+2; seq=seq+1; data.requestId=seq
    local before=#a.sent; onExtendedOpcode(a,125,json.encode(data)); assert(#a.sent==before)
end
for _,buffer in ipairs({'{bad','[]',string.rep('x',513),'null','{"action":"list","requestId":1e100}'}) do
    now=now+2; local before=#a.sent; onExtendedOpcode(a,125,buffer); assert(#a.sent==before)
end
local before=#b.sent
now=now+10
for i=1,20 do onExtendedOpcode(b,125,json.encode({action='list',requestId=i})) end
assert(#b.sent-before==4,'Bounded per-character burst')
request(a,{action='list'},false)
now=now+200; request(b,{action='list'})
assert(a.storage[203]==0 and a.storage[293]==18 and not next(b.storage),'No progress or reward mutations')
print('PASS: discovered-only journal, hidden quests/steps/rewards/counts, early NPC discovery, access scrolls, resets, 242-entry pagination, isolation, validation and rate limits')
