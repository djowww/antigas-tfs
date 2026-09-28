# Raridade de equipamentos — cliente v44

## Regras

Cada equipamento elegível criado pelo loot de monstros pode receber uma raridade e um bônus. Itens existentes, compras em NPC e recompensas não recebem sorteio retroativo. A configuração `itemRarityLootChance` usa escala de 0 a 10000; o padrão 1000 representa 10% dos equipamentos elegíveis. As chances originais de cada item no loot continuam valendo.

| Raridade | Borda | Peso entre os itens com raridade | HP/mana/resistência | Ataque/defesa/skill | Speed da bota |
|---|---|---:|---:|---:|---:|
| Incomum | Verde `#42C96B` | 50% | 1% | +1 | 1–2% |
| Raro | Azul `#3E8BFF` | 27% | 2% | +2 | 3–4% |
| Épico | Roxo `#A855F7` | 14% | 3% | +3 | 5–6% |
| Lendário | Amarelo `#F5C542` | 7% | 4% | +4 | 7–8% |
| Mítico | Vermelho `#EF4444` | 2% | 5% | +5 | 9–10% |

- Torso e pernas: um bônus sorteado entre vida máxima, mana máxima ou resistência. A resistência escolhe físico, energia, terra, fogo ou gelo.
- Botas: velocidade, calculada sobre a velocidade base do personagem.
- Anéis e amuletos: uma skill entre fist, club, sword, axe, distance, shielding, fishing e magic level.
- Armas: ataque; wands também recebem o aumento no dano produzido. Arcos somam o ataque à munição.
- Escudos: defesa. Refino e raridade são somados uma única vez.
- Capacetes, mochilas, munição e outros itens empilháveis ficam fora do sorteio desta versão.

Percentuais de HP/mana usam os valores base e arredondam para cima; velocidade arredonda para o inteiro mais próximo. Bônus acompanham mudanças de nível e alterações dos máximos via Lua. Duas resistências do mesmo tipo se somam e são aplicadas ao dano restante após os efeitos nativos. Carregar armadura na mão não concede o bônus do slot de torso/pernas.

## Persistência e integração

A raridade pertence à instância do item. É serializada como atributo 39, com quatro bytes: raridade, tipo do bônus, valor e subtipo. Clone, salvamento e transformações preservam o atributo. Os efeitos são derivados do equipamento, sem gravar bônus nos atributos base do personagem.

O cliente v44 consulta o opcode 127 para inventário e containers abertos. Cada consulta tem um token; respostas antigas são descartadas e páginas grandes são divididas em lotes de 40. Bordas e tooltips são restaurados após arrastar e limpos quando o item muda.

O Market atual representa ofertas por tipo/quantidade e não suporta atributos da instância; portanto recusa itens raros e refinados. Vendas a NPCs também protegem raros contra consumo por ID. Entregas de quests mantêm a regra original de aceitação de itens.

## Testes reproduzíveis

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DTFS_BUILD_RARITY_TESTS=ON
cmake --build build --parallel 1
ctest --test-dir build --output-on-failure
```

O teste C++ usa o núcleo real, `items.srv`, vocações e uma definição de NPC; não inicia mundo, banco ou listeners. Abrange atributos persistidos, refino, dano, resistência, evolução, chamadas Lua, loot e os caminhos de equipar/retirar/transformar anéis com efeitos nativos.

As suítes `rarity-ui-tests.lua` e `rarity-economy-tests.lua` exercitam os scripts reais com objetos simulados. `rarity-ui-runner.py` executa Lua 5.2 e LuaJIT via Lupa. `rarity-live.py` é um teste operacional separado: cria uma única conta comum descartável e só a remove após confirmar o logout. Sua execução exige o ambiente administrativo do banco e o servidor já atualizado.

## Recuperação

O binário anterior à raridade não entende o atributo 39. Não reinstalá-lo diretamente depois que itens raros forem salvos. Definir chance zero suspende novos sorteios, sem remover os atributos já existentes.

`deploy/rarity-rollback-compat.patch`, aplicado à base `64f50b8`, adiciona apenas leitura, escrita e preservação opaca da raridade nas transformações. Serve para compilar um binário de recuperação que conserva o banco atual sem aplicar os bônus novos. `tests/rarity-compat-tests.cpp` valida essa base com o patch. Use esse fallback em manutenção e restaure os scripts da versão anterior: ele não oferece as APIs Lua nem as proteções de venda da v44.

Backups de banco e configuração devem permanecer privados no host. Restaurar um banco antigo pode descartar progresso posterior; o fallback compatível evita essa exigência.
