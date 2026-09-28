# Portal público Antigas 7.4

Fonte pública de https://tibia74.tech, também mantida na pasta de trabalho `Site/`.

- `index.php`: notícias, cadastro e download do cliente.
- `account.php`: login e gerenciamento de personagens.
- `coins.php`: pedidos Pix com aprovação manual.
- `wiki.php`: guia local do jogador, com links para a Wiki Antigas original.
- `i18n.php` e `i18n-extra.php`: inglês padrão e traduções para português, espanhol e polonês.
- `language.css` e `wiki.css`: seletor de idiomas e apresentação do guia.
- CSS e `classic-assets/`: aparência do portal.
- `client-release.json`: metadados da versão publicada do cliente.

As bibliotecas de segurança/Pix e a configuração do banco são privadas e não integram esta pasta. O caminho padrão das bibliotecas é `/opt/antigas-web/private`, configurável por `ANTIGAS_WEB_LIB`. Não copie credenciais, dumps, backups, arquivos de teste ou documentos de operação para a raiz pública.

A publicação destas páginas não altera a versão do cliente nem reinicia o jogo. Valide os PHP com `php -l` antes de publicar. Os documentos deste repositório não pertencem à raiz web.

O site usa inglês como idioma inicial e permite trocar para português, espanhol e polonês pelas bandeiras. A preferência fica salva entre páginas e visitas.

O botão “Game wiki” abre `/wiki.php`, um guia local resumido que acompanha o cliente v43. Ele também mantém links seguros para a Wiki Antigas publicada no ChatGPT: https://antigas-jogador-wiki.ricardozordan1994.chatgpt.site/#/home. A edição original continua servindo como referência para o catálogo completo de magias.
