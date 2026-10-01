# Continuação da auditoria de segurança — 30/09/2026

Este documento reúne rodadas iniciadas a partir de `main` em `465ccf4` e
continuações em branches de revisão. No checkpoint atual, o worktree está na
branch `security-central-talkaction-auth-20260930`, em `62970d9`; há alterações
locais ainda não commitadas na ação de lâmpadas e seus bindings/testes, no
downloader/harness do launcher, no escape SQL e seus chamadores/testes, na
proteção do `/ipban` e seus testes, e neste relatório. Os testes citados para
cada correção correspondem ao checkpoint explicitado em sua seção; eles não
substituem build completo ou validação em staging.

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

`CRASH-01` permanece como risco de disponibilidade: exceções ainda escapam das
threads de dispatcher e banco e terminam o processo. Os pontos de entrada agora
capturam apenas para emitir um diagnóstico fatal limitado e imediatamente
relançam; não continuam filas nem escondem falhas. Não foi encontrado gatilho
remoto determinístico novo.
`BehaviourDatabase::searchDigit` captura as exceções de `substr`/`stoi`; os
callers de `vectorAtoi` recebem XML local. `LootTracker::publish` insere a chave
antes do `.at`, sem callback intermediário. Erros comuns de Lua passam por
`lua_pcall`. Continuar depois de uma exceção arbitrária pode usar mundo ou
transação parcialmente alterados, então o comportamento fail-fast é preservado.
A regressão integrada exige o término do processo de teste pela exceção exata da
fixture, com status 86, os dois marcadores de stdout, o diagnóstico sanitizado
esperado em stderr e nenhuma execução da tarefa já enfileirada depois dela. O
checkpoint anterior passou no CI; a expectativa stderr e o formatador foram
ampliados nesta retomada e ainda aguardam execução integrada. O terminate
handler existe somente no teste.

As filas de entrada do dispatcher e de tarefas SQL ainda não têm teto de
tarefas/bytes. O opcode `0x32` pode copiar uma string do cliente para uma tarefa
sem expiração. Se o dispatcher ficar lento enquanto o I/O continua ativo, os
limites de sockets e saída não limitam esse backlog. Não foi demonstrado um
pacote que cause travamento infinito nem um limiar real de saturação. O limite
seguro exige distinguir trabalho remoto de tarefas internas, retornar rejeição
ao cliente e preservar gravação/limpeza; descartar tarefas indiscriminadamente
seria uma alteração de integridade. O `new_handler` atual encerra o processo em
falta de memória; capturar `bad_alloc` apenas no dispatcher não elimina isso.

A revisão específica da fila SQL confirmou um único worker FIFO e nenhuma
admissão limitada em `DatabaseTasks::addTask`. O caminho Lua mais próximo de
jogadores é `PlayerDeath`, registrado no login: ao exceder o histórico de mortes,
ele enfileira um `DELETE`; em certas mortes durante guerra de guildas, enfileira
também um `INSERT`. Não encontrei um caminho de cliente que forneça SQL arbitrário:
os demais produtores encontrados são limpezas de startup, `/unban` privilegiado
e manutenção de bans expirados. A chamada de morte faz consultas síncronas antes
dessas inserções na fila; portanto, a alcançabilidade do produtor não prova que
ele consiga superar a vazão do worker nem demonstra saturação. A telemetria
`[QueueMetrics]` registra contagem e pico da fila e bytes das strings SQL a cada
60 segundos. Agora também registra totais cumulativos de entradas e saídas,
permitindo estimar taxas pelas diferenças entre amostras, e a idade monotônica
da tarefa SQL pendente mais antiga. Para tarefas SQL concluídas, mede o tempo
desde antes da chamada à API do banco até seu retorno; isso inclui espera pelo
mutex compartilhado e execução no driver. Uma consulta ainda em andamento não
aparece nessa duração até retornar, e já foi removida da fila pendente. Ainda não
há estimativa de memória total; Dispatcher e Scheduler também não expõem idade.
Não há limite/backpressure ativo; sem staging não escolho um teto que possa
descartar persistência ou limpeza.

Evidência adicional no ciclo de leitura: `Connection::parsePacket` chama
`Protocol::onRecvMessage` e agenda a próxima leitura sem observar a contagem da
fila do dispatcher. `ProtocolGame::addGameTask` cria tarefas sem expiração, e a
maioria das tarefas não declara bytes capturados para as métricas. A amostra
local ignorada de `config.lua` (não produção) configura 2.256 conexões e 50
pacotes por segundo por conexão: um teto teórico de entrada de 112.800 pacotes
por segundo se todas as conexões estiverem ocupadas. Isso não é medida de
throughput nem comprova que todos os pacotes criem tarefas. Sem carga de staging
e sem semântica de backpressure/rejeição, mantenho a fila como risco de
disponibilidade residual em vez de introduzir um limite que possa perder
operações internas ou persistência.

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

## Retomada — autenticação e tentativas distribuídas (30/09/2026)

- `ServicePort::onAccept` aplica o limitador de tentativas por IP antes de
  aceitar a conexão (`src/server.cpp:142-158`, `src/ban.cpp:26-29`). A janela
  mantém estado limitado a 65.536 IPs e penaliza conexões rápidas. Há também
  limites de conexões simultâneas globais e por IP (`src/connectionadmission.h:42-88`;
  padrão por IP 128). Esses controles não contam senha incorreta e podem ser
  distribuídos por várias origens.
- No loginserver, `ProtocolLogin::getCharacterList` chama
  `IOLoginData::loginserverAuthentication` e contabiliza o resultado
  (`src/protocollogin.cpp:64-85`). O login direto ao gameworld passa por
  `gameworldAuthentication` e, depois, `loginserverAuthentication`
  (`src/protocolgame.cpp:353-387`). As decisões agora distinguem sucesso,
  credenciais inválidas, personagem inválido e erro do banco
  (`src/authentication.cpp`, `src/iologindata.cpp`). A resposta pública para
  credenciais inválidas, conta ausente e personagem inválido é genérica; erro
  do banco continua informando indisponibilidade temporária.
- `AccountAuthenticationFailureLimiter` mantém no máximo 65.536 contas em LRU,
  expira entradas após 10 minutos, incrementa somente `InvalidCredentials`, e
  limpa a sequência após sucesso. As duas primeiras falhas são imediatas; as
  seguintes atrasam a resposta em passos de 250 ms até 2 segundos. A conta zero,
  personagem inválido e erro SQL não criam nem avançam estado. O protocolo agenda
  a resposta pelo scheduler e retorna sem bloquear o dispatcher; se o scheduler
  não aceitar o evento, envia a falha imediatamente. A tarefa captura uma
  referência compartilhada ao protocolo e verifica se a referência fraca à
  conexão ainda aponta para um objeto antes de enviar. Se o socket já estiver
  fechado, `Connection::send` ignora a mensagem. O atraso agendado é de até 2
  segundos, acrescido de eventual espera na fila do dispatcher.
- Limite confirmado: a autenticação e as consultas SQL ocorrem antes de calcular
  o atraso. Portanto, isto atrasa respostas de tentativas sequenciais por conta,
  mas não limita consultas ao banco, não serializa tentativas concorrentes e não
  impede que várias origens distribuídas consultem a mesma conta. O estado LRU
  também pode ser desalojado quando a tabela atinge a capacidade; isso mantém a
  memória limitada, mas reinicia a progressão daquela conta. Não há lockout
  permanente nem evidência de bypass de senha; ainda falta medir carga e definir
  se uma camada anterior à consulta é necessária sem criar enumeração ou falsos
  positivos.
- `tests/authentication-decision-tests.cpp` cobre estados de autenticação,
  progressão, expiração, capacidade, sucesso, erros não penalizados e
  concorrência. Esses testes não exercitam a integração real scheduler/protocolo
  nem uma conexão MariaDB. A suíte Python do workflow foi executada nesta
  retomada: 63 testes passaram. Também passaram os testes de segurança do
  launcher e do lifecycle do formulário; os projetos LauncherIntegration,
  AntigasLauncher e ReleaseSigner compilaram em Release sem avisos ou erros.
  O build C++ completo continua bloqueado pela ausência de CMake e dependências
  do servidor neste ambiente. Nenhum staging, banco real ou produção foi usado.

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
| 6 Banco / queries | Revisão, timeout/recuperação, transações/recibos de Market e quoting de identificador; falha SQL no tipo de conta não é propagada às sessões | Charset, parametrização incremental, permissões/schema atuais, durabilidade de sistemas legados e caso raro de UPDATE sem linha afetada sob remoção concorrente da conta. |
| 7 Cada opcode | Guard de cursor, walking, limites e inventário de 69 casos em `protocol-opcode-audit-2026-09-30.md` | Fechar validação individual dos campos e testes de comportamento fora de ordem; inventário não é cobertura dinâmica integral. |
| 8 Fuzzing | libFuzzer ASan+UBSan de NetworkMessage/walking, corpus preservado em falha | Login, deserializadores, XML/config e bindings Lua ainda sem targets equivalentes. |
| 9 DoS / limites | Adm. global/IP, tentativas/status com expiração, orçamento de saída e snapshots periódicos de filas | Calibrar backpressure de entrada e limites de ações caras em staging; não rejeitar saves/cleanup por um teto indiscriminado. |
| 10 Stress / soak | Carga atual de 50 sessões/30 s; teste histórico de Market com 100 sessões | Soak prolongado, centenas de sessões de gameplay e comparação de RAM após desconexão. |
| 11 Performance | Amostras CPU/RSS em staging; latências históricas de Market; contagens/picos e bytes explicitamente rastreados das filas | Profiling dos hot paths e comparação atual antes/depois com latência/queries; os bytes de fila não são RAM total e não substituem staging. |
| 12 Organização de scripts | Módulos e documentação existentes; mudanças focadas | Inventário de duplicação/storage/lifecycle antes de refatoração; não mover regras de gameplay sem teste. |
| 13 Secrets | Gitleaks no checkout/histórico e CI, configurações privadas ignoradas | Revalidar custódia externa de credenciais/chaves; scan do repo não cobre outros clones/host. |
| 14 Dependências / CVEs | Dependabot Actions/NuGet; alerts e security updates ativados; cinco projetos .NET escaneados contra advisories NuGet, sem pacote vulnerável | Inventário de versões reais de sistema/vendorizadas, scan de advisories C++/SO e SBOM ainda faltam. |
| 15 CodeQL / alternativa | Queries C#/C++ executadas; upload recusado pelo plano/settings; Cppcheck e Gitleaks ativos | Ativação externa de Code Security para publicar CodeQL; continuar a análise alternativa. |
| 16 Actions | Permissões mínimas, SHA de Actions, matriz de build/testes | Builds, análise C++ e secrets passaram nesta branch; CodeQL externo falhou. Registrar os checks do merge sem presumir aprovação. |
| 17 Proteção da main | APIs de protection/rulesets recusaram o recurso para o plano do repositório privado (HTTP 403) | Quando disponível, exigir PR, builds/checks aprovados e impedir force push/delete. O processo de PR pode ser seguido agora, mas a API confirmou que o enforcement nativo exige mudança externa de plano. |
| 18 Pipeline | Build, testes, fuzz smoke, secret scan, Cppcheck, parsing PHP/Lua/Python, Actionlint e ShellCheck | Lint semântico Lua e dependency scan ainda não equivalem a simples parsing. |
| 19 Hardening binário | Release hardened Ubuntu 22.04 testada/deployada, flags compatíveis | Artefato novo validado no CI, staging e produção por hash, conforme entrega v54; produção usa Release hardened sem sanitizadores. |
| 20 Warnings | Builds e baseline Cppcheck; launcher TreatWarningsAsErrors | Baseline de warnings C++ ampliados e revisão dos diagnósticos .NET exploratórios. |
| 21 Sistema operacional | Serviço dedicado e hardening validado; capabilities zeradas | Observação atual em `host-security-observation-2026-09-30.md`; login root por senha ainda habilitado, revisão integral e mudanças seguras pendentes. |
| 22 Firewall / exposição | Portas 7173/7174 e site verificadas; isolamento do staging; lista versionada de Cloudflare comparada às fontes oficiais atuais e idêntica | Ainda falta reler a configuração efetivamente instalada no host e comprovar permissões globais SQL; mudanças remotas exigem rollback verificado. |
| 23 Logs | Startup/shutdown/banco/Lua/rede documentados sem conteúdo de credenciais; os dois workers agora emitem diagnóstico fatal limitado e sanitizado antes do fail-fast | Rate limiting de logs acionáveis remotamente; confirmação de persistência/rotação dos logs em produção. |
| 24 Observabilidade | Coleta leve CPU/RSS, serviço ativo em testes e log de 60 s com contagem/picos das filas e bytes explicitamente rastreados | Tick, percentis, latência SQL, backlog por idade, conexões e contador de erros Lua ainda não têm cobertura completa. |
| 25 Shutdown / recovery | Ordem de scheduler/DB/dispatcher/sockets corrigida; recuperação independente staging | Shutdown com 50 sessões ainda conectadas passou na entrega v54; isso não comprova todos os sistemas nem falhas de save. |
| 26 Falha do banco | Testes históricos isolados de Market e recuperação documentados | Repetir contra código atual e expandir falhas para gameplay/saves e autorização; fixtures de lookup não substituem MariaDB real. |
| 27 Startup automático | Runner de staging confirma serviço/listeners e operação mínima, depois recuperação | Smoke completo com DB de teste e runtime ASan/UBSan/shutdown/exit verificados automaticamente. |
| 28 Regressões | Bugs corrigidos possuem alvos nativos/Lua/Python no CI | Registrar limites dos testes de fonte antigos; novos testes devem executar comportamento real. |
| 29 Fronteiras de entrada | Rede, JSON/ZIP, SQL/HTML, path, XML e Lua revistos por caminhos | Allowlist e limites ainda precisam de mapa completo por fronteira, inclusive configurações/admin. |
| 30 Crash handling | Política fail-fast identificada; diagnóstico fatal agora inclui worker e mensagem limitada/sanitizada; formatador passou teste isolado MSVC | Build/SHA, stack trace e core utilizável; execução integrada no worker e política systemd/restart continuam sem validação local/hospedada atual. |
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

## Atualização — backlog de tarefas e falta de backpressure (30/09/2026)

Esta aferição adicional parte do `main` em `9b0d1364c5499e769b1d7d5111a2a53be975f836`;
as seções anteriores preservam snapshots e resultados de commits anteriores.
O risco permanece condicional: a revisão confirma filas sem limite e produtores
remotos, mas não reproduziu saturação, travamento infinito ou um limiar seguro
de rejeição.

`config.lua` define `maxPlayers=2000` e `maxPacketsPerSecond=50`, sem definir
`maxConnections`. Nesse caso, `ConfigManager` usa o padrão `maxPlayers + 256`
(`src/connectionadmission.h`), ou 2.256 conexões; o limite padrão por IP é 128.
O produto de 2.256 conexões por 50 pacotes/s dá um envelope teórico de 112.800
quadros/s. Esse cálculo não é uma medição de capacidade nem uma previsão de
tráfego sustentável: o volume de tarefas por pacote varia conforme o opcode e
o trabalho adicional agendado pelos callbacks, e CPU, rede, banco e distribuição
de IP alteram o resultado.

`Connection::parsePacket` entrega o quadro ao protocolo e agenda a leitura do
próximo cabeçalho sem aguardar o Dispatcher (`src/connection.cpp`). O limite
de pacotes é por conexão, não uma cota agregada de trabalho. O opcode `0x32`
retém a string do cliente em uma tarefa (`src/protocolgame.cpp`); a lista do
Dispatcher não tem teto de tarefas ou bytes (`src/tasks.h`). A fila de eventos
do Scheduler também não tem capacidade máxima (`src/scheduler.h`), e a fila
SQL é uma lista sem teto atendida por um worker (`src/databasetasks.h`). O
Scheduler transfere eventos vencidos ao Dispatcher, e callbacks SQL também
podem enfileirar trabalho nele.

Um teto indiscriminado pode perder gravações SQL aceitas ou impedir limpeza,
como `Protocol::release`. Um limite apenas por número também não cobre o total
de bytes retidos por strings grandes. A telemetria registra contagem e pico de
tarefas, totais cumulativos de entrada/saída, bytes de payload explicitamente
acompanhados e os respectivos picos; diferenças entre totais permitem estimar
taxas por intervalo. Para SQL, os bytes são somente o tamanho das strings de
consulta, não a memória total da tarefa/processo. DatabaseTasks informa a idade
monotônica da tarefa pendente mais antiga e duração acumulada/máxima das chamadas
SQL concluídas. Uma chamada em andamento não aparece até finalizar. Ainda faltam
idade para Dispatcher/Scheduler, uma medição de memória retida e carga de staging
para calibrar limites sem risco de rejeitar picos legítimos.

Próximo passo seguro: obter essas métricas em staging ou telemetria equivalente
sob carga representativa; em paralelo, uma implementação de contabilidade pode
ser validada sinteticamente no CI para garantir soma/subtração de tarefas e
bytes em execução, expiração, cancelamento e destruição, além de preservar uma
reserva para trabalho interno. O teste sintético não calibrará limites para
produção. Não havia ambiente ou credenciais de staging disponíveis neste
checkpoint; nenhum limite foi ativado e nenhum servidor foi alterado.

## Implementação — autorização central das talkactions `/` (30/09/2026)

A fragilidade de manutenção descrita na retomada foi fechada nesta branch por uma política obrigatória no carregamento de cada talkaction ativa iniciada por `/`. O loader agora rejeita a ação e registra erro se a política estiver ausente, inválida ou incompleta; o despacho verifica a autorização antes de chamar Lua e recusa a ação por padrão se não houver política configurada.

