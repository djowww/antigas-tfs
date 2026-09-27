local protocolCallbacks, sent, children = {}, {}, {}
local unread, nextEvent, removedEvent = 0, 0, nil
local window = {visible=false, entries={}, summary={}}
function window:hide() self.visible=false end
function window:show() self.visible=true end
function window:isVisible() return self.visible end
function window:raise() end
function window:focus() end
function window:destroy() self.destroyed=true end
function window.summary:setText(value) self.text=value end
function window.entries:destroyChildren() children={} end

g_game = {
	isOnline=function() return true end,
	getFeature=function() return true end,
	getProtocolGame=function() return {sendExtendedOpcode=function(_,opcode,message)
		assert(opcode==126); sent[#sent+1]=message
	end} end
}
GameExtendedOpcode = 1
g_ui = {
	displayUI=function() return window end,
	createWidget=function(name,parent)
		assert(name=='AchievementEntry')
		local row={title={},reward={},progress={}}
		function row.title:setText(value) self.text=value end
		function row.reward:setText(value) self.text=value end
		function row.progress:setText(value) self.text=value end
		function row:setBackgroundColor(value) self.background=value end
		children[#children+1]=row
		return row
	end
}
ProtocolGame = {
	registerExtendedOpcode=function(opcode,callback) protocolCallbacks[opcode]=callback end,
	unregisterExtendedOpcode=function(opcode) protocolCallbacks[opcode]=nil end
}
modules = {game_playerbars={setAchievementsUnread=function(count) unread=count end}}
json = {
	encode=function(value) return value end,
	decode=function() return _G.incomingPayload end
}
function connect() end
function disconnect() end
function scheduleEvent() nextEvent=nextEvent+1; return nextEvent end
function removeEvent(id) removedEvent=id end

dofile('Cliente/modules/game_achievements/achievements.lua')
init()
toggle()
assert(window.visible and #sent==3, 'opening requests state and acknowledges unread rewards')
assert(sent[2].action=='markSeen' and sent[3].action=='getProgress')
incomingPayload = {action='progress',unread=2,entries={{
	title='Walk 100 steps',reward='+1 speed',progress=100,target=100,completed=true
}},bonuses={speed=1,attack=0,pvp=0,deathReduction=0}}
protocolCallbacks[126](nil,126,'encoded progress payload')
assert(unread==2, 'new server-side completions highlight the sidebar button')
assert(#children==1 and children[1].title.text=='[DONE] Walk 100 steps')
assert(children[1].background=='#3b392f' and window.summary.text:find('1 / 1',1,true))
toggle()
assert(not window.visible and removedEvent==nextEvent, 'closing cancels the refresh timer')
terminate()
assert(window.destroyed and protocolCallbacks[126]==nil)

print('PASS Achievements UI: button feedback, progress rendering, refresh lifecycle and opcode handler')
