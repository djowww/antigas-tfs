# Abertura imediata e brilho sutil de raridade — v47

## Correção do atraso

Ao abrir um corpo, o cliente recebia primeiro a lista normal de itens e enviava uma consulta Lua separada para descobrir a raridade de cada um. Essa ida e volta pela rede deixava os itens comuns por alguns milissegundos antes de aplicar a cor.

Agora `ProtocolGame::sendContainer` inclui os metadados no mesmo pacote que abre ou atualiza o container. O cliente processa os itens e seus tiers no mesmo fluxo. Containers longos são divididos em blocos de até 40 registros; cada bloco usa índices absolutos e o cliente só o aplica se ele ainda corresponder à página visível. A consulta existente continua atendendo atualizações individuais de itens e mudanças de página.

O envio usa o extended opcode 127 já negociado pelos clientes OTC. Clientes clássicos não recebem o segmento adicional.

## Efeito visual

No chão, o sprite de cada item raro alterna lentamente entre a cor original da raridade e um tom ligeiramente mais claro. O ciclo usa a verificação compartilhada que já mantém as referências dos itens do mapa atualizadas; não cria um temporizador por item. A textura pixelada continua visível e as cores do inventário e das bordas permanecem estáveis.

## Validação

- Raridade/container: **109 verificações em Lua 5.2 e 109 em LuaJIT**.
- Raridade no chão: **82 verificações em Lua 5.2 e 82 em LuaJIT**.
- Cliente nativo com o ZIP final: **54 verificações**, screenshot renderizado e conexão de teste restrita a localhost.
- Build Release na VPS e teste C++ do núcleo: **79.076 verificações aprovadas**.
- Pacote cliente: `Antigas-7.4-Client-v47.zip`, SHA-256 `A831E6280927B28D557FE41909FE0046970C93B016F2D3BBC5372FBF76E64C11`.

## Publicação — 28/09/2026

- Servidor ativo: SHA-256 `747d954b2ff080f8b284912552a60a09963700b8e3a7a275e2f9e36cc0728000`.
- Serviço `imperium772.service` ativo, sem reinícios automáticos; portas **7173 e 7174** abertas.
- Download público: [Antigas 7.4 v47](https://tibia74.tech/Antigas-7.4-Client-v47.zip); manifesto e checksum correspondem ao ZIP publicado.
- Backup privado: `/root/antigas-backups/rarity-container-v47-20260928T201634Z`, incluindo snapshots do banco antes e depois da parada graciosa.
- A primeira validação do encerramento não reconheceu as reticências do log; o executável ainda não havia sido trocado. O servidor anterior foi reiniciado e confirmado saudável, a validação foi ajustada, e então a instalação v47 foi concluída sem encerramento forçado.
