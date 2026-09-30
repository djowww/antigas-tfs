# ContinuaÃ§Ã£o da auditoria de seguranÃ§a â€” 30/09/2026

Esta rodada parte de `main` em `465ccf4`, cujo cÃ³digo de servidor corresponde a
`f4fa832`. A revisÃ£o do worktree confirmou ausÃªncia de alteraÃ§Ãµes pendentes
antes desta rodada. As correÃ§Ãµes novas sÃ£o desenvolvidas na branch
`security-auth-updater-20260930`; os resultados anteriores nÃ£o substituem builds
e testes destas alteraÃ§Ãµes.

O objetivo original continua sendo a auditoria de todas as 34 fases solicitadas,
com correÃ§Ãµes pequenas, compatibilidade, ferramentas, testes e documentaÃ§Ã£o.
Este documento registra progresso e lacunas. NÃ£o declara a auditoria encerrada.

## Problemas desta rodada

| ID / severidade | Local / condiÃ§Ã£o | EvidÃªncia e impacto | CorreÃ§Ã£o / validaÃ§Ã£o | Risco residual |
|---|---|---|---|---|
| LOGIN-01 / P2 | `src/protocolgame.cpp`, `ProtocolGame::onRecvFirstMessage`, `login`, `connect`; `src/protocollogin.cpp`, `getCharacterList` | `blockLogin` era consultado somente na entrada da lista de personagens. Um cliente com credenciais vÃ¡lidas podia conectar diretamente Ã  porta de jogo. Uma mudanÃ§a da configuraÃ§Ã£o enquanto uma tarefa de login/reconexÃ£o aguardava tambÃ©m nÃ£o era reavaliada. | Aplicado o bloqueio na entrada de jogo, no login no dispatcher, na lista de personagens jÃ¡ enfileirada e no callback atrasado de reconexÃ£o. A mensagem configurada Ã© preservada. Teste nativo integrado implementado, aguardando CI. | O bloqueio controla novas entradas e reconexÃµes; nÃ£o Ã© um mecanismo para expulsar sessÃµes jÃ¡ autenticadas. ConfiguraÃ§Ã£o administrativa continua precisando de proteÃ§Ã£o. |
| BANLOOKUP-01 / P2 condicional | `src/ban.cpp`, consultas de conta/IP/namelock; callers em ambos os protocolos | `Database::storeQuery` retorna `nullptr` tanto para zero linhas quanto para falha. Os helpers anteriores tratavam ambos como ausÃªncia de banimento. Uma falha da tabela de banimentos com contas/personagens legÃ­veis podia liberar uma entrada proibida. | Resultado explÃ­cito `Clear`, `Banned`, `Error`, usando o indicador de sucesso da consulta. Em `Error`, o login recebe indisponibilidade temporÃ¡ria. Teste do cÃ³digo verdadeiro de consulta com uma interface de banco simulada implementado, aguardando CI. | Corrigir erros do banco continua necessÃ¡rio. A indisponibilidade de uma consulta de autorizaÃ§Ã£o agora recusa acesso; nÃ£o passa a representar usuÃ¡rio liberado nem banimento permanente. |
| LOGINPARSE-01 / P3 | `src/protocollogin.cpp`, `onRecvFirstMessage` | O parser da lista de personagens nÃ£o verificava o cursor final antes de enfileirar autenticaÃ§Ã£o. O buffer admite folga para outros formatos, mas o primeiro pacote jÃ¡ possui comprimento absoluto, exigindo validaÃ§Ã£o estrita desse limite. NÃ£o foi demonstrado bypass de credenciais ou crash por este caminho. | Checagem de overrun e cursor antes do dispatch, correspondente ao primeiro pacote do jogo. RegressÃ£o deve incluir consumo de bytes alÃ©m do comprimento declarado, inclusive trailer OTCv8. | A correÃ§Ã£o nÃ£o substitui a auditoria individual de todos os campos/opcodes. O formato e o padding legÃ­timos sÃ£o preservados. |
| UPD-02 / P2 | `deploy/launcher/AntigasLauncher/UpdateApplyForm.cs`, `ApplyAsync` / fechamento da janela | Fechar a janela enquanto `Task.Run` troca arquivos encerra o message loop e pode terminar o processo antes do catch que faria rollback. A lista de alteraÃ§Ãµes existe somente em memÃ³ria. | `OnFormClosing` cancela o fechamento enquanto validaÃ§Ã£o/aplicaÃ§Ã£o/rollback estÃ¡ pendente e o libera quando termina. O harness `LauncherFormLifecycle` invoca mÃ©todos reais sem mostrar janela nem iniciar cliente; passou. O mesmo harness falha com a fonte anterior. Build Release normal passou sem avisos/erros. | Encerramento forÃ§ado e perda de energia ainda exigem journal persistente/recuperaÃ§Ã£o apÃ³s reinÃ­cio. O harness nÃ£o simula perda de energia nem certifica todos os caminhos de interface. |
| LUALIFE-01 / P2 | `src/luascript.cpp`, construtor/init/close; `src/raids.cpp`, construÃ§Ã£o global | Ao tornar UBSan bloqueante, cinco testes de core acusaram chamada de membro com vptr invÃ¡lido: `Game` constrÃ³i `Raids` antes do `LuaEnvironment` de outro translation unit. O teardown tambÃ©m podia ler um ambiente global jÃ¡ destruÃ­do. | Guarda de lifetime com inicializaÃ§Ã£o constante; Raids inicializa a interface no carregamento, apÃ³s os globais. RegressÃ£o real de load/clear/reload/Lua e teardown implementada, aguardando CI. | NÃ£o foi demonstrado gatilho remoto. A guarda protege a existÃªncia do ambiente; nÃ£o modifica regras de raids nem resolve todos os riscos de reload/Lua. |

