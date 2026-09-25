# Estabilidade e cliente v16

> Correção posterior: o teste do Loot abaixo chamava o callback diretamente e não cobria o despachante de rede. Duas incompatibilidades deixavam os contadores vazios. Veja a [correção v17 e sua validação](loot-v17.md), que também delimita a garantia de não avaliar Lua nos avisos de Loot.

## Encerramento do servidor Linux

SIGTERM e SIGINT são recebidos pelo Boost.Asio e encaminhados à fila principal do jogo. O mesmo caminho usado pelo comando de encerramento salva os personagens e o mundo antes de terminar. O manipulador é registrado antes das threads do servidor; sinais repetidos não iniciam salvamentos concorrentes.

O serviço já mantém a dependência e a ordem de encerramento com o MariaDB. O novo ajuste `graceful-stop.conf` define SIGTERM e concede até 300 segundos para terminar o salvamento. Falta de energia, SIGKILL e falhas prolongadas do banco continuam exigindo proteção e recuperação próprias.

O ajuste versionado está em `deploy/systemd/graceful-stop.conf`; na VPS, fica em `/etc/systemd/system/imperium772.service.d/graceful-stop.conf`. Os identificadores da compilação e do pacote estão no [registro de validação](validation/stability-v16.json).

Validação em mundo e banco isolados: 29 verificações com SIGTERM, SIGINT, SIGTERM repetido e reentrada. Alterações de saldo, itens e storage comprovadamente ainda não persistidas antes do sinal foram salvas uma única vez; o processo encerrou com sucesso e o registro de jogadores online ficou vazio.

## Limpeza e distribuição

- Retiradas as perguntas sobre NPCs de tasks e a pergunta sem resposta do tutor. Respostas restantes continuam acessíveis por seus identificadores.
- Removido o módulo de tasks do cliente. Os arquivos anteriores estão preservados no histórico local.
- Cliente v16 identificado na tela de entrada e no log. Uma consulta HTTPS ao manifesto oficial avisa sobre versões futuras, com download restrito ao domínio oficial e sem executar conteúdo da resposta. Falha na consulta não impede jogar; o aviso aguarda o jogador sair do jogo.
- Clientes anteriores precisam baixar a v16 uma vez. O servidor também informa a versão oficial na mensagem de entrada.
- O módulo criptografado de Loot foi substituído por código legível, usando as notificações já existentes de itens e suprimentos. O leitor aceita somente os três campos esperados, sem avaliar Lua recebido pela rede; limita quantidade de linhas e contagens e limpa a sessão ao sair. Esses contadores são informativos, não recibos financeiros ou prova de posse dos itens.

O cliente real foi usado em cópia isolada para verificar abertura, contadores, entradas inválidas, limpeza entre personagens, botão Loot e comportamento de atualização. A publicação usa pacote versionado com SHA-256; os pacotes anteriores continuam disponíveis.
