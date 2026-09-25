# Sistemas legados removidos

- Removidos os oito NPCs Tusker, seus pontos de spawn, diálogo de tarefas, contador de abates e comandos `!tasks`.
- Removido o bounty hunter: comando `!hunt`, eventos de abate e anúncio periódico, biblioteca de implementação e respectivos registros de inicialização.
- Removida a coleta automática customizada de frascos vazios: comando `!vial`, timer, evento de logout e funções de login.
- Removida a chance de dano crítico do arquivo de configuração, do carregador C++ e do cálculo de armas.
- Preservado `src/tasks.cpp`: é infraestrutura interna de filas do servidor, sem relação com tarefas de NPCs.
- Preservados o uso normal de frascos e o diálogo nativo dos NPCs para comprar, usar ou vender vials.
- A rotina de aposentadoria verificou as pendências antes da publicação. Nenhum personagem tinha vials guardados pela função removida e o sistema bounty não tinha recompensas pendentes. A tabela vazia do bounty foi removida após cópia do schema no backup; saldos/storages de jogadores não foram apagados.
