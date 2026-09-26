# Progresso de caça no Bestiary

Patch dos módulos de interface do cliente Antigas atual (v30) para mostrar o progresso individual de abates no Bestiary. Copie os arquivos preservando seus caminhos relativos para a pasta do cliente.

- `modules/game_wiki/`: progresso em cada criatura e na janela de detalhes.
- `modules/game_inventory/inventory.otui`: rótulo e tooltip do botão Bestiary; o ID `logoutButton` permanece intacto para o layout clássico.

O servidor envia os contadores pelo extended opcode 124. Cada personagem progride de forma independente até 1.000 abates por monstro. Este patch não adiciona recompensas e mantém os sprites originais. O ZIP público do cliente não é gerado por este patch.
