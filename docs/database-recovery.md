# Recuperação de banco e concorrência do Market

Evidências e identificadores da compilação: [resultados das verificações](validation/database-recovery-20260925.json). Não incluem senhas, contas reais nem conteúdo do banco de jogadores.

## Correções

- Consultas não entram mais em repetição infinita quando o banco perde a conexão. Há timeout de conexão/leitura/escrita, espera de lock limitada e intervalo de recuperação. Nenhuma escrita é repetida implicitamente.
- As leituras idempotentes usadas para autenticar a conta, listar personagens e verificar bloqueios podem refazer uma única tentativa após uma desconexão transitória. A reconexão tem timeout limitado; consultas em transações e escritas mantêm a regra de não repetir.
- Falhas de conexão ou ROLLBACK no Market não encerram mais todo o processo.
- Antes de uma alteração financeira, um checkpoint salva o progresso anterior do personagem.
- Uma falha anterior ao COMMIT desfaz a operação. Se o resultado do COMMIT for desconhecido, ou se a compensação em memória falhar, somente o personagem afetado é desconectado e removido sem sobrescrever seu estado persistido.
- O próximo login lê o personagem e seus itens dentro de uma transação, bloqueando sua linha até a operação anterior estar resolvida. Os recibos existentes impedem duplicação ao reenviar o pedido.
- Erro de leitura do Market é distinguido de resultado vazio. Indisponibilidade não é apresentada como saldo zero. Falha ao atualizar saldos não substitui um recibo de sucesso já obtido.
- A API Lua antiga continua compatível; a nova consulta com indicador de sucesso é `db.storeQueryChecked`.

## Validação isolada

Mundo separado, banco `imperium_market_qa`, usuário SQL restrito a esse banco e proxy de falhas em loopback. Nenhuma interrupção de banco foi provocada em produção.

46 verificações aprovadas: conexão perdida, resposta de leitura suspensa, gravação interrompida antes do COMMIT, confirmação perdida antes/depois da entrega do COMMIT, ROLLBACK interrompido e falha de compensação em memória. Inclui preservação do progresso ainda não salvo, reentrada, pedidos idempotentes e transações nas duas moedas após recuperação.

14 verificações aprovadas com 100 sessões simultâneas, distribuídas entre 20 trabalhadores do simulador:

- 100 ofertas de compra/venda em gold e Antigas Coins, preenchidas por outros personagens;
- reenvio dos 100 pedidos sem duplicação;
- 99 compradores disputando duas unidades: exatamente dois vencedores;
- 100 cancelamentos e reenvios com restituição única;
- conferência de todos os valores em banco, inventário e depot: 1.122.000 gold equivalentes, 10.000 Antigas Coins e 400 espadas conservados;
- 3.000 consultas de uso misto junto de comandos de jogo, sem troca do processo do servidor.

## Teste público e limites de operação

### Resultado da repetição no servidor principal — 25/09/2026

- 100 personagens simultâneos, entrada gradual em 10/25/50/100, perto do DP de Thais.
- 15.000 consultas de catálogo, ofertas, histórico, itens próprios e saldos, combinadas com comandos de inventário, outfits, cura, direção/movimento, modos de combate e canal Help.
- 20 reconexões programadas em dois grupos de dez; população voltou a 100 após cada grupo.
- 392 segundos no total, incluindo preparação, entrada e limpeza; quatro minutos de fases de uso misto, além das reconexões.
- Mesmo processo durante toda a rodada; nenhum erro novo detectado pelos padrões monitorados e nenhuma desconexão inesperada.
- Mediana de resposta: 86,4 ms; percentil 95: 168,9 ms; máximo: 360,5 ms. Medições locais da VPS, incluindo custo do simulador.
- CPU do processo em torno de 11–13% nas fases normais e 21% na fase sincronizada; crescimento de memória residente de aproximadamente 0,52 MiB em relação ao início da repetição. Isso não representa uso total da máquina nem limite máximo de capacidade.
- Evidência persistida: 12 personagens gastaram mana, 13 mudaram cores da outfit e os 100 salvaram normalmente. Demais comandos foram exercitados pelo protocolo, sem alegar validação visual individual de cada ação.
- As 100 contas e seus itens sintéticos foram removidos após conferir identidade, ausência de saldo/entregas/ofertas e inventário esperado. Nenhum ativo de jogador foi utilizado.

### Limitações

O timeout do conector não é garantia de pausa máxima de exatamente um segundo: bibliotecas podem realizar tentativas internas de leitura. O objetivo é eliminar a espera infinita e falhar de forma limitada, sem repetir escritas incertas.

Esta mudança não torna todo o jogo tolerante a uma interrupção prolongada do banco. Sistemas legados fora do Market e perda de energia/processo merecem testes próprios. O checkpoint acrescenta uma gravação completa por operação financeira, cujo custo precisa continuar sendo acompanhado em cargas maiores e inventários grandes.

O teste público é limitado, com personagens normais, sem moeda artificial ou ofertas públicas. Não equivale a certificação de capacidade de 100 jogadores em caçadas, PvP, invasões ou redes externas. Os tempos do simulador executado na própria VPS não representam o ping dos jogadores.

Uma primeira rodada pública foi interrompida após 4.500 consultas por fechamento de uma conexão do simulador; o processo do servidor permaneceu ativo e as 100 contas temporárias foram removidas. O decodificador mínimo só respondia ao ping quando ele ocupava uma mensagem inteira, podendo ignorá-lo junto de outras atualizações do mundo. O simulador passou a enviar heartbeat explícito antes da repetição integral, sem alterar timeout ou proteção do servidor. A entrada gradual também respeita o limitador de conexões por IP.

As sessões de carga aparecem no contador público e podem elevar o recorde de jogadores online; esse pico inclui personagens de teste e não deve ser apresentado como população orgânica.

A publicação utiliza backup, encerramento pelo comando do jogo, espera pelo término do salvamento, instalação atômica do executável e verificação de login/Market. Uma reversão de código nunca restaura um banco antigo por cima de negociações concluídas.
