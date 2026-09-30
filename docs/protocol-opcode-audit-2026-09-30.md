# Inventário dos opcodes de jogo — 30/09/2026

## Escopo e evidência

Leitura do worktree em `1cbe884`, após a correção do harness de login. O recorte
é a entrada de `ProtocolGame::parsePacket`, seus leitores e o enfileiramento de
tarefas. Foram identificados **69 valores no switch**, além de `0x0F` tratado
somente em condições de saída antecipada e do caso desconhecido. Agrupar
valores na tabela não elimina nenhum dos 69 casos.

A conferência entre os valores `case` de `protocolgame.cpp:423–493` e a coluna
de opcodes encontrou 69 valores distintos em ambos, sem ausentes, extras ou
duplicados. `0x0F` e o default são linhas adicionais e não entram nessa conta.

Esta revisão não executou testes, fuzzers, sockets, banco ou mundo. A existência
de um alvo ou harness abaixo não afirma que ele passou neste commit. Os
resultados de CI devem ser registrados separadamente. O inventário não encerra
a auditoria de regras, autorização ou efeitos de cada método de `Game`/Lua.

Fontes principais: `src/protocolgame.cpp:395` (switch), `:723` (leitores comuns),
`:2408` (extensões); `src/protocolgame.h:283` (helpers de dispatch);
`src/networkmessage.h:51` e `src/networkmessage.cpp:27` (leituras).

## Convenções e guards comuns

- `u8`, `u16`, `u32`, `i32`: leituras de tamanho fixo por `getByte`/`get<T>`.
  `Pos` lê `x:u16`, `y:u16`, `z:u8` por `getPosition`.
- `S`: `getString`, com comprimento `u16` seguido daqueles bytes. O helper de
  leitura sinaliza overrun em falha; a string tem comprimento explícito e pode
  conter NUL. O limite de 8192 de `addString` pertence à **saída**, não limita
  essa leitura de entrada.
- `G`: `addGameTask(msg, ...)` verifica `isReadPositionValid` antes de criar a
  tarefa. `T`: `addGameTaskTimed(msg, DISPATCHER_TASK_EXPIRATION, ...)` faz a mesma
  verificação e usa expiração de 2000 ms (`src/tasks.h:27`). Ambos capturam os
  argumentos no trabalho do dispatcher e passam o ID da sessão do jogador.
- `D`: tarefa criada diretamente com `createTask`, sem expiração. A coluna de
  guard identifica a validação local feita antes dela. `G0`/`T0`: variantes sem
  `msg`, usadas em opcodes sem campos adicionais.
- `isReadPositionValid` usa a convenção do corpo XTEA: cursor no máximo em
  `length + INITIAL_BUFFER_POSITION` (4), sem overrun e abaixo do fim físico.
  `canRead` admite folga de 8 bytes; por isso a verificação final e o guard
  anterior ao dispatch têm funções distintas. Eles não exigem, em geral, que
  todo byte restante tenha sido consumido (`src/networkmessage.h:148–176`).
- Antes do switch, `acceptPackets`, estado SHUTDOWN e corpo vazio encerram a
  entrada. Sem jogador, só `0x0F` desconecta. Jogador removido ou morto permite
  apenas `0x14`; `0x0F` desconecta nesse estado. Após o switch, cursor inválido
  desconecta (`src/protocolgame.cpp:395–500`). Isso não substitui a validação
  anterior ao enfileiramento.

## Matriz da entrada autenticada

Os nomes de tarefas abaixo pertencem a `Game`, exceto quando `ProtocolGame`
estiver indicado. `playerId` é obtido do jogador associado ao protocolo; IDs de
alvos, posições, nomes e textos continuam sendo entrada não confiável.

