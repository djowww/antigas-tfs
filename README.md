# Antigas 7.4

Código-fonte do servidor Antigas: um projeto de MMORPG com a experiência clássica de Tibia 7.4 e sistemas próprios de progressão, comércio e exploração.

O núcleo utiliza C++11 e LuaJIT, com protocolo **7.72** e extensões para o cliente customizado do projeto. A identidade 7.4 descreve a proposta do jogo; a compatibilidade de rede é definida pelo protocolo e pelos módulos do cliente.

[Site oficial e download do cliente](https://tibia74.tech) · [Documentação](docs/INDEX.md) · [Como contribuir](CONTRIBUTING.md)

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

O servidor usa MySQL/MariaDB para persistência. As fontes complementares de cliente e site têm requisitos próprios: este repositório não oferece um pacote completo e autossuficiente de instalação. O schema base do banco também precisa ser obtido separadamente; os SQL versionados aqui são do Market. Veja [compilação e configuração](docs/building.md) e [cliente, launcher e site](docs/client-and-web.md).

## Compilar o servidor

Em Linux, com CMake 3.16+, compilador C++11 e as dependências instaladas:

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel
```

As dependências incluem Boost System/Filesystem, LuaJIT, PugiXML, GMP e a biblioteca cliente MySQL/MariaDB. O [guia de compilação](docs/building.md) descreve os requisitos e a configuração necessária para executar o servidor.

## Participar

Leia o [guia de contribuição](CONTRIBUTING.md) para propor mudanças e a [política de segurança](SECURITY.md) para comunicar vulnerabilidades. A origem do código e os avisos de licença estão descritos em [NOTICE.md](NOTICE.md).
