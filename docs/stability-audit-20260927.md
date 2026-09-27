# Auditoria de estabilidade — 27/09/2026

## Resultado e limite da validação

O site foi publicado e validado. Após autorização explícita de manutenção, o teste final confirmou **50 jogadores simultâneos dentro do mundo**. A correção do Market foi ativada no oficial ao reiniciar. O servidor oficial voltou às 18:29:55 UTC (15:29:55 de Brasília), com resposta de status e acesso de jogador confirmados. O staging está desligado, limitado novamente a 1 GiB, e todas as contas/personagens sintéticos foram removidos. Não foi executado teste de 100 jogadores.

A VPS tem 3.911 MiB de RAM, sem swap; o serviço oficial consumia aproximadamente 1.738 MiB e havia 1.559 MiB disponíveis. O staging continua parado, limitado a 1 GiB. Carregar dois mapas completos nessa máquina já provocou OOM em rodada anterior. Esses números descrevem o estado anterior ao ensaio; os resultados medidos com 50 jogadores estão abaixo.

## Correções verificadas

- Market: a limpeza do controle de frequência ocorria em todos os pedidos recebidos no segundo exato da virada do minuto, ou nunca ocorria se não houvesse pedidos naquele segundo. Agora é feita uma vez a cada intervalo de 60 segundos. Os limites continuam em oito consultas e três mutações por jogador/segundo.
- Três XMLs locais de monstros declaravam `UTF - 8`: `raids/orc.xml`, `raids/orcwarlord.xml` e `arena/ultimate/tentacles.xml`. Corrigidos para `UTF-8`. A VPS já continha a declaração correta; o problema era divergência local/Git.
- Removida `data/spells/spells x 1.xml`, uma cópia sem referências. O carregador usa `data/spells/spells.xml`. A versão anterior permanece no Git e no backup privado da publicação.
- Fonte pública do site passou a integrar `deploy/site-public/`: botão Wikipédia para o artigo Tibia em português, ajuda de formulário associada aos campos, URL canônica e respeito à preferência por movimento reduzido. Bibliotecas e configurações privadas não foram incluídas.

## Testes realizados

| Verificação | Resultado |
|---|---|
| XMLs locais | 246 válidos; referências de arquivos/scripts conferidas |
| Sintaxe Lua 5.2 | 704 scripts aprovados |
| Market | Limites, uma limpeza para 100 jogadores simulados em memória, intervalo sem pedido na virada e retenção aprovados |
| Bestiary | Isolamento, summons, limites, consultas e pedidos malformados aprovados |
| Quest Log | Descoberta, ocultação de conteúdo, paginação de 242 entradas, isolamento e validação aprovados |
| Bônus online | Migração, acúmulo/teto, logout e frações de experiência/skills aprovados |
| Roteiro de carga Python | Cinco regressões offline aprovadas: transporte, frames fragmentados/ping, alvo, inventário e recibos |
| Carga real no staging | 50/50 conectados; 20 ofertas, 20 negociações, 40 históricos, zero entregas pendentes; limpeza completa |
| PHP | `index.php`, `account.php` e `coins.php` aprovados em `php -l` |
| Site publicado | HTTP 200; links conferidos; desktop e mobile 390×844 sem overflow horizontal |

O arquivo `data/globalevents/lib/lamp_states.lua` guarda uma tabela serializada de estado e é lido como dados pela biblioteca de lâmpadas. Não é um script executável; foi corretamente excluído da checagem de sintaxe e preservado.

O teste unitário do Market usa 100 objetos de jogador em memória. **Ele não equivale a 100 conexões/jogadores online**. Cadastro web, pagamentos, combate prolongado, uso de todos os itens e todos os caminhos dos scripts não receberam validação ponta a ponta nesta rodada. A inspeção não garante ausência de outros defeitos.

## Roteiro de carga corrigido e preparado

`tests/load-test-50.py` agora usa o backpack correto (2854), SIDs válidos e dois peixes por vendedor. Exige identificação do personagem no login e confirmação de todos os jogadores no registro do mundo. Corrige a leitura do alvo e envio do ataque, evita que a thread de keepalive consuma recibos do Market, falha em transações rejeitadas e monitora quedas durante chat/movimento. O transporte é autocontido em `load_test_protocol.py`, sem chaves RSA privadas.

O staging recebeu uma cópia do executável/data atuais. O SHA256 dos dois executáveis foi conferido: `af27c7c444d3e511c74bf62d80cbb9b935a976596e438af59b7dce57c4225ca3`. Configuração, banco e credenciais continuam separados; portas 7175/7176 em loopback. Server Save permanece desativado apenas no staging.

