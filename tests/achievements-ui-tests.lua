local function clientFile(relative)
	for _, prefix in ipairs({'Cliente/', '../../Cliente/', 'deploy/client-current/', 'Servidor/TFS/deploy/client-current/'}) do
		local path = prefix .. relative
		local file = io.open(path, 'r')
		if file then file:close(); return path end
	end
	error('Client file not found: ' .. relative)
end

dofile(clientFile('modules/corelib/json.lua'))

-- OTClient resolves sibling anchors as widget dependencies, even when the
-- edges affect different axes. A mutual dependency can prevent UI creation.
local function checkAnchorGraph(source)
	local root, stack, dependencyCount = {children={}}, {}, 0
	for line in source:gmatch('[^\r\n]+') do
		local whitespace, text = line:match('^(%s*)(.-)%s*$')
		local indent = #whitespace
		local widgetClass = text:match('^([%a_][%w_]*)$')
			or text:match('^([%a_][%w_]*)%s*<%s*[%w_]+$')
		if widgetClass then
			while #stack > 0 and stack[#stack].indent >= indent do table.remove(stack) end
			local parent = stack[#stack] or root
			local widget = {indent=indent,children={},anchors={},class=widgetClass}
			parent.children[#parent.children+1] = widget
			stack[#stack+1] = widget
		elseif #stack > 0 then
			local widget = stack[#stack]
			local id = text:match('^id:%s*([%w_]+)$')
			if id then widget.id=id end
			local target = text:match('^anchors%.[%w_]+:%s*([%w_]+)%.[%w_]+$')
			if target and target ~= 'parent' then widget.anchors[#widget.anchors+1]=target end
		end
	end
	local function checkScope(parent)
		local siblings, state = {}, {}
		for _, widget in ipairs(parent.children) do
			if widget.id then siblings[widget.id]=widget end
		end
		local function visit(widget)
			if state[widget] == 1 then return false, 'Anchor dependency cycle at ' .. (widget.id or widget.class) end
			if state[widget] == 2 then return true end
			state[widget]=1
			for _, target in ipairs(widget.anchors) do
				local dependency = siblings[target]
				if dependency then
					dependencyCount=dependencyCount+1
					local ok, reason=visit(dependency)
					if not ok then return false, reason end
				end
			end
			state[widget]=2
			return true
		end
		for _, widget in ipairs(parent.children) do
			local ok, reason=visit(widget)
			if not ok then return false, reason end
			ok, reason=checkScope(widget)
			if not ok then return false, reason end
		end
		return true
	end
	local ok, reason=checkScope(root)
	return ok, reason, dependencyCount
end

assert(not checkAnchorGraph([[Panel
  Panel
    id: list
    anchors.right: scroll.left
  Panel
    id: scroll
    anchors.top: list.bottom
]]), 'the checker must catch cycles across different coordinate axes')
assert(checkAnchorGraph([[Panel
  Panel
    id: list
    anchors.right: scroll.left
  Panel
    id: scroll
    anchors.top: parent.top
]]), 'ordinary sibling anchors must remain valid')
local otuiFile=assert(io.open(clientFile('modules/game_achievements/achievements.otui'), 'r'))
local otui=otuiFile:read('*a')
otuiFile:close()
local anchorsValid, anchorError, dependencies=checkAnchorGraph(otui)
assert(anchorsValid, anchorError)
assert(dependencies>0, 'the actual UI anchor dependencies must be inspected')

local callbacks, sent, children, events = {}, {}, {}, {}
local unread, eventId, now, online, featureEnabled = 0, 0, 0, true, false
local gameEvents = {}
local function label()
	local widget = {}
	function widget:setText(value) self.text=value end
	function widget:setTooltip(value) self.tooltip=value end
	return widget
end
local function combo()
	local widget = {options={}}
	function widget:addOption(text, value) self.options[#self.options+1]={text=text,value=value} end
	function widget:select(value)
		for _, option in ipairs(self.options) do
			if option.value == value then self.onOptionChange(self, option.text, value); return end
		end
		error('Unknown option: ' .. tostring(value))
	end
	return widget
end
local window = {visible=false,entries={},summary=label(),bonuses=label(),message=label(),
	filter=combo(),category=combo(),entriesScroll={value=0}}
function window:hide() self.visible=false end
function window:show() self.visible=true end
function window:isVisible() return self.visible end
function window:raise() end
function window:focus() end
function window:destroy() self.destroyed=true end
function window.entries:destroyChildren() children={} end
function window.entriesScroll:getValue() return self.value end
function window.entriesScroll:setValue(value) self.value=value end

g_game = {
	isOnline=function() return online end,
	getFeature=function() return featureEnabled end,
	getProtocolGame=function() return {sendExtendedOpcode=function(_,opcode,message)
		assert(opcode==126 and type(message)=='string')
		sent[#sent+1]=json.decode(message)
	end} end
}
g_clock = {millis=function() return now end}
GameExtendedOpcode = 1
g_ui = {
	displayUI=function() return window end,
	createWidget=function(name,parent)
		assert(name=='AchievementEntry' and parent==window.entries)
		local row={title=label(),reward=label(),progress=label(),bar={}}
		function row.bar:setPercent(value) self.percent=value end
		function row:setBackgroundColor(value) self.background=value end
		children[#children+1]=row
		return row
	end
}
ProtocolGame = {
	registerExtendedOpcode=function(opcode,callback,raw) assert(raw==true); callbacks[opcode]=callback end,
	unregisterExtendedOpcode=function(opcode) callbacks[opcode]=nil end
}
modules = {game_playerbars={setAchievementsUnread=function(count) unread=count end}}
function connect(target,handlers)
	assert(target==g_game)
	for name,callback in pairs(handlers) do gameEvents[name]=callback end
end
function disconnect(target,handlers)
	assert(target==g_game)
	for name,callback in pairs(handlers) do assert(gameEvents[name]==callback); gameEvents[name]=nil end
end
function scheduleEvent(callback,delay)
	eventId=eventId+1
	events[eventId]={callback=callback,due=now+delay}
	return eventId
end
function removeEvent(id) events[id]=nil end
local function advance(milliseconds)
	local target, iterations = now+milliseconds, 0
	while true do
		local nextId, due
		for id,event in pairs(events) do
			if event.due<=target and (not due or event.due<due or (event.due==due and id<nextId)) then
				nextId,due=id,event.due
			end
		end
		if not nextId then break end
		local event=events[nextId]
		events[nextId]=nil; now=due
		event.callback()
		iterations=iterations+1
		assert(iterations<100, 'timer callbacks must settle')
	end
	now=target
end
local function pages(id, prefix, completedEvery)
	local result={}
	for page=1,5 do
		local entries={}
		for index=(page-1)*12+1,page*12 do
			local completed=index%completedEvery==0
			entries[#entries+1]={id='objective_'..index,title=prefix..index,
				category=index<=20 and 'Steps' or index<=40 and 'Monsters' or 'Skills',
				reward='+1 speed',progress=completed and 100 or index,target=100,completed=completed}
		end
		result[page]={action='progress',snapshotId=id,page=page,pages=5,entries=entries,
			unread=4,bonuses={speed=15,attack=5,pvp=5,deathReduction=5}}
	end
	return result
end
local function receive(payload)
	local encoded=json.encode(payload)
	assert(#encoded<=7000, 'real paginated JSON fits the server wire limit')
	callbacks[126](nil,126,encoded)
end
local function receiveAll(snapshot)
	for _,payload in ipairs(snapshot) do receive(payload) end
end

dofile(clientFile('modules/game_achievements/achievements.lua'))
init()
assert(not window.visible and #sent==0, 'init must wait for the extended-opcode handshake')
advance(999)
assert(#sent==0)
featureEnabled=true
advance(1)
assert(#sent==1 and sent[1].action=='getProgress', 'request follows the startup delay')

local first=pages(100,'Objective ',3)
receive(first[3]); receive(first[1]); receive(first[1]); receive(first[5]); receive(first[2])
assert(#children==0 and unread==0, 'out-of-order and duplicate pages cannot expose a partial catalog')
receiveAll(pages(99,'Obsolete ',2))
assert(#children==0, 'an obsolete snapshot cannot replace an incomplete newer one')
receive(first[4])
assert(#children==60 and unread==4, 'all objectives appear after the complete hidden-window snapshot')
assert(children[1].title.text=='Objective 1' and children[60].title.text=='[DONE] Objective 60')
assert(children[3].bar.percent==100 and children[1].bar.percent==1)
assert(children[3].background=='#3b392f' and children[1].background=='#303030')
assert(children[1].title.tooltip=='Steps: Objective 1' and children[1].reward.tooltip=='+1 speed')
assert(window.summary.text:find('20 / 60',1,true) and window.bonuses.text:find('Attack +5%',1,true))
assert(#window.category.options==4, 'categories are added only once')

window.entriesScroll:setValue(300)
window.filter:select('active')
assert(#children==40 and window.entriesScroll:getValue()==0)
window.filter:select('completed')
assert(#children==20)
window.category:select('Steps')
assert(#children==6)
window.filter:select('active')
assert(#children==14)
window.filter:select('all')
assert(#children==20)
window.category:select('all')
assert(#children==60)

window.entriesScroll:setValue(132)
show()
assert(window.visible and unread==0 and sent[#sent].action=='markSeen')
assert(#children==60 and window.entriesScroll:getValue()==132, 'opening preserves the cached catalog and scroll')
local beforeRefresh=#sent
refresh()
assert(#sent==beforeRefresh, 'rapid refresh requests share a delayed request')
advance(2100)
assert(sent[#sent].action=='getProgress' and #children==60, 'refresh never blanks existing objectives')

receive(pages(101,'Intermediate ',3)[1])
local newer=pages(102,'Updated ',2)
receive(newer[2])
receiveAll(pages(101,'Intermediate ',3))
assert(children[1].title.text=='Objective 1', 'a newer incomplete response preserves the rendered snapshot')
for _,index in ipairs({5,3,1,4}) do receive(newer[index]) end
assert(#children==60 and children[1].title.text=='Updated 1' and unread==0)
assert(window.summary.text:find('30 / 60',1,true) and sent[#sent].action=='markSeen',
	'new completions in the open window are acknowledged after rendering')
assert(window.entriesScroll:getValue()==132 and #window.category.options==4)
receiveAll(first); receiveAll(newer)
assert(children[1].title.text=='Updated 1', 'obsolete and completed duplicate snapshots are ignored')

refresh(); advance(2100)
receive(pages(103,'Incomplete ',2)[1])
advance(8000)
assert(#children==60 and children[1].title.text=='Updated 1', 'timeout preserves the last complete catalog')
assert(window.message.text:find('could not be updated',1,true))
receiveAll(pages(103,'Expired ',2))
assert(children[1].title.text=='Updated 1', 'timed-out snapshot fragments cannot replace the catalog')

local invalid=pages(104,'Duplicate entry ',2)
invalid[5].entries[12].id=invalid[1].entries[1].id
receiveAll(invalid)
assert(children[1].title.text=='Updated 1', 'duplicate achievement ids invalidate an entire snapshot')
callbacks[126](nil,126,'{invalid')
callbacks[126](nil,126,string.rep('a',8193))
callbacks[126](nil,125,json.encode(pages(105,'Wrong opcode ',2)[1]))
assert(children[1].title.text=='Updated 1')

hide()
receiveAll(pages(106,'Hidden update ',3))
assert(not window.visible and unread==4, 'hidden updates restore the unread button highlight')
callbacks[126](nil,126,json.encode({action='seen'}))
assert(unread==0)
online=false; gameEvents.onGameEnd()
assert(#children==0 and unread==0 and next(events)==nil, 'logout clears per-character state and all timers')

online=true; gameEvents.onGameStart()
local beforeStartup=#sent
assert(#sent==beforeStartup)
show()
assert(next(events)~=nil, 'startup, polling and request timers are active for termination coverage')
terminate()
assert(window.destroyed and callbacks[126]==nil and next(events)==nil and next(gameEvents)==nil)
advance(20000)
assert(#sent==beforeStartup+1, 'terminated timers cannot send subsequent requests')

print('PASS Achievements UI: real JSON, 60 objectives, page ordering/duplicates/stale data, filters, cached refresh/timeouts, handshake delay, unread states and timer cleanup')
