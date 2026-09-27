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
`8a7cae4c7d70840e9b85ec351540fa674e6264989ce063592167d2b01d73ee5c`.
Os metadados do PNG no ZIP são fixos para que Windows e Linux produzam o
mesmo pacote byte a byte.

Publicada em 27/09/2026: https://tibia74.tech/Antigas-7.4-Client-v34.zip.
ZIP local e da VPS com SHA-256 idêntico; manifesto e link público na v34,
download HTTP 200 (25.717.880 bytes), PHP sem erro de sintaxe e serviço
`imperium772` ativo. Backup da página/manifesto no estágio protegido da VPS.