O inventário cobre 36 comandos. A matriz preserva os controles que já existiam nos scripts: acesso de grupo, tipo mínimo de conta, `PlayerFlag_CanBroadcast`, ou acesso público. Comandos que exigiam tanto acesso de grupo quanto God/GM mantêm as duas condições. `/pos` continua público para consultar posição; a guarda Lua existente ainda limita o teleporte a personagens com acesso. As guardas originais dos scripts continuam ativas como defesa adicional.

Limitação revisada pelo agente Luna: a política central é por comando e não
representa condições dependentes do argumento. `/pos` mantém a guarda
condicional no Lua; o teste Python atual verifica estaticamente que ela
continua presente, mas não executa parser XML, despacho C++ ou Lua real.

Validação local: os 50 testes Python do conjunto de regressão do workflow `security-build` passaram, incluindo o teste que compara todas as 36 políticas XML com a matriz revisada e verifica scripts/guardas. `git diff --check` passou. Foi adicionado também um teste C++ isolado para a função de decisão da política e sua execução ao workflow; não foi possível compilá-lo localmente porque este ambiente Windows não tem CMake nem compilador C++ disponíveis. A primeira execução do CI revelou que o teste nativo precisava incluir `otpch.h` antes de `enums.h`; a compilação do servidor chegou até `talkaction.cpp`, mas os quatro jobs que compilam o alvo falharam nesse teste. O include foi corrigido no commit `2dd6a5e`; a nova execução de CI ainda está pendente.

Esta alteração está em revisão na branch `security-central-talkaction-auth-20260930`; ainda não foi publicada ou implantada. Não havia staging isolado configurado/disponível neste checkpoint, portanto o servidor local e o online não foram tocados. Após CI, permanece necessário um ensaio de negação/uso autorizado contra uma instância de staging para cobrir o caminho real de carregamento XML, dispatcher e Lua.

## Estado do CI — commit `35c3fc8` (30/09/2026)

Após corrigir o include do teste C++, os cinco workflows de PR foram repetidos uma vez. O GitHub reportou falha para todos os jobs em aproximadamente três segundos, sem passos registrados; a consulta dos logs retornou `404 BlobNotFound`. Esses checks não validam nem reprovam a correção C++: a causa de inicialização não ficou disponível. O server core já havia compilado `src/talkaction.cpp` no intento anterior, mas o alvo de teste falhou por falta do include de `otpch.h`; após a correção, ainda falta uma compilação observável do alvo e a execução do CTest. O PR permanece aberto e não foi integrado na `main`.

## Revisão adicional — alvo staff em `/ban` e `/ipban` (30/09/2026)

O achado preliminar desta revisão foi supersedido pelas correções registradas adiante em “Correção adicional — alvos de `/ban` e `/ipban`” e pela retomada descrita abaixo. No estado atual, os dois comandos continuam exigindo `group.access` do emissor, e `/kick` também recusa alvos com acesso. `/ban` valida o grupo online ou offline, consulta o tipo de conta persistido e inspeciona todos os personagens da conta antes de gravar. `/ipban` valida o grupo e o tipo persistido do personagem nomeado e agora também percorre os grupos de todos os personagens da conta antes de gravar ou remover o alvo. Falha de consulta e grupo não verificável são tratados como recusa. Evidências atuais: `data/talkactions/scripts/ban.lua`, `data/talkactions/scripts/ipban.lua`, `data/talkactions/scripts/kick.lua` e `tests/test_staff_ban_commands.py`.

O risco residual do IP compartilhado permanece: um IP ban aplicado contra personagem comum ainda pode afetar terceiros em outras contas no mesmo endereço/NAT; o comando verifica todos os personagens da conta nomeada, mas não enumera outras contas ou sessões do IP. Há também uma janela entre consulta de ban existente e inserção, e os testes Python cobrem estrutura/ordem do handler, não execução Lua com MariaDB. Nenhuma base de produção foi consultada.

## CI — commit `b7be0df`

O commit posterior ao registro anterior também teve os cinco workflows do PR marcados como falha sem passos ou logs; a API de logs retornou `404 BlobNotFound`. A causa continua indeterminada, então não há build nativo pós-correção verificável e o PR não foi integrado à `main`.

Na cabeça atual `e24a848`, a nova execução repetiu o mesmo padrão: 12 checks do PR foram concluídos como falha em 3–4 segundos, cada um com uma anotação e sem passos; a saída do check e os logs não trazem mensagem. Isso confirma a repetição do estado sem diagnóstico, mas não identifica sua causa. PR #9 continua aberto; não fiz merge nem deploy.

## Atualização — causa do CI do commit `29c4fc7` (30/09/2026)

A inspeção da interface de Actions do GitHub para o run `36751933127` mostrou a anotação de que os jobs não foram iniciados porque pagamentos recentes da conta falharam ou o limite de gastos precisa ser aumentado. Os cinco workflows associados a `29c4fc7` encerraram em 3–4 segundos; nenhum executou build nem teste. Portanto, essa falha não é evidência contra o código. Não alterei plano, cobrança ou limite de gastos.

Na cópia local, o conjunto Python do workflow foi executado no commit atual e passou nos 50 testes. O ambiente não tem CMake, compilador C++ ou LuaJIT; a meta de compilação e CTest C++ pós-correção continua sem evidência. Para retomá-la é necessário que o proprietário da conta resolva a restrição de cobrança/limite e então reexecute Actions, ou disponibilize um ambiente de build local equivalente. PR #9 segue aberto e não mesclado; nenhum servidor foi alterado ou reiniciado.

## Correções adicionais — comandos de jogador e persistência de tutor (30/09/2026)

A revisão com Luna confirmou que o gate existente em `playerSaySpell` negava os 12 comandos `!` a jogadores comuns, embora só `!online`, `!z` e `!x` sejam administrativos e os três já tenham guarda Lua de acesso. A configuração agora declara política nos 12 comandos; as nove ações de jogador são `public`, as três administrativas exigem `access`, e o dispatcher aplica a autorização central para `/` e `!`. O teste de inventário compara o conjunto exato de políticas e preserva as guardas dos scripts.

A revisão também confirmou que falhas SQL em promoção/demissão de tutor eram ignoradas. `IOLoginData::setAccountType` agora rejeita tipos fora do intervalo e retorna o resultado da gravação. O binding Lua só altera as sessões ativas daquela conta depois que o banco confirma a atualização. Os comandos de promoção e rebaixamento só confirmam sucesso quando a operação correspondente retorna sucesso; o caminho offline de rebaixamento também trata falha e libera o resultado da consulta em seus caminhos de erro.

Validação local após essas alterações: 54 testes Python do workflow passaram, incluindo regressões de policy de talkaction e verificações de falha de persistência. Esses novos testes são verificações de fonte/configuração, não exercitam o dispatcher real nem uma falha SQL em servidor ativo. `git diff --check` passou. Não há CMake, compilador C++ nem LuaJIT neste Windows, e os workflows hospedados estão bloqueados pela restrição de cobrança/limite descrita acima; portanto ainda não há build C++, CTest ou parsing Lua da revisão atual. Nenhuma produção/staging foi alterada.

Riscos ainda sem correção: um `/ipban` de alvo comum pode bloquear terceiros em outras contas no mesmo NAT/endereço, e a consulta seguida de inserção ainda não é atômica. A regra implementada rejeita contas que contenham qualquer alvo `TUTOR+` ou personagem com `group.access`, sem hierarquia entre emissores e alvos. SHA-1 sem salt para senhas precisa de plano de migração compatível e rollback. Alterar tutor propaga o tipo a todas as sessões online da conta; ainda falta testar falha de persistência com servidor compilado e MariaDB descartável.

## Correção adicional — alvos de `/ban` e `/ipban` (30/09/2026)

Ambos verificam o grupo do personagem alvo online ou offline e falham fechados quando não conseguem resolvê-lo. Como `/ban` afeta a conta inteira, a consulta também lê o tipo persistido em `accounts.type` e percorre os grupos de todos os personagens; recusa tipos `TUTOR` ou superiores, além de qualquer grupo com `access`. A leitura vem do banco porque `Player:getAccountType()` pode rebaixar GM/God para `NORMAL` quando o personagem está no grupo `player`. `/ipban` também recusa o tipo persistido `TUTOR` ou superior e percorre os grupos de todos os personagens da conta nomeada antes de gravar; assim, um personagem comum não pode usar o comando contra o endereço compartilhado com seu personagem staff da mesma conta. As consultas usam `storeQueryChecked`, diferenciando falha SQL de consulta sem resultados. `/ban` valida duração como inteiro positivo; ambos só removem o alvo online depois que a inserção confirma sucesso.

Naquele checkpoint, `/ipban` ainda verificava só o personagem nomeado; a retomada registrada abaixo ampliou a checagem para todos os personagens da mesma conta. O limite remanescente é que um IP banido contra um alvo comum ainda pode afetar terceiros de outras contas no mesmo NAT/endereço. As verificações não comparam hierarquia entre emissores e alvos; para `/ban` e `/ipban`, a política implementada recusa qualquer alvo `TUTOR+` ou grupo com `access`, sem diferenciar GM de God. Também resta uma corrida entre consulta de banimento existente e inserção; `storeQueryChecked` fecha o caso de erro de consulta, mas não torna a sequência atômica. Os testes Python estruturais cobrem guardas e ordem gravação/remoção, mas não executam handlers Lua nem MariaDB.

Após a ampliação para `account_type`, a suíte Python local passou em 56 testes; `git diff --check` e parsing de `talkactions.xml` passaram. O LuaJIT 2.1 que já estava na pasta temporária compilou 750 arquivos Lua e passou os três testes Lua do workflow (`economy-inventory`, parser de lamp-state e `rarity-economy`). O MSVC 14.51 compilou e executou os testes nativos isolados de admissão, limite da fila de saída e política de talkaction; este último usou um PCH shim mínimo para remover dependências externas que não são usadas pelo teste, então não equivale a compilar o servidor. O build completo segue indisponível: não há CMake nem as dependências Boost/pugixml/MariaDB do projeto neste ambiente. O Actions do commit `370c371` iniciou o run `36756569877`, mas as anotações dizem que os jobs não foram iniciados por falha de pagamentos recentes/limite de gastos; CodeQL teve o mesmo bloqueio no run `36756569964`. Nenhuma instância staging ou produção foi modificada.

Nesta retomada, `/ipban` passou a selecionar o `account_id` do alvo e a verificar, com `storeQueryChecked`, o `group_id` de todos os personagens da conta. Grupo ausente, conta inválida ou falha da consulta recusam o comando antes de inserir o IP ban; se qualquer personagem da conta tiver `group.access`, a operação é recusada. O teste estrutural `test_staff_ban_commands` foi ampliado para verificar a nova consulta e garantir que essa guarda antecede a gravação. Ele não simula o dispatcher Lua nem MariaDB.

Verificação desta alteração: os 63 testes Python do workflow passaram; `luaparse` em modo Lua 5.1 analisou `ipban.lua` sem erro; `actionlint` aceitou `security-build.yml`; `git diff --check` passou. Ainda não há execução com LuaJIT/servidor e banco descartável nesta revisão. O limite para outras contas que compartilham o mesmo IP continua, portanto, explicitado acima.

## Retomada com Luna — valores persistidos de tipo de conta (30/09/2026)

Classificação: risco condicional de privilégio por dado persistido inválido, não entrada direta de jogador. `AccountType_t` usa `uint8_t` e os valores válidos são 1–5. Antes da correção, leituras de `accounts.type` eram convertidas diretamente para o enum; por exemplo, se a coluna aceitar `258` ou `259`, o cast pode reduzir esses valores a `TUTOR` ou `SENIORTUTOR`. `Player::getAccountType()` só rebaixa GM/God de personagens no grupo `player`; não rebaixa Tutor/SeniorTutor. O schema da tabela não está versionado neste checkout, então não foi possível confirmar se a coluna aceita números acima de 255. O setter já recusava gravações fora de 1–5.

Agora `authentication.cpp` valida o inteiro cru antes do cast e retorna erro de banco para tipos fora de 1–5, tanto no loginserver como no gameworld. `IOLoginData::loadAccount`, `preloadPlayer` e `getAccountType` também validam as leituras; o accessor sem retorno de erro cai para NORMAL e registra a condição, e o carregamento de personagem falha se não conseguir carregar a conta identificada. Tipos válidos permanecem iguais. Não houve mudança de protocolo ou schema.

Validação local: os 57 testes Python do subconjunto definido no workflow passaram, incluindo os quatro testes de `test_account_type_persistence.py`. `authentication-decision-tests.cpp` compilou com MSVC 2026 18.10 e passou para valores inválidos `0`, `6`, `258`, `259`, `261` e `-1` nos dois fluxos de autenticação, além de validar os tipos 1–5. O harness isolado usou shims temporários mínimos de PCH e uma substituição determinística para `transformToSHA1`, mais uma cópia temporária do `authentication.cpp` com apenas a inclusão do PCH adaptada; portanto verifica as decisões da autenticação real, mas não testa o SHA-1 nem constitui build do servidor ou teste de leituras em MariaDB. `git diff --check` passou. Schema/dados e staging continuam indisponíveis para confirmar ou inspecionar valores persistidos; nenhuma produção foi tocada.

Luna revisou também o limitador por IP e não recomendou uma segunda camada equivalente: `ServicePort::onAccept` chama `ConnectionAttemptLimiter` antes de aceitar o protocolo, o qual já limita bursts por origem. Um limitador adicional repetiria essa política e poderia aumentar falsos positivos em NAT/proxy; tentativas distribuídas continuam sendo uma lacuna operacional, sem mudança nesta rodada.

## Retomada com Luna — consistência de trade no save individual (30/09/2026)

A revisão estática confirmou uma janela condicional de divergência entre snapshots: `Game::playerAcceptTrade` transfere os dois itens em memória e encerra o estado de trade; não grava os dois personagens como uma unidade. `IOLoginData::savePlayer` transaciona tabelas de apenas um personagem por chamada. No logout, `Player::onRemoveCreature` tenta salvar apenas o personagem que saiu até três vezes e só registra erro se todas falharem. No save global, `Game::saveGameState` também salva cada personagem separadamente e não trata o retorno de falha. Se, depois do trade, um snapshot persistir e o outro falhar definitivamente, os dados podem divergir entre duplicação/perda até serem reconciliados.

O efeito não foi reproduzido: não há failpoint/harness de MariaDB que permita falhar o save de exatamente um lado mantendo uma base descartável. Por isso permanece um risco de integridade condicional, sem afirmar exploit reproduzido. Não foi feita correção: tornar trade atômico exigiria transacionar ambos os saves e definir uma recuperação segura da troca em memória quando o banco falha, além de medir o custo de gravar dois personagens a cada trade. O próximo passo é implementar a injeção determinística de falha e conferir os dois snapshots em ambiente isolado antes de decidir a semântica.

## Retomada — varredura de segredos no estado atual (30/09/2026)

Gitleaks 8.30.1 examinou o histórico Git até o `HEAD` atual: 175 commits, sem achados. A varredura da pasta de trabalho encontrou quatro detecções `generic-api-key`, todas em relatórios JSON locais dentro de `/build/` (`script-lint-results-repro/summary.json:35`, `script-lint-results/summary.json:35`, `script-lint-results-final/summary.json:35` e `script-lint-results/lua-inventory.json:31990`). Esses caminhos são ignorados pelo `.gitignore` e não aparecem no histórico versionado; no momento da varredura, `git status` não indicava mudanças rastreadas. Os valores foram mantidos redigidos. Como os padrões estão em artefatos gerados e ignorados, isso não demonstra exposição de credencial do servidor ou do repositório, mas também não os classifica conclusivamente como falsos positivos. O relatório redigido ficou em `%TEMP%\antigas-audit-tools-20260929\gitleaks-current.json`; não houve leitura de configuração privada ou dados de produção.

## Correção — acesso à ação de lâmpadas em casas (30/09/2026)

`Game::playerUseItemEx` encaminhava a ação 0x83 para `Actions::useItemEx`, que não aplicava a opção `ONLY_INVITED_CAN_MOVE_HOUSE_ITEMS` ao tile de destino. A ação de lâmpadas usava `toPosition` para gravar o estado de uma lâmpada em qualquer tile de casa e transformava o item antes da gravação. Isso permitia que “use item com alvo” gravasse estado para uma posição diferente do item usado; se ali houvesse uma lâmpada compatível, a carga seguinte poderia alterá-la sem verificar convidados. A escrita no arquivo de estado era síncrona no dispatcher.

A ação agora só persiste uma lâmpada quando a posição de origem e a de destino são iguais. Para um tile de casa, se a opção de convidados estiver ativa, a ação consulta `House::isInvited` antes de transformar o item ou gravar. A API Lua `House:isInvited(player)` é somente leitura e retorna falso para userdata inválido; a chave existente da opção foi registrada em `configKeys`. `Actions::useItemEx` genérico não foi alterado, preservando as demais ações. O clique direto continua compatível: `Actions::internalUseItem` passa a mesma posição como origem e destino.

Verificação: as regressões Lua do parser e da ação passaram com LuaJIT 2.1; a nova regressão cobre jogador não convidado, convidado, opção desativada e posições diferentes, verificando que a recusa antecede transformação e escrita. O subconjunto seguro do workflow passou em 58 testes Python e 50 arquivos Python versionados foram analisados pelo parser AST. Actionlint passou nos cinco workflows, e `git diff --check` passou. A regressão Lua usa uma casa mockada; a binding C++ ainda não recebeu build de servidor nesta máquina, pois CMake/dependências e banco descartável continuam indisponíveis. Não houve teste integrado cliente-servidor, staging ou produção.

