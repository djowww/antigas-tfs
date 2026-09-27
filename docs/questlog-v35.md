# Quest Log — cliente v35

## Uso

O botão **Quests**, ao lado de Market na segunda linha de serviços, abre o diário.
Atalho alternativo: **Ctrl+J**. O visual reutiliza MainWindow, TextList, ComboBox,
Label e barras de rolagem do cliente clássico. Equipamentos e sprites não mudam.

- Busca literal por nome ou região, filtros All/In progress/Completed/Not recorded.
- 35 entradas por página; seleção à esquerda e etapas à direita.
- Atualização a cada 6 segundos somente enquanto a janela está aberta, ou Refresh.
- Logout limpa os dados do personagem; respostas antigas são descartadas.
- Recompensas continuam sendo obtidas no mundo, pelos scripts e NPCs originais.

## Cobertura e limites

A auditoria local encontrou **245 objetos de baú**, ligados a **229 storages** de
conclusão. Baús que compartilham uma flag aparecem como uma entrada, com alternativas
quando aplicável, não como prêmios cumulativos. O catálogo acrescenta **13 linhas
de missões de NPCs**, totalizando **242 entradas**.

NPCs: Banshee, Postman, Blue/Green Djinn, Ape City, Explorer Society e suas duas
entregas auxiliares, Sam's Backpack, White Raven Monastery, Windtrouser,
Old Dragon e as pistas de Paradox Tower. Arquivos `.npc` e seus includes `.ndb`
foram examinados; foram encontrados 92 storages escritos nesses diálogos.

Isso não equivale a prometer 242 quests narrativas independentes nem todas as
interações possíveis do jogo. Baús sem identificação canônica recebem nomes
descritivos da recompensa e uma região aproximada (cidade mais próxima no mapa).
Algumas quests possuem vários registros de recompensa, exibidos separadamente.
Scripts sem progresso persistente, diálogos transitórios, blessings e serviços
de addons não foram transformados em missões fictícias.

“Not recorded” significa ausência de registro, não prova de que o jogador nunca
visitou o local. Baús normalmente registram apenas a conclusão. Não são inventadas
etapas de viagem ou combate. O Annihilator também registra conclusão na saída;
o texto explica que a flag não prova qual recompensa foi coletada. Scrolls de
acesso podem completar permissões de Djinn/Postman/Banshee sem executar missões
anteriores; as etapas ausentes não são preenchidas artificialmente.

## Implementação e segurança

- `data/lib/custom/questCatalog.lua`: catálogo gerado a partir das regras revisadas.
- `data/creaturescripts/scripts/questlog.lua`: consulta somente storages do próprio
  jogador autenticado, sem consultas SQL ou alterações de progresso.
- Registro do evento no XML e no login; extended opcode **125**, compatível com
  clientes anteriores, que simplesmente não enviam essa consulta.
- Apenas ações `list` e `detail`, IDs da lista permitida, limites de tipo/tamanho,
  resposta de até 48 KB, requisição de até 512 bytes, até 35 entradas por página.
- Limite por personagem: capacidade inicial de 4 pedidos, reposição de 1/segundo;
  limpeza das entradas inativas. Não há endpoint de recompensa, playerId ou storage
  controlável pelo cliente. Busca não interpreta padrões Lua.
- Sem migração de banco, recompilação de binário, alteração de mapa ou de rewards.

## Reproduzir a auditoria e os testes

Na raiz do servidor:

```text
python tests/quest-map-audit.py --out audit.json
python tests/build-quest-catalog.py audit.json
```

O gerador é uma ferramenta de manutenção, não roda a cada login. Revisar a
lista `STORIES` antes de aceitar novos storages; não deduzir semântica
apenas por números. A auditoria não modifica o mapa.

- `tests/questlog-tests.lua`: catálogo/páginas, flags antigas, etapas, atualização,
  dois personagens, entradas malformadas, tentativas de alteração, rate limiting.
- `tests/questlog-ui-tests.lua`: cliente real offline com transporte simulado;
  abertura/fechamento, busca/filtros, seleção, logout, respostas antigas, textos
  longos, scrollbar e botões em 800×600, 1024×768 e 1366×768.
- `tests/questlog-live.py`: smoke test limitado na VPS com dois jogadores comuns
  descartáveis; não chama scripts de recompensas nem altera jogadores existentes.
- O script específico de publicação v35 foi arquivado após ser substituído por
  releases posteriores. O fluxo antigo não faz parte dos arquivos de deploy atuais.

Naquela release, as cópias do cliente ficavam em `deploy/client-questlog/`; após
a publicação, o snapshot foi arquivado localmente em `../../backup/TFS-deploy-antigo-20260927/`.
O ZIP público não inclui fixtures, contas, credenciais ou ferramentas de desenvolvimento.

### Conferência independente do mapa online

A trava de publicação detectou mapas binariamente diferentes e interrompeu a
primeira tentativa **antes de qualquer escrita no servidor**. A auditoria foi
repetida diretamente na VPS: mesmos 245 baús, 229 flags e 92 storages de NPCs.
O catálogo inteiro gerado a partir do mapa online é idêntico, campo por campo,
ao revisado localmente; itens e fontes de NPCs também são idênticos. O mapa online
foi preservado, sem substituição pela cópia local.

- Mapa local: `94409f5997d4040441893e01bc292f484be4461752fabe0fb22bd5eb7a665328`.
- Mapa online: `47abff45182fd7b9b15b20bc95bfac52145b4d352eb31586093fb14cb94996e0`.
- Catálogo normalizado: `62e460bdfb08635dd3906948f2822dd634998e1b5d152f7e378fe7ef9ddde425`.

`reconcile-map` só aceita essa divergência após conferir o mapa auditado e a
igualdade completa das entradas, mantendo as demais travas de publicação.

## Recuperação

O diretório de release na VPS preserva `server-before.tar.gz`, os arquivos-base,
o v34 público e `website-before/`. Para voltar, restaurar os dois arquivos de
registro/login desse backup e reiniciar `imperium772`; os dois novos arquivos Lua
ficam inativos. Restaurar o índice e manifest do site se necessário. Nenhum dado
de progresso requer rollback, pois o Quest Log não grava storages.
