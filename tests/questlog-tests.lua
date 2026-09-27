dofile('data/lib/core/json.lua')
dofile('data/creaturescripts/scripts/questlog.lua')
local now=1000
os.time=function() return now end
local function player(id,storage)
  return {storage=storage or {}, sent={},getGuid=function() return id end,
    getStorageValue=function(self,key) return self.storage[key] or 0 end,
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
  assert(p.sent[#p.sent].requestId==seq)
  return p.sent[#p.sent]
end
local first=request(a,{action='list'})
assert(first.total==242 and #first.entries==35 and first.pages==7)
local seen={}
for page=1,first.pages do
  local result=request(a,{action='list',page=page})
  for _,q in ipairs(result.entries) do assert(not seen[q.id]); seen[q.id]=true end
end
local count=0; for _ in pairs(seen) do count=count+1 end
assert(count==first.total,'Pagination must cover every quest exactly once')
local q=request(a,{action='detail',id='chest-203'}).quest
assert(q.status=='completed' and q.done==1 and not q.steps[1].key,'Do not expose raw storage keys')
assert(request(b,{action='detail',id='chest-203'}).quest.status=='unstarted','Independent characters')
q=request(a,{action='detail',id='ape-city'}).quest
assert(q.status=='active' and q.done==3,'Existing NPC milestones')
q=request(a,{action='detail',id='blue-djinn'}).quest
assert(q.status=='completed' and q.done==1,'Access scroll must not fabricate earlier stages')
a.storage[293]=18
assert(request(a,{action='detail',id='ape-city'}).quest.status=='completed','Fresh storage reads')
a.storage[203]=0
assert(request(a,{action='detail',id='chest-203'}).quest.status=='unstarted','No stale global progress')
assert(request(a,{action='list',query='APE CITY',filter='completed'}).matched==1)
assert(request(b,{action='list',query='APE CITY',filter='completed'}).matched==0)
assert(request(a,{action='list',query='[.*%'}).matched==0,'Literal search, not Lua pattern')
assert(request(a,{action='list',page=999}).page==7,'Clamp page without overflow')
local invalid={
  {action='detail',id='unknown'}, {action='claim',id='chest-203'},
  {action='list',playerId=2},{action='detail',id='chest-203',storage=203,value=1},
  {action='list',page=-1},{action='list',page=1.5},{action='list',page='1'},
  {action='list',query=string.rep('x',49)}, {action='list',query='a\nb'},
  {action='list',filter='admin'}, {action='list',id={}}
}
-- An irrelevant but bounded id on list cannot change authorization; test the
-- dangerous fields and malformed typed input separately.
table.remove(invalid,#invalid)
for _,data in ipairs(invalid) do
  now=now+2; seq=seq+1; data.requestId=seq
  local before=#a.sent; onExtendedOpcode(a,125,json.encode(data))
  assert(#a.sent==before,'Rejected malformed or unauthorized request')
end
for _,buffer in ipairs({'{bad','[]',string.rep('x',513),'null','{"action":"list","requestId":1e100}'}) do
  now=now+2; local before=#a.sent; onExtendedOpcode(a,125,buffer); assert(#a.sent==before)
end
local before=#b.sent
now=now+10
for i=1,20 do onExtendedOpcode(b,125,json.encode({action='list',requestId=i})) end
assert(#b.sent-before==4,'Bounded per-character burst')
request(a,{action='list'},false)
now=now+200
request(b,{action='list'})
assert(a.storage[203]==0 and a.storage[293]==18 and not next(b.storage),'Read-only guarantees')
print('PASS Quest Log: 242 entries, pagination, existing flags, NPC steps, two-player isolation, literal search, read-only authorization, size limits and rate limits')
