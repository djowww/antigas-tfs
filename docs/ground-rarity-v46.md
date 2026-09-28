# Raridade sobre o próprio item — v46

Correção posterior: [reaplicação imediata ao sair da tela e voltar](ground-rarity-scroll-fix.md). Compatível com o mesmo cliente v46.

Equipamentos raros recebem uma camada de cor no sprite, inclusive quando estão no chão. A cor usa os metadados reais de cada exemplar: verde para incomum, azul para raro, roxo para épico, amarelo para lendário e vermelho para mítico. Itens comuns mantêm a aparência normal.

A camada também aparece no inventário e nos containers abertos, junto às bordas de raridade existentes. A textura original continua visível.

O destaque do chão é visível para quem pode ver aquele item, independentemente de quem o soltou. Ele acompanha movimentos e desaparece ao recolher o item. Equipamentos do mesmo tipo, inclusive empilhados no mesmo quadrado, podem ter raridades e cores diferentes.

## Funcionamento

O opcode **129**, negociado por `H|1`, transporta estados completos de cada tile com raridades visíveis. Cada registro contém posição, índice nativo da pilha, ID do item e tier; uma sequência crescente protege a ordem. Somente o servidor escolhe as raridades. O cliente vincula imediatamente a mensagem ao objeto nativo do mapa; uma posição antiga não é usada posteriormente para escolher outro item igual.

O servidor atualiza o estado depois dos pacotes nativos de alteração do mapa. Uma verificação limitada à área visível recupera itens já existentes, trocas de tela e mudanças de atributos; o reenvio periódico também recupera objetos recriados pelo cliente.

No mapa, `g_map.colorizeThing` aplica a cor ao sprite e `g_map.removeThingColor` limpa tanto a cor quanto a referência mantida pelo renderizador. A camada de destaque do cursor e dos corpos permanece independente. Nos widgets de inventário, `UIItem:setColor` aplica a mesma cor; a reutilização do widget restaura branco antes de receber novos metadados.

Limites: 256 tiles com raridade por jogador; somente os dez slots que o protocolo do mapa pode transmitir; mensagens abaixo de 8.192 bytes; uma verificação periódica no cliente. Nenhum conteúdo de mochila, corpo fechado, depósito ou inventário alheio entra nas mensagens de chão.

O brilho dos corpos ainda fechados continua sendo controlado pelo [sistema Loot v45](loot-v45.md). A cor dos equipamentos usa estado separado. Não há alteração de chance de drop, bônus, preço, fórmula de dano ou formato de persistência.

## Validação e operação

As fixtures exercitam pilhas com sprites iguais e tiers diferentes, itens comuns, mochila fechada, recolhimento e devolução ao chão, alteração de atributos, pacotes inválidos, limite de slots e troca de sessão. O cliente nativo é executado em cópia isolada, com uma conexão dummy exclusivamente em localhost para inicializar o jogador nativo e conferir a renderização. Essa fixture não usa conta real nem conecta ao servidor do jogo.

O smoke em produção usa somente personagem e itens temporários. O ciclo real de soltar/recolher exige ausência de outros jogadores online e um tile comprovadamente livre; quando essas condições não existem, o relatório identifica essa etapa como não executada. O teste de negociação e a cobertura isolada continuam separados.

Os resultados da release ficam em `validation/ground-rarity-v46/`. O pacote parte do ZIP v45 arquivado e sobrepõe apenas os arquivos revisados. A instalação usa `deploy/deploy-ground-rarity-v46.py`, com backup privado antes da parada, snapshot depois do salvamento, verificações em produção e publicação do manifesto ao final.

### Resultado da publicação — 28/09/2026

- Núcleo C++: **4.105 verificações** aprovadas.
- Lua 5.2 e LuaJIT: **36 verificações de chão**, **105 de raridades**, **38 de interface Loot** e **68 do canal Loot**, além das regressões de economia, Market, conquistas, Bestiary, Quest Log e PvP.
- Cliente nativo extraído do ZIP final: **42 verificações**, frame renderizado e saída 0; transporte dummy restrito a localhost.
- Produção: negociação e troca de sessão de chão, canal Loot e movimentação/persistência dos bônus aprovados; personagens e itens temporários removidos.
- O ciclo físico de soltar/recolher no chão em produção foi **pulado**, pois nenhum tile adjacente pôde ser confirmado como piso livre. A cobertura de pilhas, movimentação e cor permaneceu nas fixtures isoladas.
- Salvamento e parada limpos às **17:44:23 UTC**; servidor online às **17:44:59 UTC**, sem reinício automático.
- Backup privado: `/root/antigas-backups/groundrarity-v46-20260928T174422Z`, com arquivos anteriores e banco antes/depois da parada.

Cliente: `Antigas-7.4-Client-v46.zip`, SHA-256 `5b87c70945a1fbc6cd4228f1d4f4b0f30c6ca2c369c88f3bab28a6ca8b6f2fc4`.

Servidor: SHA-256 `eceb3937795720583a724e46ef45715faca7b9adb865bccbdd183edce5929686`.
