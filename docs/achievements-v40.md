# Achievements do cliente v40

O sistema guarda progresso e recompensas nos storages do personagem. O cliente
solicita apenas a leitura da lista e confirma que o jogador abriu o painel;
contadores, marcos e prêmios são calculados pelo servidor.

| Categoria | Marcos | Recompensa por marco |
| --- | --- | --- |
| Passos caminhados | 100, 1.000, 10.000, 100.000, 1.000.000 | +1, +2, +3, +4 e +5 de velocidade |
| Monstros derrotados | 100, 1.000, 10.000, 100.000, 1.000.000 | +1% de dano físico e mágico |
| Mortes | 1, 10, 100, 1.000, 10.000 | reduz em 1% a perda de experiência e skills ao morrer |
| Abates PvP | 1, 10, 100, 1.000, 10.000 | +1% de dano PvP |
| Level | 20, 50, 100, 150, 200 | um scroll de experiência de 25% por uma hora |
| Skills | 40, 60, 80, 100, 120 | arma de treino correspondente; Magic concede scroll de XP |

A contagem de passos usa o evento nativo disparado após cada movimento
concluído pelo próprio personagem; considera deslocamentos adjacentes e ignora
teletransportes. Bônus de ataque e perda na morte são aplicados no cálculo
central do TFS. As estatísticas de PvP contam apenas abates creditados
diretamente ao jogador.

Os IDs `17800–17808` guardam os contadores, bônus e notificações. A faixa
`17820–17901` guarda os prêmios já entregues de level e skill; ela foi
conferida contra as storages usadas pelo conteúdo Lua existente.

Na primeira entrada, mortes e abates PvP migram dos contadores históricos
`3001` e `3000`, respectivamente. Prêmios antigos de level/skill são
concedidos retroativamente; se a mochila estiver cheia, o servidor tenta
novamente na próxima entrada ou avanço.
