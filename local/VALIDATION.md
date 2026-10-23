# Validação do pacote local

Verificado em Windows x64 com Docker Desktop e containers Linux em 23/10/2026.

- Build completo do servidor C++ em Ubuntu 22.04, a partir destas fontes.
- MariaDB 11.4 inicializado em volume novo com `local/schema.sql`: uma conta e
  um personagem de demonstração, sem importação de dados de produção.
- Geração automática de RSA de 1024 bits exclusiva da instalação e cliente
  usando o módulo público correspondente.
- Login real na porta 17173, lista com **Local Adventurer** e endereço de jogo
  devolvido pelo servidor igual a **127.0.0.1:17174**.
- Entrada no mapa, atributos recebidos e movimento confirmado pelo teste
  `python local/smoke-test.py`.
- Cliente Windows DirectX do ZIP local autenticou pela lista de personagens,
  entrou no jogo, carregou posição e executou um movimento confirmado:
  `32097,32218,7` → `32097,32217,7`. Saiu normalmente em seguida.
- `STOP-LOCAL.cmd` parou somente os serviços deste Compose. O iniciador
  `local/start.ps1 -NoClient` reiniciou o ambiente; a posição salva permaneceu
  `32097,32217,7`, com a mesma conta. Nenhum volume foi apagado.
- Portas do jogo publicadas apenas no loopback do computador; nenhuma porta
  do banco publicada. Servidor público e banco de produção não foram usados.
- Recuperação de instalação interrompida: um executável vazio preexistente,
  sem marcador de conclusão, foi substituído após download HTTP real,
  verificação SHA-256 e extração em staging; a pasta incompleta foi preservada.
  Essa checagem específica isolou as respostas do Docker, que havia sido
  encerrado no computador. Build, jogo, cliente e persistência acima foram
  testados separadamente contra containers reais, sem simulação.

Essa validação cobre instalação, login e movimentação básica. Não representa
um teste completo de todas as quests, do Market ou de todos os computadores e
drivers gráficos. O pacote precisa de Docker Desktop; o primeiro build e o
download automático do cliente precisam de internet.
