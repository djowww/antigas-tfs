# Canal Loot e avisos visuais — cliente v45

## Comportamento

- O canal **Loot** abre ao entrar no jogo e pode ser reaberto na lista de canais. É somente para leitura.
- Cada morte gera uma linha para o dono do loot e os membros da party naquele momento. Jogadores fora desse grupo não recebem as mensagens nem os efeitos novos.
- Cada nome usa a raridade daquela instância: comum cinza, incomum verde, raro azul, épico roxo, lendário amarelo e mítico vermelho. Dois itens iguais podem aparecer com cores diferentes na mesma linha.
- Um drop com raridade recebe um efeito nativo e um texto animado com a maior raridade encontrada. O efeito aparece uma vez para cada destinatário com o corpo visível.
- Corpos com conteúdo ainda fechado recebem um brilho pulsante discreto. Uma abertura aceita pelo servidor encerra o brilho para os destinatários daquele corpo. Tentar abrir de longe ou enviar uma confirmação forjada não altera esse estado.
- Corpos vazios geram a linha `nothing`, sem brilho. A mensagem de loot continua chegando a integrantes da party fora da tela; os efeitos dependem da visibilidade.
- Fechar voluntariamente a aba interrompe sua exibição até reabri-la. Clientes anteriores recebem o texto simples no canal; o cliente v45 habilita cores e brilho.

## Integração

O canal usa o ID **10**. O opcode estendido **128** negocia `H|1` e aceita `S|1` como pedido limitado de sincronização. O servidor responde com JSON de versão 1; somente eventos originados no servidor alimentam o cliente.

Eventos: `ready`, `loot`, `marker`, `opened` e `removed`. Cada corpo tem um token decimal transitório e uma lista de GUIDs destinatários. Sua identidade visual combina token, posição, ID de sprite e índice de pilha recebido junto ao mapa. O cliente preserva a referência ao objeto nativo enquanto ela ainda pertence ao tile.

O opcode **127** continua responsável pelos metadados de raridade do inventário e dos containers. Esta release não altera as probabilidades, atributos de equipamentos, tabelas de monstros ou fórmula de sorteio descritas em [item-rarity.md](item-rarity.md).

Limites:

- 4.096 corpos no índice global; expiração em 30 minutos e remoção ao destruir o container.
- 256 marcadores visíveis por jogador, com um único timer de pulso no cliente.
- 512 tokens no histórico de deduplicação do cliente.
- Até 128 entradas de itens, com resumo da quantidade omitida e pacote abaixo de 8.192 bytes.
- Atualizações limitadas por jogador; repetição de marcadores a cada cinco segundos recupera objetos recriados pelo mapa sem repetir a animação.
- Logout, troca de conexão, remoção, abertura, movimento e mudança de andar limpam ou sincronizam os marcadores.

Os estados de loot fechado são temporários. Um reinício do servidor não restaura o brilho de corpos antigos.

## Validação e publicação

Publicado em **28/09/2026** no serviço principal `imperium772.service`. O encerramento da v44 salvou as casas em 0,094 s e terminou normalmente, sem erro de banco. A v45 iniciou com PID 123848 e zero reinícios automáticos. Cliente e manifesto publicados às **14:11:52 BRT**.

- Download: [Antigas 7.4 v45](https://tibia74.tech/Antigas-7.4-Client-v45.zip).
- SHA-256 do servidor: `e147af97d53b6867e777e5428148c337a2c9648ab0ed777e843d9c22cd8f3208`.
- SHA-256 do ZIP: `a26c10020fd19dad95968e4d32a1efaabd3951d3361a11c544634772ca29a4e7`.
- Pacote: 25.726.950 bytes, 682 entradas; quatro arquivos existentes alterados e dois adicionados sobre a v44.
- Backup privado: `/root/antigas-backups/loot-v45-20260928T170804Z`.

| Verificação | Resultado |
|---|---|
| Núcleo C++ real | 4.078 verificações aprovadas, incluindo 30 novas de Loot |
| Loot UI / canal | 38 / 68 verificações em Lua 5.2 e LuaJIT |
| Regressão de raridade UI | 105 verificações por runtime |
| Cliente nativo usando o ZIP publicado | 32 verificações, saída 0; cores conferidas visualmente |
| Smokes no principal | Loot: 20,23 s; raridades: 34,38 s; ambos aprovados |
| Contas e personagens temporários | Limpeza confirmada; zero contas de teste restantes |
| Download, manifesto, página e portas públicas | HTTP 200, hash conferido, 7173/7174 acessíveis |

Resultados desta publicação são registrados em `validation/loot-v45/`. A suíte C++ usa o núcleo real em processo isolado, sem carregar o mundo principal; as suítes de UI incluem o executável nativo do cliente sem conexão. Os smokes em produção usam contas comuns temporárias e confirmam sua remoção após logout.

O smoke de rede de Loot valida canal, isolamento e reconexão. Mortes, pilhas de corpos e renderização são exercitadas pelas fixtures isoladas; não são apresentadas como combates realizados no mundo principal.

O pacote público é construído a partir do ZIP v44 arquivado, com os módulos revisados sobrepostos. Artefatos privados de operação e configurações de jogadores ficam fora do ZIP e do Git.

O procedimento guardado em `deploy/deploy-loot-v45.py` separa backup, instalação após encerramento confirmado e publicação do manifesto após os smokes. O backup inclui arquivos e banco antes do encerramento e outro snapshot do banco depois dele. A reversão de arquivos para v44 é compatível com a raridade persistida; não se deve restaurar automaticamente um banco antigo.

A ocorrência anterior no encerramento completo está documentada em [rarity-v44-review-20260928.md](rarity-v44-review-20260928.md). Esta release de interface não corrige aquele caminho de salvamento.