| Opcode(s) | Leitor / linha em `protocolgame.cpp` | Campos após o opcode | Guard e dispatch | Destino / efeito solicitado |
|---|---|---|---|---|
| `0x14` | switch:424 | Nenhum | D, captura `getThis()` | `ProtocolGame::logout(true, false)` |
| `0x1D`, `0x1E` | switch:425–426 | Nenhum | G0 | `playerReceivePingBack`, `playerReceivePing` |
| `0x32` | `parseExtendedOpcode`:2408 | Subopcode:u8, buffer:S | G | `parsePlayerExtendedOpcode`; evento Lua |
| `0x40` | `parseNewPing`:2417 | pingId:u32, localPing:u16, fps:u16 | Cursor validado; G e D | `playerReceiveNewPing`; `ProtocolGame::sendNewPing(pingId)` |
| `0x42` | `parseChangeMapAwareRange`:2439 | width:u8, height:u8 | Exige OTCv8 e cursor válido; D | `ProtocolGame::changeMapAwareRange` |
| `0x45` | `parseNewWalking`:2499 | walkId:u32, predictiveWalkId:i32, Pos, flags:u8, numdirs:u16, direções:u8[] | `parseNewWalkingPath`; D com `self` e caminho | Filtra caminhada antiga/preditiva; `playerNewWalk` |
| `0x64` | `parseAutoWalk`:753 | numdirs:u8, direções:u8[] | Quantidade não zero, fim exato `length+4`, caminho não vazio; G | `playerAutoWalk` |
| `0x65`, `0x66`, `0x67`, `0x68`, `0x6A`, `0x6B`, `0x6C`, `0x6D` | switch:432–440 | Nenhum | G0; direção fixa por opcode | `playerMove`: N, E, S, W, NE, SE, SW, NW |
| `0x69` | switch:436 | Nenhum | G0 | `playerStopAutoWalk` |
| `0x6F`, `0x70`, `0x71`, `0x72` | switch:441–444 | Nenhum | T0; direção fixa por opcode | `playerTurn`: N, E, S, W |
| `0x78` | `parseThrow`:851 | from:Pos, spriteId:u16, fromStack:u8, to:Pos, count:u8 | Só se posições diferem; T | `playerMoveThing` |
| `0x7D` | `parseRequestTrade`:976 | Pos, spriteId:u16, stack:u8, targetPlayerId:u32 | G | `playerRequestTrade` |
| `0x7E` | `parseLookInTrade`:985 | counterOffer:u8, index:u8 | counterOffer é verdadeiro só para 1; T | `playerLookInTrade` |
| `0x7F`, `0x80` | switch:448–449 | Nenhum | G0 | `playerAcceptTrade`, `playerCloseTrade` |
| `0x82` | `parseUseItem`:804 | Pos, spriteId:u16, stack:u8, index:u8 | T | `playerUseItem` |
| `0x83` | `parseUseItemEx`:813 | from:Pos, fromSprite:u16, fromStack:u8, to:Pos, toSprite:u16, toStack:u8 | T | `playerUseItemEx` |
| `0x84` | `parseUseWithCreature`:824 | from:Pos, spriteId:u16, fromStack:u8, creatureId:u32 | T | `playerUseWithCreature` |
| `0x85` | `parseRotateItem`:1004 | Pos, spriteId:u16, stack:u8 | T | `playerRotateItem` |
| `0x87` | `parseCloseContainer`:833 | containerId:u8 | G | `playerCloseContainer` |
| `0x88` | `parseUpArrowContainer`:839 | containerId:u8 | G | `playerMoveUpContainer` |
| `0x89` | `parseTextWindow`:961 | windowTextId:u32, text:S | G | `playerWriteItem` |
| `0x8A` | `parseHouseWindow`:968 | doorId:u8, id:u32, text:S | G | `playerUpdateHouseWindow` |
| `0x8C` | `parseLookAt`:864 | Pos, spriteId ignorado:2 bytes, stack:u8 | `skipBytes(2)` e T | `playerLookAt` |
| `0x8D` | `parseLookInBattleList`:872 | creatureId:u32 | T | `playerLookInBattleList` |
| `0x96` | `parseSay`:878 | type:u8; receiver:S ou channelId:u16 conforme tipo; text:S | Texto no máximo 255 bytes e sem LF; G | `playerSay`; receiver/canal só lidos nos tipos correspondentes |
| `0x97` | switch:461 | Nenhum | G0 | `playerRequestChannels` |
| `0x98` | `parseOpenChannel`:735 | channelId:u16 | G | `playerOpenChannel` |
| `0x99` | `parseCloseChannel`:741 | channelId:u16 | G | `playerCloseChannel` |
| `0x9A` | `parseOpenPrivateChannel`:747 | receiver:S | G | `playerOpenPrivateChannel` |
| `0x9B` | `parseProcessRuleViolationReport`:949 | reporter:S | G | `playerProcessRuleViolationReport` |
| `0x9C` | `parseCloseRuleViolationReport`:955 | reporter:S | G | `playerCloseRuleViolationReport` |
| `0x9D` | switch:467 | Nenhum | G0 | `playerCancelRuleViolationReport` |
| `0xA0` | `parseFightModes`:911 | fight:u8, chase:u8, secure:u8 | Normaliza fight/chase e secure != 0; G | `playerSetFightModes` |
| `0xA1` | `parseAttack`:937 | creatureId:u32 | G | `playerSetAttackedCreature` |
| `0xA2` | `parseFollow`:943 | creatureId:u32 | G | `playerFollowCreature` |
| `0xA3` | `parseInviteToParty`:1036 | targetId:u32 | G | `playerInviteToParty` |
| `0xA4` | `parseJoinParty`:1042 | targetId:u32 | G | `playerJoinParty` |
| `0xA5` | `parseRevokePartyInvite`:1048 | targetId:u32 | G | `playerRevokePartyInvitation` |
| `0xA6` | `parsePassPartyLeadership`:1060 | targetId:u32 | G | `playerPassPartyLeadership` |
| `0xA7` | switch:475 | Nenhum | G0 | `playerLeaveParty` |
| `0xA8` | `parseEnableSharedPartyExperience`:1054 | active:u8 | Verdadeiro só para 1; G | `playerEnableSharedPartyExperience` |
| `0xAA` | switch:477 | Nenhum | G0 | `playerCreatePrivateChannel` |
| `0xAB` | `parseChannelInvite`:723 | name:S | G | `playerChannelInvite` |
| `0xAC` | `parseChannelExclude`:729 | name:S | G | `playerChannelExclude` |
| `0xBE` | switch:480 | Nenhum | G0 | `playerCancelAttackAndFollow` |
| `0xC9` | switch:481 | Nenhum lido | Sem tarefa | No-op, comentário `update tile` |
| `0xCA` | `parseUpdateContainer`:845 | containerId:u8 | G | `playerUpdateContainer` |
| `0xCC` | `parseSeekInContainer`:1074 | containerId:u8, index:u16 | G | `playerSeekInContainer` |
| `0xD2` | switch:484 | Nenhum | G0 | `playerRequestOutfit` |
| `0xD3` | `parseSetOutfit`:785 | lookType:u16, head/body/legs/feet/addons:u8, mount:u16 | G | `playerChangeOutfit` |
| `0xD4` | `parseToggleMount`:798 | mount:u8 | Verdadeiro só para 1; G | `playerToggleMount` |
| `0xDC` | `parseAddVip`:992 | name:S | G | `playerRequestAddVip` |
| `0xDD` | `parseRemoveVip`:998 | guid:u32 | G | `playerRequestRemoveVip` |
| `0xE6` | `parseBugReport`:1012 | bug:S | G | `playerReportBug` |
| `0xE7` | switch:490 | Nenhum lido | Sem tarefa | No-op, comentário `violation window` |
| `0xE8` | `parseDebugAssert`:1018 | assertLine:S, date:S, description:S, comment:S | Ignora após primeiro relatório; cursor validado antes de marcar `debugAssertSent`; G | `playerDebugAssert` |
| `0xF9` | `parseModalWindowAnswer`:1066 | id:u32, button:u8, choice:u8 | G | `playerAnswerModalWindow` |
| `0x0F` (fora do switch) | guards:403–418 | Nenhum | Só sem jogador ou jogador removido/morto | Desconecta; jogador vivo chega ao default |
| Demais valores | default:493 | Nenhum lido | Sem tarefa | Log do opcode desconhecido; checagem final do cursor |

