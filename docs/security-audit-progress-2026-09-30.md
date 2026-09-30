# Continuação da auditoria de segurança — 30/09/2026

Esta rodada parte de `main` em `465ccf4`, cujo código de servidor corresponde a
`f4fa832`. A revisão do worktree confirmou ausência de alterações pendentes
antes desta rodada. As correções novas são desenvolvidas na branch
`security-auth-updater-20260930`; os resultados anteriores não substituem builds
e testes destas alterações.

O objetivo original continua sendo a auditoria de todas as 34 fases solicitadas,
com correções pequenas, compatibilidade, ferramentas, testes e documentação.
Este documento registra progresso e lacunas. Não declara a auditoria encerrada.

## Problemas desta rodada

| ID / severidade | Local / condição | Evidência e impacto | Correção / validação | Risco residual |
|---|---|---|---|---|
| LOGIN-01 / P2 | `src/protocolgame.cpp`, `ProtocolGame::onRecvFirstMessage`, `login`, `connect`; `src/protocollogin.cpp`, `getCharacterList` | `blockLogin` era consultado somente na entrada da lista de personagens. Um cliente com credenciais válidas podia conectar diretamente à porta de jogo. Uma mudança da configuração enquanto uma tarefa de login/reconexão aguardava também não era reavaliada. | Aplicado o bloqueio na entrada de jogo, no login no dispatcher, na lista de personagens já enfileirada e no callback atrasado de reconexão. A mensagem configurada é preservada. Teste nativo integrado passou nas quatro variantes C++ do CI, inclusive sanitizadores. | O bloqueio controla novas entradas e reconexões; não é um mecanismo para expulsar sessões já autenticadas. Configuração administrativa continua precisando de proteção. |
| BANLOOKUP-01 / P2 condicional | `src/ban.cpp`, consultas de conta/IP/namelock; callers em ambos os protocolos | `Database::storeQuery` retorna `nullptr` tanto para zero linhas quanto para falha. Os helpers anteriores tratavam ambos como ausência de banimento. Uma falha da tabela de banimentos com contas/personagens legíveis podia liberar uma entrada proibida. | Resultado explícito `Clear`, `Banned`, `Error`, usando o indicador de sucesso da consulta. Em `Error`, o login recebe indisponibilidade temporária. Teste do código verdadeiro de consulta com uma interface de banco simulada passou no CI; não simula falha real de MariaDB. | Corrigir erros do banco continua necessário. A indisponibilidade de uma consulta de autorização agora recusa acesso; não passa a representar usuário liberado nem banimento permanente. |
| LOGINPARSE-01 / P3 | `src/protocollogin.cpp`, `onRecvFirstMessage` | O parser da lista de personagens não verificava o cursor final antes de enfileirar autenticação. O buffer admite folga para outros formatos, mas o primeiro pacote já possui comprimento absoluto, exigindo validação estrita desse limite. Não foi demonstrado bypass de credenciais ou crash por este caminho. | Checagem de overrun e cursor antes do dispatch, correspondente ao primeiro pacote do jogo. Regressão nativa passou, incluindo consumo além do comprimento declarado e trailer OTCv8. | A correção não substitui a auditoria individual de todos os campos/opcodes. O formato e o padding legítimos são preservados. |
| UPD-02 / P2 | `deploy/launcher/AntigasLauncher/UpdateApplyForm.cs`, `ApplyAsync` / fechamento da janela | Fechar a janela enquanto `Task.Run` troca arquivos encerra o message loop e pode terminar o processo antes do catch que faria rollback. A lista de alterações existe somente em memória. | `OnFormClosing` cancela o fechamento enquanto validação/aplicação/rollback está pendente e o libera quando termina. O harness `LauncherFormLifecycle` invoca métodos reais sem mostrar janela nem iniciar cliente; passou. O mesmo harness falha com a fonte anterior. Build Release normal passou sem avisos/erros. | Encerramento forçado e perda de energia ainda exigem journal persistente/recuperação após reinício. O harness não simula perda de energia nem certifica todos os caminhos de interface. |
| LUALIFE-01 / P2 | `src/luascript.cpp`, construtor/init/close; `src/raids.cpp`, construção global | Ao tornar UBSan bloqueante, cinco testes de core acusaram chamada de membro com vptr inválido: `Game` constrói `Raids` antes do `LuaEnvironment` de outro translation unit. O teardown também podia ler um ambiente global já destruído. | Guarda de lifetime com inicialização constante; Raids inicializa a interface no carregamento, após os globais. Regressão real de load/clear/reload/Lua e teardown passou no CI, inclusive UBSan bloqueante. | Não foi demonstrado gatilho remoto. A guarda protege a existência do ambiente; não modifica regras de raids nem resolve todos os riscos de reload/Lua. |

