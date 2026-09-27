# Auditoria de estabilidade — 27/09/2026

## Resultado e limite da validação

O teste final do **servidor v40 confirmou 50 jogadores simultâneos dentro do mundo**, com produção ativa após a recuperação. O site público entrega o cliente v40, a página de novidades de Achievements e o link da Wiki Antigas; o manifesto, o ZIP e o hash coincidem. A rodada terminou às 21:55:42 UTC (18:55:42 de Brasília). O staging está desligado e limitado novamente a 1 GiB, e todas as contas/personagens/ofertas sintéticas foram removidas. Não foi executado teste de 100 jogadores.

A VPS tem 3.911 MiB de RAM, sem swap; o serviço oficial consumia aproximadamente 1.738 MiB e havia 1.559 MiB disponíveis. O staging continua parado, limitado a 1 GiB. Carregar dois mapas completos nessa máquina já provocou OOM em rodada anterior. Esses números descrevem o estado anterior ao ensaio; os resultados medidos com 50 jogadores estão abaixo.

## Correções verificadas

- Market: a limpeza do controle de frequência ocorria em todos os pedidos recebidos no segundo exato da virada do minuto, ou nunca ocorria se não houvesse pedidos naquele segundo. Agora é feita uma vez a cada intervalo de 60 segundos. Os limites continuam em oito consultas e três mutações por jogador/segundo.
- Três XMLs locais de monstros declaravam `UTF - 8`: `raids/orc.xml`, `raids/orcwarlord.xml` e `arena/ultimate/tentacles.xml`. Corrigidos para `UTF-8`. A VPS já continha a declaração correta; o problema era divergência local/Git.
- Removida `data/spells/spells x 1.xml`, uma cópia sem referências. O carregador usa `data/spells/spells.xml`. A versão anterior permanece no Git e no backup privado da publicação.
- Fonte pública do site integra `deploy/site-public/`: botão “Wiki do jogo” para a Wiki Antigas publicada no ChatGPT, ajuda de formulário associada aos campos, URL canônica e respeito à preferência por movimento reduzido. Bibliotecas e configurações privadas não foram incluídas.

## Testes realizados

| Verificação | Resultado |
|---|---|
| XMLs locais | 246 válidos; referências de arquivos/scripts conferidas |
| Sintaxe Lua 5.2 | 704 scripts aprovados |
| Market | Limites, uma limpeza para 100 jogadores simulados em memória, intervalo sem pedido na virada e retenção aprovados |
| Bestiary | Isolamento, summons, limites, consultas e pedidos malformados aprovados |
| Quest Log | Descoberta, ocultação de conteúdo, paginação de 242 entradas, isolamento e validação aprovados |
| Bônus online | Migração, acúmulo/teto, logout e frações de experiência/skills aprovados |
| Achievements v40 | Marcos persistentes, bônus de velocidade/dano/PvP/morte, recompensas por level/skill, protocolo e realce do botão aprovados nos testes Lua dedicados |
| Compilação v40 | CMake Release compilado no VPS; binário de produção e staging com SHA256 `450f2b1a8e75243afedd36c72df5ac7da44de00f7ddde3b76440e04c48aa797` |
| Roteiro de carga Python | Cinco regressões offline aprovadas: transporte, frames fragmentados/ping, alvo, inventário e recibos |
| Carga real no staging | 50/50 conectados; 20 ofertas, 20 negociações, 40 históricos, zero entregas pendentes; limpeza completa |
| PHP | `index.php`, `account.php` e `coins.php` aprovados em `php -l` |
| Site publicado | HTTP 200; links conferidos; desktop e mobile 390×844 sem overflow horizontal |

O arquivo `data/globalevents/lib/lamp_states.lua` guarda uma tabela serializada de estado e é lido como dados pela biblioteca de lâmpadas. Não é um script executável; foi corretamente excluído da checagem de sintaxe e preservado.

O teste unitário do Market usa 100 objetos de jogador em memória. **Ele não equivale a 100 conexões/jogadores online**. Cadastro web, pagamentos, combate prolongado, uso de todos os itens e todos os caminhos dos scripts não receberam validação ponta a ponta nesta rodada. A inspeção não garante ausência de outros defeitos.

## Roteiro de carga corrigido e preparado

`tests/load-test-50.py` agora usa o backpack correto (2854), SIDs válidos e dois peixes por vendedor. Exige identificação do personagem no login e confirmação de todos os jogadores no registro do mundo. Corrige a leitura do alvo e envio do ataque, evita que a thread de keepalive consuma recibos do Market, falha em transações rejeitadas e monitora quedas durante chat/movimento. O transporte é autocontido em `load_test_protocol.py`, sem chaves RSA privadas.

O staging recebeu uma cópia do executável e dos dados v40, incluindo os arquivos de Bestiary e bônus online alinhados ao Git. O binário ativo da produção foi conferido após a recuperação; o SHA256 dos dois executáveis é `450f2b1a8e75243afedd36c72df5ac7da44de00f7ddde3b76440e04c48aa797`. Configuração, banco e credenciais continuam separados; portas 7175/7176 em loopback. Server Save permanece desativado apenas no staging.

