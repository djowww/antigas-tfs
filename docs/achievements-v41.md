# Achievements: catálogo e interface v41

A versão v40 montava um JSON com aproximadamente 9,3 KB para 60 conquistas,
mas `NetworkMessage::addString` aceita no máximo 8.192 bytes. O limite de
16.000 bytes no Lua deixava o pacote ser enviado incompleto; o cliente
permanecia em “Loading achievements...”. Os testes anteriores substituíam o
JSON por tabelas e não exercitavam esse limite real.

O servidor agora envia cinco páginas de 12 conquistas com `snapshotId`, `page`
e `pages`. Todas são serializadas e verificadas antes do envio, com limite
conservador de 7.000 bytes por mensagem. O cliente só substitui a lista após
receber um conjunto completo, rejeita páginas duplicadas/obsoletas e mantém
a lista anterior durante atualizações ou timeout. O envio inicial aguarda um segundo após o login para permitir a
negociação do protocolo; tentativas repetidas respeitam o intervalo do servidor.

A janela lista também as conquistas ainda não iniciadas, com meta, recompensa,
contador e barra de progresso. Há filtros de categoria, objetivos pendentes e
concluídos. O painel de rolagem usa altura fixa pelas âncoras, evitando o ciclo
de redimensionamento causado por `fit-children: true`. A barra de rolagem
usa âncoras independentes para não formar um ciclo com o painel da lista.

O menu lateral agora coloca seus botões dentro de `contentsPanel`, que é
ocultado ao minimizar, e apresenta um controle visível de minimizar/expandir.
O estado recolhido é preservado durante redimensionamentos e entre sessões.

## Validação

- `tests/achievements-tests.lua`: JSON real, 60 objetivos nos estados inicial e
  máximo, limite de pacote, recompensas, idempotência e entrada inválida.
- `tests/achievements-ui-tests.lua`: montagem de páginas, duplicatas, filtros,
  progresso, timeout, negociação inicial, notificações e limpeza de timers.
- `tests/playerbars-ui-tests.lua`: minimizar/expandir com `UIMiniWindow`,
  redimensionamento recolhido e restauração do estado salvo.
- `tests/achievements-live.py`: uma conta temporária comum solicita o catálogo
  completo pelo protocolo real; remove seus dados após confirmar logout.

O executável C++ mantém o hash da v40; esta correção altera o Lua e o cliente.
Fontes atuais de cliente usadas nas regressões também estão em
`deploy/client-current/`, sem manter releases antigos nessa pasta.

Validação em produção em 28/09/2026: catálogo real completo, cinco páginas,
60 objetivos e maior mensagem de 2.050 bytes. A conta temporária foi removida
após logout. O teste de valores máximos gerou páginas de até 2.095 bytes.

A janela nativa foi conferida com o catálogo capturado pelo teste real, sem
login em conta de jogador: renderização, categorias, contagem e barras de
progresso. Não houve erro novo de layout na inicialização após a correção.
