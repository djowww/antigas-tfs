-- Load the production callbacks. The fake consumer only records their arguments.
local checks, draws = 0, 0
local function expect(ok, why) checks = checks + 1; assert(ok, why) end
COMBAT_HEALING=1;COMBAT_PARAM_TYPE=2;COMBAT_PARAM_EFFECT=3;COMBAT_PARAM_DISPEL=4;COMBAT_PARAM_AGGRESSIVE=5
CONST_ME_MAGIC_BLUE=6;CONST_ME_NONE=7;CONDITION_PARALYZE=8
CALLBACK_PARAM_LEVELMAGICVALUE=9;CALLBACK_PARAM_TARGETCREATURE=10
WORLD_TYPE_NO_PVP=1;Game={getWorldType=function() return 0 end};AREA_CIRCLE3X3={}
local captured
function Combat()
 local c={}
 function c:setParameter() end
 function c:setArea() end
 function c:setCallback(kind,name) self.kind=kind;self.callback=name end
 function c:execute(caster,var)
  if self.kind==CALLBACK_PARAM_TARGETCREATURE then
   for _,target in ipairs(var) do _G[self.callback](caster,target) end
  end
  return true
 end
 captured=c;return c
end
function createCombatArea(x) return x end
createCombatObject=Combat
setCombatParam=function(c,...) c:setParameter(...) end
setCombatCallback=function(c,...) c:setCallback(...) end
doCombat=function(c,...) return c:execute(...) end
local residue=0
math.random=function(lo,hi) draws=draws+1;expect(residue>=lo and residue<=hi,'RNG bounds');return residue end
for _,row in ipairs({{'spells/light healing',20,10},{'spells/intense healing',40,20},{'spells/ultimate healing',250,50},{'spells/heal friend',120,40},{'runes/intense healing',70,30},{'runes/ultimate healing',250,0}}) do
 dofile('data/spells/scripts/'..row[1]..'.lua')
 for _,pair in ipairs({{1,0},{20,10},{100,30}}) do
  for _,roll in ipairs({-row[3],0,row[3]}) do
   residue=roll;draws=0
   local a,b=onGetFormulaValues({},pair[1],pair[2])
   local expected=math.floor((row[2]+roll)*math.max(2*pair[1]+3*pair[2],100)/100)
   expect(a==expected and b==expected,'original sampled integer curve '..row[1])
   expect(draws==1,'one sample per heal')
  end
 end
