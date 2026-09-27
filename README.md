# Antigas 7.4 — servidor

Repositório privado do servidor Antigas 7.4. O repositório contém o código-fonte do TFS, scripts e dados do jogo, inclusive o mapa versionado. Não contém o executável compilado nem o arquivo local de configuração com credenciais.

## Estrutura

- `src/`: código-fonte C++ do servidor.
- `data/`: scripts Lua, definições XML/NPC, itens e conteúdo do mundo.
- `data/sql/`: estrutura e migrações do Market.
- `deploy/`: arquivos de implantação em uso: fonte pública do site e configurações operacionais do systemd. Os pacotes e scripts de releases anteriores foram retirados dessa pasta; cópias locais recuperáveis ficam em `../../backup/TFS-deploy-antigo-20260927/`.
- `docs/`: documentação operacional e funcional; comece pelo [índice](docs/INDEX.md).
- `tests/`: validações isoladas, sem dados de jogadores.

`tests/` é necessário para desenvolvimento, auditoria e manutenção; não faz parte do binário do servidor, da unidade systemd nem do pacote público do cliente. Os testes de regressão e o roteiro isolado de carga continuam versionados.
- `config.example.lua`: exemplo sem credenciais. Copie para `config.lua` no servidor e configure os dados locais. `config.lua` é ignorado pelo Git.

## Trabalho seguro

- Nunca adicione senhas, chaves, dumps do banco, arquivos de jogadores ou logs.
- A `.gitignore` exclui a configuração local, executável, estado de execução e arquivos temporários. O mapa e o conteúdo do jogo permanecem versionados.
- Revise `git status` antes de cada commit. Uma chave inserida em um commit continua no histórico mesmo depois de apagada; se acontecer, troque a credencial e reescreva o histórico antes de enviar.
- Faça mudanças e valide-as em uma cópia de testes. O `git push` não publica o servidor automaticamente. Deploy e reinício são tarefas separadas.

## Compilação

Use o toolchain e as dependências documentados para esta versão do TFS. Os arquivos de projeto em `CMakeLists.txt` e `src/` são a referência; mantenha binários de build fora do repositório.

## Recuperação de banco e teste de concorrência

Consulte também [as correções de encerramento e do cliente v16](docs/stability-v16.md).

A regressão da aba Loot da v16 foi corrigida no [cliente v17](docs/loot-v17.md), com teste do despachante e pacotes de coleta reais.

Consulte [o relatório de recuperação e concorrência](docs/database-recovery.md). Esta atualização exige o novo executável junto do `market.lua`; recarregar apenas o Lua não aplica as proteções do banco. O cliente v15 continua compatível.

Os sistemas antigos de tarefas Tusker, bounty hunter, coleta customizada de frascos vazios e acertos críticos foram removidos. Veja [o resumo da aposentadoria](docs/retired-legacy-systems.md); o uso e as negociações normais de frascos continuam disponíveis.

## Market — histórico e catálogo (cliente v15)

- Em instalação nova, aplique `data/sql/market.sql`, `market-v2.sql` e `market-v3.sql`, nessa ordem. Em instalação com Market v2, aplique somente `market-v3.sql` **antes** de carregar o novo `market.lua`. A migração é aditiva, usa InnoDB e pode ser repetida no MariaDB.
- O histórico começa nesta atualização: compras, vendas e cancelamentos são registrados na mesma transação dos bens e do comprovante de idempotência. Entregas anteriores continuam disponíveis, mas não têm histórico retroativo inventado.
- Cada registro acompanha sua entrega: uma coleta parcial mantém o saldo pendente; a coleta completa passa a constar como recolhida. Gold vai ao banco; itens e Antigas Coins vão ao depot da cidade do personagem.
- O catálogo oferece filtro de itens próprios e menor preço de venda/maior preço de compra por moeda. Os preços são calculados sobre ofertas ativas, não são cotações garantidas e não misturam as moedas.
- Wands e rods de combate são bloqueadas no servidor para novas ofertas e negociações, inclusive em clientes antigos. Ofertas antigas continuam visíveis ao dono para cancelar e recolher. A fishing rod permanece disponível.
- Validação isolada: 37 testes de protocolo mais 5 verificações adicionais, incluindo concorrência, repetição de pedidos, falha de gravação do histórico, duas moedas, devolução legada, coleta parcial, paginação e isolamento entre personagens. Interface validada no cliente real com dados de teste, sem usar contas de jogadores.
- Para atualizar sem desconectar jogadores: faça backup do Lua anterior, aplique a migração, instale o arquivo e use `/reload creaturescripts` com uma conta autorizada. Verifique o log e faça testes de leitura. Em rollback, restaure somente o Lua anterior e recarregue; nunca restaure um banco antigo sobre negociações já concluídas.