Risco residual: para jogador convidado (ou opção desativada), cada alternância ainda grava sincronamente a tabela inteira. O arquivo atual tem 3.420 bytes; não há medição de latência/volume em servidor online. A correção fecha a escrita cruzada via tile de destino e a ação de não convidados, mas não implementa debounce ou coalescência, cuja semântica de durabilidade precisa ser medida separadamente.

## Limites de persistência runtime para lâmpadas — 30/09/2026

A validação na carga já limitava `lamp_states.lua` a 8 MiB e 100.000 posições, mas o caminho de jogo continuava acrescentando posições sem o mesmo teto. Agora o contador é inicializado com a tabela validada na carga; a ação recusa uma nova posição persistida antes de transformar a lâmpada quando atinge 100.000, mas permite alternar posições já registradas. O writer exige a mesma contagem, serializa com `pcall`, verifica 8 MiB antes de abrir o arquivo e protege `write`/`close` com `pcall`. Isso alinha writer e reader e impede crescimento do estado além do formato aceito. A gravação continua serializando a tabela inteira sincronicamente; o caminho não faz rollback do item/memória se a escrita falhar depois da transformação, e o arquivo ainda não é substituído atomicamente.

O harness Lua de ação agora cobre o limite de novas posições e a atualização de uma posição existente no limite. Na verificação final desta retomada, os 106 testes Python por descoberta, os quatro harnesses Lua (`economy-inventory`, parser e ação de lamp-state, `rarity-economy`), os `loadfile` da biblioteca/ação, Actionlint em todos os workflows e `git diff --check` passaram. A tentativa de `luajit -b` não foi possível porque esta build não tem `jit.bcsave`; isso é limitação da ferramenta, não falha da sintaxe. O teste integrado de arquivo/dispatcher e a medição do custo síncrono continuam pendentes em staging; o build completo do servidor também não foi executado nesta máquina.

## Revisão complementar — autenticação de senha e recibos PIX (30/09/2026)

O ZIP e os executáveis locais do cliente foram comparados por hash e correspondem à versão 54 declarada em `client.version` e `client-release.json`. Isso confirma consistência do pacote local; não verifica os arquivos atualmente servidos pelo site/launcher online.

No caminho observado, o módulo Lua do cliente envia a senha digitada como string do protocolo, protegida pela criptografia RSA do pacote. O servidor calcula SHA-1 para comparar com `accounts.password`; os fluxos versionados de login, cadastro e troca de senha do site também usam SHA-1. O snapshot local de `accounts` usa `password CHAR(40)`, compatível com o formato hexadecimal SHA-1 observado. Isso mostra compatibilidade entre as versões locais examinadas, mas também significa que uma migração para hash resistente a ataque offline precisa coordenar servidor, site, todos os escritores de senha e a alteração de schema, com plano de rollback. O snapshot é de 23/09/2026 e não prova o schema atual; não foram consultados registros de conta, senhas ou hashes.

O dump local `Servidor/Database/imperium.sql` e os demais SQL locais não contêm DDL para `coin_orders`. A cópia atual do `approve-pix.php` está em `C:\Users\Usuário\Desktop\Servidor Antigas\Site-privado`, fora do checkout/versionamento de `Servidor/TFS`; ela restringe o comando a CLI executado como root e pede conferência manual do extrato. O fluxo abre transação e bloqueia o pedido escolhido; se ele já foi aprovado, aceita apenas a repetição do mesmo recibo sem novo crédito. Para pedido pendente, porém, não procura o identificador `receipt_e2e` em outros pedidos antes de inserir `market_claims` e marcar o pedido aprovado. Se não houver uma constraint única no schema efetivo, reutilizar o mesmo recibo em pedidos distintos pode criar créditos distintos. A presença dessa constraint na base atual não foi comprovada.

O risco permanece operacional e sem correção nesta retomada: uma consulta adicional no código protegeria aprovações sequenciais, mas não provaria unicidade sob concorrência. A correção robusta precisa do DDL/schema efetivo, unicidade de recibo no banco (ou ledger equivalente), reconciliação de recibos existentes e um teste concorrente com MariaDB descartável. Não há teste de `approve-pix.php` reproduzível no checkout; o relatório local de auditoria PIX registra ensaios anteriores, mas seus harnesses não estão presentes aqui. A máquina atual não tem serviço MariaDB e o Docker Engine não está ativo, então não há banco descartável local. Não alterei o handler privado nem banco real, e não inferi constraints a partir do dump incompleto.

Validação refeita nesta retomada: os 58 testes Python definidos pelo workflow passaram; os testes Lua do parser e da ação de lâmpadas passaram com LuaJIT 2.1; actionlint passou nos cinco workflows; `git diff --check` passou. Não houve build completo do servidor, consulta a produção, publicação nem reinício de serviço.

## Ajuste do harness — pacote isolado do launcher (30/09/2026)

O harness de integração do launcher lia um manifesto de staging, mas `ReleaseService.DownloadPackageAsync` sempre formava a URL do ZIP a partir da raiz de produção. Assim, o modo de candidato podia verificar um manifesto de staging e, em seguida, baixar o nome de pacote correspondente da produção, sem exercitar o artefato isolado pretendido. A revisão Luna também notou que o harness aceitava a URL de produção embora se identificasse como staging. O fluxo normal do launcher não tinha essas divergências: ele continua usando o endereço oficial fixo.

A sobrecarga interna do downloader agora recebe a base do pacote para o harness; a resolução valida HTTPS, domínio oficial ou subdomínio, porta 443, ausência de userinfo/query/fragment, barra final e nome de pacote exato para a versão. O teste de integração deriva essa base do diretório do manifesto assinado e recusa URLs que não estejam sob `/staging/` ou em `staging.tibia74.tech`, evitando confundir uma execução de produção com staging. Também não consulta mais o manifesto de produção. A regressão local verifica resolução ao lado do manifesto, aceita as localizações de staging e rejeita HTTP, host externo/lookalike, userinfo, porta não padrão, query, URL de produção e caminho/nome não autorizado.

Verificação: `dotnet run --project tests/LauncherSafetyTests.csproj --configuration Release` e `dotnet run --project tests/LauncherFormLifecycle/LauncherFormLifecycle.csproj --configuration Release` passaram; o launcher Release e `tests/LauncherIntegration` compilaram sem avisos/erros. Executei ainda o harness com a URL do manifesto de produção e confirmei que ele recusa a URL no preflight, antes de qualquer chamada HTTP. O ensaio HTTPS ponta a ponta continua pendente de um manifesto e ZIP publicados em endpoint de staging confirmado; nenhum endpoint de produção foi acessado e nenhum cliente foi instalado.

## Correção — retorno de erro de escape SQL (30/09/2026)

