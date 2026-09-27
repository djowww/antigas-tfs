# Fórmula de dano do servidor

Este documento resume o cálculo encontrado no código do servidor em `Servidor/TFS`.

## Ataque físico de jogador

O servidor calcula o dano máximo da arma com:

```text
máximo = round((nível inteiro / 5) + ((((skill / 4 + 1) × (ataque / 3)) × 1,03) / fatorDeAtaque))
```

Em que `skill` é a habilidade usada pela arma (por exemplo, sword, axe, club ou distance), `ataque` é o valor de ataque do item e `fatorDeAtaque` depende do modo de luta:

- Ataque: `1,0`
- Balanceado: `1,2`
- Defesa: `2,0`

Para ataques corpo a corpo, o dano sorteado vai de `0` até o máximo. Para ataques à distância, o mínimo depende do alvo: arredonda para cima `10% do nível` contra jogadores e `20% do nível` contra monstros. O ataque máximo à distância inclui o ataque da munição e da arma, quando aplicável.

O valor é multiplicado pelo modificador da vocação (`meleeDamage` ou `distDamage`). No arquivo atual de vocações, esses modificadores são `1,0` para todas as vocações.

## Magias com fórmula nível/magic level

A fórmula genérica do servidor usa:

```text
base = 2 × nível + 3 × magicLevel
mínimo = base × coeficienteMínimo + constanteMínima
máximo = base × coeficienteMáximo + constanteMáxima
dano = valor aleatório entre mínimo e máximo
```

O dano é representado internamente como valor negativo. As magias podem definir os coeficientes e constantes no script ou substituir esse cálculo por um callback próprio. Por isso, não existe um único intervalo que sirva para todas as magias.

## Mitigação e limites

O dano calculado ainda pode ser reduzido ou zerado ao atingir o alvo, por defesa, armadura, bloqueio ou imunidade, conforme o tipo de combate e os parâmetros do ataque. Monstros também podem ter ataques com valores próprios definidos em seus arquivos e scripts.

## Arquivos usados como referência

- `Servidor/TFS/src/weapons.cpp` — cálculo do dano máximo e dano aleatório de armas.
- `Servidor/TFS/src/player.cpp` — fator de ataque dos modos de luta.
- `Servidor/TFS/src/combat.cpp` — fórmula genérica por nível e magic level.
- `Servidor/TFS/src/game.cpp` e `Servidor/TFS/src/creature.cpp` — aplicação de bloqueio/mitigação.
- `Servidor/TFS/data/XML/vocations.xml` — modificadores de dano por vocação.
- `Servidor/TFS/data/spells/lib/spells.lua` — função auxiliar de dano em Lua; atualmente só está definida nesse arquivo.

> Observação: a fórmula reflete o código que está nesta cópia do servidor. Scripts individuais podem usar cálculos diferentes.