Esta rodada encontrou quatro problemas P2 e um P3 acima. NÃ£o confirmou problema
novo P0/P1. Esse recorte nÃ£o Ã© uma contagem final de todo o projeto. As mudanÃ§as
de autorizaÃ§Ã£o nÃ£o modificam senha, protocolo, schema, combate, loot ou regras
de economia; recusam caminhos invÃ¡lidos ou indisponÃ­veis.

## RevisÃ£o independente de rede e tarefas

A revisÃ£o do cÃ³digo atual de `f4fa832` nÃ£o confirmou problema novo na reserva ou
liberaÃ§Ã£o de admissÃ£o/saÃ­da. HÃ¡ um accept pendente por porta; o protocolo sÃ³ Ã©
criado depois da admissÃ£o. A liberaÃ§Ã£o do slot Ã© idempotente. O fechamento
forÃ§ado retÃ©m o buffer de `async_write` atÃ© seu callback, enquanto descartes e
destrutor devolvem as reservas restantes. Essa Ã© evidÃªncia de revisÃ£o de fonte,
nÃ£o um novo ensaio de rede.

`CRASH-01` permanece: as threads de dispatcher e banco nÃ£o capturam exceÃ§Ãµes
C++ de uma tarefa. NÃ£o foi encontrado gatilho remoto determinÃ­stico novo.
`BehaviourDatabase::searchDigit` captura as exceÃ§Ãµes de `substr`/`stoi`; os
callers de `vectorAtoi` recebem XML local. `LootTracker::publish` insere a chave
antes do `.at`, sem callback intermediÃ¡rio. Erros comuns de Lua passam por
`lua_pcall`. Continuar depois de uma exceÃ§Ã£o arbitrÃ¡ria pode usar mundo ou
transaÃ§Ã£o parcialmente alterados; nÃ£o foi adicionado catch que esconda essa
condiÃ§Ã£o. Uma regressÃ£o integrada de encerramento por exceÃ§Ã£o foi implementada:
o driver exige o tÃ©rmino do processo de teste pela exceÃ§Ã£o exata da fixture,
com status 86, dois marcadores e nenhuma execuÃ§Ã£o da tarefa jÃ¡ enfileirada
depois dela. A execuÃ§Ã£o nativa aguarda CI; o terminate handler existe somente
no teste, nÃ£o modifica o comportamento do servidor.

