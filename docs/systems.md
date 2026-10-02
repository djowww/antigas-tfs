# Sistemas do Antigas

Este guia apresenta o comportamento dos sistemas customizados presentes no código. As interfaces dependem dos módulos correspondentes do cliente Antigas; o servidor usa protocolo 7.72 com extensões próprias.

## Market

O Market permite criar ofertas de compra e venda em **Gold** ou **Antigas Coins**. Uma oferta reserva os itens ou a moeda necessários e pode ser negociada parcialmente. Cancelamentos e negociações geram entregas pendentes, recolhidas pelo personagem na interface do Market.

O histórico registra compras, vendas e cancelamentos junto às operações do sistema. A coleta parcial preserva o saldo pendente; a coleta completa registra a entrega como recolhida. Gold é enviado ao banco do personagem; itens e Antigas Coins são entregues ao depot da sua cidade.

O catálogo oferece filtro de itens próprios e os melhores preços das ofertas ativas por moeda. Esses valores representam as ofertas disponíveis, sem misturar Gold e Antigas Coins nem garantir que uma negociação será concluída naquele preço.

As ofertas representam tipo e quantidade de item. Equipamentos raros ou refinados são recusados, pois carregam atributos individuais que esse formato não preserva. Containers, fluidos e itens com identificadores especiais também têm restrições. Wands e rods de combate são bloqueadas para novas ofertas; a fishing rod permanece disponível.

O banco precisa das migrações `market.sql`, `market-v2.sql` e `market-v3.sql`, nessa ordem, para uma instalação nova do Market. Consulte a [documentação SQL](../data/sql/README-market.md) para os detalhes da estrutura.

Referências: [`market.lua`](../data/creaturescripts/scripts/market.lua) e [`economy.lua`](../data/lib/custom/economy.lua).

## Achievements

As conquistas acompanham objetivos do personagem e guardam progresso e recompensas em storages persistentes. O servidor calcula os contadores, os marcos e os prêmios; o cliente exibe o progresso e solicita o resgate.

O painel destaca metas próximas e recompensas pendentes. Ao atingir uma meta, o direito ao prêmio fica registrado antes da tentativa de entrega. Se faltar capacidade ou espaço, a recompensa permanece pendente para resgate posterior. Repetir o pedido não entrega novamente um prêmio já recebido.

Referências: [`antigasAchievements.lua`](../data/lib/custom/antigasAchievements.lua) e [`achievements.lua`](../data/creaturescripts/scripts/achievements.lua).

## Bestiary

O Bestiary mantém contadores de abates por monstro e personagem. Os dados são persistidos no servidor e enviados ao cliente para apresentação do catálogo e do progresso. Monstros invocados por jogadores não contam para esse progresso.

Cada Bestiary concluído concede um bônus permanente de **0,2% de experiência**. O servidor controla os contadores e o total de conclusões.

Referências: [`antigasBestiary.lua`](../data/lib/custom/antigasBestiary.lua) e [`bestiary.lua`](../data/creaturescripts/scripts/bestiary.lua).

## Diário de quests

O diário acompanha as descobertas do personagem. Listas, busca, filtros e detalhes incluem apenas quests conhecidas e etapas aceitas ou concluídas; o servidor filtra as respostas antes de enviá-las ao cliente.

O catálogo interpreta os estados existentes das quests. Uma missão sem sinal de início pode aparecer somente quando sua conclusão é registrada. As notas apresentam o progresso conhecido, e recompensas específicas são mostradas apenas quando os registros permitem identificar o item recebido.

Esse diário organiza a informação para o jogador sem substituir os scripts originais de NPCs, missões e recompensas.

Referências: [`questJournal.lua`](../data/lib/custom/questJournal.lua), [`questCatalog.lua`](../data/lib/custom/questCatalog.lua) e [`questlog.lua`](../data/creaturescripts/scripts/questlog.lua).

## Raridade de equipamentos

Equipamentos elegíveis do loot de monstros podem receber raridade e atributos adicionais. Há cinco tiers: **incomum, raro, épico, lendário e mítico**. A raridade pertence ao exemplar do item e acompanha sua persistência e transformações.

O cliente utiliza bordas, cores e tooltips para apresentar os atributos. A identificação visual aparece no inventário, nos containers abertos e nos itens no chão. As integrações de comércio protegem itens com atributos individuais contra negociações que perderiam esses dados.

Consulte [raridade de equipamentos](item-rarity.md) para conhecer os pesos, bônus, itens elegíveis e detalhes da persistência.

## Loot

O canal **Loot** abre ao entrar no jogo e pode ser reaberto na lista de canais. Cada morte gera uma mensagem para o dono do loot e os membros da party naquele momento. Os nomes dos itens usam a raridade de cada exemplar, permitindo cores diferentes para itens do mesmo tipo.

Drops com raridade também geram um efeito e texto animado para os destinatários com o corpo visível. A cor do aviso corresponde à maior raridade encontrada.

Referências: [`loot.cpp`](../src/loot.cpp) e [`loot.lua`](../data/chatchannels/scripts/loot.lua).

## Combate e conteúdo legado

As [fórmulas de combate](combat-formulas.md) descrevem os cálculos do núcleo e seus pontos de integração. Scripts de magias e definições de monstros podem estabelecer valores específicos.

Os antigos sistemas Tusker, bounty hunter, coleta customizada de frascos vazios e chance legada de crítico foram retirados. O [resumo dos sistemas removidos](retired-legacy-systems.md) explica o escopo dessas remoções.
