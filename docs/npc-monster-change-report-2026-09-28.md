# Relatório de alterações de NPCs e monstros — 28/09/2026

## NPCs

Foram atualizados somente textos de fala em 13 NPCs, com 39 respostas alinhadas aos arquivos correspondentes de Desktop\npc. Cada alteração exigiu um gatilho único e idêntico nos dois lados. Não foram alterados palavras-chave, preços, compras, condições de quests, ações, ramificações ou a estrutura dos scripts.

NPCs alterados: alexander, asima, avar, bigben, fenech, frans, haroun, rachel, shiriel, sigurd, tandros, topsy e xodet.

Na revisão seguinte, foram removidas 12 menções a wands/rods de falas em 11 NPCs. Na comparação atual, os únicos 12 textos de fala diferentes entre gatilhos únicos correspondentes são essas referências removidas; os demais textos comparáveis coincidem. Ainda há quatro nomes de arquivo exclusivos entre as pastas e os gatilhos e conteúdos de regra listados acima para reconciliar antes de tornar os conjuntos idênticos.

A pasta de referência e TFS/data/npc contêm 337 arquivos .npc cada, com 335 nomes em comum. Os arquivos markwin.npc e orcking.npc existem apenas na referência; angel.npc e rashid.npc existem apenas no Antigas. Não foram adicionados nem removidos NPCs.

A análise comparativa encontrou 218 gatilhos únicos presentes só na referência e 1.123 só no Antigas, além de 88 casos ambíguos por gatilhos repetidos. Há 728 pares de regras com gatilho único correspondente cujo restante da linha difere além da fala, incluindo valores e formas de ação; esses pontos exigem revisão por regra. As listas de estoque e os preços também permanecem próprios do Antigas, mesmo quando o texto de referência descreve uma oferta diferente.

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

Os XMLs finais foram analisados pelo parser XML. A conferência confirmou os itens e valores de loot da referência nos 158 pares, preservou os drops exclusivos preexistentes e manteve a estrutura XML fora dos elementos `<item>` de loot. `git diff --check` não apontou erros. Nos NPCs, a validação confirmou as 39 substituições de fala elegíveis nos 13 arquivos, sem diferenças restantes nos gatilhos únicos comparáveis. Antes da publicação, os hashes dos 13 NPCs e dos dois arquivos do site foram conferidos; os PHPs passaram pela verificação de sintaxe. O servidor foi reiniciado de forma controlada, voltou a anunciar-se online e as portas 7173 e 7174 ficaram abertas. Não foi feito teste de gameplay com clientes conectados.
