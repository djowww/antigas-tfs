# Inicialização do ambiente

Cada tarefa na nuvem já é isolada. Use os checkouts existentes em `/workspace`; não crie um Git worktree salvo se o usuário pedir explicitamente. Preserve arquivos versionados, testes, manifests e lockfiles. Antes e depois de qualquer atualização, confira o status Git dos três repositórios e preserve mudanças do usuário.

O fluxo preparado é: build e testes do núcleo C++/Lua do Antigas, aplicação FIFA com SQLite e OCR local, e componente idle do Ragnarok com API, Vite e MariaDB. Node 24 deve estar disponível. Dependências e helpers ficam em `/workspace/cloud-onboarding`; builds ficam nos caminhos ignorados dos repositórios. Processos e o estado do daemon Docker devem ser reiniciados ou verificados em cada tarefa.

## Ferramentas e reinstalação

Para usar CMake, LuaJIT, headers e bibliotecas C++ locais em cada shell:

```bash
source /workspace/cloud-onboarding/native-env.sh
```

O FIFA usa pnpm 10.32.0; o Ragnarok usa pnpm 11.25.0. Use os executáveis específicos abaixo. Não substitua seus lockfiles ou manifests.

Quando houver necessidade de reinstalar ou atualizar dependências/builds, execute o script completo salvo na configuração, cuja cópia local é:

```bash
bash /workspace/antigas-tfs/tools/cloud-onboarding/install.sh
```

Ele usa índices Debian assinados, valida SHA256 dos pacotes, instala bibliotecas localmente, mantém instalações Node com lockfile congelado e recompila o Antigas quando a versão das bibliotecas muda. O build nativo usa dois jobs. Não desative verificação TLS, assinaturas, hashes ou assertions para contornar falhas.

## FIFA

Primeiro confira se a instância desejada já responde em `127.0.0.1:5174` e se seus dados ficam em `/workspace/cloud-onboarding/fifabet-data`. Se precisar iniciá-la, execute como processo de longa duração, com log próprio:

```bash
bash /workspace/cloud-onboarding/start-fifabet.sh > /workspace/cloud-onboarding/logs/fifabet-server.log 2>&1
```

O helper usa o diretório `/workspace/fifabet-arena`, host `127.0.0.1`, porta 5174, armazenamento fora do site e pagamentos desconfigurados. Um `instance.lock` existente exige verificar o PID, o comando, o diretório de execução e a ausência de outro servidor usando esses dados. Remova somente um lock comprovadamente obsoleto. SIGTERM no processo dessa instância encerra o servidor e remove seu lock; não sinalize um PID reutilizado por outro processo.

Validação de prontidão, em outro comando:

```bash
node --input-type=module - <<'JS'
import assert from 'node:assert/strict';
const response = await fetch('http://127.0.0.1:5174/api/v1/status');
assert.equal(response.status, 200);
const status = await response.json();
assert.equal(status.available, true);
assert.equal(status.storage, 'sqlite');
assert.equal(status.recognition.available, true);
const page = await fetch('http://127.0.0.1:5174/');
assert.equal(page.status, 200);
assert.match(await page.text(), /<!doctype html>/i);
console.log('FIFA: UI, SQLite e OCR disponíveis.');
JS
```

Testes existentes, no diretório `/workspace/fifabet-arena`:

```bash
/workspace/cloud-onboarding/fifabet-tools/node_modules/.bin/pnpm test
/workspace/cloud-onboarding/fifabet-tools/node_modules/.bin/pnpm audit --prod --audit-level=high
```

Baseline: 404 testes passaram; auditoria sem vulnerabilidades conhecidas. Foram validadas 20 requisições funcionais, incluindo contas, salas sem pagamento, chat, upload e OCR real. Não existem scripts de build ou typecheck. OAuth e Pix precisam de configuração própria e não foram habilitados.

## Ragnarok idle

Inicie os serviços com o helper idempotente, a partir de qualquer diretório:

```bash
bash /workspace/cloud-onboarding/ragnarok/start.sh
```

Ele verifica o socket Docker local, restaura a imagem MariaDB pelo arquivo `/workspace/cloud-onboarding/ragnarok/mariadb-image.tar` quando necessário, cria ou inicia `codex-ragnarok-db`, aguarda sua saúde e inicia o serviço de diagnóstico de assets, a API e o Vite. Depois exercita UI, catálogo e sessão persistida pelas duas entradas HTTP. As portas são MariaDB 3307 em loopback, API/UI compilada 3339, Vite 5173 e diagnóstico de assets 8081. A porta Vite 5173 corresponde às origens POST autorizadas pelo código.

