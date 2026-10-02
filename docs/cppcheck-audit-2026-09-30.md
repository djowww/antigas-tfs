# Revisão Cppcheck — 30/09/2026

## Método e limites

Cppcheck 2.13.0 no Ubuntu 24.04, usando `compile_commands.json` produzido pelo
CMake em Release, arquitetura unix64, modelo POSIX e categorias warning,
performance, portability e information. Foram percorridas as **73 unidades de
compilação do servidor**. Isso não inclui código fora do build, configuração
Windows nem todos os caminhos dinâmicos de Lua.

[Primeiro relatório](https://github.com/djowww/antigas-tfs/actions/runs/36655268858):
54 diagnósticos não informativos. [Nova análise após a correção](https://github.com/djowww/antigas-tfs/actions/runs/36655725889):
50; os quatro avisos de `Events` desapareceram. Os XML completos permanecem nos
artefatos dos jobs. Nenhuma categoria foi suprimida para obter essa redução.

Há 101 ocorrências informativas de `missingIncludeSystem` e três de
`checkLevelNormal`. O Cppcheck modela a biblioteca padrão sem precisar de seus
cabeçalhos, mas a lista também inclui headers de terceiros em diretórios
implícitos do compilador. Portanto esta análise não prova cobertura semântica
completa das dependências. Os avisos permanecem nos resultados; a build real
continua sendo uma verificação separada.

## Correção confirmada

| ID | Severidade | Local | Evidência e impacto | Correção / regressão |
|---|---|---|---|---|
| EVENTS-01 | P2 condicional | `src/events.cpp`, `Events::clear` | `partyOnShareExperience`, `playerOnRemoveCount` e `playerOnUseItem` não recebiam -1 no construtor via `clear()`. Se o evento não fosse carregado, o dispatch poderia tentar usar um identificador indeterminado. Depois de carregar e chamar `clear()`, esses callbacks também continuavam ativos. `playerOnReportRuleViolation` era igualmente omitido, mas não possui implementação/caminho ativo confirmado. Não foi reproduzido crash remoto. | Adicionadas quatro atribuições -1 seguindo o padrão existente. Regressão nativa carrega callbacks Lua reais, confirma execução, limpa, carrega XML com eventos desativados e confirma ausência de execução, por dois ciclos. Regressão Python compara todos os IDs declarados com os IDs resetados. |

Os três eventos ativos citados estão habilitados no XML atual e são carregados
normalmente no startup. O risco aparece com evento ausente/desativado ou uso da
API de reset. Não foi identificado um comando de produção que chame esse reset;
o teste de reload exercita diretamente a API. Não mudamos os callbacks, as
regras de experiência ou a autorização de uso/remoção de itens.

## Diagnósticos revisados que não confirmaram vulnerabilidade

- `missingReturn`, `Container::queryRemove`: o aviso de caminho sem retorno era
  falso, mas a revisão separada do bloco `HouseTile` confirmou um problema de
  autorização: `onlyInvitedCanMoveHouseItems` é verdadeiro por padrão, porém a
  função retornava sucesso antes de delegar a checagem de convite. A delegação
  agora ocorre antes do retorno de sucesso, com uma regressão de ordem no teste
  `test_container_house_removal`. O achado `missingReturn` foi removido do
  baseline após não aparecer no novo relatório Cppcheck 2.13; ainda falta um
  ensaio dinâmico no jogo com uma conta não convidada.
- `ctunullpointer` e `nullPointerRedundantCheck`, `InstantSpell`: ambos os ramos
  que encontram alvo nulo retornam ou definem `useDirection = true`. A chamada
  denunciada ocorre somente quando `useDirection` é falso. O outro chamador
  verifica alvo e saúde explicitamente. Não foi confirmado caminho nulo.
- `localtimeCalled`: o único uso de `std::localtime` fica sob mutex e copia o
  resultado antes de liberar a trava; há regressão concorrente para o helper.

As exceções acima são específicas e vinculadas ao conteúdo dos arquivos
revisados. Modificações nesses arquivos exigem nova revisão, mesmo se o aviso
mantiver o mesmo texto.

## Pendências visíveis

Os demais avisos ficam como `NEEDS_INVESTIGATION`, inclusive inicialização em
`Npc`, `Condition`, `ScriptReader`, `Outfit`, `ChatChannel` e outros tipos.
Não se presume que um membro sem inicialização no construtor seja lido antes de
ser preenchido, nem que todo aviso seja falso. As sugestões de performance
aguardam profiling. Esses registros não contam automaticamente como novas
vulnerabilidades confirmadas P0/P1/P2/P3.

## Como manter o gate

`tests/cppcheck-baseline.json` é um inventário explícito do legado, com razão e
classificação por diagnóstico. Não é um arquivo de supressão do Cppcheck. O
workflow preserva o XML completo e `tests/cppcheck_gate.py`:

1. exige relatório XML íntegro e confirmação de todas as unidades de compilação;
2. rejeita falhas internas/sintáticas do analisador;
3. rejeita diagnósticos novos ou ocorrências adicionais de um mesmo diagnóstico;
4. exige revisão ao mudar a versão do analisador;
5. não permite classificar erro do analisador como pendência aceita;
6. exige reavaliação das exceções falsas-positivas quando seu código muda.

Não atualizar o inventário automaticamente para deixar o CI verde. Corrigir o
bug ou registrar a evidência específica da classificação. Relatórios vazios,
execuções incompletas e diagnósticos fora da árvore de fontes falham no gate.

Referência: [manual oficial do Cppcheck](https://cppcheck.sourceforge.io/manual.html).

## Verificação desta entrega

- [CI da correção EVENTS-01](https://github.com/djowww/antigas-tfs/actions/runs/36655725879):
  sete jobs aprovados, incluindo o teste nativo `events-reset` nas quatro
  configurações release/hardened/ASan+UBSan/TSan.
- [Gate Cppcheck completo](https://github.com/djowww/antigas-tfs/actions/runs/36655992047):
  aprovado contra o inventário explícito, com XML e progresso preservados.
- 44 regressões Python locais aprovadas, incluindo teste de multiplicidade,
  mudança de versão, relatório inválido, path externo e invalidação de exceções
  após alteração de código.
- Artefato hardened do commit `30abd168d0fc1dc70bf6b522f3904bf14f871b0c`:
  SHA-256 `7c286f4b0085578bd88c2b5658b26ea8c284efe254ce5a316b2cbb276e02e926`.
  A rodada dinâmica de 50 jogadores documentada anteriormente pertence ao
  binário anterior; não foi repetida neste artefato.
- Publicado em produção às 01:41:26 UTC. Hash conferido em `/proc/<pid>/exe`,
  serviço ativo, zero reinícios automáticos e startup sem erros Lua observados.
  As portas 7173/7174 responderam a conexões TCP externas. Staging permanece
  inativo e o manifesto oficial do cliente continua na versão 53.
- Backup do executável anterior preservado fora do repositório; o caminho
  exato do servidor foi omitido desta documentação pública.