Esta rodada encontrou quatro problemas P2 e um P3 acima. Não confirmou problema
novo P0/P1. Esse recorte não é uma contagem final de todo o projeto. As mudanças
de autorização não modificam senha, protocolo, schema, combate, loot ou regras
de economia; recusam caminhos inválidos ou indisponíveis.

## Revisão independente de rede e tarefas

A revisão do código atual de `f4fa832` não confirmou problema novo na reserva ou
liberação de admissão/saída. Há um accept pendente por porta; o protocolo só é
criado depois da admissão. A liberação do slot é idempotente. O fechamento
forçado retém o buffer de `async_write` até seu callback, enquanto descartes e
destrutor devolvem as reservas restantes. Essa é evidência de revisão de fonte,
não um novo ensaio de rede.

`CRASH-01` permanece: as threads de dispatcher e banco não capturam exceções
C++ de uma tarefa. Não foi encontrado gatilho remoto determinístico novo.
`BehaviourDatabase::searchDigit` captura as exceções de `substr`/`stoi`; os
callers de `vectorAtoi` recebem XML local. `LootTracker::publish` insere a chave
antes do `.at`, sem callback intermediário. Erros comuns de Lua passam por
`lua_pcall`. Continuar depois de uma exceção arbitrária pode usar mundo ou
transação parcialmente alterados; não foi adicionado catch que esconda essa
condição. Uma regressão integrada de encerramento por exceção foi implementada:
o driver exige o término do processo de teste pela exceção exata da fixture,
com status 86, dois marcadores e nenhuma execução da tarefa já enfileirada
depois dela. A execução nativa passou no CI; o terminate handler existe somente
no teste, não modifica o comportamento do servidor.

As filas de entrada do dispatcher e de tarefas SQL ainda não têm teto de
tarefas/bytes. O opcode `0x32` pode copiar uma string do cliente para uma tarefa
sem expiração. Se o dispatcher ficar lento enquanto o I/O continua ativo, os
limites de sockets e saída não limitam esse backlog. Não foi demonstrado um
pacote que cause travamento infinito nem um limiar real de saturação. O limite
seguro exige distinguir trabalho remoto de tarefas internas, retornar rejeição
ao cliente e preservar gravação/limpeza; descartar tarefas indiscriminadamente
seria uma alteração de integridade. O `new_handler` atual encerra o processo em
falta de memória; capturar `bad_alloc` apenas no dispatcher não elimina isso.

## Persistência e autenticação que exigem trabalho separado

- O SHA-1 de `AUTH-01` continua inadequado após vazamento do banco. A revisão
  estática de `src/protocol.cpp:137-144`, `src/protocollogin.cpp:168-174`,
  `src/protocolgame.cpp:302-304` e `src/networkmessage.cpp:27-38` confirma que,
  após RSA, o servidor lê a senha como string prefixada por comprimento e recebe
  seus bytes antes de aplicar hash. Não confirma a codificação/bytes produzidos
  pela implementação do cliente: o código-fonte dessa implementação não está
  versionado neste checkout. Portanto, não há evidência para afirmar que o
  cliente envia SHA-1 nem que seus bytes foram inspecionados.
- `src/iologindata.cpp:54-65` confere `transformToSHA1(password)` no loginserver;
  `:88-99` faz o mesmo no gameworld. Nesse segundo caminho a autenticação de
  conta também chama `loginserverAuthentication`, repetindo a conferência. A
  transformação em `src/tools.cpp:123-187` produz 40 caracteres hexadecimais
  minúsculos, sem salt ou marcador de versão. O site repete o formato ao criar
  conta (`deploy/site-public/index.php:29-30`), autenticar e alterar senha
  (`deploy/site-public/account.php:27-40`).
