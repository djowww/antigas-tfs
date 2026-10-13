# Compatibilidade com Tibia 7.4

O Antigas combina um recorte clássico com sistemas próprios. As alterações abaixo retiram comportamentos cuja introdução posterior ao 7.4 foi documentada pela CipSoft. Isso não certifica uma reprodução integral do jogo, do mapa ou do protocolo de 2004.

## Correções documentadas

| Tema | Recorte aplicado | Fonte oficial |
| --- | --- | --- |
| Port Hope nos barcos | Retirada a opção de viagem para Port Hope nos capitães que ofereciam esse destino e ajustadas suas listas de destinos. Mapa, cidades, spawns, quests e outros acessos permanecem como antes desta auditoria, conforme o escopo escolhido para o Antigas. | [Tibia 7.5](https://www.tibia.com/news/?id=329&subtopic=newsarchive) |
| Móveis | Desativadas a venda e a abertura dos construction kits stock. Móveis vendidos diretamente mantêm seus IDs e preços; não foi inventada uma tabela substituta de mobiliário 7.4. | [Solutions Against Cheaters](https://www.tibia.com/news/?id=327&subtopic=newsarchive) |
| Addons e viagem | Desativadas as transações de addons e as viagens imediatas de capitães em estado `BUSY`. Saudações, fila e viagens normais para destinos mantidos foram preservadas. | [Tibia 7.8](https://www.tibia.com/news/?id=399&subtopic=newsarchive) |
| Banco | Retirados os comandos de saldo, depósito e saque dos NPCs. A troca de moedas continua disponível. | [Tibia 7.9](https://www.tibia.com/news/?id=437&subtopic=newsarchive) |
| Combate | Desativados os handlers de combate das wands/rods stock e as magias de gelo identificadas. Spear e throwing star deixam de usar chance de quebra. | [Tibia 7.6](https://www.tibia.com/news/?id=355&subtopic=newsarchive), [Tibia 8.1](https://www.tibia.com/news/?id=643&subtopic=newsarchive), [anúncio de quebra dos arremessáveis](https://www.tibia.com/news/?id=327&subtopic=newsarchive) |
| Cliente e fala | Bloqueadas hotkeys de itens no modo `OLD_SCHOOL`; hotkeys de texto continuam disponíveis. O mute é verificado antes da tentativa de conjurar uma magia, e a configuração de referência deixa de desligar o limitador de mensagens. | [Tibia 7.8](https://www.tibia.com/news/?id=399&subtopic=newsarchive), [Tibia 7.3](https://www.tibia.com/news/?id=271&subtopic=newsarchive) |

## Sistemas e progresso preservados

Shared experience e seu bônus continuam como escolhas customizadas do Antigas. Sua preservação não os classifica como recursos originais do 7.4. Permanecem também os sistemas próprios, incluindo Market, raridade, conquistas, Bestiary e trainers customizados.

O saldo persistido e as APIs internas de banco continuam disponíveis para as integrações customizadas, mesmo com o atendimento bancário retirado dos NPCs. A retirada de um fluxo não apaga seus códigos, definições de itens, storages, outfits, itens possuídos ou progresso já salvo. Construction kits stock já possuídos permanecem como itens, mas sua abertura está desativada; os pacotes dos trainers customizados mantêm seu funcionamento.

## Limites para administradores

- O mapa e todos os spawns foram preservados. A opção de Port Hope nos barcos está desativada; a geografia e os outros acessos não foram alterados. Esse escopo não certifica um mapa integral do Tibia 7.4.
- O aluguel fica temporariamente desativado na configuração de referência, com `houseRentPeriod = "never"`. O anúncio do [banco no 7.9](https://www.tibia.com/news/?id=437&subtopic=newsarchive) comprova a posterioridade do débito bancário, mas não certifica a regra anterior de cobrança. Não foi criado um método substituto.
- As missões e os requisitos da Explorer Society foram preservados. Não houve retirada de Plant Collection, outras missões de área ou mudança de storages/ranks.
- Throwing knife e small stone mantêm o comportamento existente porque não foi documentado um algoritmo anterior suficiente para reconstruí-lo. Fórmulas e valores não comprovados também não são apresentados como números oficiais do 7.4.
- A compatibilidade integral do cliente e do protocolo com o 7.4 não foi certificada. Os atalhos `ADDRESS` para destinos mantidos e os IDs/preços do mobiliário direto também não receberam certificação histórica por estas fontes.

As fontes vinculadas sustentam as diferenças específicas descritas. Elas não validam automaticamente todo o conteúdo restante do Antigas.
