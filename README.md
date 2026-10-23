![Tibia 7.4 - A classic rpg version](docs/assets/antigas-74-banner.svg)

# Tibia 7.4 - A classic rpg version

[![Compilação e testes](https://github.com/djowww/tibia-7.4-a-classic-rpg-version/actions/workflows/security-build.yml/badge.svg?branch=main)](https://github.com/djowww/tibia-7.4-a-classic-rpg-version/actions/workflows/security-build.yml)
[![CodeQL](https://github.com/djowww/tibia-7.4-a-classic-rpg-version/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/djowww/tibia-7.4-a-classic-rpg-version/actions/workflows/codeql.yml)

Um servidor independente inspirado na experiência clássica de Tibia 7.4, anteriormente conhecido como **Antigas**. Um projeto feito para compartilhar com a comunidade o carinho por esse mundo e pela aventura de descobrir o que existe depois da próxima escada.

## Um sonho que virou servidor

Desenvolver este servidor foi a realização de um sonho: transformar minha admiração pelo Tibia clássico em um lugar onde outras pessoas também pudessem viver suas próprias histórias. Quis oferecer à comunidade um mundo para explorar, encontrar companhia para uma caça, aprender com os erros e sentir a alegria de conquistar algo com o próprio esforço.

Por trás de cada ajuste existe esse desejo de receber bem quem chega. Aprender a desenvolver, investigar problemas e cuidar dos detalhes faz parte de construir algo que eu gostaria de compartilhar com outros jogadores. O projeto nasceu desse carinho e continua sendo um trabalho em evolução.

Mais do que disponibilizar um servidor, quero prestigiar a comunidade que mantém viva essa paixão. A quem joga, testa, aponta um problema, compartilha uma ideia ou dedica seu tempo a ajudar: meu muito obrigado. Espero que este mundo possa ser palco de boas aventuras e boas lembranças para vocês também.

— **[djowww](https://github.com/djowww)**, mantenedor do projeto

## Créditos e agradecimentos

Este sonho se apoia no trabalho de muitas pessoas. A manutenção e as adaptações deste projeto não substituem a autoria das bases utilizadas:

- **CipSoft e os criadores de Tibia:** pela criação do jogo e do universo que inspiram esta homenagem. Este é um projeto independente, sem vínculo oficial com a CipSoft.
- **Alejandro Mujica:** os cabeçalhos do núcleo identificam a base como **Tibia GIMUD Server**, com copyright de 2017 e termos GPL versão 2 ou posterior. Consulte [os avisos de origem](NOTICE.md) e os cabeçalhos preservados no código.
- **Comunidades OpenTibia e OTClient, incluindo os colaboradores das distribuições utilizadas:** pelas bases, ferramentas e conhecimentos que permitem desenvolver servidores e clientes independentes. O snapshot do cliente contém referências a OTClientV8; os avisos e termos de cada componente devem ser preservados.
- **rxi:** pela biblioteca JSON em Lua, distribuída sob licença MIT, com os avisos originais mantidos nos arquivos do servidor e do cliente.
- **Colaboradores do repositório e comunidade de jogadores:** pelas contribuições, testes, relatos e ideias. O histórico de [commits](https://github.com/djowww/tibia-7.4-a-classic-rpg-version/commits/main/) e a lista de [contribuidores](https://github.com/djowww/tibia-7.4-a-classic-rpg-version/graphs/contributors) registram as contribuições versionadas.

Os créditos acima não atribuem autoria exclusiva sobre mapas, gráficos, músicas ou outros conteúdos de terceiros. Os avisos existentes continuam válidos; veja [NOTICE.md](NOTICE.md) para a procedência documentada e os limites de identificação dos componentes.

## Sobre o projeto

O núcleo utiliza C++11 e LuaJIT, com extensões para o cliente customizado. A inspiração é clássica, mas há sistemas próprios de progressão, comércio e exploração; não se trata de uma reprodução integral das regras históricas. Use o cliente distribuído pelo projeto para manter a compatibilidade de rede e dos módulos.

## Comece por aqui

### Testar no seu computador

Baixe o [pacote local para Windows](https://github.com/djowww/tibia-7.4-a-classic-rpg-version/releases/tag/local-test-v1), extraia e abra **START-LOCAL.cmd**, com o Docker Desktop em execução. O pacote inclui o cliente; ao usar o repositório, o iniciador baixa e verifica o cliente automaticamente.

**Conta: `1` · Senha: `local123` · Personagem: `Local Adventurer`.** Servidor e cliente usam **127.0.0.1**, nas portas **17173/17174**. Banco e chaves são preparados automaticamente, sem dados da produção. A primeira inicialização compila o servidor e pode demorar vários minutos; exige internet. Depois, use **STOP-LOCAL.cmd** para parar sem apagar o progresso.

Veja o [guia do ambiente local](local/README.md) para requisitos, persistência e diagnóstico. Não é necessário configurar o site ou os pagamentos para jogar localmente.

### Comunidade e servidor público

- [Conheça o servidor](https://tibia74.tech/)
- [Crie sua conta](https://tibia74.tech/#criar-conta)
- [Baixe o cliente do projeto](https://tibia74.tech/#download)
- [Leia o guia do jogador](https://tibia74.tech/wiki.php)

Para explorar o projeto, veja a [documentação](docs/INDEX.md), o [guia de compilação](docs/building.md), [como contribuir](CONTRIBUTING.md) e a [política de segurança](SECURITY.md).

## Sistemas do projeto

- **Market:** ofertas de compra e venda em Gold e Antigas Coins, negociações parciais, histórico e coleta de entregas.
- **Achievements e Bestiary:** conquistas com recompensas e progresso persistente por personagem, além de contadores de abates de monstros.
- **Diário de quests:** missões e etapas reveladas conforme as descobertas do personagem, com busca e filtros.
- **Raridade de equipamentos:** cinco tiers de raridade, atributos adicionais e identificação visual no inventário, nos containers e no chão.
- **Loot:** canal dedicado com cores por raridade e avisos para o dono do loot e sua party.

Consulte o [guia dos sistemas](docs/systems.md) para conhecer as regras e integrações.

## Código e conteúdo

| Caminho | Conteúdo |
| --- | --- |
| `src/` | Núcleo C++: mundo, combate, rede, persistência e APIs Lua. |
| `data/` | Scripts Lua, NPCs, monstros, itens, definições XML e mapa. |
| `data/sql/` | Estrutura e migrações do Market. |
| `deploy/` | Fontes complementares do cliente, launcher Windows, portal web e ferramentas de implantação. |
| `tests/` | Testes e ferramentas de desenvolvimento. |
| `tools/` | Ferramentas de manutenção e preparação de releases. |
| `docs/` | Guias de compilação, sistemas e componentes complementares. |
| `local/` e `compose.yaml` | Instalação local, banco vazio, conta de demonstração e iniciador do cliente. |
| `config.example.lua` | Modelo de configuração para uma instalação própria. |

O servidor usa MySQL/MariaDB para persistência. O modo local inclui schema vazio, dados de demonstração e preparação automática por Docker Compose; o cliente completo é distribuído na release local. Os serviços privados do portal e de pagamentos não fazem parte desse ambiente. O launcher de produção continua separado e verifica assinaturas ECDSA e SHA-256. Para configurações próprias, veja [compilação e configuração](docs/building.md) e [cliente, launcher e site](docs/client-and-web.md).

## Compilar o servidor

Em Linux, com CMake 3.16+, compilador C++11 e as dependências instaladas:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
```

As dependências incluem Boost System/Filesystem, LuaJIT, PugiXML, GMP e a biblioteca cliente MySQL/MariaDB. O [guia de compilação](docs/building.md) descreve os requisitos e a configuração necessária para executar o servidor.

## Participar

Leia o [guia de contribuição](CONTRIBUTING.md) para propor mudanças e a [política de segurança](SECURITY.md) para comunicar vulnerabilidades. A origem do código e os avisos de licença estão descritos em [NOTICE.md](NOTICE.md).
