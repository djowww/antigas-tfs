function onSay(cid, player, words, param)
	cid:registerEvent("modalwindowhelper")
 
    local titulo = "Automatic Tutor" -- Esse é o titulo do ModalWindow
    local mensagem = "Hello, I am the automatic tutor of Antiga, I can answer some of your questions." -- Subtitulo do ModalWindow
 
    local popup = ModalWindow(1000, titulo, mensagem)
 
    popup:addButton(100, "Confirm")
    popup:addButton(101, "Cancel")
 
    popup:addChoice(1, "Where is the Task NPC?") -- Aqui é onde voce vai adicionar as perguntas, basta seguir a sequencia
	popup:addChoice(2, "What is the maximum task that I can perform?")
    popup:addChoice(3, "How much is the promotion worth?")
	popup:addChoice(4, "Can the desert quest go alone?")
	popup:addChoice(5, "Where is the trainer area?")
	popup:addChoice(6, "Is there a banking system?")
	popup:addChoice(7, "What weapons are infinite for paladin?")
	popup:addChoice(8, "Do spears fall when attacking?")
	popup:addChoice(9, "What is the difference online/offline training?")
	popup:addChoice(10, "How do I know which creature is bosted?")
 
    popup:setDefaultEnterButton(100)
    popup:setDefaultEscapeButton(101)
 
    popup:sendToPlayer(cid)
	
    return true
end