`tests/staging-maintenance.py` prepara smoke seguido de 50 jogadores, coleta memória/CPU e restaura o oficial ao terminar. O ciclo de manutenção foi executado com sucesso. Ele exige aprovação explícita e execução sob systemd com limite de duração e recuperação independente em `ExecStopPost`, conforme seu cabeçalho. A espera de inicialização agora confirma ambas as portas em vez de usar oito segundos fixos. Não iniciar outro mapa com produção ativa nem elevar o limite de memória fora da janela.

### Resultado medido da carga

O ensaio v40 durou 91,4 segundos incluindo a subida gradual e o encerramento. Os 50 jogadores foram confirmados no registro do servidor e permaneceram online durante **30 segundos monitorados**, enquanto o roteiro fazia chat, movimento, Market e caça. Isso é um teste curto, não um teste prolongado nem uma certificação de capacidade para 100 jogadores.

- Pico RSS do TFS: **1.723,74 MiB (~1,68 GiB)**; pico da métrica de memória: **1.719,57 MiB**.
- O processo TFS acumulou **7,85 segundos de CPU** durante a execução registrada. A VPS tem uma vCPU. A métrica não inclui MariaDB nem mede latência de rede ou uso total da VPS.
- Market: **20 ofertas criadas, 20 negociações concluídas, 40 registros de histórico, zero entregas pendentes**, usando Gold e Antigas Coin.
- Chat e movimento: comandos repetidos durante a carga; todas as sessões monitoradas permaneceram online. O roteiro não confirma cada posição final individualmente.
- Caça: **10/10 alvos identificados; 3/10 caçadores registraram morte de rato** no storage persistido. Cobertura parcial de caça; não afirmar sucesso para os demais.
- Sem crash/OOM observado na rodada final. A parada final foi administrativa e graciosa. Após ela: zero contas/personagens sintéticos, zero ofertas/entregas de teste, staging sem portas abertas, oficial respondendo em 7173/7174.

O histórico v38 desta auditoria registrou tentativas anteriores com limitação de conexões e caçadores mortos durante a rampa; o roteiro passou a espaçar aberturas em **750 ms**, preservando as proteções do servidor. Na primeira tentativa de publicação v40, o smoke encontrou dados antigos de Bestiary na cópia do staging e a recuperação automática manteve a produção ativa. Os arquivos de suporte foram atualizados em produção e staging, os testes de Bestiary e bônus online passaram e a repetição v40 aprovou o smoke e os 50 jogadores.

Na rodada válida, os dez caçadores sintéticos receberam **5.000 HP** para sobreviver à preparação. Nenhuma regra de combate, criatura ou personagem real foi alterado. Isso valida carga e integrações, não balanceamento de combate. Personagens em combate podem recusar logout; no encerramento em manutenção o staging é parado normalmente antes da limpeza, permitindo salvar o estado e confirmar zero online sem apagar personagens conectados.

Métricas publicadas em [validation/load-50-20260927.json](validation/load-50-20260927.json). As amostras completas e os logs das três tentativas estão no histórico local privado da auditoria.

A recuperação independente usada está em `deploy/systemd/staging-maintenance-recovery.sh`. Foi instalada com permissão 0700 e configurada como `ExecStopPost` do serviço transitório, com `KillMode=control-group` e `RuntimeMaxSec` limitado à janela. A opção `--skip-smoke` da última rodada só foi usada porque o smoke do mesmo executável já havia passado duas vezes. Esses comandos não devem ser executados sem nova janela coordenada.

## Organização e recuperação

- Backups privados locais centralizados em `../../backup/Historico/Backups-privados/`.
- Releases antigos do cliente foram reunidos em `../../backup/Client-releases/` e `../../backup/Historico/Pacotes-antigos/`; alias `Antigas-7.4-Client-atual.zip` aponta para o v40. O webroot público agora mantém apenas o ZIP v40; versões anteriores removidas do site estão preservadas no snapshot `/root/backups/antigas-achievements-v40-20260927/site-before/`.
- Binário alternativo, fontes e instruções antigas reunidos em `../../backup/Historico/`.
- Releases e ferramentas antigas retiradas de `deploy/` e arquivadas em `../../backup/TFS-deploy-antigo-20260927/`; só os arquivos atuais do site e do systemd permanecem em `deploy/`.
- Log legado do cliente arquivado; o log aberto pelo processo atual foi preservado. Diretório vazio `data/globalevents/scripts/events` removido.
- Módulos carregados dinamicamente, editor de mapa, bibliotecas privadas, migrações e backups úteis preservados. Ausência de referência textual não foi usada sozinha para apagar recursos.
- Backup da publicação na VPS: `/root/backups/antigas-stability-20260927`. Para rollback de código, restaurar somente os arquivos envolvidos; não restaurar banco sobre operações recentes.

Concluído: carga curta de 50 jogadores, ativação do Market, restauração do oficial e limpeza dos dados sintéticos. Permanecem fora da cobertura testes prolongados, 100 jogadores, consumo de poções/runas/comida, cama, duplicação e exaustão de todos os caminhos de jogo.
