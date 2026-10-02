# Sistemas legados removidos

- Removidos os oito NPCs Tusker, seus pontos de spawn, diálogo de tarefas, contador de abates e comandos `!tasks`.
- Removido o bounty hunter: comando `!hunt`, eventos de abate e anúncio periódico, biblioteca de implementação e respectivos registros de inicialização.
- Removida a coleta automática customizada de frascos vazios: comando `!vial`, timer, evento de logout e funções de login.
- Removida a chance de dano crítico do arquivo de configuração, do carregador C++ e do cálculo de armas.
- Preservado `src/tasks.cpp`: é infraestrutura interna de filas do servidor, sem relação com tarefas de NPCs.
- Preservados o uso normal de frascos e o diálogo nativo dos NPCs para comprar, usar ou vender vials.
