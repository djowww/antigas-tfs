![Antigas 7.4 — um mundo clássico para explorar em pedra, aço e bronze](docs/assets/antigas-74-banner.svg)

# Antigas 7.4

[![Compilação e testes](https://github.com/djowww/antigas-tfs/actions/workflows/security-build.yml/badge.svg?branch=main)](https://github.com/djowww/antigas-tfs/actions/workflows/security-build.yml)
[![CodeQL](https://github.com/djowww/antigas-tfs/actions/workflows/codeql.yml/badge.svg?branch=main)](https://github.com/djowww/antigas-tfs/actions/workflows/codeql.yml)

Código-fonte do servidor Antigas: um projeto de MMORPG com a experiência clássica de Tibia 7.4 e sistemas próprios de progressão, comércio e exploração.

O núcleo do Antigas 7.4 utiliza C++11 e LuaJIT, com extensões para o cliente customizado do projeto. Use a distribuição oficial do cliente para manter a compatibilidade de rede e dos módulos.

## Comece por aqui

- [Conheça e jogue Antigas](https://tibia74.tech/)
- [Crie sua conta](https://tibia74.tech/#criar-conta)
- [Baixe o cliente oficial assinado](https://tibia74.tech/#download)
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
| `config.example.lua` | Modelo de configuração para uma instalação própria. |

O servidor usa MySQL/MariaDB para persistência. Este repositório reúne o código-fonte do servidor e fontes selecionadas do cliente e do site. O cliente completo assinado e os serviços privados são distribuídos separadamente; este checkout não é um pacote autossuficiente para executar o jogo. O schema base do banco também precisa ser obtido separadamente; os SQL versionados aqui são do Market. Veja [compilação e configuração](docs/building.md) e [cliente, launcher e site](docs/client-and-web.md).

## Compilar o servidor

Em Linux, com CMake 3.16+, compilador C++11 e as dependências instaladas:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
```

As dependências incluem Boost System/Filesystem, LuaJIT, PugiXML, GMP e a biblioteca cliente MySQL/MariaDB. O [guia de compilação](docs/building.md) descreve os requisitos e a configuração necessária para executar o servidor.

## Participar

Leia o [guia de contribuição](CONTRIBUTING.md) para propor mudanças e a [política de segurança](SECURITY.md) para comunicar vulnerabilidades. A origem do código e os avisos de licença estão descritos em [NOTICE.md](NOTICE.md).
