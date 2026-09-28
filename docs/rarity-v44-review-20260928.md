# Revisão e publicação de raridades v44 — 28/09/2026

## Resultado

Publicado no servidor principal `imperium772.service`. Mundo online às **13:41:01 BRT**; cliente e download do site publicados às **13:42:50 BRT**. Verificação final: serviço ativo, PID 123120, nenhum reinício automático e portas públicas 7173/7174 acessíveis.

- Servidor: `56ebec1f1dfcd845f78af0b60ac2f1d6cb4848e4ecec0d65fdb3b19494d3bdc1`.
- Cliente v44: `cb48865197d7982b0cd0effbbcac302fc573da0a6f568226dfebfe74adcdb145`, 25.723.308 bytes.
- Download: https://tibia74.tech/Antigas-7.4-Client-v44.zip
- Chance ativa: 10% por equipamento elegível criado pelo loot; pesos e regras em [item-rarity.md](item-rarity.md).

## Correções da revisão

1. Separação entre estado da raridade e habilidades nativas dos equipamentos.
2. Recalcular HP/mana/speed quando nível ou atributos base mudam; retirada exata do bônus.
3. Conceder bônus apenas no slot correto e preservar metadados nas transformações.
4. Look mostra ataque/defesa efetivos; wands recebem aumento no dano real.
5. Validar os metadados persistidos e excluir itens empilháveis/munição do sorteio.
6. Exportar a API de raridade entre sandboxes dos módulos do cliente e corrigir constantes de slots no Lua do servidor.
7. Tokens contra respostas antigas, paginação em lotes, restauração após arraste e limpeza de bordas/tooltips.
8. Market recusa itens cujos atributos não conseguiria entregar. NPCs protegem raros e só pagam após remoção bem-sucedida dos comuns.

## Testes executados

| Verificação | Resultado |
|---|---|
| Compilação C++ Release com LuaJIT na VPS | Passou |
| Núcleo C++ real, sem mundo/banco/listeners | **4.048 checks**, passou |
| Interface/protocolo, Lua 5.2 e LuaJIT | **105 checks por runtime**, passou |
| OTClient OpenGL real, cópia offline do ZIP v44 | **67 checks**, saída 0 |
| Market, refino, rollback e preservação de metadados | Passou nos dois runtimes Lua |
| Regressões Market/rate limit, Achievements, Bestiary, Quest Log e contagem PvP | Passaram nos dois runtimes Lua |
| Interface de Achievements | Passou nos dois runtimes Lua |
| Bônus online | Passou em LuaJIT |
| Fallback com leitura/escrita opaca da tag 39 | Compilou; **10 checks** passaram |
| Teste com personagem comum descartável no principal | Passou em **34,51 segundos** |
| Download público, manifesto, link do site e SHA-256 | HTTP 200 e hash conferido |

O teste real de produção cobriu seis itens, opcode 127, Look, inventário/mochila, HP 150↔158, mana 100↔105, speed 220↔242, sword 10↔15, ataque 18 e defesa 17. Dois ciclos de login/logout preservaram metadados e atributos base, sem duplicar itens. Cleanup confirmado; consulta posterior encontrou zero contas `rarityprobe_*@test.invalid`.

O pacote usa a release pública v43 como base: 680 entradas, apenas cinco conteúdos alterados (init, LEIA-ME e três módulos de raridade). CRC e sintaxe dos Lua do ZIP conferidos. As definições de itens, vocações e NPC usadas no C++ tiveram hashes iguais aos arquivos de produção.

O teste no cliente real não fez login; o teste de rede em produção usa um cliente de protocolo direcionado, sem renderização. Combate, resistência e probabilidades foram exercitados no núcleo C++, sem combates no mundo principal. Não foi repetido o teste de carga de 50 jogadores nesta release. As fixtures antigas de UI Bestiary/Quest Log exigem um cliente completo e não foram contadas como testes offline de Lua; a suíte de bônus online usa APIs Lua 5.1 e foi validada em LuaJIT.

## Ocorrência no encerramento da versão anterior

O desligamento começou às 13:37:01 BRT. O banco confirmou o logout do GM; não houve mensagem de falha final ao salvar personagem nem de COMMIT ambíguo. Durante `Map::save`, o binário anterior registrou erro de comunicação 2013. Depois de `Shutting down... done!`, permaneceu uma thread main em execução, com portas fechadas e nenhuma sessão/transação no banco.

Após snapshot privado e essas verificações, o processo residual 116325 foi encerrado de forma dirigida às 13:40:34, liberando a atualização. As tabelas de casas eram InnoDB, com zero casas pertencentes a jogadores; `tile_store` continha 6.262 linhas/75.152 bytes. Não é possível confirmar pelo log que a última tentativa de salvamento das casas concluiu. Desde a inicialização da v44 até a verificação final, não foram encontrados novos erros de banco/Lua no journal.

**Pendência operacional:** `Game::saveGameState` ignora o retorno de `Map::save`; tentativas imediatas podem coincidir com o cooldown de reconexão. Tratar essa falha e investigar o encerramento com stack trace e mapa completo em uma manutenção específica. A causa do processo residual ainda não foi determinada. Os testes de raridade não validam esse desligamento completo.

## Backup e recuperação

- Backup privado no host: `/root/antigas-backups/rarity-v44-20260928T163701Z` (configuração, binário/scripts anteriores e snapshots do banco; gzip validado).
- Artefatos e logs no host: `/opt/antigas-rarity-20260928`.
- Fallback compatível compilado: `/opt/antigas-rarity-20260928/compat-build/tfs`.
- SHA-256 do fallback: `f162636767c452481b7ff1bdd540679589357e3ecf38302a3b2e9788c12f6363`.

O fallback preserva a tag 39 e desativa os efeitos novos; deve ser usado com scripts anteriores e em manutenção. O binário antigo sem patch não lê raridades. Não restaurar um banco antigo automaticamente: isso descartaria progresso posterior.

Relatórios resumidos sem credenciais estão em `docs/validation/rarity-v44/`. Logs brutos locais ficam em `backup/QA-rarity-v44-20260928/`, fora do pacote público.
