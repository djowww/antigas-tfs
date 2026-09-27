# Shop clássica — cliente v33

Patch exclusivamente visual sobre o cliente público v32. O catálogo, preços,
points, histórico, compra, confirmação e protocolo permanecem no servidor sem
alterações. A categoria Outfits já estava aposentada; não foi recriada.

Arquivos do cliente: `modules/game_shop/shop.otui` e `shop.lua`. O release troca
somente esses dois arquivos e o número `APP_VERSION` de 32 para 33 em `init.lua`.
Sprites, banner, executáveis e demais módulos são idênticos aos da v32.

Medidas principais: janela 750×500 px, sidebar 210 px, bloco de points 68 px,
banner 54 px, categorias 36 px, produtos 56 px, área fixa do sprite 44×44 px
com sprite original 32×32, BUY 48×22 px e botões do rodapé 22 px de altura.
O preço e o botão têm colunas estáveis, independentes do comprimento do nome.
Descrições extensas preservam o texto integral em tooltip.

Validação offline no OTClient real (sem login nem compra concluída): abertura,
fechamento, troca de categorias de 1/2/5/6/10 itens, títulos/descrições longos,
preços de 1/2/3 dígitos, alinhamento de sprites/preço/BUY, confirmação de BUY
cancelada, Buy Points (callback presente, URL não aberta), histórico, atualização
de points, scrollbar e última linha visível. Geometria testada em 800×600,
1024×768 e 1366×768. Teste automatizado: `tests/shop-ui-tests.lua`.

Empacotamento/publicação: `deploy/shop-v33-release.py`. Ele exige o SHA-256 da
v32 pública, valida a sintaxe Lua na VPS, compara cada entrada do ZIP novo com
a v32 e publica ZIP, link e manifesto de forma atômica, preservando backups.