As filas de entrada do dispatcher e de tarefas SQL ainda nÃ£o tÃªm teto de
tarefas/bytes. O opcode `0x32` pode copiar uma string do cliente para uma tarefa
sem expiraÃ§Ã£o. Se o dispatcher ficar lento enquanto o I/O continua ativo, os
limites de sockets e saÃ­da nÃ£o limitam esse backlog. NÃ£o foi demonstrado um
pacote que cause travamento infinito nem um limiar real de saturaÃ§Ã£o. O limite
seguro exige distinguir trabalho remoto de tarefas internas, retornar rejeiÃ§Ã£o
ao cliente e preservar gravaÃ§Ã£o/limpeza; descartar tarefas indiscriminadamente
seria uma alteraÃ§Ã£o de integridade. O `new_handler` atual encerra o processo em
falta de memÃ³ria; capturar `bad_alloc` apenas no dispatcher nÃ£o elimina isso.

## PersistÃªncia e autenticaÃ§Ã£o que exigem trabalho separado

- O SHA-1 de `AUTH-01` continua inadequado para proteÃ§Ã£o apÃ³s vazamento do banco.
  A revisÃ£o atual esclareceu que o protocolo jÃ¡ entrega a senha apÃ³s RSA e o
  SHA-1 Ã© aplicado pelo servidor. Portanto a migraÃ§Ã£o nÃ£o exige necessariamente
  novo formato de cliente; exige hash versionado, schema compatÃ­vel, site e sua
  biblioteca de autenticaÃ§Ã£o, rehash/reset e rollback testados. A descriÃ§Ã£o da
  auditoria histÃ³rica sobre compatibilidade deve ser lida com essa precisÃ£o.
- O charset do cliente MySQL ainda nÃ£o Ã© explicitamente configurado no core.
  Strings SQL manuais e permissÃµes/schema precisam de revisÃ£o antes de mudar
  encoding ou migrar as chamadas para parÃ¢metros. Nenhuma injeÃ§Ã£o explorÃ¡vel
  foi confirmada nesta rodada.
- A thread I/O chama consultas de login usando a conexÃ£o criada pelo dispatcher,
  sem inicializaÃ§Ã£o MySQL de thread explÃ­cita prÃ³pria. A correÃ§Ã£o anterior
  `DBTHREAD-01` cobre apenas o worker SQL. O impacto depende da biblioteca
  efetivamente linkada; requer revisÃ£o antes de afirmar crash. TambÃ©m falta um
  contador de tentativas de senha por conta: o limitador atual Ã© por conexÃ£o/IP.
- HÃ¡ um candidato de integridade fora do Market: o logout libera o personagem
  apÃ³s trÃªs tentativas imediatas de save falharem. Uma transferÃªncia entre dois
  jogadores existe em memÃ³ria antes dos saves independentes; com falha no save
  de um participante e sucesso posterior do outro, os snapshots podem divergir.
  O impacto de duplicaÃ§Ã£o exige reproduÃ§Ã£o isolada com dois personagens e
  falha de banco controlada; nÃ£o Ã© tratado aqui como exploit confirmado. O
  checkpoint/recibo do Market nÃ£o prova durabilidade de trades legados.
- O site visÃ­vel contÃ©m controles de CSRF, escaping de HTML, consultas
  parametrizadas e filtro de proprietÃ¡rio de pedido. A autenticaÃ§Ã£o efetiva,
  rate limiter e validaÃ§Ã£o de preÃ§o/proprietÃ¡rio/idempotÃªncia de Pix dependem de
  `security.php` / `pix.php`, externos ao checkout; nÃ£o foram inspecionados nesta
  rodada. A fonte visÃ­vel nÃ£o prova a configuraÃ§Ã£o desses componentes privados.

## Cobertura do pedido original

Os estados abaixo distinguem evidÃªncia jÃ¡ registrada de requisito ainda sem
prova suficiente. Os documentos de validaÃ§Ã£o sÃ£o histÃ³ricos: uma mudanÃ§a no
caminho testado exige nova execuÃ§Ã£o. Os testes desta branch serÃ£o acrescentados
ao registro depois de sua execuÃ§Ã£o; nÃ£o se presume aprovaÃ§Ã£o antecipada.