### Guards específicos que não são regras completas de jogo

`0x45`: o helper limita `numdirs` a 1–4096 e aos bytes restantes, converte
direções 1–8 e ignora valores desconhecidos. Uma lista sem direção válida é
rejeitada. Não exige igualdade entre quantidade e bytes restantes, nem rejeita
uma lista mista válida/inválida. Os checks de walkId/predição ocorrem na tarefa
do dispatcher (`src/walkpathparser.h:29–57`, `protocolgame.cpp:2515–2535`).

`0x64`: exige quantidade/fim exatos, faz leitura reversa e também filtra
direções desconhecidas. Isso difere do helper usado por `0x45`; cobertura do
helper não é cobertura automática deste leitor (`protocolgame.cpp:753–783`).

`0x42`: o callback reavalia existência/estado/saúde do jogador e `acceptPackets`,
limita mudanças a uma por 500 ms e aplica `MapViewport::set`, com alcance
horizontal 8–15 e vertical 6–8. Serialização do mapa ocorre no dispatcher
(`protocolgame.cpp:2449–2471`, `src/mapviewport.h:9–20`). Teste de geometria não
prova o enfileiramento, rate limit ou lifetime desse callback.

`0x96`: o parser distingue receiver para PRIVATE/PRIVATE_RED/RVR_ANSWER e
channelId para CHANNEL_Y/CHANNEL_R1/CHANNEL_R2. Os outros tipos usam canal zero;
validade de tipo, permissões, destinatário e efeitos são responsabilidade dos
callers posteriores. Outros campos `S`, como textos de janela, bug e extensão,
não recebem aqui o teto de 255 bytes específico de fala.

