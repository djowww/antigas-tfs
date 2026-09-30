# Auditoria de threads do banco — 30/09/2026

## Escopo e decisão

Revisão de `main` em `fa24974fdb53724eb59e65292ceaf2db04f1d170`, de
`Database`, `DatabaseTasks`, inicialização do cliente SQL e testes existentes.
A revisão desta área não consultou produção, executou probes, abriu conexão SQL
nem modificou código, CMake ou workflows.

**A ausência de `mysql_thread_init()` na thread I/O não é um bug de estado
local de thread para MariaDB Connector/C 3.3.17.** As funções de inicialização e
encerramento por thread dessa biblioteca são vazias. Portanto, esse candidato
não fundamenta crash ou vazamento para a biblioteca confirmada no host.
`DBTHREAD-01` da [auditoria histórica](SECURITY_AUDIT.md) deve ser interpretado
como compatibilidade com clientes que exigem essa inicialização, sem atribuir
o mesmo requisito à implementação MariaDB atual.

## Identificação da biblioteca

A [observação do host](host-security-observation-2026-09-30.md) registra
`libmariadb.so.3` e o pacote Ubuntu
`libmariadb3 1:10.6.23-0ubuntu0.22.04.1`. O responsável pela rodada confirmou
`mysql_get_client_info() == "3.3.17"` às **06:07:47 UTC de 30/09/2026** e informou
a captura sanitizada `validation-artifacts/host-installed-packages.json`.
Essa consulta foi feita pelo responsável; nesta revisão usei essa evidência
fornecida e fontes públicas.