Esse banco local de desenvolvimento usa `DB_HOST=127.0.0.1`, `DB_PORT=3307`, `DB_NAME=hercules`, `DB_USER=root`, `DB_PASSWORD=` e volume `codex-ragnarok-db-data`. O volume existente é preservado; seu estado não é garantido em um novo snapshot. Se estiver ausente, o banco é inicializado novamente e a API aplica migrations e cria um perfil de desenvolvimento. A imagem usa ID imutável registrado no helper. Não remova volumes ou dados existentes para contornar falhas.

Validação independente:

```bash
node /workspace/cloud-onboarding/ragnarok/smoke.mjs
```

Para encerrar somente os processos de aplicação criados pelo helper, mantendo o banco:

```bash
bash /workspace/cloud-onboarding/ragnarok/stop.sh
```

Comandos existentes, no diretório `/workspace/ragnarok-old-times-idle/idle`:

```bash
bash /workspace/cloud-onboarding/ragnarok/pnpm.sh build
bash /workspace/cloud-onboarding/ragnarok/pnpm.sh typecheck
DB_HOST=127.0.0.1 DB_PORT=3307 DB_NAME=hercules DB_USER=root DB_PASSWORD= IDLE_DB_TEST=1 \
  bash /workspace/cloud-onboarding/ragnarok/pnpm.sh test --maxWorkers=2
```

Baseline: build e smoke passaram; 64 testes passaram, 21 falharam e um foi pulado (86 total). Os sete testes SQL passaram. Typecheck falha em `idle/tests/engine-fixture.ts:15` porque falta `Challenge.category`. As 21 falhas são divergências existentes nos testes de classes/recuperação, seleção de evento de combate, animação de morte e catálogo. O repositório Ragnarok registra o baseline e o diagnóstico em `docs/cloud-environment.md`. Investigue novas falhas; não trate esse baseline como aprovação de testes futuros nem altere o código durante onboarding.

Os assets originais do cliente são opcionais e ausentes. A resposta 404 `ASSET_UNAVAILABLE` para um asset ausente é esperada. O teste de integração com GRFs está pulado. Hercules e o cliente clássico completos não foram construídos.

## Antigas

O build reutilizável e os testes do núcleo executam sem banco de jogo:

```bash
bash /workspace/cloud-onboarding/build-antigas.sh
source /workspace/cloud-onboarding/native-env.sh
cd /workspace/antigas-tfs
ctest --test-dir build --output-on-failure
for content_name in playerbars-ui economy-inventory lamp-state-parser lamp-state-action ipban-security account-type-persistence rarity-economy achievements-ui rarity-visuals ground-rarity-bolt; do
  luajit "tests/${content_name}-tests.lua"
done
PYTHONPATH=tests PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  test_load_test test_staging_safety test_staging_recovery test_recovery_script \
  test_database_task_thread_affinity test_container_house_removal test_scheduler_lifetime \
  test_raid_callback_lifetime test_spawn_callback_lifetime test_global_event_callback_lifetime \
  test_npc_callback_lifetime test_report_bug_path test_coin_page_cache \
  test_dispatcher_shutdown_order test_connection_shutdown_serialization test_connection_admission \
  test_lamp_state_parser test_deployment_preconditions test_connection_output_queue \
  test_sql_identifier test_database_escape test_queue_metrics test_workflow_checkout_credentials \
  test_script_filename test_talkaction_authorization test_account_type_persistence \
  test_staff_ban_commands test_remote_log_rate_limiter -v
```

Baseline: build passou, 32 testes C++ passaram, 108 testes Python passaram e dez scripts Lua passaram. Sanitizers/fuzzer, portal PHP e launcher Windows não fizeram parte deste fluxo.

`build/tfs` executa e lê o `config.lua` local ignorado, criado apenas se ausente. O servidor de jogo não está online: falta uma chave RSA privada compatível, schema base completo e configuração de banco. A inicialização já foi exercitada e rejeitou explicitamente a ausência de `ANTIGAS_RSA_KEY_FILE`. Obtenha os materiais próprios e siga `/workspace/antigas-tfs/docs/building.md` antes de iniciar um mundo. O arquivo RSA deve conter os primos decimais no formato documentado, fora do Git; não é PEM. Não invente credenciais nem use chaves públicas padrão. Depois que os pré-requisitos estiverem disponíveis, exporte somente o caminho em `ANTIGAS_RSA_KEY_FILE` e execute `./build/tfs` na raiz do checkout; confirme a resposta do protocolo antes de declarar o mundo online.

## Limites e conservação

Nenhum segredo ou domínio adicional é necessário para os fluxos locais validados. A autenticação HTTPS Git existente funcionou. Não imprima valores de credenciais; verifique somente nomes/presença e operações específicas. Instruções salvas não publicam o ambiente. Publicação e restauração em uma nova tarefa precisam de confirmação própria. Não crie links de preview para localhost; faça requisições locais e relate os resultados em texto.