end
local results={}
function doTargetCombatHealth(_,target,_,a,b) results[#results+1]={a,b};expect(a==b,'no second Combat roll') end
local caster={getId=function()return 99 end,getLevel=function()return 20 end,getMagicLevel=function()return 10 end}
local target={isPlayer=function()return true end,getHealth=function()return 50 end}
dofile('data/spells/scripts/spells/mass healing.lua');residue=13;draws=0
onCastSpell(caster,{target,target,target})
expect(draws==1 and #results==3,'one Mass roll shared across3 targets')
expect(results[1][1]==213 and results[2][1]==213 and results[3][1]==213,'same Mass amount and factor floor')
-- Real fishing callback: prerequisite failures never credit; failed RNG still does.
SKILL_FISHING=1;CONST_ME_LOSEENERGY=2;TILESTATE_PROTECTIONZONE=3
local pz,bait,credits,fish,removed,water= false,1,0,0,0,4597
Tile=function()return {hasFlag=function()return pz end} end
local p={getPosition=function()return {}end,getItemCount=function()return bait end,addSkillTries=function()credits=credits+1 end,getEffectiveSkillLevel=function()return 79 end,addItem=function()fish=fish+1 end,removeItem=function()removed=removed+1 end}
local t={isItem=function()return true end,getId=function()return water end,getPosition=function()return {sendMagicEffect=function()end}end,transform=function(_,id)water=id end}
local rod={getId=function()return 3483 end}
dofile('data/actions/scripts/others/fishing_rod.lua')
local rolls={79,50};math.random=function(lo,hi)local v=table.remove(rolls,1);expect(v>=lo and v<=hi,'fishing residues');return v end
onUse(p,rod,{},t,{})
expect(credits==1 and fish==1 and removed==1 and water==4609,'inclusive fishing51/100 and depletion')
onUse(p,rod,{},t,{})
expect(credits==1,'depleted water no training')
water=4597;pz=true;onUse(p,rod,{},t,{});expect(credits==1,'PZ no training')
pz=false;bait=0;onUse(p,rod,{},t,{});expect(credits==1,'no bait no training')
bait=1;rolls={79,51};onUse(p,rod,{},t,{})
expect(credits==2 and fish==1 and removed==1,'failed fishing credits before roll, retains bait')
-- Real food action: exact1200 inclusive.
CONDITION_REGENERATION=20;CONDITIONID_DEFAULT=0;MESSAGE_STATUS_SMALL=1
ItemType=function()return {getNutrition=function()return 15 end}end
local fed,taken=0,0
local fooditem={getId=function()return 3577 end,remove=function()taken=taken+1 end}
local reserve=1020
local hungry={getCondition=function()return {getTicks=function()return reserve*1000 end}end,feed=function(_,n)fed=fed+n end,sendTextMessage=function()end}
dofile('data/actions/scripts/others/food.lua');onUse(hungry,fooditem)
expect(fed==180 and taken==1,'1200 inclusive food')
reserve=1021;onUse(hungry,fooditem);expect(fed==180 and taken==1,'1201 rejected without consuming')
-- Active custom reward flags cannot alter production numerical callbacks.
SKILL_MAGLEVEL=99;Player={};CONDITION_SOUL=21;CONDITION_PARAM_TICKS=22;CONDITION_PARAM_SOULGAIN=23
Condition=function()return {setParameter=function()end,setTicks=function()end,addDamage=function()end}end
getExpForLevel=function()return 100000 end
getGlobalStorageValue=function()error('custom event read in strict math')end
configManager={getNumber=function()error('rate read in strict math')end}
local strict={getVocation=function()return {getMaxSoul=function()return 100 end}end,getSoul=function()return 100 end,getLevel=function()return 20 end,getExperience=function()return 500 end,addAnalyzerExp=function()end}
dofile('data/events/scripts/player.lua')
expect(Player.onGainExperience(strict,{isPlayer=function()return false end},101,101)==101,'XP ignores all custom rates/rewards')
for _,enabled in ipairs({false,true}) do
 APPLY_SKILL_MULTIPLIER=enabled
 expect(Player.onGainSkillTries(strict,1,3)==3,'skills ignore all custom rates/rewards')
 expect(Player.onGainSkillTries(strict,SKILL_MAGLEVEL,1600)==1600,'magic ignores all custom rates/rewards')
end
-- Real fluid action: fixed ranges, no factor, exhaustion and vial retention.
for i,name in ipairs({'NONE','WATER','WINE','BEER','MUD','BLOOD','SLIME','OIL','URINE','MILK','MANAFLUID','LIFEFLUID','LEMONADE'}) do _G['FLUID_'..name]=i-1 end
CONDITION_DRUNK=30;CONDITION_POISON=31;CONDITION_EXHAUST=32;RETURNVALUE_YOUAREEXHAUSTED=33;TALKTYPE_SAY=34
ItemType=function()return nil end
local hp,mp,fluid,exhaust=50,50,FLUID_NONE,false
local drinker={getId=function()return 99 end,isCreature=function()return true end,getHealth=function()return hp end,getPosition=function()return {sendMagicEffect=function()end}end,addHealth=function(_,n)hp=math.min(1000,hp+n)end,addMana=function(_,n)mp=math.min(1000,mp+n)end,getCondition=function()return exhaust end,addCondition=function()exhaust=true end,removeCondition=function()end,sendCancelMessage=function()end,say=function()end}
local vial={getId=function()return 2874 end,getFluidType=function()return fluid end,transform=function(_,_,value)fluid=value end}
dofile('data/actions/scripts/others/fluids.lua')
for _,row in ipairs({{FLUID_LIFEFLUID,25,75},{FLUID_MANAFLUID,50,150}}) do
 for _,roll in ipairs({row[2],row[3]}) do
  hp=50;mp=50;fluid=row[1];exhaust=false
  math.random=function(lo,hi)expect(lo==row[2] and hi==row[3],'fluid exact RNG range');return roll end
  onUse(drinker,vial,{},drinker,{})
  expect((row[1]==FLUID_LIFEFLUID and hp==50+roll or row[1]==FLUID_MANAFLUID and mp==50+roll),'fixed fluid amount')
  expect(fluid==FLUID_NONE and exhaust,'empties liquid and shares exhaustion')
 end
end
fluid=FLUID_LIFEFLUID;exhaust=true
math.random=function()error('exhausted potion must not draw')end
onUse(drinker,vial,{},drinker,{})
expect(fluid==FLUID_LIFEFLUID,'exhausted potion retained')
print(checks..' real legacy healing/food/fishing/reward/fluid callback checks passed')
