# Menu e botões v42

O OTUI adiciona filhos declarados pelo módulo aos herdados do estilo base.
A v41 criava um segundo `minimizeButton`: o herdado tinha tamanho zero e
recebia o callback de `UIMiniWindow:setup`; o ícone novo tinha 14 × 14 px,
mas nenhum callback. O teste anterior construía um único botão artificial.

A v42 usa um único cabeçalho próprio `menuToggle`, com callback explícito,
24 px de altura, largura do menu e texto `Menu [-]` / `Menu [+]`.
Ele utiliza minimize/maximize e a persistência existentes; o controle base
fica reservado às operações internas de UIMiniWindow. O menu recolhido tem
28 px. Botões têm 22 px de altura, margens alinhadas e seleção destacada.
Conquistas não lidas aparecem também no cabeçalho recolhido.

Validação: clique real para recolher e expandir numa cópia isolada do cliente,
sem login; preferência minimized=true gravada e restaurada após fechar e reabrir
a janela; o menu expandiu novamente e exibiu aviso de conquistas recolhido. A sessão
real do jogador permaneceu aberta. Teste de regressão carrega as declarações
OTUI e verifica os ids herdados, callbacks, expansão, largura e persistência.

Nenhum script ou executável de servidor foi alterado nesta versão.
