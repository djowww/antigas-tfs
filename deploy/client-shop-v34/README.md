# Shop clássica com brasão — cliente v34

Refinamento visual incremental sobre a v33. Substitui o banner azul com texto
grande pelo brasão A já existente em `Site/classic-assets/crest.svg`. A cópia SVG
está neste diretório como fonte; o cliente recebe somente seu PNG transparente
56×64, rasterizado com Sharp, sem geração de arte nova ou alteração de sprites.

O cabeçalho local identifica categoria e quantidade de ofertas, ou o histórico.
O saldo e o cabeçalho têm 68 px; as listas começam na mesma altura. As linhas
alternam discretamente o fundo. Só a categoria selecionada recebe destaque.
Preços, itens, confirmação, histórico, protocolo e servidor não foram alterados.
O logo preserva o link enviado pelo servidor, quando presente; a imagem de
publicidade remota não é mais baixada nem exibida nessa interface.

Arquivos do cliente:
- `modules/game_shop/shop.otui`
- `modules/game_shop/shop.lua`
- `data/images/antigas-shop-crest.png`
- `init.lua`: somente APP_VERSION 33 → 34.

Testes offline no OTClient real: categorias com 1/2/5/6/10 produtos, alinhamento
de colunas, sprites 32×32, nomes/descrições longos com tooltip, atualização de
saldo, histórico, abertura/fechamento, BUY com confirmação cancelada, presença e
remoção do link do cabeçalho, cabeçalho estável sem publicidade/Buy Points,
scrollbar e último produto inteiramente visível. Resoluções 800×600, 1024×768
e 1366×768. Inspeção visual do cliente e logs sem erros nesses testes.
Nenhuma compra real foi realizada. Fixture: `tests/shop-ui-tests.lua`.

Empacotamento: `deploy/shop-v34-release.py`. Exige a v33 pelo SHA-256, compara
cada entrada do ZIP e permite apenas as alterações acima. Não inclui fixture,
contas ou arquivos de desenvolvimento. Publicação mantém a v33 e backup da
página e do manifesto. Não requer reiniciar o servidor do jogo.

SHA-256 do pacote v34 validado localmente:
`e05268221d4eaf6b29233e7d2872b90c4407198466e064abdf04af1e9e88ec1c`.