| Fase | EvidÃªncia disponÃ­vel | Trabalho ainda necessÃ¡rio |
|---|---|---|
| 1 InventÃ¡rio / arquitetura | Mapa em `SECURITY_AUDIT.md`, CMake e inventÃ¡rio de superfÃ­cies | Atualizar inventÃ¡rio de componentes externos quando forem acessÃ­veis. |
| 2 Crashes / memÃ³ria | CorreÃ§Ãµes de parser, include, ambientes Lua, scheduler, callbacks/reset; anÃ¡lise Cppcheck | Rastreabilidade de todos os callbacks/ownership e candidatos restantes; CRASH-01 continua residual. |
| 3 Sanitizers | Builds separados ASan+UBSan e TSan, CTest no CI | Os alvos nÃ£o cobrem a partida inteira; ampliar cenÃ¡rios sem confundir build instrumentada com runtime coberto. |
| 4 AnÃ¡lise C++ | Cppcheck com 73 unidades, baseline revisada, gate de anÃ¡lise completa | DiagnÃ³sticos `NEEDS_INVESTIGATION` restantes; dependÃªncias nÃ£o tÃªm cobertura semÃ¢ntica completa. |
| 5 Lua | Syntax de todos os scripts, parser de lamp, inventÃ¡rio/economia e regressÃµes de lifecycle | Lint semÃ¢ntico compatÃ­vel, mapa de storage/eventos e fechamento da revisÃ£o individual de todos os scripts. |
| 6 Banco / queries | RevisÃ£o, timeout/recuperaÃ§Ã£o, transaÃ§Ãµes/recibos de Market e quoting de identificador | Charset, parametrizaÃ§Ã£o incremental, permissÃµes/schema atuais e durabilidade de sistemas legados. |
| 7 Cada opcode | Guard de cursor antes de tarefas, walking, limites NetworkMessage | Matriz por opcode/campo/estado e casos fora de ordem ainda incompletos. |
| 8 Fuzzing | libFuzzer ASan+UBSan de NetworkMessage/walking, corpus preservado em falha | Login, deserializadores, XML/config e bindings Lua ainda sem targets equivalentes. |
| 9 DoS / limites | Adm. global/IP, tentativas/status com expiraÃ§Ã£o e orÃ§amento de saÃ­da | Backpressure de entrada e mediÃ§Ã£o de aÃ§Ãµes caras; nÃ£o rejeitar saves/cleanup por um teto indiscriminado. |
| 10 Stress / soak | Carga atual de 50 sessÃµes/30 s; teste histÃ³rico de Market com 100 sessÃµes | Soak prolongado, centenas de sessÃµes de gameplay e comparaÃ§Ã£o de RAM apÃ³s desconexÃ£o. |
| 11 Performance | Amostras CPU/RSS em staging; latÃªncias histÃ³ricas de Market | Profiling dos hot paths e comparaÃ§Ã£o atual antes/depois com latÃªncia/queries, sem micro-otimizaÃ§Ã£o por palpite. |
| 12 OrganizaÃ§Ã£o de scripts | MÃ³dulos e documentaÃ§Ã£o existentes; mudanÃ§as focadas | InventÃ¡rio de duplicaÃ§Ã£o/storage/lifecycle antes de refatoraÃ§Ã£o; nÃ£o mover regras de gameplay sem teste. |
| 13 Secrets | Gitleaks no checkout/histÃ³rico e CI, configuraÃ§Ãµes privadas ignoradas | Revalidar custÃ³dia externa de credenciais/chaves; scan do repo nÃ£o cobre outros clones/host. |
| 14 DependÃªncias / CVEs | Dependabot Actions/NuGet; alerts e security updates ativados e verificados por API; dependÃªncias CMake identificadas | InventÃ¡rio de versÃµes reais de sistema/vendorizadas, scan de advisories e SBOM ainda faltam. |
| 15 CodeQL / alternativa | Queries C#/C++ executadas; upload recusado pelo plano/settings; Cppcheck e Gitleaks ativos | AtivaÃ§Ã£o externa de Code Security para publicar CodeQL; continuar a anÃ¡lise alternativa. |
| 16 Actions | PermissÃµes mÃ­nimas, SHA de Actions, matriz de build/testes | Nova branch precisa passar os checks; nÃ£o usar apenas status vazio da API como prova de aprovaÃ§Ã£o. |
| 17 ProteÃ§Ã£o da main | APIs de protection/rulesets recusaram o recurso para o plano do repositÃ³rio privado (HTTP 403) | Quando disponÃ­vel, exigir PR, builds/checks aprovados e impedir force push/delete. O processo de PR pode ser seguido agora, mas a API confirmou que o enforcement nativo exige mudanÃ§a externa de plano. |
| 18 Pipeline | Build, testes, fuzz smoke, secret scan, Cppcheck, parsing PHP/Lua/Python | Lint Lua/ShellCheck e dependency scan ainda nÃ£o equivalem a simples parsing. |
| 19 Hardening binÃ¡rio | Release hardened Ubuntu 22.04 testada/deployada, flags compatÃ­veis | Revalidar o artefato das novas alteraÃ§Ãµes antes de deploy; nÃ£o instrumentar produÃ§Ã£o com sanitizers. |
| 20 Warnings | Builds e baseline Cppcheck; launcher TreatWarningsAsErrors | Baseline de warnings C++ ampliados e revisÃ£o dos diagnÃ³sticos .NET exploratÃ³rios. |
| 21 Sistema operacional | ServiÃ§o dedicado e hardening validado; capabilities zeradas | RevisÃ£o completa de SSH/permissÃµes/core dumps/atualizaÃ§Ãµes e dados externos permanece parcial. |
| 22 Firewall / exposiÃ§Ã£o | Portas 7173/7174 e site verificadas; isolamento do staging | InventÃ¡rio atual integral e regra de banco/admin devem ter evidÃªncia de host, com rollback para mudanÃ§as. |
| 23 Logs | Startup/shutdown/banco/Lua/rede documentados sem conteÃºdo de credenciais | DiagnÃ³stico de exceÃ§Ã£o C++ e rate limiting de logs acionÃ¡veis remotamente. |
| 24 Observabilidade | Coleta leve CPU/RSS e serviÃ§o ativo em testes | Tick, percentis, latÃªncia SQL, backlog, conexÃµes e contador de erros Lua ainda nÃ£o tÃªm cobertura completa. |
| 25 Shutdown / recovery | Ordem de scheduler/DB/dispatcher/sockets corrigida; recuperaÃ§Ã£o independente staging | ExercÃ­cio atual de shutdown com sessÃµes/carga ainda ativas e checagem de todos os dados salvos. |
| 26 Falha do banco | Testes histÃ³ricos isolados de Market e recuperaÃ§Ã£o documentados | Repetir contra cÃ³digo atual e expandir falhas para gameplay/saves e autorizaÃ§Ã£o; fixtures de lookup nÃ£o substituem MariaDB real. |
| 27 Startup automÃ¡tico | Runner de staging confirma serviÃ§o/listeners e operaÃ§Ã£o mÃ­nima, depois recuperaÃ§Ã£o | Smoke completo com DB de teste e runtime ASan/UBSan/shutdown/exit verificados automaticamente. |
| 28 RegressÃµes | Bugs corrigidos possuem alvos nativos/Lua/Python no CI | Registrar limites dos testes de fonte antigos; novos testes devem executar comportamento real. |
| 29 Fronteiras de entrada | Rede, JSON/ZIP, SQL/HTML, path, XML e Lua revistos por caminhos | Allowlist e limites ainda precisam de mapa completo por fronteira, inclusive configuraÃ§Ãµes/admin. |
| 30 Crash handling | PolÃ­tica fail-fast identificada; systemd documentado | Ensaio de diagnÃ³stico, build/SHA/thread/stack trace e core utilizÃ¡vel; teste fixture nÃ£o altera diagnÃ³stico de produÃ§Ã£o. |
| 31 Backup / restore | Backups e artefatos anteriores retidos; sem restore em produÃ§Ã£o | Procedimento e restauraÃ§Ã£o integral isolada com conferÃªncia de schema/dados/arquivos ainda nÃ£o comprovados. |
| 32 Economia / duplicaÃ§Ã£o | Market idempotente/concorrente e raridade persistente testados | Trade, rewards/quests e falha no save dos dois lados exigem testes prÃ³prios. |
| 33 Comandos admin | AutorizaÃ§Ã£o de comandos e caminhos de logs revistos | Matriz final de papÃ©is/talkactions/reloads e testes server-side de negaÃ§Ã£o. |
| 34 DocumentaÃ§Ã£o / entrega | Auditoria, hardening, addenda e relatÃ³rios atuais | Totais/tabela final e conclusÃ£o sÃ³ apÃ³s reunir a evidÃªncia que falta acima; preservar riscos residuais explÃ­citos. |

