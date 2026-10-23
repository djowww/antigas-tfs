# Novidades do projeto na wiki

A página oficial e inicial é a wiki existente, `wiki.php`, também servida na raiz. O visual clássico e as seções do guia são preservados. `blog.php` redireciona para a raiz.

O conteúdo editorial vem de `project-updates.json`: `id`, `date` (YYYY-MM-DD), `title`, `summary`, `changes` (lista do changelog), `paragraphs` (detalhes e validação) e `url` da entrega no GitHub. Textos usam as traduções em `i18n-extra.php`; os valores em inglês também servem de fallback. IDs são estáveis e exclusivos. Use texto simples, sem HTML, e URLs HTTPS deste repositório.

Publique apenas entregas importantes para jogadores e pessoas que testam o projeto: novas versões jogáveis, funcionalidades ou correções relevantes. Agrupe commits relacionados. Refactors, diagnósticos, pequenos ajustes de CI e manutenção não viram notícias isoladas. Não existe importação automática de todo commit.

Antes de publicar: confirme a release ou diff, descreva requisitos e limites, valide JSON e `php tests/project-home-tests.php`, preserve backup privado e confira o HTTPS real. Não confunda código publicado com implantação no jogo público.

Não exponha dados de jogadores, dados pessoais do mantenedor, pagamento, credenciais ou notas privadas de operação. `1 / local123` é somente a conta normal de demonstração do localhost. GET com `?jogar=1` e todos os POSTs continuam usando o cadastro original.
