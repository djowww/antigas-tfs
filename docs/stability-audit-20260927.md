# Auditoria de estabilidade — 27/09/2026

## Resultado e limite da validação

O site foi publicado e validado. A correção do Market foi instalada em disco na VPS; **a ativação por reload/reinício está pendente**. Não foi executado teste com 50 ou 100 jogadores dentro do mundo nesta rodada. A manutenção de até dez minutos foi solicitada ao proprietário e aguarda resposta. O oficial permaneceu online, com um jogador na última consulta.

A VPS tem 3.911 MiB de RAM, sem swap; o serviço oficial consumia aproximadamente 1.738 MiB e havia 1.559 MiB disponíveis. O staging continua parado, limitado a 1 GiB. Carregar dois mapas completos nessa máquina já provocou OOM em rodada anterior. Esses números descrevem o estado observado, não a capacidade com 50 jogadores.

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
| PHP | `index.php`, `account.php` e `coins.php` aprovados em `php -l` |
| Site publicado | HTTP 200; links conferidos; desktop e mobile 390×844 sem overflow horizontal |

O arquivo `data/globalevents/lib/lamp_states.lua` guarda uma tabela serializada de estado e é lido como dados pela biblioteca de lâmpadas. Não é um script executável; foi corretamente excluído da checagem de sintaxe e preservado.

O teste unitário do Market usa 100 objetos de jogador em memória. **Ele não equivale a 100 conexões/jogadores online**. Cadastro, pagamentos, combate prolongado, uso de todos os itens e todos os caminhos dos scripts não receberam validação ponta a ponta nesta rodada. A inspeção não garante ausência de outros defeitos.

## Roteiro de carga corrigido e preparado

`tests/load-test-50.py` agora usa o backpack correto (2854), SIDs válidos e dois peixes por vendedor. Exige identificação do personagem no login e confirmação de todos os jogadores no registro do mundo. Corrige a leitura do alvo e envio do ataque, evita que a thread de keepalive consuma recibos do Market, falha em transações rejeitadas e monitora quedas durante chat/movimento. O transporte é autocontido em `load_test_protocol.py`, sem chaves RSA privadas.

O staging recebeu uma cópia do executável/data atuais. O SHA256 dos dois executáveis foi conferido: `af27c7c444d3e511c74bf62d80cbb9b935a976596e438af59b7dce57c4225ca3`. Configuração, banco e credenciais continuam separados; portas 7175/7176 em loopback. Server Save permanece desativado apenas no staging.

`tests/staging-maintenance.py` prepara smoke seguido de 50 jogadores, coleta memória/CPU e restaura o oficial ao terminar. Sua sintaxe foi verificada, mas o ciclo de manutenção não foi executado. Ele exige aprovação explícita e execução sob systemd com limite de duração e recuperação independente em `ExecStopPost`, conforme seu cabeçalho. Não iniciar outro mapa com produção ativa nem elevar o limite de memória fora da janela.

Depois da autorização: confirmar o watchdog, iniciar a janela, executar smoke e então 50 jogadores, medir sessões/CPU/RAM e os resultados reais do Market/caça, desligar staging, restaurar MemoryMax=1G, religar oficial e verificar ausência de contas sintéticas. Se caça não encontrar alvos ou não registrar mortes, declarar essa cobertura incompleta.

## Organização e recuperação

- Backups privados locais centralizados em `Historico/Backups-privados/`.
- ZIPs v37/v38 locais arquivados em `Historico/Pacotes-antigos/`; alias `Antigas-7.4-Client-atual.zip` permanece na raiz. Download online v38 foi preservado.
- Binário alternativo e fontes/instruções antigas arquivados em `Historico/Executaveis-antigos/` e `Historico/implantacao-20260924/`.
- Log legado do cliente arquivado; o log aberto pelo processo atual foi preservado. Diretório vazio `data/globalevents/scripts/events` removido.
- Módulos carregados dinamicamente, editor de mapa, bibliotecas privadas, migrações e backups úteis preservados. Ausência de referência textual não foi usada sozinha para apagar recursos.
- Backup da publicação na VPS: `/root/backups/antigas-stability-20260927`. Para rollback de código, restaurar somente os arquivos envolvidos; não restaurar banco sobre operações recentes.

Pendências: aprovação da janela, carga real de 50 jogadores e ativação/verificação do Market no processo oficial. Não há resultado de desempenho sob carga a publicar antes desse ensaio.
