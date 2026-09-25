# Arquivos da correção Loot v17

Estes dois módulos acompanham o pacote completo do cliente v17. Não copie a pasta `tests` para o cliente distribuído. O pacote completo também altera `APP_VERSION` em `init.lua` de 16 para 17 e inclui `LEIA-ME-V17.txt`.

Para repetir a regressão: em uma cópia isolada do cliente completo, use um `APP_NAME` próprio em `init.lua` para não tocar nas configurações do jogador. Copie os três arquivos de `tests/` para a raiz dessa cópia e agende `dofile('/loot-tests.lua')` após `loadModules()`. Execute o cliente sem se conectar. O teste substitui funções de sessão somente nessa instância descartável e termina o processo automaticamente.

Esperado no log: `LOOT_V17_CLIENT_PASS checks=23` e `MARKET_V15_QA_PASS`, sem `FAIL`, `ERROR` ou `FATAL`. `wire-results.json` contém somente três avisos sem dados de conta, capturados de ações reais no servidor de QA. Os testes devem passar pelo despachante `ProtocolGame.onExtendedOpcode`, não chamar os callbacks de Loot diretamente.

Consulte `docs/loot-v17.md` para causa, escopo, hash do pacote e limitações.