## Estado atual de verificaÃ§Ã£o

O CI do baseline `465ccf4` foi consultado nesta rodada: build/regressÃµes,
Cppcheck e secret scan concluÃ­ram com sucesso. O run CodeQL concluiu com falha;
o resultado nÃ£o Ã© contado como aprovaÃ§Ã£o. Os runs relevantes sÃ£o
[build/regressÃµes](https://github.com/djowww/antigas-tfs/actions/runs/36666883768),
[Cppcheck](https://github.com/djowww/antigas-tfs/actions/runs/36666883749),
[secret scan](https://github.com/djowww/antigas-tfs/actions/runs/36666883715) e
[CodeQL](https://github.com/djowww/antigas-tfs/actions/runs/36666883716).

Os resultados da branch desta rodada ainda precisam ser acrescentados apÃ³s
builds/testes. O ambiente Windows tem .NET disponÃ­vel; nÃ£o tem CMake e o
conjunto de dependÃªncias Linux do servidor no PATH. Os testes integrados de
core serÃ£o executados pelo CI Linux. Nenhum probe destrutivo, fuzzing ou falha
de banco desta rodada foi executado contra produÃ§Ã£o.

## ConfiguraÃ§Ãµes de seguranÃ§a do GitHub verificadas nesta rodada

A API confirmou que o repositÃ³rio continua privado e que a autorizaÃ§Ã£o tem
permissÃ£o administrativa. As consultas de proteÃ§Ã£o da `main` e rulesets
retornaram HTTP 403 com a mensagem de exigir GitHub Pro ou um repositÃ³rio
pÃºblico; nÃ£o houve contrataÃ§Ã£o nem mudanÃ§a de visibilidade. Essa limitaÃ§Ã£o
difere da disponibilidade do CodeQL e deve ser acompanhada separadamente.

Dependabot alerts estavam desativados (GET retornava 404). Foram ativados os
alerts/dependency graph e os security updates. Ambos os PUT retornaram 204.
A leitura posterior confirmou alerts ativos (204) e security updates
`enabled=true`, `paused=false`. A configuraÃ§Ã£o mensal de atualizaÃ§Ãµes de
Actions/NuGet permanece no repositÃ³rio. A ativaÃ§Ã£o nÃ£o prova ausÃªncia de CVEs,
nem cobre automaticamente bibliotecas instaladas por apt ou cÃ³digo sem
manifesto. ReferÃªncias: [configuraÃ§Ã£o de alerts](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-dependabot-alerts)
e [endpoints oficiais de repositÃ³rio](https://docs.github.com/en/rest/repos/repos#enable-vulnerability-alerts).

## Rodada intermediÃ¡ria preservada

O CI `36670481654` de `1cbe884` aprovou Release, Release hardened, TSan,
Windows, regressÃµes PHP/Lua/Python e fuzz smoke. ASan/UBSan falhou em cinco
testes de core quando `UBSAN_OPTIONS=halt_on_error=1` passou a ser exigido.
O diagnÃ³stico de vptr invÃ¡lido em `LuaScriptInterface` revelou LUALIFE-01.
Essa execuÃ§Ã£o nÃ£o Ã© aprovaÃ§Ã£o completa, e seu binÃ¡rio nÃ£o foi promovido.
A primeira tentativa `36669612392` falhou ao compilar a fixture de login,
que tentava herdar de `Player final`; foi corrigida sem retirar `final`.
TambÃ©m foram corrigidos a associaÃ§Ã£o do protocolo na conexÃ£o simulada e o
timeout que podia liberar capturas de stack com callbacks ainda pendentes.

A candidata assinada v54 passou nos sete controles do harness de integraÃ§Ã£o
Windows contra manifesto de staging HTTPS: assinatura/hash, adulteraÃ§Ã£o,
traversal, adulteraÃ§Ã£o apÃ³s extraÃ§Ã£o, instalaÃ§Ã£o limpa/userdata e rollback
apÃ³s falha injetada. O bundle contÃ©m o launcher corrigido; o Update ZIP o
omite, como nas versÃµes anteriores. NÃ£o houve inspeÃ§Ã£o visual de janelas.
