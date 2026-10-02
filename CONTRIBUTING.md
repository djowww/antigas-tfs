# Como contribuir

O Antigas reúne código C++, scripts Lua e componentes complementares do cliente e do portal. Comece pela [documentação](docs/INDEX.md) e pelo [guia de compilação](docs/building.md).

## Relatar um problema

Abra uma [issue](https://github.com/djowww/antigas-tfs/issues) com o comportamento esperado, o que aconteceu, a versão ou commit utilizado e os passos para reproduzir. Inclua apenas o trecho de log necessário.

Para vulnerabilidades, use o canal indicado em [SECURITY.md](SECURITY.md).

## Propor uma mudança

1. Crie uma branch a partir da `main` atual.
2. Mantenha o pull request focado em uma mudança e explique o problema que ela resolve.
3. Preserve os avisos de autoria e licença dos arquivos.
4. Atualize a documentação quando mudar uma regra, configuração ou interface.
5. Descreva as verificações realizadas e eventuais limitações.

Use uma instalação isolada para alterações que dependam do mundo, do banco ou de contas. Configurações pessoais, chaves privadas, dumps, logs de jogadores e resultados operacionais ficam fora do Git.

## Verificações

Os workflows em [`.github/workflows/`](.github/workflows/) descrevem as verificações disponíveis de C++, Lua, Python, PHP e launcher. Escolha as que correspondem à mudança.

Para documentação, confira os links relativos e execute `git diff --check`. Para alterações no servidor, as opções de testes em [`CMakeLists.txt`](CMakeLists.txt) permitem compilar suítes isoladas; indique no pull request quais foram executadas.

O snapshot em [`deploy/client-current/`](deploy/client-current/) precisa ser integrado a um cliente completo para validação da interface. Os componentes do portal também têm dependências externas, descritas no [guia de cliente e site](docs/client-and-web.md).