## Cobertura encontrada por leitura

| Fonte / alvo ou harness existente | Chamadas e asserts presentes na fonte | Limite para a matriz acima |
|---|---|---|
| `tests/networkmessage-bounds-tests.cpp:22–105`; alvo `networkmessage-bounds` | Helpers verdadeiros de skip, backtracking e validade do cursor; negativos de limite físico/lógico e overrun | Não chama `ProtocolGame::parsePacket` nem os leitores da tabela. Não valida todos os campos `getString/getPosition/get<T>` em cada opcode. |
| `tests/protocol-walk-parser-tests.cpp:23–69`; alvo `protocol-walk-parser` | `parseNewWalkingPath` inline: direções válidas, truncamento, lista toda inválida, zero e quantidade 4097 | Cobertura parcial do helper de `0x45`; não lê seu cabeçalho, não testa dispatch, walkId/predição, estado do jogador ou `0x64`. |
| `tests/protocol-input-fuzzer.cpp:30–92`; alvo opt-in `protocol-input-fuzzer` | `NetworkMessage` e `parseNewWalkingPath`, com invariantes de caminho/posição | Não chama `ProtocolGame`, `Game`, login/RSA ou dispatcher. Não representa fuzzing de todos os 69 opcodes. |
| `tests/viewport-geometry.cpp:5–23`; harness standalone | `MapViewport` real: dimensões iniciais, 65.536 pares de entradas, limites e dimensões inclusivas; três pares explícitos | Não há alvo CMake/CTest nem invocação em workflow ou script encontrada. `docs/viewport-v38.md:104–105` documenta compilação/execução manual. Todos os oráculos usam `assert`; com `NDEBUG` ficam desabilitados, embora a mensagem PASS continue sendo impressa. Não chama `parseChangeMapAwareRange`, rate limit, dispatch ou callback de `0x42`. |
| `tests/login-gate-core-tests.cpp:171–273`; alvo opt-in `login-gate-core` | Core verdadeiro com Dispatcher/Scheduler. `ProtocolGame::onRecvFirstMessage` é chamado para o gate `blockLogin` (`:205–208`); fixtures RSA malformados e legacy são enviados a `ProtocolLogin::onRecvFirstMessage` (`:212–231`). Também chama login e reconnect atrasado | Login é anterior a `parsePacket`, não integra o switch autenticado. Os negativos de password/trailer não são testes do parser de primeiro pacote de jogo. Sem banco, socket aberto, mapa ou sessão completa. Não prova ownership de jogador carregado nem todos os resultados de autorização SQL. Execução deste commit não foi feita nesta revisão. |
| `tests/ban-lookup-tests.cpp:38–114`; alvo opt-in `ban-lookup` | Código real de `src/ban.cpp`, com resultados Database/DBResult simulados, para Error/Clear/ban ativo/expirado | Não envia opcode autenticado, não testa MariaDB ou todos os callers em Error. |