`Database::escapeString` verificava apenas se `handle` era nulo. `connectionFailed()` fecha esse handle e o substitui por um novo `mysql_init`, deixando um ponteiro não nulo com `connected == false`. A função podia então chamar `mysql_real_escape_string` em uma conexão não aberta e passar seu retorno sem validação para `std::string::append`. A [documentação oficial do MySQL](https://dev.mysql.com/doc/c-api/8.4/en/mysql-real-escape-string.html) define `(unsigned long)-1` como retorno de erro; tratá-lo como comprimento pode causar leitura inválida/exceção e encerrar o processo. Isso caracteriza risco de disponibilidade sob falha do conector, não prova de injeção nem de condição ativa na produção.

A API agora retorna sucesso/erro em parâmetro de saída, exige handle conectado, confere o comprimento de entrada/capacidade antes da alocação e rejeita o sentinela de erro ou qualquer retorno que alcance/exceda o buffer antes de anexar bytes. Todos os chamadores C++ abortam a consulta em caso de falha; a ponte Lua retorna `nil`, fazendo as concatenações SQL existentes falharem antes de executar/enfileirar consulta. `db.tableExists` interrompe o script com erro Lua se a verificação falhar, em vez de apresentar `false` indistinguível de tabela ausente. A consulta que verifica schema/configuração também distingue falha de leitura de resultado vazio, para não interpretar erro de escape/conectividade como ausência de tabela/configuração e prosseguir com escrita de setup.

Adicionado helper puro e regressão nativa para sentinela `ULONG_MAX`, comprimento no/acima do limite, entrada que não cabe no tipo da API e overflow de capacidade. O alvo foi incluído no CMake e no workflow `security-build`. Revisão read-only de Luna confirmou que um texto sentinela como substituto do valor não garantiria SQL inválido em todos os contextos Lua; por isso o erro é propagado explicitamente.

Validação local: o alvo isolado `database-escape-tests.cpp` compilou com MSVC 14.51.36231 e passou; os 63 testes Python da suíte configurada no workflow passaram, incluindo as regressões de propagação de erro e da mock `IOBan`; `actionlint` aceitou o workflow `security-build.yml`; `git diff --check` passou. Ainda falta compilar o servidor completo e executar `CTest`: este ambiente não tem CMake/dependências do servidor. Também não há MariaDB descartável para exercitar o retorno real do conector sob `NO_BACKSLASH_ESCAPES`; o charset da sessão não foi alterado porque o contrato real entre cliente, writers e schema ainda não foi confirmado. Nenhuma instância staging ou produção foi consultada, publicada ou reiniciada.

## Scan NuGet e runtime do launcher (30/09/2026)

Rodei `dotnet list <projeto> package --vulnerable --include-transitive` nos cinco `.csproj` versionados (`AntigasLauncher`, `ReleaseSigner`, `LauncherSafetyTests`, `LauncherIntegration` e `LauncherFormLifecycle`). Todos consultaram `https://api.nuget.org/v3/index.json` e reportaram nenhum pacote vulnerável. Os manifests não declaram `PackageReference`; logo, esse resultado cobre a superfície NuGet atual, não bibliotecas de sistema nem as dependências C++ listadas no CMake (`luajit`, `pugixml`, `mysqlclient`, `gmp` e Boost). Não existe lockfile/manifests de versões para essas dependências neste checkout; sem CMake/pkg-config ou pacotes instalados para o alvo, ainda não dá para associar versões de runtime a advisories ou produzir SBOM completo.

O launcher é `net10.0-windows`, `win-x64`, self-contained e single-file. A máquina local tem SDK 10.0.401 e runtime 10.0.12. A [política oficial de suporte .NET](https://dotnet.microsoft.com/en-us/platform/support/policy/dotnet-core), atualizada em 08/09/2026, lista 10.0.12 como patch mais recente, LTS ativo até 14/11/2028. A máquina também lista runtimes 7.0.20 (fora de suporte) e patches 8.0.25/9.0.13 abaixo dos patches então atuais; não há evidência de que processos do Antigas usem essas instalações locais, e não removi runtimes que podem servir a outros programas. A política indica que os patches suportados devem permanecer atualizados; o bundle distribuído continua precisando de verificação por hash/versão no fluxo de release.

Isso não altera arquivos de dependência nem é um scan do artefato publicado. A auditoria de versões de Boost/LuaJIT/PugiXML/MariaDB/GMP e bibliotecas do host Linux continua pendente de um ambiente que exponha os pacotes efetivamente usados.

## Retomada com Luna — integridade do limitador de tentativas do site (30/09/2026)

Na função `webLimit` de `C:\Users\Usuário\Desktop\Servidor Antigas\Site-privado\security.php`, JSON persistido inválido era convertido em lista vazia. Uma corrupção/truncamento podia reiniciar a contagem. O helper não é versionado dentro do checkout TFS; os arquivos públicos apenas o carregam pelo caminho externo configurado. Portanto a alteração local abaixo não entrou no Git nem foi publicada.

`webLimit` agora exige um array JSON de timestamps inteiros não negativos. A gravação mantém o `flock` no mesmo arquivo primário para serializar leitores da versão existente; antes de truncar, grava atomicamente um backup lateral com o estado prospectivo, incluindo a tentativa atual. Se primary e backup são válidos, reconcilia as multiplicidades dos timestamps para não perder tentativas adiantadas pelo backup; primary inválido/removido só é recuperado por backup válido. Backup existente inválido, leitura/gravação incompleta ou erro de persistência recusa a operação. Um arquivo vazio só inicia contador se acabou de ser criado e não há backup preexistente. Não acessei nem alterei produção, configuração, credenciais ou permissões.

PHP 8.3.35 passou `php -l` no helper e no harness temporário. O harness passou 34 verificações, incluindo estado inicial, janela/limite, JSON malformado/estruturalmente inválido, recuperação de vazio/corrupção, primary removido, backup prospectivo, falha de persistência e igualdade primary/backup após sucesso. Em um ensaio com 12 processos simultâneos e limite 3, exatamente 3 foram admitidos e primary/backup terminaram iguais. O ensaio simula estados deixados por interrupção, mas não encerra um processo no meio de `ftruncate`. PHP 8.1 não está instalado; compatibilidade foi revisada pelas APIs/sintaxe usadas, não executada nesse runtime.

Validações do TFS repetidas nesta retomada: os 63 testes Python do workflow passaram e AST analisou todos os 50 arquivos Python versionados; PHP 8.3.35 lintou os sete arquivos PHP versionados e passou o teste de HTML seguro; os quatro testes Lua (`economy-inventory`, parser e ação de lamp-state, `rarity-economy`) passaram e LuaJIT analisou os scripts alterados; `actionlint` aceitou os cinco workflows; testes de segurança/ciclo de vida do launcher passaram; launcher, signer e harness de integração compilaram em Release sem avisos/erros. Gitleaks examinou 98,43 MB; a primeira varredura achou quatro correspondências genéricas apenas em relatórios JSON ignorados em `build/`, nos caminhos `secret-scan.yml` e `key.lua`. A repetição com essas quatro ocorrências exatas como baseline não encontrou novos vazamentos. `git diff --check` passou após esta atualização.

O build completo do servidor, CTest, MariaDB descartável, validação integrada do handler PIX, e staging continuam indisponíveis neste ambiente. A primeira repetição do teste C++ isolado falhou antes de compilar devido ao caminho acentuado no batch temporário; refiz diretamente pelo `VsDevCmd.bat` do Visual Studio 2026, compilei `tests/database-escape-tests.cpp` com MSVC 14.51.36231 e o executável passou. O helper privado segue fora do Git/CI, a unicidade do recibo PIX continua dependente de schema não disponível, e permissões do diretório de rate limit em produção não foram verificadas. Não houve commit, push, deploy ou reinício de servidor.

O risco de cardinalidade do `webLimit` foi confirmado em um teste isolado: 100 chaves sintéticas produziram 200 arquivos persistentes. A recomendação de não apagar estados sem coordenar os workers continua válida. Em 01/10/2026, a cópia privada local recebeu uma mitigação com lock estável do diretório, teto de chaves e expurgo coordenado; os limites de produção e a implantação atômica seguem por validar, conforme a seção de revalidação ao final deste documento.

## Verificação read-only do pacote público do launcher (30/09/2026)

O manifesto HTTPS publicado em `https://tibia74.tech/client-release.json` foi lido e validado pelo método `ReleaseService.ReadAndVerifyManifest` compilado nos testes do launcher: versão 54, pacote `Antigas-7.4-Update-v54.zip`, assinatura `ECDSA-P256-SHA256-P1363` válida. Em seguida, invoquei o overload do próprio `ReleaseService.DownloadPackageAsync` com a raiz oficial HTTPS e diretório temporário. O downloader concluiu sem redirecionamento e o SHA-256 do ZIP recebido foi `f45500bd2734ae9ad03b0033c978e4b0494929727abea9daae49589ed4ed6bd1`, igual ao hash assinado no manifesto. O artefato baixado também passou `ClientPackage.ExtractToStaging` e `ValidateStagedPackage` do launcher: versão interna 54, cliente executável encontrado e 56.510.779 bytes expandidos validados contra o conteúdo do ZIP.

Essa foi uma leitura dos endpoints públicos de produção para conferir o release atualmente servido. A extração ocorreu apenas numa pasta temporária e não instalou nem executou o cliente; nenhum arquivo, serviço ou dado remoto foi alterado. Isso verifica a integridade do pacote publicado hoje, não a segurança funcional do conteúdo inteiro, nem substitui staging, teste integrado ou revisão do processo de assinatura.

Luna também comparou por HTTPS os arquivos completos `Client-v54.zip` e `Launcher-v54.zip` servidos pelo site com as cópias em `validation-artifacts/release-v54/`; tamanho e SHA-256 coincidiram nos dois pares. Esses pacotes não constam como payload do manifesto assinado, portanto essa igualdade confirma que o servidor oferece as cópias esperadas neste momento, mas não dá a eles a autenticação criptográfica que o launcher aplica ao Update v54.

## Revalidação do worktree atual (30/09/2026)

Com o mesmo estado de arquivos, rodei novamente os 63 testes Python declarados no workflow `security-build`: todos passaram. Os quatro testes Lua de economy/inventory, parser de lamp-state, ação de lamp-state e rarity/economia passaram com LuaJIT; `loadfile` aceitou os dois scripts Lua alterados. Actionlint validou os workflows sem erros. Launcher, ReleaseSigner e harness de integração compilaram em Release com zero avisos/erros, e o teste de lifecycle do launcher passou. Gitleaks 8.30.1 varreu 98,45 MB; a primeira chamada com raiz relativa mostrou as quatro detecções genéricas já conhecidas nos JSON ignorados de `build/`, enquanto a repetição com caminho absoluto e o baseline registrado retornou zero novos achados. Os valores ficaram redigidos. `git diff --check` passou (restaram apenas avisos de conversão LF/CRLF do Git em arquivos existentes). Essas verificações não substituem o build completo do servidor, CTest ou teste integrado com banco/staging, que seguem pendentes.

Também comparei as 22 redes em `deploy/nginx/antigas-cloudflare-realip.conf` com as fontes oficiais atuais de [IPv4](https://www.cloudflare.com/ips-v4) e [IPv6](https://www.cloudflare.com/ips-v6): 15 e 7 redes, respectivamente, sem diferenças. Isso valida o arquivo versionado; não confirma que o arquivo instalado no host ou o UFW em execução sejam idênticos agora.

Luna revisou independentemente o diff de escape SQL, `/ipban`, lamp-state e launcher. Não encontrou regressão concreta nova: os chamadores C++ propagam falha antes da query, a ponte Lua falha fechada, `/ipban` libera resultados inclusive nas saídas antecipadas, o teste de casa ocorre antes de transformar lâmpadas, e os parâmetros de download permanecem presos ao host HTTPS oficial no fluxo de produção. Essa é revisão estática; não substitui o build integral do servidor, falhas reais de MariaDB ou teste dinâmico de staging.

## Retomada — expiração de IP bans (30/09/2026)

Luna encontrou um caso de disponibilidade no `/ipban`: o comando considerava qualquer linha para o IP como ban ativo, mesmo depois de `expires_at`. O dump local `Servidor/Database/imperium.sql` confirma `expires_at` não nulo e `ip` como chave primária; `0` representa ban permanente, conforme a limpeza no startup e a leitura em `src/ban.cpp`. Um registro expirado pode continuar no banco até o startup ou até uma conexão daquele IP. Apenas filtrar a consulta de duplicidade deixaria a nova inserção em conflito com a chave primária.

O handler agora apaga, de forma síncrona e restrita ao IP validado, somente uma linha finita com `expires_at <= os.time()` antes da consulta de duplicidade. Se essa limpeza falhar, a operação aborta e não remove o alvo. Bans permanentes (`expires_at = 0`) e ainda válidos permanecem intactos. O harness de `/ipban` e a verificação de fonte cobrem o predicado de limpeza, a ordem e o retorno de erro; o mock não substitui execução contra MariaDB.

Após essa mudança, os 64 testes Python do workflow passaram e `git diff --check` passou. Este shell não tem LuaJIT nem Actionlint no PATH; portanto o harness Lua atualizado não foi executado nesta retomada. O harness já havia passado antes da adição da limpeza, e Actionlint havia aceitado o workflow anteriormente, que não foi alterado nesta etapa; nenhuma dessas execuções anteriores valida dinamicamente a nova ramificação Lua. O build completo e o teste MariaDB continuam pendentes. Nenhuma instância, servidor ou banco foi alterado remotamente.

## Retomada — observabilidade de filas (30/09/2026)

Adicionei snapshots sincronizados pelo mutex de cada fila e um log agregado a cada 60 segundos após o servidor entrar em operação normal. O Dispatcher e DatabaseTasks informam tarefas pendentes e picos; DatabaseTasks informa também bytes das strings SQL enfileiradas. O Scheduler diferencia eventos ativos de nós físicos retidos, incluindo tombstones cancelados até sua remoção ou compactação. Os produtores atuais declaram bytes apenas para payloads selecionados (como caminho de caminhada e texto de opcode estendido); o restante das closures não é mensurado. O log não inclui conteúdo SQL, IPs, contas ou nomes de jogadores.

`tracked_payload_bytes` e `queued_sql_bytes` indicam somente os bytes explicitamente contabilizados — não tamanho total de objetos, memória do alocador ou RAM do processo. `counter_anomaly` só sinaliza overflow/underflow dos próprios contadores, não cobertura total de payloads. Os snapshots são lidos um de cada vez, não como uma fotografia global atômica; uma tarefa em transferência pode aparecer momentaneamente entre as filas. Não foram introduzidos limites ou rejeições de tarefas. Ainda faltam idade/taxa de drenagem, latência SQL, correlação com CPU/RSS e calibração de backpressure baseada em staging.

Verificação desta etapa: os 70 testes Python do workflow passaram; cinco alvos nativos isolados (`queue-metrics-tests`, `scheduler-event-queue-tests`, `database-escape-tests`, `sql-identifier-tests` e `script-filename-tests`) compilaram e passaram com MSVC. O agente GPT-6 Luna revisou estaticamente a sincronização, lifetime e contabilidade e não encontrou defeito concreto. O build integral do servidor, CTest completo e MariaDB/staging seguem pendentes; por isso a telemetria e os demais caminhos C++ ainda precisam passar pelo workflow e teste integrado. Nenhum servidor foi reiniciado e nada foi publicado.

## Revalidação de lint local (30/09/2026)

Após a nota acima, usei `tools/script_lint_tools.py` para baixar as versões fixadas de Actionlint 1.7.12 e ShellCheck 0.11.0; o instalador validou os SHA-256 dos arquivos oficiais antes de extraí-los em `build/security-lint-tools/`. `tools/check_script_lint.py` analisou os cinco workflows e três scripts shell rastreados: Actionlint terminou com código 0 e ShellCheck terminou com código 0, sem diagnósticos. O relatório completo está em `build/script-lint-results-current/summary.json` (saída ignorada pelo Git). A observação anterior de Actionlint ausente descreve o estado antes desta revalidação; agora o workflow alterado foi validado. Isso não substitui build, teste Lua ou verificação de dependências.

Também confirmei a disponibilidade do ambiente sem ler arquivos de configuração: `cmake`, `ctest`, LuaJIT, MariaDB e `systemctl` não estão disponíveis nesta sessão. O Docker CLI existe, mas o daemon Linux não está ativo; WSL lista somente `docker-desktop`, parado; o pipe do motor Linux do Docker não existe. O guard explícito de mutações de staging está ausente e não há listener nos ports de staging locais 7176/7186. Por isso não executei o harness LuaJIT, o build integral, MariaDB ou teste vivo de staging, nem tentei SSH ou iniciei serviços. Esses requisitos continuam sem verificação dinâmica.

O SDK .NET 10.0.401, por outro lado, está disponível. `LauncherSafetyTests` passou seus testes de I/O limitado e URLs de staging; `LauncherFormLifecycle` passou as verificações de fechamento pendente e liberação após falha real de arquivo, sem abrir janela nem iniciar o cliente. `AntigasLauncher.csproj` compilou em Release para `win-x64`, self-contained, com zero avisos e erros. Esses testes são locais e não baixaram nem instalaram release de cliente.

Compilei também `LauncherIntegration.csproj` e invoquei seu teste somente-leitura com os dois endpoints de staging aceitos pelo código: `https://tibia74.tech/staging/v54/client-release.json` respondeu HTTP 404 e `https://staging.tibia74.tech/client-release.json` falhou na resolução DNS. A validação encerrou antes de baixar pacote; o diretório temporário criado pelo harness foi removido no `finally`. Assim, os testes locais do launcher passaram, mas não foi possível fazer validação ponta a ponta contra um pacote de staging publicado neste momento. Os resultados históricos de v54 não provam o estado atual.

## Retomada com GPT-6 Luna — recuperação dos runners de staging (30/09/2026)

Luna identificou uma falsa confirmação de sucesso nos dois runners de manutenção: depois de as fases de teste passarem, os códigos de `systemctl stop staging`, restauração de `MemoryMax` e `systemctl start produção` eram só registrados. Um erro ao iniciar a produção podia deixar o serviço parado enquanto o runner terminava com status `passed`. A consulta do estado final também podia falhar sem que isso anulasse o resultado.

Adicionei `tests/staging_recovery.py` para executar as três ações independentemente, registrar códigos/timeouts e consultar o estado final de cada unidade. Agora o relatório só preserva `passed` quando todas as ações retornam zero, a produção está `active` e o staging está `inactive`; caso contrário, o runner grava `failed` e termina com código não zero. O runner legado também valida a aprovação do alvo de banco/porta antes de parar produção. A nova regressão foi incluída na job Python do workflow.

Verificação local: os 79 testes Python configurados em `security-build.yml` passaram; quatro fontes do runner/teste passaram por AST; Actionlint 1.7.12 e ShellCheck 0.11.0 passaram nos cinco workflows e três scripts shell; `git diff --check` passou. O formato anterior do campo `recovery` foi preservado no relatório novo, junto aos campos de estado/falha. Luna revisou estaticamente a implementação e não encontrou regressão. Não executei os runners de staging: esta sessão não tem `systemctl`, MariaDB, guard de mutação de staging nem listeners 7176/7186. O teste cobre a lógica com substitutos, não a recuperação real do host; build integral, CTest, MariaDB e staging permanecem pendentes.

## Retomada com GPT-6 Luna — narrowing no tipo de conta (30/09/2026)

Luna identificou que `luaPlayerSetAccountType` convertia primeiro o argumento Lua para `AccountType_t`, cujo underlying type é `uint8_t`, e só depois `IOLoginData::setAccountType` validava o intervalo. Assim, um número como 258 podia truncar para 2 (`TUTOR`). Os dois callsites versionados passam constantes, então não há evidência de gatilho remoto atual; a validação antecipada fecha uma barreira insegura para scripts futuros ou entradas incorretamente encaminhadas.

O binding agora compara o número Lua original com cada valor permitido (1–5) e só faz o cast depois da igualdade exata. Isso também rejeita frações, NaN, infinitos e aliases fora do intervalo. Acrescentei casos à regressão C++ de autenticação/tipos e uma verificação Python para a ordem validar → cast → persistir → propagar às sessões. O alvo C++ já está ligado ao CTest e ao workflow `security-build`.

Validação desta continuação: os 79 testes Python do workflow passaram; Luna revisou NaN, infinitos, frações, strings numéricas e truncamento e não encontrou regressão. `git diff --check` passou. Um teste isolado da função de allowlist compilou e passou com MSVC; o alvo C++ completo não foi construído por falta de CMake e dependências de projeto. Risco condicional anotado: `setAccountType` verifica erro SQL, mas não distingue UPDATE com zero linhas afetadas. A nova busca não encontrou caminho no repositório que exclua accounts; Luna classificou o cenário como residual baixo e dependente de remoção externa enquanto a sessão está ativa, sem vetor online encontrado. Alterar a API compartilhada para checar linhas afetadas sem MariaDB validaria apenas um mock e poderia mudar semântica do driver, então mantive esse ponto documentado em vez de ampliar a mudança sem teste real.

## Retomada com GPT-6 Luna — sincronização de sessões ao remover Tutor (30/09/2026)

Luna revisou a validação de tipo de conta e apontou um caso adjacente no `/removetutor`: se o personagem nomeado estivesse offline, mas outra sessão da mesma conta estivesse online, o caminho anterior atualizava apenas `accounts.type`. A sessão em memória continuava com privilégios Tutor até sair. Isso depende de múltiplas sessões por conta estarem permitidas; a política de clones da produção não foi verificada.

O caminho offline agora percorre os jogadores online pelo account ID. Quando encontra uma sessão, usa `Player:setAccountType`, que persiste a alteração e propaga o novo tipo às sessões dessa conta; o `UPDATE` direto permanece apenas para contas sem sessões online. Em falha, o comando libera o resultado SQL e informa erro sem anunciar sucesso. O harness `tests/account-type-persistence-tests.lua` cobre sessão alternativa da conta, falha do setter sem fallback e atualização direta quando não há sessão; Luna confirmou que `Game.getPlayers()` e `Player:getAccountId()` têm as formas esperadas pelo Lua do projeto. O mock não substitui execução com bindings reais nem modela múltiplas sessões simultâneas.

Validação local desta retomada: os 79 testes Python da lista exata do workflow passaram; a descoberta completa executou 84 testes Python e também passou. Depois compilei LuaJIT x64 em `build/luajit-src` com MSVC, a partir do repositório oficial na referência `v2.1`/commit `c6ffc141a8762b41703f9287d63d93622a13dd8f`, seguindo as [instruções oficiais para Windows](https://luajit.org/install.html). A compilação terminou com sucesso e avisos de conversão apenas no código upstream do LuaJIT. Os seis harnesses Lua do workflow passaram (`economy-inventory`, parser e ações de lâmpada, `/ipban`, tipo de conta e raridade/Market), assim como o bytecode check dos 750 arquivos Lua versionados. O primeiro teste de `/ipban` revelou apenas um erro na expectativa do harness: no caminho de falha da limpeza, o handler já havia criado e liberado dois resultados; corrigi `assertFreed(1)` para `assertFreed(2)`, e o harness passou.

Actionlint 1.7.12 e ShellCheck 0.11.0 passaram nos cinco workflows e três scripts shell; `git diff --check` passou, com avisos apenas sobre conversão LF/CRLF. CMake, CTest, MariaDB e `systemctl` continuam ausentes; o build completo, persistência real e staging não foram executados. PHP também não está instalado/disponível nesta sessão, então o teste de segurança HTML e o parse PHP não foram repetidos nesta retomada; nenhuma fonte PHP mudou no worktree atual. Os testes nativos isolados anteriores não substituem o alvo completo. Nenhum serviço ou servidor remoto foi alterado.

Também revalidei o launcher: `LauncherSafetyTests` passou; o projeto do launcher e o harness de integração compilaram sem avisos/erros; `LauncherFormLifecycle` passou sem abrir janela nem iniciar o cliente. Luna revisou o fluxo de URLs e downloads e não encontrou desvio de host/SSRF: produção usa a URI base fixa, o overload de integração é interno e valida esquema, host, porta, componentes da URI e nome exato do ZIP, e redirecionamentos são recusados. A revisão encontrou ausência de casos de teste para porta, credenciais e fragmento no validador de URL de staging; acrescentei esses casos à regressão. Não rodei o harness ponta a ponta contra staging nesta retomada, e o build completo do servidor/CTest continua pendente.

## Revisão final do diff crítico com GPT-6 Luna (30/09/2026)

Luna revisou o diff atual de escape SQL e chamadores, bans, scheduler/dispatcher/shutdown e recuperação de staging. Não encontrou regressão nova confirmada: falhas de escape abortam antes de montar/executar SQL; transações de carregamento/salvamento fazem rollback ao sair sem commit; os resultados de `/ipban` são liberados nos caminhos de erro; e os testes de fila/shutdown cobrem cancelamento e janelas de corrida identificadas.

Observação operacional: a recuperação tenta iniciar produção mesmo se o stop do staging falhar, priorizando disponibilidade e marcando o resultado como falha. Nesse caso, as duas unidades podem ficar ativas temporariamente; a inspeção de host anterior encontrou staging isolado, mas essa configuração e seus recursos não foram revalidados nesta sessão. Mantive esse comportamento e registrei o risco/necessidade de inspeção operacional no achado OPS-07, sem mudar a política de disponibilidade sem dados atuais do host.

## Retomada com GPT-6 Luna — inspeção de metadados do ZIP v54 (30/09/2026)

Inspecionei somente metadados do pacote `build/client-release-v54-security-check.zip`, sem extrair ou executar arquivos. Seu SHA-256 é `f45500bd2734ae9ad03b0033c978e4b0494929727abea9daae49589ed4ed6bd1`, igual ao hash associado ao manifesto assinado validado na leitura anterior. O ZIP contém 685 entradas, 56.510.779 bytes expandidos e arquivo maior de 24.126.590 bytes; esses valores ficam abaixo dos limites do `ClientPackage` (20.000 entradas, 500 MiB no total, 150 MiB por arquivo). Não foram encontrados caminhos absolutos, segmentos `.`/`..`, caminhos duplicados sem distinção de maiúsculas, symlinks Unix, aliases de nomes Windows nem conflitos entre arquivo e diretório. `init.lua`, `Antigas_gl.exe` e `Antigas_dx.exe` estão presentes; `APP_VERSION` é 54.

O agente GPT-6 Luna revisou os metadados com uma verificação independente em Python; minha checagem em PowerShell confirmou contagem, limites, caminhos, duplicatas, symlinks, arquivos obrigatórios, versão e SHA-256. A verificação desta retomada não extraiu o arquivo; a extração e validação integral pelo `ClientPackage.ExtractToStaging`/`ValidateStagedPackage` estão registradas na inspeção read-only anterior do mesmo artefato. Staging continua indisponível (endpoint de manifesto retorna 404 e o hostname alternativo não resolve), então não há validação ponta a ponta de atualização contra um ambiente isolado. O estado dos workflows hospedados também não foi confirmado: `gh` não está instalado, não há token GitHub na sessão e a API REST anônima retornou 404, sem distinguir repositório privado, ausência do recurso ou permissão; não tirei conclusão sobre CI no GitHub. Repeti localmente `LauncherSafetyTests` e `LauncherFormLifecycle` (ambos passaram) e compilei `LauncherIntegration` em Release, com zero avisos e erros. `git diff --check` passou; os avisos emitidos são apenas sobre conversão LF/CRLF em arquivos já modificados.

## Reavaliação com GPT-6 Luna — exceções de workers (30/09/2026)

Revisei o residual `CRASH-01` em `Dispatcher::threadMain` e `DatabaseTasks::threadMain`. Luna confirmou que não é seguro capturar uma exceção arbitrária e continuar a fila: tarefas do dispatcher podem ter alterado parcialmente o mundo, enquanto uma falha no worker de banco pode deixar resultado SQL ou publicação de callback ambíguos. O teste `tests/dispatcher-failfast-tests.cpp` já exercita o loop real do dispatcher, lança uma exceção controlada depois de enfileirar outra tarefa e exige que a tarefa posterior não seja executada. O histórico registra um passe nativo hospedado para o checkpoint correspondente, mas não consegui reproduzir o build nesta sessão: CMake e as dependências do core estão ausentes, e o estado dos workflows GitHub não pôde ser consultado. Mantive a política fail-fast e atualizei `SECURITY_AUDIT.md`; recuperação exigiria semântica por tipo de tarefa, não um catch genérico. A política real de restart do processo continua fora do checkout e sem verificação atual.

## Diagnóstico fail-fast de workers — 30/09/2026

Para reduzir a opacidade sem mudar o resultado de uma falha, os pontos de entrada do Dispatcher e DatabaseTasks agora registram o nome do worker e uma mensagem `std::exception::what()` limitada a 256 bytes; bytes de controle/não ASCII viram `?`, e exceções não derivadas de `std::exception` geram texto fixo. O logger usa buffer fixo, `fwrite`/`fflush` com tratamento local de falha, e os wrappers executam `throw;` imediatamente depois. Assim não tentam continuar a fila, marcar o worker saudável ou iniciar um shutdown a partir de estado potencialmente parcial. A escrita em stderr é best-effort e ainda pode bloquear; não inclui SQL, IDs de conta ou payloads de tarefas.

Ampliei `dispatcher-failfast-tests.cpp` para lançar texto com newline e ESC e `check_dispatcher_failfast.py` para exigir a linha sanitizada, preservando o status/marcador do terminate handler e a ausência de execução da tarefa posterior. `worker-exception-diagnostic-tests.cpp` cobre texto longo/truncamento, exceção desconhecida e limite de buffer. Compilei e executei esse teste isolado com MSVC `/W4 /WX` em modo sem otimização e `/O2`; ambos passaram. O checker Python passou por `py_compile` usando o runtime empacotado. Os 80 testes Python configurados no workflow passaram, incluindo as regressões do dispatcher e do worker de banco depois da alteração dos wrappers. Não consegui compilar nem executar os wrappers reais nem o teste do dispatcher integrado: `dispatcher-failfast-tests.exe`, CMake e as dependências do core não estão disponíveis nesta máquina. Permanecem sem prova o build/SHA da versão que falhar, stack trace, coleta/utilidade de core dump e configuração de restart do supervisor.

## Retomada com GPT-6 Luna — callbacks de raid e reload — 30/09/2026

Uma revisão de lifetime encontrou um use-after-free estreito em callbacks de raid. `Scheduler::threadMain` remove o ID do evento, solta o mutex e depois publica a closure no Dispatcher; `/reload raids` também roda no Dispatcher e pode, durante esse intervalo, falhar ao cancelar o ID e apagar a `Raid`/`RaidEvent` ainda referenciadas pela closure. O comando está limitado a `acctype=5` em `data/XML/commands.xml`; a inicialização manual de raids é `acctype=4`. Nenhuma reprodução com servidor ativo foi feita.

Removi referências crus às entidades das closures. Agora eventos capturam nome, índice e uma geração; o callback é ignorado se a geração foi invalidada ou seu dono deixou de existir, e somente então a instância ativa é resolvida no Dispatcher. A mesma proteção cobre o timer periódico após reload. A revisão da Luna também encontrou que raids automáticas não repetíveis eram removidas de `raidList` ao começar e nunca liberadas após concluir. Agora elas passam por `splice` para uma lista de propriedade separada, que mantém os objetos válidos durante a execução e os libera em reload/shutdown; isso também elimina o caso de órfão/double-delete na limpeza.

`callback-generation-tests.cpp` valida execução da geração atual, invalidação de callback já separado da fila e expiração do dono. Compilei e executei o teste com MSVC `/W4 /WX` em configuração sem otimização e `/O2`. Sete verificações Python cobrem a janela Scheduler → Dispatcher, os caminhos de início, a resolução após validar geração, o timer periódico, a transferência para a lista de propriedade e a limpeza; os 87 testes Python configurados no workflow passaram. `git diff --check` também passou. O teste nativo integrado está registrado no CMake/workflow. O core do servidor não foi compilado e CTest, TSan, teste vivo do Scheduler/Dispatcher, staging e gameplay não foram executados; CMake e as dependências do core continuam indisponíveis localmente. A Luna fez uma revisão independente; nenhuma publicação, deploy ou reinício foi feito.

## Continuação com GPT-6 Luna — spawns no shutdown e timers globais — 30/09/2026

A revisão da fronteira Scheduler/Dispatcher encontrou mais dois casos. No shutdown normal, `Spawn::checkSpawn` podia permanecer na fila antes do sentinel do Dispatcher enquanto `map.spawns.clear()` destruía seu `Spawn`; a sequência entre `g_scheduler.shutdown()`, o encerramento das tarefas de banco e o sentinel deixa uma janela real. Também confirmei que `/reload globalevents` podia limpar e carregar mapas novos depois de o Scheduler retirar um timer/think antigo: a closure continuava válida sobre o singleton, processava os mapas novos e criava uma segunda cadeia periódica, com risco de executar scripts repetidamente.

Spawns e GlobalEvents agora também usam a geração compartilhada: cada callback é validado antes de tocar no proprietário/mapa, e a limpeza invalida a geração antes de cancelar IDs ou destruir o estado. O agendador de spawns usa a mesma geração ao repetir o timer. GlobalEvents zera o ID expirado antes de executar e reagendar; apenas a cadeia atual permanece ativa. Luna revisou as duas correções e confirmou a sequência e a ausência de acesso após invalidação sob a serialização do Dispatcher.

Foram adicionadas seis verificações Python para a ordem de shutdown, os pontos de invalidação e o registro/reagendamento global. A suíte Python configurada naquele checkpoint tinha 93 casos e passou; Actionlint 1.7.12 passou em todos os workflows, e `git diff --check` passou. O teste C++ isolado de geração compilou em MSVC `/W4 /WX` e passou em configuração sem otimização e `/O2`. CMake/projeto completo, CTest, TSan, reprodução viva dos dois races, gameplay e staging continuam indisponíveis. A observação sobre a fala atrasada de NPC foi reavaliada na retomada abaixo.

## Continuação com GPT-6 Luna — callbacks atrasados de NPC e timers Lua — 30/09/2026

Luna confirmou que o reload normal mantém o objeto `Npc`, portanto não há UAF confirmado no fluxo atual. Existe, porém, uma corrida de cancelamento: se Scheduler já publicou uma fala atrasada no Dispatcher, `BehaviourDatabase::reset()` não consegue mais cancelá-la; a fala da conversa anterior ainda podia aparecer após reset/reload. A closure também retinha `Npc*`; não encontrei chamada atual nos scripts para remover NPCs, embora a API Lua confiável permita remover criaturas genericamente. Para rejeitar callbacks obsoletos e evitar acesso ao proprietário se seu ciclo de vida mudar, a fala agora captura a resposta já calculada e é protegida por geração; reset invalida a geração antes de tentar cancelar IDs, e o destrutor da base invalida e cancela antes de liberar comportamentos. Três regressões Python verificam a guarda, a ordem de invalidação e a limpeza no destrutor. Luna revisou o diff, confirmou a compatibilidade C++11 e a cobertura da janela Scheduler→Dispatcher sob a serialização atual do Dispatcher; o helper não é proteção contra destruição concorrente fora desse modelo.

Também revisei Lua `addEvent`: os parâmetros ficam em referências do registry, e callback cancelado/retirado de `timerEvents` retorna antes de acessar o estado Lua. Com `convertUnsafeScripts=true` na configuração versionada, userdata de criaturas nos parâmetros vira ID. O comportamento observado é que timers criados por script podem continuar após reload de um subsistema, pois ficam no estado Lua global; não confirmei que isso viole a semântica esperada, então não mudei a política global de timers.

A varredura final de `createSchedulerTask` não encontrou outro UAF confirmado. `OutputMessagePool` usa singleton estático, conserva os protocolos por `shared_ptr`, e o processo une Scheduler/Dispatcher antes de sair. A aplicação/remoção de condições atrasadas re-resolve a criatura por ID; se ela sumiu, a condição é destruída. Resta um leak pequeno apenas se a tarefa de aplicar a condição for descartada durante shutdown antes de `Game::forceAddCondition`: o closure ainda captura `Condition*` sem ownership. Como são condições temporárias e o processo está encerrando, Luna não classificou isso como risco de segurança. Uma remoção atrasada por ID/tipo também pode afetar condição reaplicada nesse intervalo, mas não há problema de lifetime.

Validação desta retomada: os 96 testes Python configurados no workflow e os 101 testes Python por descoberta passaram; os seis harnesses Lua do workflow passaram; Actionlint 1.7.12 validou os workflows; o helper C++ de geração compilou e passou em MSVC `/W4 /WX` nos modos sem otimização e `/O2`; `git diff --check` passou, com avisos de conversão LF/CRLF em arquivos já alterados. As verificações de lifetime em Python cobrem invariantes de fonte, não reproduzem uma intercalação Scheduler/Dispatcher real. O build completo do servidor, CTest, TSan, execução com Scheduler/Dispatcher, staging e validação de gameplay seguem pendentes por falta de CMake/dependências e ambiente de staging. Nenhuma publicação, deploy, reinício ou alteração de servidor foi feita.

## Retomada da auditoria — launcher, dependências e lint (30/09/2026)

Revalidei o estado atual do worktree e os alvos locais do launcher. `AntigasLauncher`, `ReleaseSigner` e `LauncherIntegration` compilaram em Release com zero avisos/erros; `LauncherSafetyTests` e `LauncherFormLifecycle` passaram. O audit `dotnet list package --vulnerable --include-transitive` percorreu os cinco `.csproj` versionados e não encontrou pacotes NuGet vulneráveis nas fontes atuais. Isso cobre dependências NuGet declaradas, não bibliotecas nativas nem pacotes do sistema.

O verificador local de lint passou com Actionlint 1.7.12 em cinco workflows e ShellCheck 0.11.0 em três scripts shell, sem diagnósticos. O runtime LuaJIT local aceitou por `loadstring` os 750 arquivos Lua versionados (o arquivo persistido de lâmpadas foi analisado como expressão, sem execução). Os seis harnesses Lua já registrados no workflow passaram na retomada anterior. Uma tentativa de usar `luajit -b` nesta sessão mostrou que o build local não inclui o módulo auxiliar `jit.bcsave`; por isso o parse desta retomada usou o compilador embutido `loadstring` e não afirma ter gerado bytecode.

Na verificação de disponibilidade atual, `cmake`, `ctest`, Cppcheck, Clang-Tidy, PHP e ShellCheck não estão no `PATH`; os linters fixados em `build/security-lint-tools/` foram usados diretamente. Revalidei os endpoints de staging apenas por leitura: `https://tibia74.tech/staging/v54/client-release.json` respondeu HTTP 404; `staging.tibia74.tech` não resolveu no DNS; não há listeners locais nas portas 7176/7186. Sem CMake/Boost e sem ambiente de staging operacional, não há evidência nova de build integrado, CTest, TSan ou execução ao vivo. Nenhum serviço de jogo foi contatado ou reiniciado; nada foi publicado.

## Fluxo de autenticação e pressão ao banco — 30/09/2026

GPT-6 Luna revisou protocol login/gameworld, `AuthenticationDataSource`, `IOLoginData` e `Database::escapeString`. Não encontrou bypass de credenciais nem injeção SQL confirmada: o account ID é numérico; senha errada e personagem inválido compartilham resposta genérica; o nome de personagem passa por escape com falha fechada; e o retorno do conector/capacidade é validado. A ressalva de `DB-01` continua condicional porque não temos a sessão MariaDB para medir charset e `NO_BACKSLASH_ESCAPES`. SHA-1 sem salt permanece um risco offline se a tabela de contas for exposta e exige migração compatível, não indica bypass remoto.

Confirmei, porém, uma limitação de disponibilidade: em loginserver e gameworld, a consulta de conta ocorre antes de `AccountAuthenticationFailureLimiter::processResult`; no gameworld, `lookupIpBan` também consulta o banco antes da autenticação. O atraso por conta ocorre após a consulta. Antes de criar o protocolo, `ConnectionAttemptLimiter` já restringe bursts e repetições rápidas por IP; além disso, os caps globais/per-IP limitam sockets simultâneos. Esses controles reduzem tentativas por origem e conexões concorrentes, mas não impõem um orçamento global de consultas ao longo do tempo. Um conjunto distribuído de IPs ainda pode espalhar tentativas inválidas e consultas. Registrei AUTH-04 como risco condicional de pressão no banco/dispatcher. Sem medição de picos legítimos, latência e headroom do MariaDB em staging, não escolhi um limite global arbitrário que poderia bloquear jogadores legítimos ou pessoas em NAT compartilhado.

Não consultei contas, banco ou host, e não alterei o fluxo de autenticação. A validação anterior dos testes C++ isolados e harnesses do account type continua sendo evidência de regressões específicas; o protocolo real e a carga em MariaDB continuam sem teste integrado.

## Revalidação do estado remoto e do controle de tentativas — 30/09/2026

`git ls-remote --heads origin` confirmou que `origin/security-central-talkaction-auth-20260930` aponta para o mesmo commit do HEAD local (`62970d9544e746312dae3396743187aea3b11019`). O worktree ainda contém alterações rastreadas e arquivos de teste/helper não commitados; portanto, a igualdade dos refs não significa que essas alterações estejam no GitHub. `origin/main` continua em `f764c0a2e36962ec5a1d69e1980c8ec152c3302f`. Não fiz commit, push, deploy nem reinício.

A consulta anônima à API de workflows do GitHub retornou HTTP 404. Isso não permite distinguir repositório privado, endpoint indisponível ou falta de permissão, então o estado do CI hospedado segue sem confirmação. A revisão local do caminho de admissão reafirma AUTH-04: `ConnectionAttemptLimiter` é consultado antes de criar o protocolo e limita tentativas rápidas por IP; `ConnectionAdmissionSettings` limita sockets simultâneos globalmente e por IP. Esses controles não limitam globalmente consultas de autenticação ao longo do tempo, e endereços distribuídos podem contornar o gate por IP. Não adicionei um limite arbitrário sem a linha de base de login legítimo e latência/headroom do MariaDB em staging.

## Retomada — autenticação, parser Lua e validações locais (30/09/2026)

GPT-6 Luna e a revisão local corrigiram duas descrições antigas. **AUTH-01:** o cliente envia a senha em uma string dentro do bloco protegido por RSA; após decodificar, o servidor calcula SHA-1. Portanto, o formato do protocolo não exige que a senha armazenada seja SHA-1. As páginas de conta versionadas também criam, verificam e trocam senhas com `sha1()`, enquanto o schema real e a integração privada do site não estão no checkout. SHA-1 sem salt continua sendo um risco se a tabela de contas for exposta; não há evidência de exposição. Não fiz uma troca de hash somente no servidor, pois isso quebraria a leitura/escrita pelo site. A migração requer confirmar a capacidade da coluna e coordenar todos os leitores e escritores, com verificação e rollback em schema descartável.

**DB-01:** não encontrei injeção confirmada no fluxo de autenticação revisado. `Database::escapeString` confere conexão, capacidade e retorno, mas não define nem verifica explicitamente charset da sessão ou modo SQL. A documentação oficial do MariaDB confirma que `mysql_real_escape_string()` depende do charset de conexão e recomenda `mysql_set_character_set()` em vez de `SET NAMES`; o servidor e o schema reais seguem indisponíveis para confirmar charset e `NO_BACKSLASH_ESCAPES`. Mantive esse achado condicional e sem mudança de código; uma escolha de charset/SQL mode sem schema e writer conhecidos pode alterar dados ou falhar em produção.

**LUA-01:** a linha do relatório que dizia que `analyzersLib.unserialize` ainda usa `loadstring` estava obsoleta. A busca no `HEAD` e no worktree não encontrou `loadstring` em `data/`; `analyzersLib.lua` não define `unserialize`, e o `unserialize` ativo em `lamp_states.lua` é o parser restrito e limitado que rejeita código. Atualizei o relatório para encerrar o residual do código versionado. Os `loadstring` que apareceram na busca estão em harnesses de teste.

Validação repetida no worktree atual: passaram os 96 testes Python definidos no workflow e a descoberta completa de 101 testes; os seis harnesses Lua do workflow; parse sintático não executável por `loadstring` para 750 arquivos Lua versionados; Actionlint em cinco workflows; ShellCheck em três scripts; e os testes nativos de geração de callbacks, escape SQL, métricas de fila e diagnóstico de exceção, compilados com MSVC `/W4 /WX` tanto sem otimização quanto com `/O2`. O build Release do launcher, ReleaseSigner e LauncherIntegration terminou com zero avisos/erros; `LauncherSafetyTests` e `LauncherFormLifecycle` passaram. A auditoria de pacotes NuGet não reportou vulnerabilidades nos cinco projetos versionados. O PHP CLI passou no lint dos sete arquivos versionados, e o teste de HTML seguro passou.

Limites desta validação: o binário LuaJIT local não inclui `jit.bcsave`, então o comando de geração de bytecode não está disponível; usei compilação sintática com `loadstring`, que não executa os scripts. `git diff --check` passou, com avisos de conversão LF/CRLF em arquivos já modificados. Não há CMake no PATH nem nas localizações comuns verificadas; WSL contém somente a distribuição Docker parada e o pipe do Docker Desktop não existe, portanto não foi possível executar build integrado do servidor, CTest ou TSan.

Revalidação read-only externa: o manifesto de staging expirou por timeout, `staging.tibia74.tech` não resolve no DNS e não há listeners locais nas portas 7176/7186. A tentativa mais recente de `git ls-remote` falhou por não conseguir conectar a `github.com:443`; os refs da tentativa bem-sucedida anterior não puderam ser confirmados de novo. Nenhuma produção, staging, banco ou serviço foi acessado ou alterado; não houve commit, push ou deploy.

## Revalidação de helpers nativos — 30/09/2026

Compilei e executei seis regressões standalone adicionais: `connection-admission-tests`, `connection-output-queue-tests`, `status-query-rate-limiter-tests`, `script-environment-index-tests`, `sql-identifier-tests` e `script-filename-tests`. Todas passaram em duas compilações MSVC x64: configuração sem otimização (`/Od`) e otimizada (`/O2`), ambas com `/W4 /WX`, `/EHsc`, `/permissive-` e `/std:c++14`. Os binários e objetos ficaram apenas em `build/security-manual/`, diretório ignorado pelo Git. Esses harnesses exercitam os helpers em isolamento; não substituem build do servidor, CTest integrado, sanitizers nem testes de protocolo/DB em staging. Nenhum serviço foi contatado ou alterado.
## Regressões nativas de tempo e leitor de scripts — 30/09/2026

Também compilei e executei `localtime-thread-safety-tests` e `script-reader-open-tests` em MSVC x64, `/Od` e `/O2`. As duas variantes do teste concorrente de horário passaram; as duas variantes de `ScriptReader` confirmaram abertura nos três níveis válidos, rejeição do quarto e reutilização após o erro. Para o harness do leitor, defini `_CRT_SECURE_NO_WARNINGS` apenas na linha de compilação de teste porque o MSVC sinaliza o `fopen` legado do código exercitado (C4996); não alterei a implementação por causa desse aviso de plataforma. Os binários ficaram em `build/security-manual/`. Não executei os alvos de autenticação/core que linkam `tfs_core`, pois as dependências para compilar o core continuam ausentes. `git diff --check` passou; permanecem pendentes build integrado, sanitizers e execução de staging.
## Revalidação de toolchain, CTest e estado remoto — 30/09/2026

O ambiente atual não tem `cmake`, `pkg-config`, LuaJIT, GCC/Clang, Ninja ou os auxiliares de configuração do MySQL/GMP no `PATH`; WSL lista somente `docker-desktop`, parado; o pipe do motor Linux do Docker não existe. A leitura do `CMakeLists.txt` explica por que instalar apenas CMake não basta: antes das opções de testes, a configuração exige PkgConfig, LuaJIT, PugiXML, cliente MySQL, GMP e Boost. Os helpers independentes continuam validáveis por MSVC direto, mas isso não gera nem substitui CTest do projeto.

A rechecagem read-only de staging retornou HTTP 404 para o manifesto `/staging/v54/client-release.json`, falha de DNS para `staging.tibia74.tech` e nenhum listener local em 7176/7186. `git ls-remote` respondeu nesta rodada: `origin/security-central-talkaction-auth-20260930` está em `62970d9544e746312dae3396743187aea3b11019`, igual ao HEAD; `origin/main` permanece em `f764c0a2e36962ec5a1d69e1980c8ec152c3302f`. O worktree ainda contém alterações rastreadas e arquivos de auditoria/helper sem commit, portanto os refs remotos não contêm essas alterações locais. Não houve commit, push, teste de escrita, publicação ou contato com produção.

Além dos testes listados acima, `scheduler-event-queue-tests` passou em MSVC x64 com `/Od` e `/O2`, `/W4 /WX`. `git diff --check` passou, com avisos conhecidos de conversão LF/CRLF em arquivos modificados.
## Revisão estática da contabilização da fila de saída — 30/09/2026

A revisão do worktree atual não encontrou caminho de liberação duplicada no ciclo da fila. `NetworkMessage` reserva 65.500 bytes; os limites de 64 mensagens por conexão e 8.192 no processo correspondem a cerca de 4 MiB por conexão e 512 MiB no total. `Connection::send` reserva antes de inserir e desfaz a reserva se a alocação falhar. A mensagem em escrita permanece na frente da fila e conta no teto; o callback de escrita libera uma mensagem, `clearPendingOutputMessages` preserva apenas a mensagem em voo e libera o restante, e o destrutor libera qualquer mensagem ainda retida quando os handlers deixam de possuir a conexão. O teste helper confirma limites e reservas concorrentes, mas não executa o ciclo assíncrono real do Boost.Asio; isso permanece dependente do build integrado/staging.
## Redução de credenciais em GitHub Actions — 30/09/2026

A revisão confirmou que as cinco workflows já fixavam todas as ações externas em SHAs completos e não usam `pull_request_target` nem `workflow_run`. Havia, porém, oito usos de `actions/checkout` sem sobrescrever o padrão `persist-credentials: true`, que mantém o token/SSH key disponível para comandos Git posteriores. Como os jobs executam código do checkout, defini `persist-credentials: false` nos oito passos. Nenhum desses workflows faz `git fetch` ou `git push` depois do checkout; CodeQL mantém sua permissão própria `security-events: write`, e o token de Gitleaks continua explícito e somente de leitura. A documentação oficial do [input persist-credentials](https://github.com/actions/checkout/blob/3d3c42e5aac5ba805825da76410c181273ba90b1/action.yml) descreve o padrão anterior. Adicionei `tests/test_workflow_checkout_credentials.py` e incluí o teste na suíte da workflow de segurança.

Verificação desta mudança: o teste novo passou; a descoberta Python completa passou com 102 testes; Actionlint 1.7.12 aceitou as cinco workflows; a checagem estática encontrou oito referências checkout fixadas em 40 caracteres e todas com persistência desativada; `git diff --check` passou, com avisos apenas de normalização LF/CRLF em arquivos já modificados. A execução hospedada do GitHub não foi disparada e ainda não confirma os resultados dessas alterações locais.
## Checagem de estado do limitador de falhas de login — 30/09/2026

Revisei `AccountAuthenticationFailureLimiter::processResult` após considerar se IDs de conta variados poderiam causar crescimento de memória. O estado tem capacidade padrão explícita de 65.536 entradas e expiração de dez minutos; ao atingir capacidade, remove o item LRU antes de inserir. A suíte nativa `authentication-decision-tests.cpp` cobre progressão, expiração, capacidade/LRU e concorrência, mas não foi compilada nesta máquina porque depende de `tfs_core`. A limitação de disponibilidade AUTH-04 continua: a consulta SQL acontece antes de o limitador atrasar a resposta, então o LRU limita apenas a memória do próprio controle, não consultas a MariaDB. Não adicionei outro limite sem medição de staging.
## Varredura Gitleaks do worktree e do histórico — 30/09/2026

Baixei o Gitleaks 8.30.1 para `build/security-lint-tools/` a partir do release oficial e conferi o SHA-256 do ZIP contra o arquivo oficial de checksums antes de executá-lo (`d29144deff3a68aa93ced33dddf84b7fdc26070add4aa0f4513094c8332afc4e`). A varredura do histórico Git retornou código 0 e nenhum achado. A varredura recursiva inicial do worktree reportou cinco regras `generic-api-key`, todas em relatórios/inventários gerados sob `build/script-lint-results*` — conteúdo local ignorado pelo Git. Rodei então a varredura Gitleaks 8.30.1 nos diretórios versionados (`.github`, `data`, `deploy`, `docs`, `src`, `tests`, `tools`) e em todos os arquivos da raiz, inclusive `config.lua` local: zero achados. O relatório usou redação de 100%; nenhum valor de possível segredo foi exibido. Não criei allowlist para ocultar os cinco resultados gerados. O ZIP, relatórios e logs do scanner permanecem apenas em `build/`, ignorado pelo Git. Este resultado cobre o worktree/histórico local acessível, não o servidor implantado nem a execução hospedada do workflow.
## Verificação da configuração local de bind e admissão — 30/09/2026

O `config.lua` ignorado pelo Git existe no desktop e foi modificado em 2026-09-28. Extraí apenas as opções não secretas relevantes: `bindOnlyGlobalAddress=false`, `maxPlayers=2000`, `maxConnections=0` (o loader calcula 2.256) e `maxConnectionsPerIP=128`; login/game estão configurados nas portas 7173/7174. `src/server.cpp::ServicePort::open` liga `INADDR_ANY` quando o bind global está desativado. Não encontrei processo local `tfs`/`forgottenserver`/`antigas` nem listeners em 7173/7174. Portanto, o arquivo descreve a configuração disponível na estação, não comprova que o servidor local esteja ativo nem que a mesma configuração esteja no host online. Não alterei esse arquivo ignorado; firewall, NAT e exposição pública continuam sem prova.
## Validação do limite de pacotes por conexão — 30/09/2026

O limitador em `Connection::parseHeader` compara a taxa observada com `MAX_PACKETS_PER_SECOND` convertido para `uint32_t`. A leitura anterior aceitava valores negativos sem validação, convertendo-os em limites unsigned muito altos; zero, por sua vez, desconectava no primeiro pacote. `ConfigManager::load` agora lê e valida esse campo imediatamente após carregar o Lua e antes de aplicar quaisquer campos à configuração ativa. Só aceita valores finitos, inteiros, positivos e representáveis pelo armazenamento `int32_t`, preservando o padrão 25 e configurações positivas existentes. Assim, um reload com esse campo inválido retorna erro sem aplicar parcialmente as configurações.

Adicionei testes de fronteira para valores positivos, zero, negativos, frações, NaN, infinito e overflow, além de uma regressão Python para a ordem validação → mutação. Validação nesta retomada: o teste nativo de admissão compilou com MSVC `/W4 /WX` em `/Od` e `/O2` e passou em ambas as execuções; a descoberta Python completa passou com 103 testes; `git diff --check` passou. Isso não substitui o build integrado do servidor nem validação de tráfego em staging, e nenhuma configuração de produção foi alterada.

## Busca por execução de processos nas superfícies versionadas — 30/09/2026

Como parte da revisão das fronteiras, pesquisei `src/`, `data/` e `deploy/` por chamadas C/POSIX/Windows para criar processos (`system`, `popen`, `exec*`, `CreateProcess`, `WinExec`, `ShellExecute`); não encontrei callsites. A busca nas páginas PHP versionadas também não encontrou `exec`, `shell_exec`, `system`, `passthru`, `proc_open`, `popen` ou `eval`. Nos scripts Lua versionados não encontrei `os.execute`, `io.popen` nem `loadstring`; nos bindings C++ não encontrei `luaL_loadstring`, `luaL_loadbuffer`, `lua_load` ou `luaL_dostring`. Os `dofile` encontrados carregam caminhos literais do código. Isso reduz a superfície direta de injeção de comandos/código nesse checkout, mas é busca estática por nomes, não prova sobre dependências, funções criadas dinamicamente, arquivos privados `security.php`/`pix.php` ou código no host implantado.

## Limitação de logs disparados por opcode desconhecido — 30/09/2026

`ProtocolGame::parsePacket` mantinha conexões abertas para opcodes desconhecidos e escrevia uma linha em `std::cout` por pacote. `Connection::parseHeader` também escrevia por conexão ao ultrapassar a taxa, então abrir conexões sucessivas repetia o diagnóstico mesmo com o limite individual. Como o leitor agenda a próxima leitura e o controle de pacotes é por conexão, os dois caminhos permitiam escrita remota repetitiva. A correção usa um token bucket compartilhado pelo processo e por ambos os callsites, com burst de 10 mensagens e reposição de 10 tokens por minuto. Mensagens suprimidas são contadas de forma saturada e a contagem aparece na próxima linha admitida. Isso limita essas classes de mensagens sem alterar resposta ou estado do jogo; não limita outros caminhos de logging remoto.

O teste nativo cobre burst, reposição, contagem, concorrência e identidade do acessor entre duas unidades de tradução; a regressão Python confirma que os dois caminhos consultam a mesma instância antes de escrever e que o alvo está ligado ao CMake/CI. O teste nativo de duas unidades passou com MSVC `/W4 /WX` em `/Od` e `/O2`; os 106 testes Python por descoberta, Actionlint 1.7.12 em todos os workflows e `git diff --check` passaram. A suíte CTest integrada e o volume de logs sob conexão real ainda precisam de build/staging.

## Limite para relatórios de debug enviados pelo cliente — 30/09/2026

O opcode `0xE8` aceitava um relatório por instância de protocolo, mas uma reconexão permitia novo envio. `Game::playerDebugAssert` gravava as quatro strings recebidas diretamente em modo append, sem limite de bytes ou tamanho total do arquivo. Adicionei política de payload agregado máximo de 8 KiB, cota compartilhada de 10 gravações por minuto e teto de 16 MiB para `client_assertions.txt`. O arquivo existente nunca é truncado/rotacionado; falha de `fseek`/`ftell`, estado inválido, excesso de payload, cota ou orçamento recusam o novo registro. O cálculo reserva 256 bytes de metadados e até 2× o payload para expansão de newline em runtime Windows. Relatórios suprimidos por taxa são contabilizados e indicados no próximo registro aceito.

Os testes nativos da política de bytes/tamanho e do limitador (incluindo concorrência e compartilhamento entre duas unidades de tradução) passaram com MSVC `/W4 /WX`, `/Od` e `/O2`. A regressão Python verifica que validação e cota precedem `fopen`, que o tamanho atual do arquivo é conferido antes de `fprintf`, e que o alvo fica no CMake/CI. A suíte Python completa passou com 106 testes, Actionlint 1.7.12 passou nos workflows e `git diff --check` passou. Ainda falta build integrado do core e exercício do I/O real em staging.

Revisei também o sink de `Player:onReportBug`: a função recusa contas normais, limita o comentário a 4.096 bytes e troca nomes contendo separadores por GUID antes de formar o caminho. Não encontrei nele o mesmo acesso de qualquer jogador que aciona o opcode `0xE8`; a confirmação de categorias/uso legítimo segue coberta pelo código Lua versionado, não por tráfego em staging.

## Revalidação dos limites de conexão — 30/09/2026

Uma conferência do estado atual encontrou controles de admissão global e por IP já presentes no worktree, embora a linha `NET-01` do relatório principal ainda descrevesse a ausência desses limites. `ServicePort::onAccept` aplica a cota depois do TCP accept e antes de construir o protocolo; `ConnectionAdmission` sincroniza contagem global e por endereço e libera a reserva quando o socket fecha. `maxConnections=0` calcula `maxPlayers + 256` (ou 4.096 quando `maxPlayers` é ilimitado), e `maxConnectionsPerIP` usa 128 por padrão. O limite de filas de saída continua em 64 mensagens por conexão e 8.192 no processo, cerca de 512 MiB de buffers fixos.

Recompilei e executei `tests/connection-admission-tests.cpp` com MSVC x64, `/W4 /WX /O2`; passou cobrindo limites global/por IP, concorrência, liberação, reload de limites e defaults. Os sete testes de integração Python de `test_connection_admission.py` também passaram. Atualizei `SECURITY_AUDIT.md` para refletir a implementação. A admissão ocorre depois do TCP accept e não previne saturação de rede, SYN ou backlog; a cota por IP pode agrupar jogadores atrás de NAT/proxy. Configuração/firewall do host de produção, comportamento sob carga real e build integrado/staging continuam sem evidência.

## Rechecagem de build integrado e staging — 30/09/2026

Confirmei novamente o ambiente nesta retomada: `cmake` não está no `PATH` nem nas localizações do componente CMake do Visual Studio consultadas; o executável Docker existe, mas não consegue abrir `dockerDesktopLinuxEngine`, e a distribuição WSL `docker-desktop` está parada. `staging.tibia74.tech` não resolve por DNS e, por isso, a URL read-only do manifesto não pode ser acessada. Assim, esta sessão não oferece build CMake/CTest do core nem staging vivo; não iniciei serviços nem tentei contornar a falta de ambiente instalando dependências. As regressões C++ independentes continuam compiláveis por MSVC e as verificações Lua/Python seguem locais.

## Revisão direcionada de consultas SQL — 30/09/2026

Revisei os callsites dinâmicos de SQL nas áreas C++ de login, bans, guildas e persistência e nos scripts Lua de Market, loja, morte, compatibilidade e comandos administrativos. Não encontrei nesta amostra concatenação direta de texto livre sem escape: nomes, razões, buscas e campos textuais passam por `db.escapeString`/`Database::escapeString`; IDs e quantidades são valores numéricos obtidos do binding ou validados pelo script antes da construção. `DatabaseManager` usa `quoteSqlIdentifier` para o nome de tabela obtido de `information_schema`. Esta busca direcionada não prova segurança de todos os fluxos nem substitui análise dinâmica.

Recompilei e executei `database-escape-tests.cpp` e `sql-identifier-tests.cpp` com MSVC x64 `/W4 /WX /O2`; ambos passaram. O primeiro verifica o cálculo seguro de buffers e rejeição de overflow/sentinela da API, não chama MariaDB nem comprova a semântica de escaping da conexão ativa. Mantive `DB-01` aberto: ainda falta verificar em conexão real o charset efetivo e o modo SQL, em particular a compatibilidade com escaping baseado em barras invertidas, e migrar novos fluxos de alto risco para consultas parametrizadas.

## Revisão da aprovação manual de PIX — 30/09/2026

O diretório local `C:\Users\Usuário\Desktop\Servidor Antigas\Site-privado` contém apenas `security.php`, `pix.php` e `approve-pix.php`, fora do Git. Inspecionei o handler de aprovação: ele exige CLI como root, usa prepared statements e bloqueia a ordem em transação, mas só tornava idempotente a repetição do mesmo recibo na mesma ordem. Um operador podia inserir o mesmo `receipt_e2e` em outra ordem e gerar outro claim; não houve evidência de que isso ocorreu.

Adicionei à cópia local, sem tocar no banco, uma trava consultiva `GET_LOCK` com timeout que serializa as execuções desta ferramenta e uma consulta preparada, dentro da transação, que recusa um recibo já associado a outra ordem antes de criar o claim. A repetição do recibo da própria ordem aprovada continua idempotente. O uso de named locks é por sessão: a documentação do [MariaDB `GET_LOCK`](https://mariadb.com/docs/server/reference/sql-functions/secondary-functions/miscellaneous-functions/get_lock) informa que `COMMIT` não os libera e que o encerramento da conexão sim; isso protege as invocações cooperantes deste CLI, não writers desconhecidos que não usem a mesma trava. `security.php`, `pix.php`, `approve-pix.php` e os seis PHP públicos passaram `php -l` com o PHP 8.3.35 NTS baixado do diretório oficial e verificado pelo SHA-256 publicado. Sete verificações estruturais confirmaram CLI/root, ordem trava→transação, guarda de recibo antes do claim e liberação nos caminhos de sucesso/erro. Gitleaks 8.30.1, com redação total, encontrou zero segredos nos três PHP privados antes e depois da mudança.

A validação é parcial: não há PHP/MariaDB integrado no host de teste, não existe DDL local de `coin_orders`, não confirmei constraint única, isolamento/versão do banco efetivo, possíveis writers fora desse diretório nem executei duas aprovações concorrentes. A trava de aplicação reduz o risco nas execuções deste CLI, mas uma constraint única no schema continua sendo a garantia mais forte. A cópia alterada está fora do Git e não foi publicada nem implantada; não houve aprovação de pedido nem acesso a dados financeiros.

## Revalidação e contenção da cardinalidade de `webLimit` — 01/10/2026

Inspecionei novamente o helper privado atual e confirmei que não havia expurgo entre chaves. Em uma cópia de teste apontada a uma pasta descartável dentro de `build/security-lint-tools`, 100 chaves independentes geraram exatamente 200 arquivos de estado (`.json` e `.bak`). Nenhum dado do site ou da produção foi usado pelo ensaio.

A cópia local de `C:\Users\Usuário\Desktop\Servidor Antigas\Site-privado\security.php` agora limita a cardinalidade a 32.768 chaves por padrão. `TFS_WEB_RATE_MAX_KEYS` permite ajuste operacional entre 16 e 262.144. Um arquivo de lock estável permite concorrência compartilhada entre chaves existentes; a criação e expiração obtêm lock exclusivo, portanto o coletor não remove um arquivo enquanto uma chamada desta versão o utiliza. O contador é reconstruído por varredura inicial/periódica (no máximo uma a cada cinco minutos), estados sem atividade por mais de sete dias são removidos, e uma chave desconhecida falha fechada quando a capacidade está cheia. Os arquivos por chave e o backup já existentes mantêm o formato anterior; o intervalo aceito por chamada é limitado a sete dias, acima do maior intervalo observado nos chamadores atuais (uma hora).

Verifiquei em pasta isolada, com capacidade configurada em 16: duas chamadas permitidas e a terceira negada no mesmo limite; 15 chaves adicionais aceitas até completar 16; a 17ª negada; depois de envelhecer artificialmente os estados, a varredura removeu os vencidos e admitiu uma nova chave. Em ensaios separados, 24 processos PHP concorrentes na mesma chave, limite cinco, produziram exatamente cinco admissões e 19 recusas; 24 chaves distintas concorrentes com capacidade 16 produziram exatamente 16 admissões e 16 arquivos de estado. Também corrompi o contador de capacidade: a chamada nova o reconstruiu sem apagar a contagem de uma chave existente. Esses são testes do helper copiado para harnesses temporários, não testes de integração do site.

PHP 8.3.35 lintou os nove arquivos PHP públicos/privados locais. Os 106 testes Python do checkout passaram com `unittest`; `git diff --check` passou (só avisos de normalização LF/CRLF). `pytest` não está instalado; não era o runner do projeto. Os harnesses temporários e a cópia de rollback em `build/security-lint-tools` foram removidos após os ensaios.

A mitigação está apenas na cópia privada local: `security.php` não faz parte do Git nem da configuração de deploy inspecionada, e nada foi publicado ou reiniciado. Para que o teto seja efetivo, todos os workers PHP precisam usar a nova cópia juntos; durante uma implantação gradual, workers antigos não consultam o lock novo. Ainda faltam validar `flock` no filesystem real, permissões da pasta, carga/cardinalidade representativa e o valor operacional do teto em staging. O CMake/build integrado, Docker Engine e hostname de staging continuam indisponíveis. Nenhuma aprovação PIX, banco, servidor ou serviço remoto foi acessado nesta etapa.

## Revalidação dos pré-requisitos de SQL e senhas — 01/10/2026

Revisei novamente os pré-requisitos dos achados `DB-01` e `AUTH-01`. `rg --files -g '*.sql'` no checkout encontrou somente `data/sql/market.sql` e suas duas migrações; o schema de `accounts`/`players` não está versionado aqui. O único escritor PHP de senha dentro do checkout é `deploy/site-public`: cadastro, login e troca continuam usando SHA-1. O diretório privado local contém somente `security.php`, `pix.php` e `approve-pix.php`, sem um writer privado de autenticação. Em `Database::ensureConnection`, o setup da sessão define apenas `innodb_lock_wait_timeout=1`; não encontrei `mysql_set_character_set`, `SET NAMES` ou validação de `sql_mode`/`character_set_connection` no código C++/Lua/PHP pesquisado.

Essa evidência confirma que migrar o hash ou impor charset/modo SQL por suposição pode quebrar login, comparação de nomes ou compatibilidade de queries. Mantive `AUTH-01` e `DB-01` abertos: a próxima alteração precisa dos limites reais da coluna e de todos os readers/writers do hash, além de Connector/C, charset e `sql_mode` da sessão de staging. Não acessei arquivo de configuração de produção, credenciais ou banco.

## Revalidação de regressões nativas e launcher — 01/10/2026

Como não há distro Linux de desenvolvimento instalada (a listagem WSL retornou apenas `docker-desktop`), não há `cmake`, `pkg-config`, MariaDB client/server ou serviço MySQL local, e o Docker Engine continua sem o pipe Linux, repeti os alvos isolados que podem ser compilados no host Windows. Recompilei no MSVC x64 do Visual Studio 2026 (`/W4 /WX /O2 /EHsc /std:c++14 /permissive-`) e executei `connection-admission-tests`, `database-escape-tests`, `sql-identifier-tests` e `worker-exception-diagnostic-tests`; todos terminaram com código zero. Estes binários exercitam helpers e contratos isolados; não são evidência de build do servidor completo nem de conexão MariaDB.

O harness executável de `tests/LauncherSafetyTests.csproj` passou via `dotnet run` (“Launcher bounded I/O and staging URL regression tests passed”). O projeto principal `AntigasLauncher.csproj` também compilou em Release com zero avisos/erros. Isso valida o código local do launcher, não a publicação atual nem o fluxo ponta a ponta em máquina limpa.

A verificação de disponibilidade confirmou novamente que staging não resolve em DNS e que nenhum serviço MariaDB/MySQL local aparece instalado/ativo. O build integrado Linux, CTest, SQL mode/charset efetivos e teste de autenticação com schema descartável continuam sem ambiente. Não alterei configuração, banco, servidor, rede, Git remoto ou produção nesta rodada.

## Revalidação do limitador por origem antes do login — 01/10/2026

A revisão de `AUTH-04` confirmou que `Ban::acceptConnection` aplica o limitador no accept TCP, antes de instanciar o protocolo, mas a espera usava `OTSYS_TIME()`, baseado em `system_clock`. Um ajuste para frente do relógio podia expirar slots cedo; um ajuste para trás podia prolongar bloqueios. `Ban::acceptConnection` agora mede milissegundos desde um `steady_clock` monotônico iniciado no processo. O estado segue local ao processo, limitado a 65.536 IPv4 e expurgado em lotes de 256 slots quando a tabela enche.

Acrescentei regressão nativa determinística para o helper: cinco tentativas a 100 ms passam, a sexta inicia bloqueio de 3 s, uma tentativa durante o bloqueio continua negada, a origem volta a passar após o prazo estendido e duas amostras do relógio monotônico não retrocedem. `connection-admission-tests` recompilou e passou com MSVC `/W4 /WX /O2`; o teste compila e verifica `ConnectionAttemptLimiter`, não compila `Ban.cpp`. Os sete testes Python direcionados verificam também o wiring de `Ban::acceptConnection` para o helper monotônico e passaram. A mudança corrige a base temporal do controle individual; não introduz teto global de autenticações nem resolve pressão distribuída ao MariaDB. O limite global continua dependente de carga representativa em staging.

## Complemento da revisão de SQL em Lua — 01/10/2026

Ampliei a amostra de consultas dinâmicas em `market.lua`, `shop.lua`, `economy.lua`, `onlineTime.lua`, `antigasBestiary.lua`, `ipban.lua`, `playerdeath.lua` e `startup.lua`. No Market, `request.action` é despachada por uma tabela fechada; busca/categoria e campos textuais são escapados ou limitados a allowlists; página, IDs, quantidades, preços e moedas passam por validação inteira, e os valores de `claim` vêm dessas validações, de constantes ou de resultados numéricos do banco. Na loja, custo, item e callback vêm da oferta registrada no servidor e são comparados com o pedido; textos são escapados. O comando de ban escapa o nome recebido e usa IP/IDs numéricos obtidos de jogador/resultado tipado. Bestiary e persistência de tempo formatam apenas argumentos numéricos. As únicas chamadas de `Economy.redeemPoints` encontradas passam constantes `1` e `10`; não localizei chamador de `Player.addOnlineTime` neste checkout.

Não confirmei um caminho de injeção SQL remoto nesta amostra e não alterei código com base apenas em hipótese. A revisão é estática, limitada aos arquivos e chamadores encontrados; não prova os tipos em runtime nem cobre writers externos ao checkout. `DB-01` segue aberto até validar charset/modo SQL e comportamento de escaping numa conexão MariaDB do staging, além de avaliar migração para queries parametrizadas onde aplicável.

## Revalidação local da suíte e do launcher — 01/10/2026

No checkout atual, `python -m unittest discover -s tests -q` usando o Python empacotado do ambiente Codex executou 106 testes e passou. `dotnet run --project tests/LauncherSafetyTests.csproj -c Release --no-restore` passou com a mensagem “Launcher bounded I/O and staging URL regression tests passed”. O build Release de `deploy/launcher/AntigasLauncher/AntigasLauncher.csproj` concluiu com zero avisos e zero erros.

Reconfirmei que este host não expõe CMake, MySQL/MariaDB CLI ou serviço MySQL/MariaDB; o Docker CLI não alcança `dockerDesktopLinuxEngine`, e a única distro WSL listada é `docker-desktop`. `Resolve-DnsName staging.tibia74.tech` falhou com “O nome DNS não existe”, e `gh` CLI não está instalado; não consultei o estado hosted do GitHub Actions/CodeQL. Portanto, estes resultados não substituem o build integrado do servidor, CTest nem testes de persistência/autenticação contra schema descartável. O worktree já contém numerosas alterações locais e arquivos não rastreados; foram preservados, sem limpeza ou publicação.

## Revisão dos Extended Opcodes Lua — 01/10/2026

Mapeei os handlers de entrada do cliente em Shop, Market, Bestiary, conquistas, questlog e raridade. Os buffers máximos observados são 4.096, 2.048, 8.192, 512, 512 e 256 bytes, respectivamente. O Market limita mutações a três e leituras a oito por personagem por segundo; Shop limita por storage a uma compra e uma ação de leitura por segundo; Bestiary restringe o catálogo a 200 nomes e aplica intervalo de dois segundos; conquistas limita leitura/claim a um pedido por dois segundos; questlog usa balde de quatro tokens com reposição temporal, valida campos/ações e limita respostas a 48.000 bytes. O handler de raridade aceita apenas formatos numéricos fixos e no máximo 40 posições por consulta. Os dados de progressão vêm do `player` autenticado, não de um GUID ou storage escolhido pelo cliente; compras resolvem item/callback na oferta registrada pelo servidor.

`markSeen` em conquistas e pedidos de raridade não têm cota Lua própria; eles dependem do limitador central de pacotes por conexão. O código e a validação positiva da configuração desse limitador foram revisados, mas o valor efetivo do servidor online não foi verificado. Não confirmei vulnerabilidade nesses handlers. A conclusão é limitada a leitura estática: há 710 scripts Lua e 28 testes Lua neste checkout, mas este host não tem `lua`, `luajit`, `luac`, `luacheck`, `lupa` ou parser tree-sitter-Lua para executá-los/analisá-los; os testes Python locais passaram, mas não substituem os testes Lua reais nem a carga em staging.

## Regressões C++ isoladas reexecutadas — 01/10/2026

Para contornar a conversão ANSI do caminho de usuário com acento, mapeei temporariamente o checkout e a pasta de saída em unidades locais durante a compilação. Com MSVC x64 do Visual Studio 18 e `/W4 /WX /O2 /EHsc /std:c++14 /permissive-`, compilei e executei `connection-admission-tests`, `database-escape-tests`, `sql-identifier-tests`, `callback-generation-tests`, `worker-exception-diagnostic-tests`, `queue-metrics-tests` e `remote-log-rate-limiter-tests`; todos passaram. O último executável incluiu explicitamente o arquivo adicional `remote-log-rate-limiter-sharing.cpp`, necessário para cobrir o estado compartilhado entre translation units. Isso valida helpers isolados e não substitui a compilação integrada do servidor nem o CTest completo.

## Verificação do modelo IPv4 do limitador — 01/10/2026

Investiguei se o limitador por origem de 32 bits poderia ser contornado por clientes IPv6. A busca em `src/` encontrou um único listener TCP: `ServicePort::open` constrói o endpoint com `address_v4::from_string` ou `address_v4(INADDR_ANY)`. `Connection::getIP()` retorna zero quando a leitura do endpoint falha e converte o endereço com `to_v4()`; esse mesmo `remote_ip` é exigido antes de `Ban::acceptConnection` e `tryAdmitConnection`. Portanto, o código atual não abre listener IPv6 e não há bypass IPv6 no desenho presente. Acrescentei em `test_connection_admission.py` uma regressão de fonte para impedir que um listener IPv6 seja ativado sem revisar o modelo do limitador; os oito testes direcionados e a suíte Python completa (107 testes) passaram. Se IPv6 for habilitado no futuro, o limitador e as cotas por IP precisam adotar chave consciente da família e do prefixo IPv6 antes da exposição.

## Revisão da serialização de callbacks — 01/10/2026

Revisei o pressuposto de concorrência do `CallbackGeneration`. O token invalida a entrega de callbacks que ainda estão na fila, mas não é um lock que interrompa uma função já iniciada; isso agora está explícito no comentário de `callbackgeneration.h`. Nos fluxos examinados, o Scheduler entrega callbacks ao `g_dispatcher`, mensagens que chegam por `ProtocolGame` também viram `addGameTask`, e `/reload` executa pela fila do jogo; o encerramento põe a tarefa de shutdown na barreira do Dispatcher antes da limpeza. Assim, os callbacks e as invalidações dos caminhos de reload/shutdown analisados são serializados pela thread do jogo. Os testes de fonte existentes verificam esse roteamento e a ordem de invalidação. Isso não prova toda interleaving de runtime: build integrado e TSan continuam pendentes.

## Inventário de dependências e auditoria NuGet — 01/10/2026

Busquei manifests de dependências e referências NuGet no checkout: não há `vcpkg.json`, arquivo de configuração vcpkg, `conanfile`, `packages.config`, `packages.lock.json` nem `PackageReference` nos projetos C#. `CMakeLists.txt` resolve módulos do sistema (`luajit`, `pugixml`, `mysqlclient`, `gmp`), Threads e Boost com mínimo 1.53; sem lockfile, o conjunto efetivo depende do host de build.

Reexecutei `dotnet list <projeto> package --vulnerable --include-transitive --format json` nos cinco `.csproj` versionados. Todos terminaram com código zero, listaram `https://api.nuget.org/v3/index.json` como fonte e retornaram somente o caminho do projeto, sem entradas de pacote ou avisos de vulnerabilidade. Como nenhum projeto declara `PackageReference`, isso confirma a ausência atual de dependências NuGet declaradas; não audita o SDK/runtime .NET instalado nem dependências nativas do servidor. O build CMake integrado continua indisponível neste host, portanto as versões concretas e a superfície de CVEs das bibliotecas C++ permanecem sem verificação.

## Compatibilidade do padrão C++ — 01/10/2026

O build principal declara `CMAKE_CXX_STANDARD 11`. Os testes C++ isolados deste host foram compilados com MSVC `/std:c++14`; isso não prova compilação em C++11, pois MSVC não oferece um modo estrito C++11 e não há GCC/Clang instalado. Uma busca estática por APIs e sintaxes pós-C++11 comuns (`make_unique`, `exchange`, `optional`, `string_view`, `filesystem`, lambdas genéricas, init-capture e `if constexpr`) não encontrou usos de código correspondentes em `src/`/`tests/` — as correspondências de `=` eram comentários da API Lua. É uma triagem, não substitui compilar os mesmos alvos sob o padrão efetivo do CMake em Linux.

## Telemetria cumulativa da fila SQL — 01/10/2026

Estendi `QueueMetricsSnapshot` com contadores cumulativos saturantes de tarefas
enfileiradas e removidas. O log periódico agora os registra separadamente para
Dispatcher, Scheduler e DatabaseTasks; diferenças entre amostras permitem
estimar vazão de entrada/saída sem registrar consultas ou dados de jogadores.
DatabaseTasks registra também a idade do item pendente mais antigo, medida com
`steady_clock`; o helper retorna zero para um instante de amostra anterior ao
enqueue. Para operações concluídas, registra contagem e soma/máximo de duração
em microssegundos desde antes da chamada ao driver até o retorno. Isso inclui
espera pelo mutex do handle; uma consulta parada ainda em execução não atualiza
essas estatísticas enquanto não retornar. O máximo é vitalício desde o início
do processo; os contadores cumulativos permitem calcular taxas/médias entre
amostras. O teste C++ isolado passou em MSVC x64 com `/W4 /WX /O2 /std:c++14`, e
os seis testes Python de ligação/contabilidade da fila passaram. `git diff --check`
passou, com avisos de normalização CRLF em outros arquivos já modificados. Essas
métricas não limitam nem rejeitam tarefas e não estimam a memória total; build
integrado C++11, CTest e medição de staging continuam pendentes.

## Ordem FIFO no shutdown da fila SQL — 01/10/2026

`Game::shutdown` executa no Dispatcher e chama `DatabaseTasks::shutdown`. Antes,
o shutdown marcava o worker como terminado e fazia `flush()` imediatamente. O
worker retira a primeira tarefa e solta `taskLock` antes da consulta; portanto,
se ele ainda não tivesse adquirido `Database::databaseLock`, o shutdown podia
executar uma tarefa posterior primeiro. O mutex serializa o uso do handle, mas
não garante FIFO. O caminho de ban expirado enfileira `INSERT` no histórico e
depois `DELETE` do banimento, mostrando uma dependência concreta. Não reproduzi a
ordenação contra MariaDB.

Corrigi a sequência para marcar término sob `taskLock`, liberar o mutex, notificar
e fazer `join()` do worker antes de travar novamente e drenar a lista restante.
Assim, uma tarefa já removida termina antes das tarefas pendentes do `flush`, e
`addTask` recusa novos itens após a transição. A regressão de fonte confirma
join antes de flush; a suíte Python completa passou com 108 testes.
`git diff --check` passou. Build integrado, TSan e teste de ordenação em banco descartável
continuam pendentes.

## Rechecagem do ambiente de validação — 01/10/2026

`Resolve-DnsName staging.tibia74.tech` retornou que o nome DNS não existe. A
consulta de comandos do PowerShell não localizou `cmake`, `codeql`, `cppcheck`,
`luacheck`, `shellcheck` ou `actionlint` no `PATH`. O WSL listou somente
`docker-desktop`, e `docker info` terminou com erro; não há daemon Linux utilizável
para executar o ambiente de build/staging registrado no projeto. Não contatei
nenhum serviço de staging/produção nesta rechecagem. Os testes locais continuam
válidos dentro dos limites documentados, mas não substituem build C++ integrado,
MariaDB descartável, carga em staging ou resultados CodeQL hospedados.

## Admissão de conexão antes do estado por IP — 01/10/2026

Revisei a ordem de `ServicePort::onAccept`: antes, `Ban::acceptConnection`
alocava/atualizava a entrada IPv4 de rate limit antes de `tryAdmitConnection`.
Logo, uma conexão já recusada por limite global ou por IP ainda podia consumir
uma das 65.536 entradas; uma rajada distribuída podia manter novos IPs recusados
até a expiração de slots. O teste nativo existente confirma a recusa quando a
tabela está cheia e nenhum slot expirou.

Inverti a ordem: o socket precisa primeiro reservar o limite de conexões ativas;
só então usa o rate limiter. O ramo existente de fechamento forçado solta a
reserva se a origem estiver bloqueada. Atualizei a regressão de integração para
verificar que ambos os gates ocorrem antes da criação do protocolo. Isso elimina
consumo de estado por sockets já rejeitados pelos caps de conexão, mas não impede
uma rajada de muitos IPs únicos admitidos sequencialmente nem a pressão global de
consultas de login (`AUTH-04`). Build C++ integrado e carga de staging continuam
pendentes. Recompilei `connection-admission-tests.cpp` com MSVC x64 usando
`/W4 /WX /O2 /std:c++14 /permissive-` e `/analyze`; ambos os executáveis passaram. A suíte Python
completa passou com 108 testes, incluindo a regressão de ordem em `onAccept`.
Esses resultados cobrem os helpers e invariantes de fonte; não exercitam o
`ServicePort` real com sockets nem medem o efeito de um flood distribuído.

## Reexecução de scanners locais — 01/10/2026

Actionlint 1.7.12 analisou os workflows atuais sem diagnósticos. ShellCheck
0.11.0 analisou os três scripts `deploy/**/*.sh` sem diagnósticos. Gitleaks
8.30.1 escaneou o diretório de trabalho (110,45 MB) e encontrou cinco matches
`generic-api-key`, todos em resumos JSON sob `build/`, ignorado pelo Git. Sem
imprimir valores, confirmei que os matches eram campos `source_sha256` de 64
caracteres hexadecimais; o digest de `data/actions/scripts/others/key.lua`
confere com o arquivo atual, e os de `.github/workflows/secret-scan.yml` são
fingerprints de versões anteriores do workflow. Reexecutei Gitleaks nas pastas
`src`, `tests`, `data`, `deploy`, `docs`, `.github` e `tools`; todas retornaram
sem leaks. Assim, os cinco resultados iniciais são falsos positivos de hashes
nos artefatos ignorados, não segredos; não acrescentei suppressions ao scanner.

## Pré-checagem de isolamento antes da manutenção — 01/10/2026

Na revisão dos dois runners de staging, encontrei que o runner legado verificava
que staging estava parado, mas não confirmava a conta Unix nem os arquivos de
ambiente do serviço antes de parar produção. Centralizei a precondição em
`staging_safety.py`: o serviço precisa usar `tfs74-stage`, carregar
`/etc/imperium772-staging.env` e não carregar `/etc/imperium772.env`. Ambos os
runners agora falham antes da janela de manutenção se a condição não for
atendida. Regressões cobrem configuração permitida e recusas de usuário root,
ambiente de produção e mistura dos arquivos.

Os 21 testes direcionados de staging/recovery passaram; a suíte Python completa
passou com 111 testes e os cinco arquivos alterados passaram `py_compile`.
`git diff --check` passou com avisos de normalização CRLF em arquivos já
modificados no checkout. Esta mudança ainda não foi aplicada a um host: staging
remoto não está acessível nesta sessão. Build C++ integrado, CTest/sanitizadores,
CodeQL e validação dinâmica continuam pendentes.

## Expansão dos testes C++ locais — 01/10/2026

Localizei o MSVC 14.51.36231 do Visual Studio 18 fora do `PATH` e compilei
manualmente, a partir dos fontes atuais, 11 alvos independentes do TFS core:
callback generation, métricas de filas, admissão de conexões, limitador de logs
remotos, fila do scheduler, identificadores SQL, escape de banco, nomes de
scripts, conversão concorrente de hora local, rate limiter de status e fila de
saída de conexões. Todos passaram com `/W4 /WX /O2 /std:c++14 /permissive-`.
Recompilei sete desses alvos críticos com `/analyze`; compilação e execução
passaram sem diagnósticos. Os artefatos ficaram em `build/`, ignorado pelo Git.

Essa validação não é um build do servidor: faltam CMake e headers/dependências
Boost no host. Tentei também compilar `talkaction-policy-tests.cpp`; o compilador
parou em `src/otpch.h` por ausência de `boost/asio.hpp`. O projeto pede C++11,
mas o modo disponível do MSVC é C++14; portanto, essa execução também não
confirma compatibilidade estrita com C++11. O C++/Linux integrado e seus testes
com sanitizer continuam sem evidência local.

## Build local do launcher e rechecagem do CI remoto — 01/10/2026

O build Release do launcher WinForms e os projetos
`LauncherSafetyTests` e `LauncherIntegration` compilaram no .NET SDK 10.0.401,
sem warnings ou erros. O harness de segurança passou com verificação de
assinatura/URL, I/O limitado, traversal ZIP, adulteração pós-extração, instalação
limpa, preservação de userdata e rollback; o teste de lifecycle do formulário
passou sem abrir janela nem iniciar o jogo. O teste `LauncherIntegration` foi
compilado, mas não executado porque exige um manifesto HTTPS de staging real e
o host de staging não resolve no DNS.

Consultei os runs privados de Actions ligados ao PR #9, commit
`62970d9544e746312dae3396743187aea3b11019`. Na tentativa original, os sete jobs
de build/regressão e os jobs de Cppcheck, lint, secret scan e CodeQL foram
marcados como falha poucos segundos após iniciar; a API reporta `runner_name`
vazio, zero passos e não há logs dos jobs. Portanto esses estados não provam
falha no código nem aprovam a execução dos scanners. Reexecutei apenas o job
CodeQL C++; às 05:16 UTC de 01/10, setup, checkout e inicialização haviam passado,
mas a etapa Analyze ainda estava em execução. O job C# permaneceu falho sem
passos e ainda não foi repetido. O commit do PR é o HEAD, mas 103 arquivos do
worktree têm alterações staged/unstaged/untracked; os resultados do PR não
validam essas edições locais.

Actionlint e ShellCheck locais passaram novamente; a suíte Python passou com
111 testes. Os seis testes Lua do workflow passaram, assim como a compilação
sintática em memória dos 750 arquivos Lua rastreados e `php -l` nos sete arquivos
PHP rastreados.

O job CodeQL C++ terminou às 05:20 UTC com falha na etapa de upload. O log mostra
que setup, checkout, inicialização, extração, queries e geração de SARIF foram
executados; o GitHub recusou o envio com `Code scanning is not enabled for this
repository`. O job C# continuou sem passos e não foi reexecutado. A API confirma
que `djowww/antigas-tfs` é privado e pertence a uma conta pessoal. A matriz de
disponibilidade do GitHub exige organização com GitHub Code Security para
CodeQL em repositórios privados; não vou alterar a visibilidade nem transferir
o repositório sem decisão explícita. O CLI local também não foi usado: não há
arquivo de licença rastreado, e os termos da distribuição permitem a análise
sem licença Enterprise apenas de código sob licença OSI ou pesquisa acadêmica.
Ver [disponibilidade do Code Scanning](https://docs.github.com/en/code-security/tutorials/implement-supply-chain-best-practices/securing-code)
e [termos do CodeQL CLI](https://github.com/github/codeql-cli-binaries).

O build integrado, CodeQL C#, execução dos demais jobs hospedados e carga/staging
permanecem em aberto.

## Retomada e nova validação — 01/10/2026

Reexecutei a suíte Python completa no worktree atual usando o runtime Python
empacotado pelo Codex: 111 testes passaram (`unittest discover -s tests -p
'test_*.py'`). O comando Python padrão do Windows não está disponível neste
host; o runtime empacotado executou a suíte normalmente.

Também executei novamente os 18 binários de regressão nativos já compilados
em `build/security-native-tests-20261001` e
`build/security-native-analyze-20261001`; todos passaram. Os relatórios e
objetos soltos do MSVC foram movidos para
`build/security-audit-msvc-artifacts/`, que está coberto pelo `.gitignore`;
nenhum fonte ou resultado de teste foi removido.

Recompilei o launcher Release e o projeto `LauncherIntegration` no .NET
10.0.401, sem warnings/erros; `LauncherSafetyTests` e
`LauncherFormLifecycle` passaram. O teste de integração continua sem execução
porque depende de um manifesto HTTPS de staging real. Actionlint 1.7.12 e
ShellCheck 0.11.0 terminaram sem diagnósticos. Gitleaks 8.30.1 voltou a
encontrar zero leaks nas pastas atuais de código, testes, dados, implantação,
documentação, workflows, ferramentas e arquivos de configuração raiz listados
na varredura. PHP 8.3.35 passou `php -l` nos sete arquivos rastreados; os seis
testes Lua de CI relacionados a economia, lâmpada, banimento e persistência
passaram. Permanecem sem evidência o build C++ integrado, CodeQL hospedado após
habilitar Code Scanning, a integração HTTPS e os ensaios em staging.

Após a avaliação de exposição, o usuário autorizou tornar `djowww/antigas-tfs`
público, incluindo histórico e logs de Actions. Gitleaks 8.30.1 encontrou zero
leaks nos 175 commits alcançáveis; `config.lua` está ignorado e não rastreado.
O checkout atual continua privado: o GitHub abriu a tela de reautenticação por
e-mail antes de efetivar a mudança. A skill de controle do navegador impede que
o agente opere o fluxo de autenticação; é necessária a conclusão manual pelo
titular. Ainda não reexecutei CodeQL após a mudança, pois a mudança não ocorreu.
O worktree tem alterações locais não publicadas e foi preservado.

Após a reautenticação manual do titular, confirmei pela API do GitHub que o
repositório está público. Reexecutei os workflows no commit do PR
`62970d9544e746312dae3396743187aea3b11019`: regressões PHP/Lua/Python,
launcher Windows, ShellCheck/actionlint e Gitleaks concluíram com sucesso.
Builds C++ release, hardened, ASan/UBSan e TSan, fuzz smoke e Cppcheck estavam
em execução na última consulta. O rerun CodeQL C++ também estava analisando; o
rerun C# foi recusado enquanto esse run estava ativo e precisa ser tentado
depois. Esses resultados pertencem ao commit do PR, não às mudanças locais
ainda não enviadas. O PR #9 continua aberto contra `main`.

Atualização dos resultados hosted: CodeQL C++ e C# concluíram com sucesso no
PR #9 e ambos enviaram SARIF. A extração C++ usou `build-mode: none`, portanto
não substitui análise baseada em compilação; o autobuilder C# registrou que os
feeds NuGet não estavam acessíveis, embora a análise e o upload tenham
terminado com sucesso. A página de code scanning mostra zero alertas abertos
para o PR. O branch padrão ainda não havia sido analisado; iniciei o run
workflow-dispatch #59 no commit `f764c0a` de `main`, que estava em fila.

Release, ASan/UBSan, TSan, fuzz smoke, regressões PHP/Lua/Python, launcher,
Cppcheck, lint e Gitleaks passaram no commit do PR. O job release-hardened
falhou em um dos 26 testes: `scheduler-duplicate-event-id` excedeu o timeout
de 10 segundos; os outros 25 passaram. Rerodei somente esse job para
determinar se é intermitência; a nova tentativa ainda não tinha resultado.

Atualização hospedada — 01/10/2026, 05:59 UTC

O usuário perguntou se poderá devolver o repositório ao modo privado depois. Sim: a configuração pode ser revertida. A documentação atual do GitHub avisa que forks existentes do período público permanecem públicos e são separados do repositório de origem; Code Scanning deixa de estar disponível em uma conta pessoal depois da volta a privado, salvo acesso/licença organizacional compatível. O repositório foi confirmado pela API como público.

O CodeQL manual da branch `main` terminou com sucesso no commit `f764c0a`. A análise C++ continuou em `build-mode: none`, e o autobuilder C# informou indisponibilidade dos feeds NuGet; SARIF foi processado e o workflow terminou sem falha. CodeQL no PR #9 também havia terminado com sucesso, com os mesmos limites de build. Isso não é uma análise baseada em compilação.

Reexecutei o job `release-hardened` do run `36760119195`; a segunda tentativa reproduziu o mesmo timeout de 10 s em `scheduler-duplicate-event-id` (testes 25/26 passaram). O restante da matriz C++ hardened, release, ASan/UBSan, TSan, fuzz smoke, scripts e launcher passou. A falha reproduzida impede considerar a matriz totalmente verde e deve ser investigada antes do merge.

O PR #9 segue aberto e mergeable na revisão hospedada `62970d9544e746312dae3396743187aea3b11019`, mas o worktree local mantém 69 arquivos modificados e 20 untracked. Os resultados de Actions acima são da revisão já hospedada, não dessas alterações locais. O worktree continua sem commit/push; não houve alteração do servidor online.

## Revalidação e correção do worker do scheduler — 01/10/2026, 15:15 UTC

Na revisão do timeout recorrente em `scheduler-duplicate-event-id`, a instrumentação do worker mostrou que, depois de acordar uma fila vazia por causa de um evento recém-inserido, o fluxo caía diretamente no despacho e não voltava a esperar o prazo do evento. Corrigi `Scheduler::threadMain` para reavaliar a fila no começo do loop. O teste C++ agora verifica que o callback de um evento novo não roda antes do seu prazo. Também substituí os hooks POSIX globais do fixture por sincronização padrão com `std::mutex`, `std::thread` e `std::promise`, evitando que o próprio teste intercepte as esperas sob TSan.

No commit `fae0dc0388f4721561e386c8128b9d279d8a7516`, a matriz hospedada terminou integralmente com sucesso: builds e 31 testes CTest em release, release-hardened, ASan/UBSan e TSan; fuzz smoke do parser; regressões PHP/Lua/Python; build e testes do launcher; Cppcheck; ShellCheck/actionlint; Gitleaks; e CodeQL C++/C#. A análise CodeQL foi enviada ao GitHub, usando `build-mode: none` nas linguagens compiladas, portanto não equivale a uma análise baseada nos comandos completos de compilação. Localmente, os 106 testes da suíte Python segura passaram e `git diff --check` passou.

Verifiquei novamente `staging.tibia74.tech` em 01/10; a consulta DNS não retornou registros. Não foi possível fazer teste dinâmico contra staging (carregamento real, login/dispatch ou persistência no banco). Nenhuma alteração ou reinício foi feito no servidor de produção. O PR #9 continua direcionado a `main` para integração após esta revisão.

O repositório está público por autorização do titular e pode voltar a privado depois. O GitHub informa que forks criados enquanto público permanecem públicos e separados do repositório de origem; a disponibilidade de Code Scanning em repositórios privados depende do plano/organização aplicável. [Documentação do GitHub sobre visibilidade](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/managing-repository-settings/setting-repository-visibility).
