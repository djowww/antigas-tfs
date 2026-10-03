# Compilação e configuração do servidor

O servidor usa CMake 3.16 ou posterior, C++11, Boost system/filesystem, LuaJIT, PugiXML, GMP, threads e a biblioteca cliente MySQL/MariaDB. [CMakeLists.txt](../CMakeLists.txt) define o build; o [workflow de build](../.github/workflows/security-build.yml) registra as dependências e variantes do CI.

## Ubuntu Linux

Na raiz do repositório, instale as dependências utilizadas pelo CI em Ubuntu 22.04 e 24.04:

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends -y \
  build-essential cmake pkg-config \
  libboost-system-dev libboost-filesystem-dev \
  libluajit-5.1-dev luajit libpugixml-dev \
  libmariadb-dev libmariadb-dev-compat libgmp-dev

cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 2
```

O executável gerado fica em `build/tfs`; a pasta `build/` é ignorada pelo Git. `libmariadb-dev-compat` fornece a interface `mysqlclient` procurada via pkg-config. As opções `TFS_BUILD_*` habilitam testes específicos e são descritas no CMake; os comandos acima compilam o servidor sem habilitá-las.

## Pré-requisitos para executar

Este checkout não constitui uma instalação pronta para uso: faltam o schema base completo do banco, credenciais, chave RSA privada e uma distribuição completa do cliente.

Copie o [exemplo de configuração](../config.example.lua) e ajuste banco, rede e regras para seu ambiente:

```sh
cp config.example.lua config.lua
```

`config.lua` é ignorado pelo Git. O programa carrega a configuração e `data/` em relação ao diretório de execução; ao executar `./build/tfs`, use a raiz do repositório como diretório de trabalho.

Disponibilize uma base compatível antes de iniciar. Os arquivos em `data/sql/` acrescentam tabelas do Market e não substituem o schema base. Consulte [migrações e compatibilidade MySQL/MariaDB](../data/sql/README-market.md): `market-v3.sql` usa uma sintaxe de criação de índice aceita pelo MariaDB que requer adaptação no MySQL.

As correções de recuperação de conexão do banco e de permissão para retirar itens de contêineres em casas não exigem migração SQL. Elas são aplicadas ao recompilar e substituir o executável, após salvamento e encerramento gracioso do servidor. A recuperação permite uma reconexão e repetição apenas para leituras idempotentes explicitamente habilitadas fora de transações; escritas e consultas em transações não são repetidas.

## Chave RSA e cliente

A inicialização exige que `ANTIGAS_RSA_KEY_FILE` aponte para um arquivo privado legível pelo processo. O [carregador RSA](../src/rsa.cpp) espera exatamente dois primos decimais, `p` e `q`, separados por espaço ou quebra de linha, cujo módulo tenha 1024 bits; o expoente público é 65537. Um PEM não é o formato esperado por esse carregador.

Mantenha o arquivo fora do repositório e configure a variável no ambiente que inicia o servidor. O cliente precisa usar a chave pública correspondente ao par privado escolhido. A chave pública incluída no snapshot do cliente não fornece a chave privada necessária para uma instalação independente.

O servidor aceita protocolo 772 (7.72), com extensões próprias. Consulte [cliente, launcher e site](client-and-web.md) para montar uma distribuição compatível.