O CMake liga os testes de bounds/walking ao `tfs_core`, mas isso por si só não
faz seus casos chamarem `parsePacket`. O fuzzer tem somente seu arquivo,
includes e flags de compilação/link, sem ligação a `tfs_core`
(`CMakeLists.txt:163–187`). Seu entrypoint chama apenas os dois helpers
(`tests/protocol-input-fuzzer.cpp:88–92`). Não há seleção de opcode, leitura do
prefixo completo de `0x45`, `getString`, `getPosition`, sessão autenticada ou
dispatcher nesse harness. O count e o cursor são parâmetros sintéticos; a
cobertura guiada por fuzz só pode ser confirmada por resultado de execução.

A busca em `tests/`, `tools/` e `.github/` não encontrou chamada direta a
`ProtocolGame::parsePacket` ou aos demais leitores C++ da matriz. A referência
a `parseNewWalkingPath` não é chamada ao método `parseNewWalking`. Em `tools/`,
fora de artefatos `bin/obj`, foi encontrado somente o projeto `ReleaseSigner`,
sem harness de protocolo.

### Probes de staging que constroem frames de gameplay

Os arquivos abaixo têm código para conectar a um servidor de staging, montar
frames e verificar alguns resultados. Esta revisão leu esse código, sem
executá-lo. Classificação: **probe existente, execução não verificada**. Seus
frames indicam quais entradas o harness pretende enviar; não demonstram
cobertura de truncamentos, de todos os campos, de enums ou do enqueue em
rejeição.

| Opcode(s) / campos construídos | Evidência de fonte | Limite |
|---|---|---|
| `0x14`, `0x1E`; `0x65`, `0x67`; `0x96` com tipo 1 e string; `0xA0` com modos 2/0/0; `0xA1` com target:u32; `0x32`/202 com JSON de Market | `tests/load-test-50.py:38,240–256,308,353–374,435–449` | Tráfego de sessões/carga e ações de Market. Os movimentos e a fala são enviados; o código não contém uma matriz de negativos dos parsers C++. A seleção do target é condicional. |
| `0x32`/127 com string de rarity; `0x8C` com Pos, item:u16, stack:u8; `0x82` com Pos, item:u16, stack/index:u8; `0x78` com posições, item:u16, stack/count:u8 | `tests/rarity-live.py:253–268,287–296` | Há asserts de metadata, texto de Look e abertura do backpack. Os efeitos observados são de funcionalidades de rarity/inventário; não isolam o parser ou todas as variações de seus campos. |
| `0x32`/129 com string; `0x8C`; `0x78` para drop/pickup de fixture | `tests/ground-rarity-live.py:102–114` | Verificações de negociação/rejeição e resultados de ground rarity; sem chamada offline ao parser C++. |
| `0x32`/128 com string; `0x97`; `0x98`/`0x99` com channel:u16; `0x96` com tipo 5, channel:u16 e string | `tests/loot-live.py:112–123,184–209,230–232` | Asserts sobre resposta e canal Loot, inclusive tentativas de request inválido. O payload inválido do subopcode não equivale a um frame binário truncado do `parseExtendedOpcode`. |
| `0x32`/124, /125 e /126 | `tests/bestiary-live.py:42`; `tests/questlog-live.py:40`; `tests/achievements-live.py:42` | Probes de Bestiary, Quest Log e Achievements. Não foram executados nesta revisão. |

