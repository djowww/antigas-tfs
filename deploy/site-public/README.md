# Portal público Antigas 7.4

Fonte pública de https://tibia74.tech, também mantida na pasta de trabalho `Site/`.

- `index.php`: notícias, cadastro e download do cliente.
- `account.php`: login e gerenciamento de personagens.
- `coins.php`: pedidos Pix com aprovação manual.
- CSS e `classic-assets/`: aparência do portal.
- `client-release.json`: metadados da versão publicada do cliente.

As bibliotecas de segurança/Pix e a configuração do banco são privadas e não integram esta pasta. O caminho padrão das bibliotecas é `/opt/antigas-web/private`, configurável por `ANTIGAS_WEB_LIB`. Não copie credenciais, dumps, backups, arquivos de teste ou documentos de operação para a raiz pública.

A publicação desta pasta não altera a versão do cliente nem reinicia o jogo. Valide os PHP com `php -l` antes de publicar. O README é documentação do repositório; não precisa ser publicado na raiz web.

Revisão de 27/09/2026: acesso ao artigo Tibia na Wikipédia em português, descrição acessível para a abertura de nova aba, ajuda de formulário associada aos campos, URL canônica e respeito à preferência de movimento reduzido.