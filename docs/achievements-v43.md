# Integração de conquistas v43

## Progressão e interface

A visualização inicial mostra a primeira meta não entregue de cada categoria,
ordenada por proximidade e priorizando prêmios pendentes. Os 60 objetivos
permanecem acessíveis em All objectives. Cada linha mostra percentual e saldo.
Claim rewards fica habilitado apenas com prêmio pendente, conexão ativa e sem
requisição em andamento. O cliente preserva a lista durante resposta/timeout.

## Entrega e protocolo

As storages existentes de prêmios mantêm 1 para entregue e agora aceitam 2 para
pendente. Ao atingir a meta, o direito fica salvo antes de tentar entregar;
perda posterior de level/skill não o apaga. A entrega usa addItem(id,1,false)
para impedir queda no chão. Notificação de entrega e snapshot ocorrem após
registrar storage1. Login, avanço e resgate enviam um snapshot final em cinco
páginas, mesmo com muitas conquistas retroativas. Nenhuma storage nova.

O catálogo inclui ready boolean; clientes antigos ignoram o novo campo.
getProgress permanece somente leitura. claimRewards usa o mesmo limite de
uma requisição a cada dois segundos; nunca aceita progresso ou item do cliente.
Repetir resgate não entrega um prêmio já recebido. A v43 entende servidor sem
ready, mas o botão de resgate requer backend v43.

## Consistência

PvP não credita a própria morte, tanto no contador de conquistas como no legado.
A correção impede novos créditos; não remove retroativamente os históricos.
O texto do scroll agora corresponde à ação: 25% de XP por 3.600 segundos.
O bônus de ataque/PvP atual é aplicado a dano direto; a interface explicita isso.
A amplificação de dano periódico continua fora deste comportamento. Nenhum
valor de recompensa ou código C++ foi alterado.

## Validação

Regressões Lua: inventário cheio/parcial, queda de level/skill, idempotência,
leitura pura, limite de pacotes, agrupamento de 40 entregas, crédito PvP por ID,
filtros, botão de resgate, cooldown, timeout e âncoras OTUI sem ciclos.
Janela nativa conferida em perfil isolado com metas próximas e prêmio pendente.
Testes reais: achievements-live.py e achievements-claim-live.py, usando contas
temporárias comuns, removidas após confirmar logout.

Resultados em produção: 60 objetivos, cinco páginas, maior mensagem de
2.203 bytes; regressão de valores extremos até 2.274 bytes. O teste de prêmio
pendente usou mochila com peso acima da capacidade, reconectou após liberar
capacidade e confirmou exatamente um scroll entregue, mesmo abaixo do level
original. As duas contas temporárias foram removidas após logout.

Pendências também compõem o indicador do menu, inclusive quando recolhido;
abrir a janela limpa só avisos de entregas, mantendo os prêmios a receber.