- O checkout não contém o DDL/schema versionado da tabela `accounts`; `data/sql`
  contém apenas migrações do Market. Também não estão disponíveis o código do
  cliente nem a biblioteca privada `security.php` usada pelo site. Assim, tipo,
  largura, collation, constraints e demais leitores/escritores do campo não
  foram confirmados. Não foram lidos dados, configurações ou credenciais.
- Migração proposta, ainda sem implementação: (1) obter/revisar schema e todos
  os leitores, escritores e procedimento de restore; (2) escolher um hash
  resistente a tentativa offline e um formato explicitamente versionado, com
  capacidade suficiente no campo; (3) atualizar servidor e site para ler o
  legado e o novo formato, autenticar contra os bytes recebidos e rehashar após
  autenticação válida ou troca de senha; (4) habilitar gravação do novo formato
  somente quando todos os nós que autenticam/escrevem suportarem ambos, pois
  binários antigos só aceitam SHA-1; (5) documentar backup e rollback antes de
  substituir hashes legados.
- Antes de aprovar a migração, adicionar testes focados para loginserver,
  gameworld, registro, login e alteração de senha; hashes legados/novos;
  rehash concorrente e troca de senha; senha ASCII e não ASCII com a mesma
  codificação no cliente e no site; limites/rejeições e falha de banco; e
  compatibilidade durante implantação/rollback. Esses testes não foram
  executados nesta revisão documental. Nenhuma alteração de autenticação ou
  schema foi feita.
- O charset do cliente MySQL ainda não é explicitamente configurado no core.
  Strings SQL manuais e permissões/schema precisam de revisão antes de mudar
  encoding ou migrar as chamadas para parâmetros. Nenhuma injeção explorável
  foi confirmada nesta rodada.
- A thread I/O chama consultas de login usando a conexão criada pelo dispatcher,
  sem inicialização MySQL de thread explícita própria. A correção anterior
  `DBTHREAD-01` cobre apenas o worker SQL. O impacto depende da biblioteca
  efetivamente linkada; requer revisão antes de afirmar crash. Também falta um
  contador de tentativas de senha por conta: o limitador atual é por conexão/IP.
- Há um candidato de integridade fora do Market: o logout libera o personagem
  após três tentativas imediatas de save falharem. Uma transferência entre dois
  jogadores existe em memória antes dos saves independentes; com falha no save
  de um participante e sucesso posterior do outro, os snapshots podem divergir.
  O impacto de duplicação exige reprodução isolada com dois personagens e
  falha de banco controlada; não é tratado aqui como exploit confirmado. O
  checkpoint/recibo do Market não prova durabilidade de trades legados.
- O site visível contém controles de CSRF, escaping de HTML, consultas
  parametrizadas e filtro de proprietário de pedido. A autenticação efetiva,
  rate limiter e validação de preço/proprietário/idempotência de Pix dependem de
  `security.php` / `pix.php`, externos ao checkout; não foram inspecionados nesta
  rodada. A fonte visível não prova a configuração desses componentes privados.

## Retomada — lint de scripts e AUTH-01 (30/09/2026)

