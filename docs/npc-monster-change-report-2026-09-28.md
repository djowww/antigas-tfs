# Relatório de alterações de NPCs e monstros — 28/09/2026

## NPCs

Foram atualizados somente textos de fala em 13 NPCs, com 39 respostas alinhadas aos arquivos correspondentes de Desktop\npc. Cada alteração exigiu um gatilho único e idêntico nos dois lados. Não foram alterados palavras-chave, preços, compras, condições de quests, ações, ramificações ou a estrutura dos scripts.

NPCs alterados: alexander, asima, avar, bigben, fenech, frans, haroun, rachel, shiriel, sigurd, tandros, topsy e xodet.

A pasta de referência e TFS/data/npc contêm 337 arquivos .npc cada, com 335 nomes em comum. Os arquivos markwin.npc e orcking.npc existem apenas na referência; angel.npc e rashid.npc existem apenas no Antigas. Não foram adicionados nem removidos NPCs.

A comparação encontrou 219 regras da referência sem um gatilho exatamente correspondente no Antigas e 88 casos de gatilhos repetidos/ambíguos; esses ramos foram preservados. As listas de estoque e os preços também permanecem próprios do Antigas, mesmo quando o texto de referência descreve uma oferta diferente.

## Monstros alterados

Foram alterados 34 XMLs de monstros do Antigas, comparados a 158 definições correspondentes da pasta `Desktop\monsters`:

`badger`, `bandit`, `bear`, `beholder`, `blackknight`, `caverat`, `chicken`, `cryptshambler`, `demon`, `dragon`, `dragonlord`, `dwarfguard`, `efreet`, `elfarcanist`, `firedevil`, `ghoul`, `hyaena`, `marid`, `minotaurmage`, `mummy`, `necromancer`, `necropharus`, `orcleader`, `orcshaman`, `priestess`, `rat`, `rotworm`, `scarab`, `serpentspawn`, `skunk`, `terrorbird`, `wildwarrior`, `witch` e `wolf`.

### Valores alinhados

- Demon's speed: `260` → `240`.
- Dwarf Guard: experiência `170` → `165`; custo de mana `600` → `650`.
- Wild Warrior: vida `120` → `135`; experiência `55` → `60`.
- Orc Leader: armadura `27` → `20`.
- Scarab: ataque corpo a corpo `27` → `25`; habilidade `43` → `42`.
- Bandit: removida a imunidade a energia que não existe na referência.
- Minotaur Mage: a fala marcada como sussurro na referência não tem equivalente em TFS; o XML foi ajustado de grito para fala normal.

### Loot

As linhas de loot da referência foram incorporadas com seus IDs, quantidades máximas e chances. Sete linhas existentes tiveram quantidade/chance alinhadas em Black Knight, Dragon Lord e Necromancer. Drops exclusivos do Antigas foram mantidos para não remover itens usados por quests e conteúdo próprio do servidor; por isso algumas listas ainda têm itens adicionais em relação à referência.

## Validação

Os XMLs finais foram analisados pelo parser XML. A conferência confirmou os itens e valores de loot da referência nos 158 pares, preservou os drops exclusivos preexistentes e manteve a estrutura XML fora dos elementos `<item>` de loot. `git diff --check` não apontou erros. Não foi feito teste de inicialização do servidor nesta etapa.
