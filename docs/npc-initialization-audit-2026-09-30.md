# Inicialização dos NPCs — 30/09/2026

## Achado confirmado: NPC-INIT-01

- **Severidade:** P2 condicional; leitura de estado indeterminado confirmada no
  código, sem reprodução de crash remoto.
- **Arquivos/funções:** `src/npc.h`; `Npc::Npc`, `Npc::onCreatureAppear`,
  `Npc::updateIdleStatus`, `Npc::onThink`, `Npc::doSay` em `src/npc.cpp`.
- **Evidência:** o construtor chama `reset()`, que inicializa `loaded`,
  `focusCreature` e `conversationEndTime`, mas não `isIdle`. A aparição do
  primeiro jogador chama `updateIdleStatus()`, que compara `status != isIdle`
  antes da primeira atribuição garantida a `isIdle`. `onThink()` também lê o
  campo. O valor depende dos bytes anteriores da alocação.
- **Campos relacionados:** `lastTalkCreature` é comparado em `doSay()` e só era
  escrito ao receber fala de jogador. `conversationStartTime` é escrito ao
  iniciar atendimento; não foi comprovada uma leitura anterior nesse caminho.
  Ambos agora têm valor inicial explícito 0 como defesa adicional.
- **Correção:** inicializadores dos três campos na classe: `isIdle = true`,
  `lastTalkCreature = 0`, `conversationStartTime = 0`. O estado idle inicial
  corresponde ao conjunto inicialmente vazio de espectadores.
- **Compatibilidade:** nenhuma alteração de diálogo, venda, item, quest, dano ou
  script NPC. O reset de um NPC já existente continua com o comportamento
  anterior; esta correção é da construção do objeto.

## Regressão

`tests/npc-initialization-tests.cpp` vincula o core real. Constrói o NPC com
placement new sobre armazenamento previamente preenchido com 0x00, 0x01, 0xA5
e 0xFF, verifica os valores iniciais e destrói o objeto. Também altera os campos,
chama o reset real e confirma que sua semântica não foi modificada.

O acesso de teste é feito por um `friend struct` específico; a classe continua
`final`. Não é adicionado método público nem alterado o layout dos dados. Não
há sockets, banco, mapa ou scheduler em execução nesse teste.

O target `npc-initialization` integra o mesmo conjunto CTest do core em release,
hardened, ASan/UBSan e TSan. As quatro execuções passaram no
[CI 36656548841](https://github.com/djowww/antigas-tfs/actions/runs/36656548841),
junto dos outros três jobs. Também passaram as 44 regressões Python locais e
o secret scan. Esses resultados não equivalem a um teste visual ou a uma nova
rodada de carga online.

## Revisão adjacente, sem alterações

- `Condition` tem construtor default apontado pelo scanner. Os caminhos de
  construção de `ConditionDamage` encontrados no repositório usam construtor
  parametrizado ou cópia; nenhuma leitura indeterminada foi demonstrada nesta
  inspeção. O aviso continua como pendência, sem inicialização arbitrária de
  tipos/duração que poderia modificar combate ou persistência.
- `RaidEvent::delay` é atribuído pelo configurador, que falha se o atributo
  estiver ausente. Os quatro configuradores derivados chamam o base e propagam
  essa falha; `Raid::loadFromXml` só insere eventos configurados com sucesso,
  antes de ordenar/agendar. Não foi encontrado uso anterior à atribuição nesse
  caminho, por isso nenhuma alteração de temporização foi aplicada.
- `ChatChannel::id`: o canal privado provisório e os canais criados nos caminhos
  de chat inspecionados usam construtores parametrizados. Não foi demonstrado
  canal com ID indeterminado; o aviso de construtor default não basta para
  classificar uma vulnerabilidade.
- Os demais avisos do inventário Cppcheck permanecem visíveis. A aprovação do
  gate indica ausência de diagnóstico novo não revisado, não ausência de risco.

## Resultado do scanner

[Cppcheck do commit 8030fd1](https://github.com/djowww/antigas-tfs/actions/runs/36656548937):
73 unidades verificadas, 47 diagnósticos não informativos, nenhum novo.
Desapareceram exatamente os três avisos de inicialização de `Npc`; essas três
entradas foram removidas do inventário após comparar os relatórios. Os avisos
informativos de includes/cobertura continuam preservados e documentados.

## Publicação

- Binário hardened do commit `8030fd19e1a6eb694e1958f3e5db0f44cc1d13a0` publicado
  com backup e reinício do serviço em 30/09/2026, online às 01:50:25 UTC.
- SHA-256 conferido no executável do processo ativo:
  `3335b197c091211979b4d41109e984a4a6db44f86b4918b481724383c06a9792`.
- Verificação posterior: serviço ativo, zero reinícios automáticos, portas
  7173/7174 acessíveis externamente e logs observados sem erros Lua ou aviso de
  loop. Não houve nova rodada de carga nem inspeção visual do cliente.
- Backup anterior: `/opt/imperium772/backups/npc-initialization-8030fd1-20260930`.
- Cliente/launcher permanece v53. Nenhum desligamento do computador Windows.
