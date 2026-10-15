# Compatibilidade com Tibia 7.4

O Antigas combina um recorte clássico com sistemas próprios. As alterações abaixo retiram comportamentos cuja introdução posterior ao 7.4 foi documentada pela CipSoft. Isso não certifica uma reprodução integral do jogo, do mapa ou do protocolo de 2004.

## Correções documentadas

| Tema | Recorte aplicado | Fonte oficial |
| --- | --- | --- |
| Port Hope nos barcos | Retirada a opção de viagem para Port Hope nos capitães que ofereciam esse destino e ajustadas suas listas de destinos. | [Tibia 7.5](https://www.tibia.com/news/?id=329&subtopic=newsarchive) |
| Móveis | Desativadas a venda e a abertura dos construction kits stock. Móveis vendidos diretamente mantêm seus IDs e preços; não foi inventada uma tabela substituta de mobiliário 7.4. | [Solutions Against Cheaters](https://www.tibia.com/news/?id=327&subtopic=newsarchive) |
| Addons e viagem | Desativadas as transações de addons e as viagens imediatas de capitães em estado `BUSY`. Saudações, fila e viagens normais para destinos mantidos foram preservadas. | [Tibia 7.8](https://www.tibia.com/news/?id=399&subtopic=newsarchive) |
| Banco | Retirados os comandos de saldo, depósito e saque dos NPCs. A troca de moedas continua disponível. | [Tibia 7.9](https://www.tibia.com/news/?id=437&subtopic=newsarchive) |
| Combate | Desativados os handlers de combate das wands/rods stock e as magias de gelo identificadas. Spear e throwing star deixam de usar chance de quebra. | [Tibia 7.6](https://www.tibia.com/news/?id=355&subtopic=newsarchive), [Tibia 8.1](https://www.tibia.com/news/?id=643&subtopic=newsarchive), [anúncio de quebra dos arremessáveis](https://www.tibia.com/news/?id=327&subtopic=newsarchive) |
| Cliente e fala | Bloqueadas hotkeys de itens no modo `OLD_SCHOOL`; hotkeys de texto continuam disponíveis. O mute é verificado antes da tentativa de conjurar uma magia, e a configuração de referência deixa de desligar o limitador de mensagens. | [Tibia 7.8](https://www.tibia.com/news/?id=399&subtopic=newsarchive), [Tibia 7.3](https://www.tibia.com/news/?id=271&subtopic=newsarchive) |
| Monstros posteriores | Retirados 90 registros de Cyclops Drone, Cyclops Smith, Frost Dragon e Crystal Spider. Espécies sem prova de posterioridade não foram excluídas por suposição. | [Cyclops Drone e Smith](https://www.tibia.com/news/?id=623&subtopic=newsarchive), [Frost Dragon e Crystal Spider](https://www.tibia.com/news/?id=521&subtopic=newsarchive) |

## Sistemas customizados

Spears não quebram e cada arremesso transfere uma unidade da mão para o tile de destino, tanto no acerto quanto no erro; é necessário recuperá-las para continuar usando a mesma pilha. Essa regra não foi estendida às throwing stars: o destino anterior à mudança de 2005 ainda não foi confirmado em fonte primária.

Shared experience e seu bônus continuam como escolhas customizadas do Antigas. Sua preservação não os classifica como recursos originais do 7.4. Permanecem também os sistemas próprios, incluindo Market, raridade, conquistas e Bestiary.

As APIs internas de banco continuam disponíveis para as integrações customizadas, mesmo com o atendimento bancário retirado dos NPCs. As arenas, seu NPC de ingressos e todos os trainers customizados permanecem desativados.

## Limites de compatibilidade

- As correções oficiais listadas não certificam a origem histórica do mapa, dos spawns ou dos objetos de chão.
- O aluguel está desativado na configuração de referência, com `houseRentPeriod = "never"`. O anúncio do [banco no 7.9](https://www.tibia.com/news/?id=437&subtopic=newsarchive) comprova a posterioridade do débito bancário, mas não certifica a regra anterior de cobrança. Não foi criado um método substituto.
- A Explorer Society mantém suas missões, requisitos, storages e ranks, incluindo Plant Collection e outras missões de área.
- Throwing knife e small stone mantêm o comportamento existente porque não foi documentado um algoritmo anterior suficiente para reconstruí-lo. Fórmulas e valores não comprovados também não são apresentados como números oficiais do 7.4.
- A compatibilidade integral do cliente e do protocolo com o 7.4 não foi certificada. Os atalhos `ADDRESS` para destinos mantidos e os IDs/preços do mobiliário direto também não receberam certificação histórica por estas fontes.

As fontes vinculadas sustentam as diferenças específicas descritas. Elas não validam automaticamente todo o conteúdo restante do Antigas.
