# Antigas 7.4 — servidor

Repositório privado do servidor Antigas 7.4. O repositório contém o código-fonte do TFS, scripts e dados do jogo, inclusive o mapa versionado. Não contém o executável compilado nem o arquivo local de configuração com credenciais.

## Estrutura

- `src/`: código-fonte C++ do servidor.
- `data/`: scripts Lua, definições XML/NPC, itens e conteúdo do mundo.
- `data/sql/`: estrutura e migrações do Market.
- `config.example.lua`: exemplo sem credenciais. Copie para `config.lua` no servidor e configure os dados locais. `config.lua` é ignorado pelo Git.

## Trabalho seguro

- Nunca adicione senhas, chaves, dumps do banco, arquivos de jogadores ou logs.
- A `.gitignore` exclui a configuração local, executável, estado de execução e arquivos temporários. O mapa e o conteúdo do jogo permanecem versionados.
- Revise `git status` antes de cada commit. Uma chave inserida em um commit continua no histórico mesmo depois de apagada; se acontecer, troque a credencial e reescreva o histórico antes de enviar.
- Faça mudanças e valide-as em uma cópia de testes. O `git push` não publica o servidor automaticamente. Deploy e reinício são tarefas separadas.

## Compilação

Use o toolchain e as dependências documentados para esta versão do TFS. Os arquivos de projeto em `CMakeLists.txt` e `src/` são a referência; mantenha binários de build fora do repositório.
