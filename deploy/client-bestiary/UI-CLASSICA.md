# Bestiary — interface clássica (v32)

## Escopo

Somente `modules/game_wiki/wiki.lua`, `wiki.otui` e `creature.otui` mudaram no cliente. As mesmas versões estão na pasta de distribuição `deploy/client-bestiary/modules/game_wiki`. Não houve alteração de banco, scripts do servidor, opcode 124, formato das mensagens, cálculo de kills ou limite de 1.000 abates. Sem dependências novas, alterações de sprites ou recompensas.

## Interface

- Cards de 132 px de altura (antes 155), separados por 4 px, sem a moldura de janela repetida dentro de cada card.
- Quatro colunas nas resoluções usuais. Abaixo disso, o número diminui para preservar a largura e os nomes, nunca aumenta para cinco.
- Área fixa de 64 × 64 para a criatura; o quadro voltado para sul usa seu tamanho original, limitado à área. Sem ampliação artificial. Sprites paradas, centralizadas e sem efeitos novos.
- Nomes em até duas linhas, com nome completo no tooltip.
- Barra fina em dourado acinzentado sobre fundo escuro; texto de kills e percentual inteiro truncado (347 = 34%).
- Conclusão: borda dourada discreta. Seleção: borda clara e fundo ligeiramente diferente; o clique continua abrindo os detalhes.
- Filtros locais: All; In Progress (1–999); Completed (1.000). Combinam com a busca literal, sem diferenciar maiúsculas e minúsculas.
- Busca no rodapé com `Search monster...`, botão pequeno de limpeza e mensagem quando não há resultados.
- Atualizações de progresso não recriam a grade quando os itens visíveis continuam iguais, preservam a rolagem e não reabrem uma janela fechada.
- Mudança de busca/filtro volta ao início da lista. A conclusão atualiza a inclusão nos filtros automaticamente.
- Eventos de redimensionamento e busca são desconectados no encerramento do módulo.
- Revisão para publicação: tooltips explicam os filtros; a lista de loot dos detalhes não é mais cortada em 200 caracteres e apresenta cada nome uma vez. Formatos vazios antigos são aceitos. Os drops originais não foram modificados.

## Preparação futura (somente visual)

- `STAGES = {100, 500, 1000}` controla três marcadores pequenos, sem novos campos persistidos.
- `stage1`, `stage2`, `stage3` indicam os marcos já alcançados pelos contadores existentes.
- `rewardBadgeSlot`: espaço de 10 × 10 px, invisível, sem sprite, tooltip de recompensa, clique ou entrega. Pode receber futuramente uma indicação de achievement, task ou Bestiary. O título já reserva margem para isso.
- Não existem botões de resgate, rewards inventadas ou integração nova com achievements/tasks.

## Validação

O teste `tests/bestiary-ui-tests.lua` roda no executável real, em cópia isolada e offline. Deve ser chamado ao final de `init.lua`, depois dos módulos, com `BESTIARY_QA_REPORT` apontando para um arquivo de relatório gravável. A cópia de QA precisa de `APP_NAME` próprio; não inclua o teste ou essas alterações de bootstrap no cliente distribuído.

São exercitados abertura/fechamento, clique/seleção/detalhes, pesquisa literal e limpeza, filtros, atualização de mensagens de progresso existentes, transição para completo, manutenção da rolagem, reset visual no logout e encerramento/reinicialização do módulo. Testes de geometria verificam nomes, textos de progresso, rodapé, scrollbar e última linha. Resoluções de teste: 480×360 (abaixo do mínimo público, somente na cópia de QA), 640×480, 800×600 e 1100×700.

Resultado final em 26/09/2026: todos os testes acima passaram. Quatro colunas em 640×480, 800×600 e 1100×700; duas em 480×360 para manter a leitura. A rodada final passou sem erro de sintaxe ou falha de callback detectada. Foi feita também conferência visual dos cards, seleção, conclusão e detalhes. A inspeção encontrou e corrigiu uma dependência circular de âncoras e a quebra de nomes após redimensionamento. As funções de pedido e leitura do opcode foram comparadas com a v31 e permanecem idênticas.

O mínimo do cliente público continua intacto. Nenhum teste se conecta à VPS ou escreve dados de personagem. A revisão foi publicada como v32 em 26/09/2026, sem reinício do servidor. A revisão final testou também as 138 listas de loot (incluindo dez com mais de 200 caracteres) e a mensagem das criaturas sem loot. Download, manifesto e hash verificados; detalhes da publicação no README.

Referência de compatibilidade consultada para dimensionamento das criaturas: [bindings do OTCv8](https://github.com/OTCv8/otcv8-dev/blob/master/src/client/luafunctions_client.cpp), além dos módulos locais existentes. A compatibilidade foi verificada no executável usado pelo Antigas.