- A PR3 de ShellCheck/actionlint foi incorporada à `main` no merge
  [`47bdb553`](https://github.com/djowww/antigas-tfs/commit/47bdb553ee61f193d1c48ddb6ea62e06626234c7).
  A validação focada registrada para essa mudança usou ShellCheck 0.11.0 e
  actionlint 1.7.12, com arquivos oficiais fixados por SHA-256: ShellCheck
  passou sem diagnósticos nos três scripts `.sh`; actionlint passou nos cinco
  workflows. Não havia baseline de avisos. Este registro é evidência da
  validação da PR3, não uma execução dos checks hospedados neste commit.
- CodeQL permanece falho externamente: o
  [run da entrega v54](https://github.com/djowww/antigas-tfs/actions/runs/36672814245) não publicou
  resultados porque code scanning estava indisponível/desativado para o
  repositório privado. Isso não é aprovação de CodeQL nem foi contornado por
  mudanças locais de permissões/configuração. Cppcheck continua sendo análise
  complementar, não equivalente.
- A revisão AUTH-01 acima é somente de fonte/schema versionados. Nenhum teste
  geral ou de autenticação foi reexecutado nesta retomada; não houve acesso a
  produção, VPS, banco, configurações ou segredos, nem alteração de auth/schema.

## Retomada — checks hospedados e persistência de trade (30/09/2026)

- A PR4 foi incorporada à `main` em `8c7df0a3777a11ca3f912bbf74897c1d35784597`.
  Seus checks de [ShellCheck/actionlint](https://github.com/djowww/antigas-tfs/actions/runs/36726026488),
  [Cppcheck](https://github.com/djowww/antigas-tfs/actions/runs/36726026257),
  [secrets](https://github.com/djowww/antigas-tfs/actions/runs/36726026620) e
  [builds/regressões](https://github.com/djowww/antigas-tfs/actions/runs/36726026402)
  concluíram com sucesso. O [CodeQL](https://github.com/djowww/antigas-tfs/actions/runs/36726026619)
  terminou com falha nos jobs C++ e C#; o log informa que code scanning não está
  habilitado para este repositório. Isso continua sendo uma indisponibilidade
  externa, não um resultado limpo do CodeQL.
- A revisão de fonte de `Game::playerAcceptTrade` (`src/game.cpp:2533-2633`)
  confirmou que os dois movimentos terminam em memória e não são gravados ali.
  Logout remove o personagem em `src/protocolgame.cpp:239-274`; cada remoção
  chama `Player::onRemoveCreature` (`src/player.cpp:1150-1195`), que tenta salvar
  aquele personagem até três vezes. `IOLoginData::savePlayer`
  (`src/iologindata.cpp:641-907`) abre uma transação por personagem. Portanto,
  uma queda entre os dois saves, ou a falha persistente de um deles, pode deixar
  apenas um lado do trade no banco: item perdido ou duplicado após recuperação.
- Classificação atual: lacuna condicional de integridade confirmada por revisão
  estática; não há reprodução operacional nem evidência de gatilho remoto. O
  teste de carga de shutdown cobre logout gracioso, não trade combinado com
  falha de banco. Nenhum código foi alterado nesta revisão.
- Direção de correção para avaliação: salvar os dois snapshots dentro de uma
  transação estrita compartilhada no momento do trade e isolar ambos os
  personagens se qualquer save ou o resultado do commit for incerto. Antes de
  alterar gameplay, criar teste isolado de dois personagens que valide a troca
  após restart, falha no segundo save com rollback e commit de resultado
  ambíguo. Sem esse teste de falha de banco, o custo de I/O adicional e a
  recuperação de inventário não estão suficientemente verificados para uma
  mudança segura.

## Retomada — autorização de comandos administrativos (30/09/2026)

- Revisão somente de fonte das talkactions ativas em
  `data/talkactions/talkactions.xml`: não há bypass concreto confirmado neste
  escopo. O despacho central em `src/talkaction.cpp:103` restringe comandos
  `!` a grupos com acesso; as ações `/` dependem das guardas em seus scripts
  Lua. As entradas administrativas examinadas usam acesso de grupo, flag de
  broadcast ou tipo de conta conforme a ação.
- O XML não declara flags `access`/`group`, e
  `TalkAction::configureEvent` (`src/talkaction.cpp:117-131`) só interpreta
  `words` e `separator`. Portanto, flags de autorização adicionadas ao XML
  seriam ignoradas: uma futura ação `/` sem guarda Lua poderia ficar exposta.
  Isso é uma fragilidade de manutenção, não uma falha explorável demonstrada
  na configuração versionada atual.
- Os comandos nativos `/reload` e `/raid` exigem grupo e tipo de conta em
  `src/commands.cpp:143-171`; seus níveis estão definidos em
  `data/XML/commands.xml:3-4`. Os nomes aceitos por `/reload` são uma lista
  fixa (`commands.cpp:203-265`), sem caminho de arquivo controlado pelo jogador.
  Não foi encontrado harness de negação equivalente nem foram executados
  testes nesta revisão.
- Regressão recomendada: executar o despacho real com jogador comum e provar
  que `/ban`, `/reload talk` e `/raid` não produzem efeitos; confirmar que os
  níveis autorizados funcionam; e validar em CI que cada ação `/` tenha um
  campo central reconhecido ou uma guarda script-side auditada. Nenhum código
  foi alterado.

## Cobertura do pedido original

Os estados abaixo distinguem evidência já registrada de requisito ainda sem
prova suficiente. Os documentos de validação são históricos: uma mudança no
caminho testado exige nova execução. Os testes executados desta branch estão registrados na
[entrega v54](security-auth-v54-delivery-2026-09-30.md), com seus limites.

| Fase | Evidência disponível | Trabalho ainda necessário |
|---|---|---|
| 1 Inventário / arquitetura | Mapa em `SECURITY_AUDIT.md`, CMake e inventário de superfícies | Atualizar inventário de componentes externos quando forem acessíveis. |
| 2 Crashes / memória | Correções de parser, include, ambientes Lua, scheduler, callbacks/reset; análise Cppcheck | Rastreabilidade de todos os callbacks/ownership e candidatos restantes; CRASH-01 continua residual. |
| 3 Sanitizers | Builds separados ASan+UBSan e TSan, CTest no CI | Os alvos não cobrem a partida inteira; ampliar cenários sem confundir build instrumentada com runtime coberto. |
| 4 Análise C++ | Cppcheck com 73 unidades, baseline revisada, gate de análise completa | Diagnósticos `NEEDS_INVESTIGATION` restantes; dependências não têm cobertura semântica completa. |
| 5 Lua | Syntax de todos os scripts, parser de lamp, inventário/economia e regressões de lifecycle | Lint semântico compatível, mapa de storage/eventos e fechamento da revisão individual de todos os scripts. |
| 6 Banco / queries | Revisão, timeout/recuperação, transações/recibos de Market e quoting de identificador | Charset, parametrização incremental, permissões/schema atuais e durabilidade de sistemas legados. |
| 7 Cada opcode | Guard de cursor, walking, limites e inventário de 69 casos em `protocol-opcode-audit-2026-09-30.md` | Fechar validação individual dos campos e testes de comportamento fora de ordem; inventário não é cobertura dinâmica integral. |
| 8 Fuzzing | libFuzzer ASan+UBSan de NetworkMessage/walking, corpus preservado em falha | Login, deserializadores, XML/config e bindings Lua ainda sem targets equivalentes. |
| 9 DoS / limites | Adm. global/IP, tentativas/status com expiração e orçamento de saída | Backpressure de entrada e medição de ações caras; não rejeitar saves/cleanup por um teto indiscriminado. |
| 10 Stress / soak | Carga atual de 50 sessões/30 s; teste histórico de Market com 100 sessões | Soak prolongado, centenas de sessões de gameplay e comparação de RAM após desconexão. |
| 11 Performance | Amostras CPU/RSS em staging; latências históricas de Market | Profiling dos hot paths e comparação atual antes/depois com latência/queries, sem micro-otimização por palpite. |
| 12 Organização de scripts | Módulos e documentação existentes; mudanças focadas | Inventário de duplicação/storage/lifecycle antes de refatoração; não mover regras de gameplay sem teste. |
| 13 Secrets | Gitleaks no checkout/histórico e CI, configurações privadas ignoradas | Revalidar custódia externa de credenciais/chaves; scan do repo não cobre outros clones/host. |
| 14 Dependências / CVEs | Dependabot Actions/NuGet; alerts e security updates ativados e verificados por API; dependências CMake identificadas | Inventário de versões reais de sistema/vendorizadas, scan de advisories e SBOM ainda faltam. |
| 15 CodeQL / alternativa | Queries C#/C++ executadas; upload recusado pelo plano/settings; Cppcheck e Gitleaks ativos | Ativação externa de Code Security para publicar CodeQL; continuar a análise alternativa. |
| 16 Actions | Permissões mínimas, SHA de Actions, matriz de build/testes | Builds, análise C++ e secrets passaram nesta branch; CodeQL externo falhou. Registrar os checks do merge sem presumir aprovação. |
| 17 Proteção da main | APIs de protection/rulesets recusaram o recurso para o plano do repositório privado (HTTP 403) | Quando disponível, exigir PR, builds/checks aprovados e impedir force push/delete. O processo de PR pode ser seguido agora, mas a API confirmou que o enforcement nativo exige mudança externa de plano. |
| 18 Pipeline | Build, testes, fuzz smoke, secret scan, Cppcheck, parsing PHP/Lua/Python | Lint Lua/ShellCheck e dependency scan ainda não equivalem a simples parsing. |
| 19 Hardening binário | Release hardened Ubuntu 22.04 testada/deployada, flags compatíveis | Artefato novo validado no CI, staging e produção por hash, conforme entrega v54; produção usa Release hardened sem sanitizadores. |
| 20 Warnings | Builds e baseline Cppcheck; launcher TreatWarningsAsErrors | Baseline de warnings C++ ampliados e revisão dos diagnósticos .NET exploratórios. |
| 21 Sistema operacional | Serviço dedicado e hardening validado; capabilities zeradas | Observação atual em `host-security-observation-2026-09-30.md`; login root por senha ainda habilitado, revisão integral e mudanças seguras pendentes. |
| 22 Firewall / exposição | Portas 7173/7174 e site verificadas; isolamento do staging | Host atual confirma MariaDB loopback e UFW; revisar ranges Cloudflare e permissões globais SQL, com rollback antes de mudar. |
| 23 Logs | Startup/shutdown/banco/Lua/rede documentados sem conteúdo de credenciais | Diagnóstico de exceção C++ e rate limiting de logs acionáveis remotamente. |
| 24 Observabilidade | Coleta leve CPU/RSS e serviço ativo em testes | Tick, percentis, latência SQL, backlog, conexões e contador de erros Lua ainda não têm cobertura completa. |
| 25 Shutdown / recovery | Ordem de scheduler/DB/dispatcher/sockets corrigida; recuperação independente staging | Shutdown com 50 sessões ainda conectadas passou na entrega v54; isso não comprova todos os sistemas nem falhas de save. |
| 26 Falha do banco | Testes históricos isolados de Market e recuperação documentados | Repetir contra código atual e expandir falhas para gameplay/saves e autorização; fixtures de lookup não substituem MariaDB real. |
| 27 Startup automático | Runner de staging confirma serviço/listeners e operação mínima, depois recuperação | Smoke completo com DB de teste e runtime ASan/UBSan/shutdown/exit verificados automaticamente. |
| 28 Regressões | Bugs corrigidos possuem alvos nativos/Lua/Python no CI | Registrar limites dos testes de fonte antigos; novos testes devem executar comportamento real. |
| 29 Fronteiras de entrada | Rede, JSON/ZIP, SQL/HTML, path, XML e Lua revistos por caminhos | Allowlist e limites ainda precisam de mapa completo por fronteira, inclusive configurações/admin. |
| 30 Crash handling | Política fail-fast identificada; systemd documentado | Ensaio de diagnóstico, build/SHA/thread/stack trace e core utilizável; teste fixture não altera diagnóstico de produção. |
| 31 Backup / restore | Backups e artefatos anteriores retidos; sem restore em produção | Procedimento e restauração integral isolada com conferência de schema/dados/arquivos ainda não comprovados. |
| 32 Economia / duplicação | Market idempotente/concorrente e raridade persistente testados | Trade, rewards/quests e falha no save dos dois lados exigem testes próprios. |
| 33 Comandos admin | Autorização de comandos e caminhos de logs revistos | Matriz final de papéis/talkactions/reloads e testes server-side de negação. |
| 34 Documentação / entrega | Auditoria, hardening, addenda e relatórios atuais | Totais/tabela final e conclusão só após reunir a evidência que falta acima; preservar riscos residuais explícitos. |

## Estado atual de verificação

O CI do baseline `465ccf4` foi consultado nesta rodada: build/regressões,
Cppcheck e secret scan concluíram com sucesso. O run CodeQL concluiu com falha;
o resultado não é contado como aprovação. Os runs relevantes são
[build/regressões](https://github.com/djowww/antigas-tfs/actions/runs/36666883768),
[Cppcheck](https://github.com/djowww/antigas-tfs/actions/runs/36666883749),
[secret scan](https://github.com/djowww/antigas-tfs/actions/runs/36666883715) e
[CodeQL](https://github.com/djowww/antigas-tfs/actions/runs/36666883716).

Os resultados atuais estão na [entrega v54](security-auth-v54-delivery-2026-09-30.md):
19/19 testes nativos nas quatro variantes, sete jobs aprovados, Cppcheck e
secret scan aprovados em `217e85b`; CodeQL falhou por disponibilidade externa.
O binário aprovado passou em staging com 50 sessões antes da publicação e
reinício de produção. Windows executou os harnesses .NET; core/Linux rodou no
CI. Nenhum probe destrutivo, fuzzing ou falha de banco desta rodada foi
executado contra produção.

## Configurações de segurança do GitHub verificadas nesta rodada

A API confirmou que o repositório continua privado e que a autorização tem
permissão administrativa. As consultas de proteção da `main` e rulesets
retornaram HTTP 403 com a mensagem de exigir GitHub Pro ou um repositório
público; não houve contratação nem mudança de visibilidade. Essa limitação
difere da disponibilidade do CodeQL e deve ser acompanhada separadamente.

Dependabot alerts estavam desativados (GET retornava 404). Foram ativados os
alerts/dependency graph e os security updates. Ambos os PUT retornaram 204.
A leitura posterior confirmou alerts ativos (204) e security updates
`enabled=true`, `paused=false`. A configuração mensal de atualizações de
Actions/NuGet permanece no repositório. A ativação não prova ausência de CVEs,
nem cobre automaticamente bibliotecas instaladas por apt ou código sem
manifesto. Referências: [configuração de alerts](https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/configure-dependabot-alerts)
e [endpoints oficiais de repositório](https://docs.github.com/en/rest/repos/repos#enable-vulnerability-alerts).

## Rodada intermediária preservada

O CI `36670481654` de `1cbe884` aprovou Release, Release hardened, TSan,
Windows, regressões PHP/Lua/Python e fuzz smoke. ASan/UBSan falhou em cinco
testes de core quando `UBSAN_OPTIONS=halt_on_error=1` passou a ser exigido.
O diagnóstico de vptr inválido em `LuaScriptInterface` revelou LUALIFE-01.
Essa execução não é aprovação completa, e seu binário não foi promovido.
A primeira tentativa `36669612392` falhou ao compilar a fixture de login,
que tentava herdar de `Player final`; foi corrigida sem retirar `final`.
Também foram corrigidos a associação do protocolo na conexão simulada e o
timeout que podia liberar capturas de stack com callbacks ainda pendentes.

A candidata assinada v54 passou nos sete controles do harness de integração
Windows contra manifesto de staging HTTPS: assinatura/hash, adulteração,
traversal, adulteração após extração, instalação limpa/userdata e rollback
após falha injetada. O bundle contém o launcher corrigido; o Update ZIP o
omite, como nas versões anteriores. Não houve inspeção visual de janelas.

O CI `36671968916` de `a13c3b4` aprovou os sete jobs, com 19/19 testes
nativos em cada build, inclusive ASan/UBSan bloqueante e TSan. O Cppcheck
`36671969092` completou 73 unidades e reteve 47 diagnósticos, mas seu gate
falhou porque a mensagem do diagnóstico legado `virtualCallInConstructor` de
`LuaScriptInterface::~LuaScriptInterface` mudou de linha 253 para 259. A chamada
é a mesma; a baseline foi revisada para a nova linha e hash da fonte, mantendo
`NEEDS_INVESTIGATION` e a saída visível. Não foi adicionado suppress nem
retirado um diagnóstico. O teste de lifetime passou com UBSan bloqueante.