`tests/staging-maintenance.py` prepara smoke seguido de 50 jogadores, coleta memória/CPU e restaura o oficial ao terminar. O ciclo de manutenção foi executado com sucesso. Ele exige aprovação explícita e execução sob systemd com limite de duração e recuperação independente em `ExecStopPost`, conforme seu cabeçalho. A espera de inicialização agora confirma ambas as portas em vez de usar oito segundos fixos. Não iniciar outro mapa com produção ativa nem elevar o limite de memória fora da janela.

### Resultado medido da carga

O ensaio final durou 91,3 segundos incluindo a subida gradual e o encerramento. Os 50 jogadores foram confirmados no registro do servidor e permaneceram online durante **30 segundos monitorados após as transações**, além do período das operações do Market. Isso é um teste curto, não um teste prolongado nem uma certificação de capacidade para 100 jogadores.

- Pico RSS do TFS: **1.723,97 MiB (~1,68 GiB)**.
- CPU média do processo TFS durante os 30 segundos de manutenção das 50 sessões, após as transações do Market: **3,20% de uma CPU**; maior intervalo amostrado de aproximadamente um segundo: **6,92%**. A VPS tem uma vCPU. Não inclui MariaDB nem mede latência de rede ou uso total da VPS.
- Market: **20 ofertas criadas, 20 negociações concluídas, 40 registros de histórico, zero entregas pendentes**, usando Gold e Antigas Coin.
- Chat e movimento: comandos repetidos durante a carga; todas as sessões monitoradas permaneceram online. O roteiro não confirma cada posição final individualmente.
- Caça: **10/10 alvos identificados; 3/10 caçadores registraram morte de rato** no storage persistido. Cobertura parcial de caça; não afirmar sucesso para os demais.
- Sem crash/OOM observado na rodada final. A parada final foi administrativa e graciosa. Após ela: zero contas/personagens sintéticos, zero ofertas/entregas de teste, staging sem portas abertas, oficial respondendo em 7173/7174.

A primeira tentativa acionou o limitador de novas conexões por IP ao abrir um lote simultâneo; o servidor encerrou sockets sem resposta e a recuperação automática funcionou. O roteiro passou a espaçar somente as aberturas em **750 ms**, preservando as proteções do servidor. A segunda tentativa autenticou 50 personagens, mas cinco caçadores morreram enquanto esperavam a rampa; foi corretamente rejeitada como carga de 50.

Na rodada válida, os dez caçadores sintéticos receberam **5.000 HP** para sobreviver à preparação. Nenhuma regra de combate, criatura ou personagem real foi alterado. Isso valida carga e integrações, não balanceamento de combate. Personagens em combate podem recusar logout; no encerramento em manutenção o staging é parado normalmente antes da limpeza, permitindo salvar o estado e confirmar zero online sem apagar personagens conectados.

Métricas publicadas em [validation/load-50-20260927.json](validation/load-50-20260927.json). As amostras completas e os logs das três tentativas estão no histórico local privado da auditoria.

A recuperação independente usada está em `deploy/systemd/staging-maintenance-recovery.sh`. Foi instalada com permissão 0700 e configurada como `ExecStopPost` do serviço transitório, com `KillMode=control-group` e `RuntimeMaxSec` limitado à janela. A opção `--skip-smoke` da última rodada só foi usada porque o smoke do mesmo executável já havia passado duas vezes. Esses comandos não devem ser executados sem nova janela coordenada.

## Organização e recuperação

- Backups privados locais centralizados em `Historico/Backups-privados/`.
- ZIPs v37/v38 locais arquivados em `Historico/Pacotes-antigos/`; alias `Antigas-7.4-Client-atual.zip` permanece na raiz. Download online v38 foi preservado.
- Binário alternativo e fontes/instruções antigas arquivados em `Historico/Executaveis-antigos/` e `Historico/implantacao-20260924/`.
- Log legado do cliente arquivado; o log aberto pelo processo atual foi preservado. Diretório vazio `data/globalevents/scripts/events` removido.
- Módulos carregados dinamicamente, editor de mapa, bibliotecas privadas, migrações e backups úteis preservados. Ausência de referência textual não foi usada sozinha para apagar recursos.
- Backup da publicação na VPS: `/root/backups/antigas-stability-20260927`. Para rollback de código, restaurar somente os arquivos envolvidos; não restaurar banco sobre operações recentes.

Concluído: carga curta de 50 jogadores, ativação do Market, restauração do oficial e limpeza dos dados sintéticos. Permanecem fora da cobertura testes prolongados, 100 jogadores, consumo de poções/runas/comida, cama, duplicação e exaustão de todos os caminhos de jogo.
