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

Shared experience e seu bônus continuam como escolhas customizadas do Antigas. Sua preservação não os classifica como recursos originais do 7.4. Permanecem também os sistemas próprios, incluindo Market, raridade, conquistas, Bestiary e trainers customizados.

As APIs internas de banco continuam disponíveis para as integrações customizadas, mesmo com o atendimento bancário retirado dos NPCs. Os pacotes dos trainers customizados mantêm seu funcionamento. As arenas e seu NPC de ingressos foram desativados.

## Referência do mapa e estado inicial

A estrutura de 7.849.464 tiles segue a referência legada selecionada, incluindo terrenos, montanhas, bordas e decoração fixa. A origem dessa referência não foi autenticada como mapa original do Tibia 7.4. Nenhum item solto ou inventário antigo de casa foi importado; estados de camas ocupadas foram normalizados. Os IDs dos itens e os 861 IDs de casas foram mantidos.

Foram preservados 221 templates de recompensa atuais compatíveis com os baús da referência. Seis baús cujo conteúdo usava itens já retirados permanecem como decoração sem recompensa. Registros de monstros cujo chão desapareceu com a substituição da geometria foram removidos, sem inventar novas coordenadas. A localização dos spawns restantes e dos itens de respawn não foi certificada por fontes oficiais de 7.4; candidatos soltos sem essa prova não foram importados.

O reset autorizado do ambiente de teste reinicia os personagens no nível 1 em Rookgaard. Contas, personagens, nomes e permissões permanecem; inventário, depot, quests, habilidades e economia dos personagens recomeçam. O servidor entrega o kit inicial no primeiro login. Preferências e presets do cliente são preservados.

## Limites para administradores

- A referência de geometria selecionada é distinta de uma autenticação histórica do mapa. As correções oficiais listadas não certificam um mapa ou todos os spawns originais do Tibia 7.4.
- O aluguel fica temporariamente desativado na configuração de referência, com `houseRentPeriod = "never"`. O anúncio do [banco no 7.9](https://www.tibia.com/news/?id=437&subtopic=newsarchive) comprova a posterioridade do débito bancário, mas não certifica a regra anterior de cobrança. Não foi criado um método substituto.
- As missões e os requisitos da Explorer Society foram preservados. Não houve retirada de Plant Collection, outras missões de área ou mudança de storages/ranks.
- Throwing knife e small stone mantêm o comportamento existente porque não foi documentado um algoritmo anterior suficiente para reconstruí-lo. Fórmulas e valores não comprovados também não são apresentados como números oficiais do 7.4.
- A compatibilidade integral do cliente e do protocolo com o 7.4 não foi certificada. Os atalhos `ADDRESS` para destinos mantidos e os IDs/preços do mobiliário direto também não receberam certificação histórica por estas fontes.

As fontes vinculadas sustentam as diferenças específicas descritas. Elas não validam automaticamente todo o conteúdo restante do Antigas.