A [página oficial do pacote fonte Ubuntu](https://packages.ubuntu.com/source/jammy-updates/mariadb-10.6)
associa essa versão ao pacote que produz `libmariadb3`. A tag aplicada
`applied/1%10.6.23-0ubuntu0.22.04.1` do repositório Ubuntu resolve para
`dba30706b1382f8f8f31a34d5f23e8baeb0cfbf3`. Seu
[CMake do conector, linhas 53–55](https://git.launchpad.net/ubuntu/+source/mariadb-10.6/plain/libmariadb/CMakeLists.txt?id=dba30706b1382f8f8f31a34d5f23e8baeb0cfbf3)
declara **3.3.17**. A versão `10.6.23` identifica o pacote de servidor;
`3.3.17` identifica o Connector/C incluído.

## Fluxo confirmado no servidor

| Caminho | Evidência em `fa24974` | Consequência para esta revisão |
|---|---|---|
| Startup | `src/otserv.cpp:87-90,122-125,174-189` inicia dispatcher/scheduler e executa `mainLoader` no dispatcher. O loader conecta o singleton e inicia `DatabaseTasks`. | O singleton e a conexão de tarefas são inicialmente preparados no dispatcher. |
| I/O | `src/otserv.cpp:108`, `src/server.cpp:60-67`, `src/connection.cpp:267` executam o primeiro pacote na thread principal de I/O. | `ProtocolLogin` consulta IP em `src/protocollogin.cpp:197`; `ProtocolGame` consulta IP e autentica em `src/protocolgame.cpp:338,354`. |
| Singleton | `src/database.cpp:48,135-160`; `src/ban.cpp:33-39`; `src/iologindata.cpp:90-107` | O I/O efetivamente usa o singleton criado/conectado pelo dispatcher, sem chamada própria de init/end de thread. A observação do fluxo está correta. |
| Worker SQL | `src/databasetasks.h:51`, `src/databasetasks.cpp:28-41,60,78-100` | O worker possui um **Database separado**. `start()` conecta esse objeto no dispatcher; o worker chama init/end. `flush()` também pode usar esse objeto no encerramento. Esse handle é compartilhado entre os callers desse objeto separado. |
| Serialização | `src/database.cpp:37-40,94-132,135-180`; `src/database.h:103-106` | O mutex protege conexão, par query/store-result, escaping e leitura de insert-id. Uma transação mantém o mutex até commit/rollback. A revisão não identificou uso simultâneo desse handle nesses caminhos. |

## Implementação primária aplicável

Na [fonte aplicada do pacote Ubuntu](https://git.launchpad.net/ubuntu/+source/mariadb-10.6/plain/libmariadb/libmariadb/mariadb_lib.c?id=dba30706b1382f8f8f31a34d5f23e8baeb0cfbf3):

- `mysql_thread_init`, linhas **4466–4469**, retorna zero sem alocar ou
  configurar estado da thread.
- `mysql_thread_end`, linhas **4471–4473**, tem corpo vazio.
- `mysql_init`, linhas **1322–1325**, chama `mysql_server_init`.
- `mysql_server_init`, linhas **4431–4440**, usa `pthread_once` em POSIX e
  `InitOnceExecuteOnce` no Windows para a inicialização global.

A [documentação atual de mysql_thread_init](https://mariadb.com/docs/connectors/mariadb-connector-c/api-functions/mysql_thread_init)
e a [de mysql_thread_end](https://mariadb.com/docs/connectors/mariadb-connector-c/api-functions/mysql_thread_end)
confirmam que as funções são no-op e estão depreciadas desde Connector/C 3.0.
As páginas ainda contêm resumos/avisos antigos sobre memória local de thread,
contraditórios com a descrição atual. A implementação versionada acima resolve
essa ambiguidade para a versão auditada. A inicialização global automática
protegida por `once` também impede atribuir à ausência de
`mysql_library_init()` explícito a corrida de startup descrita para outro cliente.

## Condição que permanece para outro fornecedor

A [documentação Oracle MySQL 8.4](https://dev.mysql.com/doc/c-api/8.4/en/c-api-threaded-clients.html)
exige estado por thread, inclusive para a thread que apenas usa uma conexão
criada por outra; também orienta inicialização global antes das threads ou sob
mutex. O CMake atual pede `pkg-config mysqlclient`, que pode resolver para
fornecedores diferentes. Assim, trocar o cliente pode tornar o caminho I/O
incompatível com esse contrato. A chamada existente no worker não cobre o I/O
nem o ciclo completo de todas as threads que usam a API.

Essa condição deve ser tratada em uma migração de dependência: identificar o
cliente, cobrir init/end e falha de init em cada thread usuária, e revisar
startup/teardown. Não foi introduzida uma correção de produção para o candidato
refutado na versão MariaDB atual; as chamadas existentes continuam preservadas.

## Testes, limites e recomendação verificável

- `tests/test_database_task_thread_affinity.py` verifica presença e ordem de
  texto no worker. Não demonstra alocação de estado por thread, necessidade de
  inicialização no I/O nem comportamento da biblioteca linkada.
- `tests/login-gate-core-tests.cpp` executa core/parser/dispatcher reais, mas
  substitui `mysql_real_connect` e não executa uma consulta SQL real.
  `tests/ban-lookup-tests.cpp` usa uma interface de banco simulada. Esses testes
  validam suas regressões de login, sem comprovar contratos de thread do cliente.
- As rodadas de staging já documentadas exercitaram logins reais; continuam
  limitadas aos seus cenários e versões. Nenhum novo teste nativo foi executado
  nesta revisão documental, e não foi adicionado teste que espelha fonte.

**Recomendação:** encerrar o candidato de estado local de thread para
Connector/C 3.3.17 e vincular esta conclusão à identidade do cliente. No próximo
build isolado, registrar o fornecedor/versão da biblioteca efetivamente linkada
e o retorno de `Database::getClientVersion()` (`src/database.h:113-115`), já
impresso no startup (`src/otserv.cpp:180`). Se a dependência mudar para Oracle
MySQL ou um Connector/C legado, abrir a revisão de lifecycle antes da entrega.
A regressão adequada então deve executar `Database`/`DatabaseTasks` reais com o
cliente escolhido e banco descartável: preparar a conexão em uma thread,
consultar e consumir resultados em outra, processar callbacks e drenar/juntar
as threads no encerramento. Busca por chamadas na fonte não substitui esse
ensaio de comportamento.
