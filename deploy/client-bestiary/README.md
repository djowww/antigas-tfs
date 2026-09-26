# Progresso de caça no Bestiary

**Interface clássica publicada na v32:** veja [UI-CLASSICA.md](UI-CLASSICA.md). Os arquivos desta pasta incluem o novo layout; o histórico v31 abaixo se refere à publicação anterior.

## Publicação v32 — 26/09/2026

- Download: https://tibia74.tech/Antigas-7.4-Client-v32.zip
- SHA-256: `c0fe853eaec3918a34418ec7f3f6f20925a80a3f5fafeccd5b3c1ee11587d98a`.
- Pacote derivado do v31, com somente três arquivos do Bestiary e a versão em `init.lua` modificados. Executáveis, sprites, demais módulos e protocolo permanecem iguais.
- Testes no cliente real e offline: 138 fichas, filtros, busca, seleção, mensagens de progresso, ciclo do módulo e quatro tamanhos de janela. Dez listas de loot com mais de 200 caracteres foram conferidas integralmente; nomes repetidos foram eliminados somente da apresentação.
- Publicação sem reiniciar o servidor. ZIP público, manifesto e link da página inicial verificados. Pacote v31 e backup da página/manifesto preservados na VPS.
- Empacotamento/publicação específica desta versão: `deploy/bestiary-ui-v32-release.py`. Não reutilizar o script v31 para esta revisão.

Patch dos módulos de interface do cliente Antigas atual (v30) para mostrar o progresso individual de abates no Bestiary. Copie os arquivos preservando seus caminhos relativos para a pasta do cliente.

- `modules/game_wiki/`: progresso em cada criatura e na janela de detalhes.
- `modules/game_inventory/inventory.otui`: rótulo e tooltip do botão Bestiary; o ID `logoutButton` permanece intacto para o layout clássico.

O servidor envia os contadores pelo extended opcode 124. Cada personagem progride de forma independente até 1.000 abates por monstro. Este patch não adiciona recompensas e mantém os sprites originais.

## Publicação v31 — 26/09/2026

- Servidor principal atualizado e reiniciado; backup recuperável antes da implantação.
- Testes Lua: isolamento entre personagens, limite de abates, exclusão de alvos invocados por jogadores, consultas, limitação de frequência e entradas inválidas.
- Teste no servidor com dois personagens comuns simultâneos: consulta independente e persistência após reconexão. Contadores pré-carregados para esse teste; o evento de abate foi exercitado pelo teste Lua, não por combate ao vivo.
- Interface conferida no cliente v31: catálogo e detalhes com barras vazias em zero e contador legível.
- Pacote público comparado integralmente ao v30: somente cinco arquivos dos módulos e a versão em init.lua mudaram.
- Download público e manifesto conferidos pelo SHA-256: `5ef0fc7bdb282b926220c6412a167c0f41ce4be90351b5b7800bda308e8d99f3`.
- URL: https://tibia74.tech/Antigas-7.4-Client-v31.zip

O script `deploy/bestiary-release.py` separa implantação, empacotamento e publicação. Seus caminhos e versões são específicos desta implantação; revise-os antes de reutilizar. Os testes de produção em `tests/bestiary-live.py` criam personagens descartáveis e os removem ao finalizar. Nenhuma recompensa é entregue nesta versão.