O transporte Python faz framing/XTEA em
`tests/load_test_protocol.py:13–65`. Os testes offline de
`tests/test_load_test.py:17–84,112–115` usam socket/Market mocks para roundtrip,
fragmentação, ping e receipts. São testes do harness Python, sem execução do
transporte C++ ou do switch de jogo. Da mesma forma, `--self-test` de
`rarity-live.py:439–458`, `loot-live.py:266–286` e
`ground-rarity-live.py:323–354` exercita decoders Python de respostas, sem
execução dos parsers C++.

### Handlers Lua, mocks de cliente e source checks

| Fonte / subopcode ou área | O que a fonte testa | Limite para `ProtocolGame` |
|---|---|---|
| `tests/bestiary-tests.lua:53–74`; subopcode 124 | Chamada direta ao handler Lua; resposta, throttle, invalid/oversized/wrong opcode | Usa jogador simulado; não lê frame binário, comprimento `u16` ou dispatch de `0x32`. |
| `tests/questlog-tests.lua:5–25,79–92`; subopcode 125 | Handler Lua real com player mock, JSON/requestId, entradas inválidas, burst e ausência de mutação de progresso | Não chama o parser C++ ou `NetworkMessage`; limites de payload são próprios do handler. |
| `tests/achievements-tests.lua:25–27,60,105–123`; subopcode 126 | Helpers/handler Lua de ações, progress server-owned, throttle, JSON inválido e limites de entrada/saída | O envio é mockado; a comparação com 8192 se refere ao limite de string de saída. Não integra `parseExtendedOpcode`. |
| `tests/rarity-ui-tests.lua:111–116,266–274`; subopcode 127 | Handler Lua e callback do cliente ligados por filas mockadas; malformed/wrong opcode | Não atravessa `Connection`, XTEA ou parser C++. |
| `tests/loot-ui-tests.lua:51–62,158–161`; `tests/ground-rarity-ui-tests.lua:49–63,188–190`; subopcodes 128/129 | Tabela Lua substitui o `ProtocolGame` do cliente; callback direto testa payloads inválidos, tamanho e protocolo stale | São mocks de cliente, não testes do `ProtocolGame` C++ do servidor. |
| `tests/achievements-ui-tests.lua:144–146,199,291–293`; `tests/questlog-ui-tests.lua:17–28,49–51`; `tests/bestiary-ui-tests.lua:26` | Callbacks Lua de cliente e validação/renderização de payloads | Não acrescentam cobertura aos campos binários de `0x32`. |
| `tests/market-rate-limit-tests.lua:3–14,30–46` | Extrai o helper `allowed` do handler Market e testa rate limit/cleanup | Helper-only Lua; não envia frame e não testa o parser de `0x32`/202. |
| `tests/test_report_bug_path.py:9–18`; downstream de `0xE6` | Lê texto de `data/events/scripts/player.lua` e exige strings sobre filename/GUID | Source check; não executa `parseBugReport`, seu campo string ou a tarefa de relatório. |
| `tests/test_connection_output_queue.py:9–33`; `tests/test_connection_shutdown_serialization.py:10–43` | Source checks de ordem/guard e de configuração de alvo/workflow | Não executam os interleavings, a conexão ou qualquer opcode do switch. |

### Integração declarada em CMake e workflows

Configuração de build ou workflow é evidência da invocação pretendida. Não é
resultado de execução ou aprovação deste commit.

- `CMakeLists.txt:163–175`: `TFS_BUILD_NETWORKMESSAGE_TESTS` é OFF por padrão;
  registra os targets/CTest de bounds e walking ligados a `tfs_core`.
  `CMakeLists.txt:113–124` registra login/ban lookup, também opt-in.
- `CMakeLists.txt:177–187`: o fuzzer é OFF por padrão, exige Clang e recebe
  libFuzzer/ASan/UBSan. Não é um teste CTest e não liga `tfs_core`.
- `.github/workflows/security-build.yml:23–30,74–99`: matrix release, release
  hardened, ASan/UBSan e TSan; habilita os testes de networkmessage/login e
  declara build e `ctest`.
- `.github/workflows/security-build.yml:175–209`: job separado do fuzzer,
  quatro seeds sintéticos de path/cursor, ASan/UBSan e limite de 30 segundos.
  Upload de corpus/crash é declarado somente em falha (`:211–219`).
