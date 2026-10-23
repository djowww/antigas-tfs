# Atualizar o diário do projeto

O conteúdo vem de `blog-posts.json`. Não há importação automática do histórico Git.

Publique uma entrada apenas quando uma entrega mudar a experiência de quem joga ou testa: funcionalidade disponível, correção importante, versão jogável ou mudança relevante de segurança. Agrupe commits relacionados numa única notícia. Refactors, diagnósticos, pequenos ajustes de CI e manutenção de documentação não viram notícia por conta própria.

Cada entrada contém `date` (YYYY-MM-DD), `category`, `title`, `summary`, `paragraphs` (lista de textos), `label` e `url` HTTPS da release ou evidência pública. Use texto simples, sem HTML. Mantenha as entradas mais recentes primeiro e explique requisitos e limites reais. Não confunda código publicado com funcionalidade já implantada no servidor público.

Antes de publicar: confirme release/diff e validação da entrega, revise linguagem para jogadores, valide o JSON e a renderização PHP, faça backup do conteúdo atual, atualize os arquivos alterados e confira o acesso HTTPS. A mudança inicial de roteamento mantém GET com `?jogar=1` e todos os POSTs no cadastro original; não remova esse comportamento.

Não exponha dados de jogadores, credenciais de produção, detalhes exploráveis de falhas ou notas privadas de operação. A conta `1 / local123` é exclusivamente a demonstração do pacote localhost.
