# Desenvolvimento no Codex Cloud

Este ambiente isolado está preparado para compilar e testar o núcleo C++/Lua do Antigas sem banco de jogo. Use o checkout existente; não é necessário criar outro worktree. Node não é necessário para esse fluxo. Preserve código, testes, manifests e lockfiles; mantenha configuração local e saídas de build fora do versionamento.

## Ferramentas e build

Os pacotes nativos já foram carregados em `/workspace/cloud-onboarding/native`: CMake, pkg-config, Boost system/filesystem, LuaJIT, PugiXML, bibliotecas cliente MariaDB/MySQL e GMP. O compilador C++ e Python 3 vêm do ambiente. Esse prefixo e os helpers abaixo são locais ao ambiente cloud, não arquivos deste repositório. Em outra máquina, instale as dependências conforme [building.md](building.md); restaure os helpers pela configuração de onboarding antes de usar os comandos cloud.

Ative as ferramentas em **cada shell**, inclusive para executar o binário e os testes:

```bash
source /workspace/cloud-onboarding/native-env.sh
cd /workspace/antigas-tfs
bash /workspace/cloud-onboarding/build-antigas.sh
```

O helper configura Release com os testes nativos habilitados e compila com dois jobs. As saídas ficam em `build/`, ignorado pelo Git. Quando os pacotes nativos mudam, ele recompila as saídas afetadas. Para reinstalar somente as dependências nativas neste ambiente, use `bash /workspace/cloud-onboarding/install-native.sh` e repita o build; a instalação valida assinaturas e hashes dos pacotes.

## Testes existentes

Na raiz do checkout, com `native-env.sh` carregado:

```bash
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

Validação no commit `27db8e2406e9e912bed56b0f20a6a2b7aec03586`: build nativo passou, 32 testes C++ do CTest passaram, 108 testes Python passaram e os dez scripts Lua acima passaram. Esse resultado registra a validação daquele commit; execute novamente após alterações. Sanitizers/fuzzer, portal PHP e launcher Windows não foram validados neste fluxo.

## Inicialização do jogo

O setup atende desenvolvimento e testes. O jogo completo permanece bloqueado até o operador fornecer uma chave RSA privada compatível, o schema base completo e a configuração local do banco, conforme [building.md](building.md). As tabelas em `data/sql/` não substituem o schema base.

Mantenha a chave e as credenciais fora do Git. O carregador RSA exige dois primos decimais de um par compatível com o cliente, no formato documentado; PEM não serve. Não invente chaves ou credenciais. Configure `config.lua` local e exporte apenas o caminho do arquivo em `ANTIGAS_RSA_KEY_FILE`. Com todos os pré-requisitos disponíveis e as ferramentas ativadas, execute `./build/tfs` na raiz do checkout e confirme a resposta do protocolo antes de considerar o mundo online.