- `.github/workflows/security-build.yml:148–160`: declara testes Lua de
  Economy/lamp/rarity economy e unittest Python do harness/source checks.
  Não declara a execução dos probes de gameplay ou de todas as suites Lua
  listadas acima.
- `.github/workflows/cppcheck.yml:33–54`: análise estática das unidades do
  servidor pela compilation database. `.github/workflows/codeql.yml:31–40`:
  análise estática com `build-mode: none`. Nenhuma das duas executa os parsers.
- `tests/security-staging-run.py:40–41,79–80`: script standalone declara
  self-tests Python e fases de rarity, ground rarity e carga de staging.
  Não foi encontrada uma chamada a esse script no workflow de regressões.
- `tests/viewport-geometry.cpp` tem comando manual documentado em
  `docs/viewport-v38.md:104–105`. Não foi encontrada integração em CMake,
  `.github/`, `tests/` ou `tools/`; a impressão PASS sozinha não informa se
  `NDEBUG` desabilitou seus asserts.

## Revisão do harness de login corrigido

Os dois bloqueadores encontrados na leitura anterior foram removidos:
`Player` continua `final`; a fixture usa `std::shared_ptr<Player>` real e acesso
`friend` mínimo. `attachProtocol` preenche `Connection::protocol` sob seu
`connectionLock`, antes dos parsers, sem accept/read/socket. A resposta do caso
legado pode chamar `internalSend` com protocolo válido.

Os dois casos malformados vêm antes da primeira tentativa MySQL. Uma barreira
no dispatcher precede a observação do contador zero, evitando que o cooldown
da tentativa legada esconda uma autenticação anterior. Comparações de ciclos
foram removidas desses casos: `close` com protocolo associado enfileira um
`release` legítimo. `onDispatcher` espera `ready.get`, preservando a vida útil
das referências capturadas; o CTest configura timeout externo de 15 segundos
(`CMakeLists.txt:121–124`).

No reconnect, o registro de `Game` contém somente o jogador sintético; o teste
remove manualmente seu cliente anterior para representar a liberação. O
Scheduler/callback verdadeiros reavaliam manutenção antes de incrementar a
referência ou associar o novo protocolo (`protocolgame.cpp:207–227`). O cleanup
encerra/junta Scheduler, remove autosend e registro no Dispatcher, e por fim
encerra/junta Dispatcher. A leitura não confirmou novo problema de ownership
ou cleanup nesse caminho. A simulação não comprova release de uma sessão real,
serialização do mundo, salvamento ou reconexão aceita completa.

## Lacunas e próximos casos isolados

1. Para cada leitor de campos da matriz: corpo vazio, truncamento em cada campo,
   comprimento máximo/inválido de string/lista, bytes extras e valores de enum
   fora do domínio. Observar **ausência de tarefa** em rejeição, além do cursor.
2. Para cada rota: jogador ausente, morto/removido, `acceptPackets=false`, logout
   pendente, conexão fechada antes do callback e troca de cliente. A matriz
   atual identifica guards de fonte; não prova todos esses interleavings.
3. Para trade/itens/container/janelas/party: rastrear em `Game` ownership,
   alcance, ID de alvo/item, validade da janela e autorização da ação. O guard
   de cursor protege o parse; não certifica integridade de inventário, economia
   ou permissões.
4. Para `0x32`: inventariar subopcodes Lua e seus limites próprios. Strings são
   copiadas para tarefa sem expiração. As filas de entrada continuam sem teto
   de bytes/tarefas; saturação com dispatcher lento é risco condicional já
   registrado, não exploit reproduzido nesta leitura.
5. Para `0x40`, `0x42`, `0x45` e `0xE8`: casos reais de callback/flag/estado,
   incluindo falha de saída e cancelamento. Para opcodes desconhecidos, medir
   volume de log sob os limites existentes antes de propor um controle.

Nenhuma execução nova ou vulnerabilidade remota confirmada é declarada por
este inventário. Seus 69 casos têm mapeamento de fonte; a cobertura dinâmica
específica deve ser ampliada e vinculada a resultados do commit testado.
