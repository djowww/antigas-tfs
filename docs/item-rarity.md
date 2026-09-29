# Raridade de equipamentos

## Regras

Cada equipamento elegível criado pelo loot de monstros pode receber uma raridade. A quantidade de status adicionais corresponde ao tier: verde 1, azul 2, roxo 3, lendário 4 e mítico 5. Cada item recebe status distintos, sem repetição no mesmo item. A configuração `itemRarityLootChance` usa escala de 0 a 10000; o padrão 1000 representa 10% dos equipamentos elegíveis. As chances originais de cada item no loot continuam valendo.

| Raridade | Borda | Peso entre os itens com raridade | Status por item |
|---|---|---:|---:|
| Incomum | Verde `#42C96B` | 50% | 1 |
| Raro | Azul `#3E8BFF` | 27% | 2 |
| Épico | Roxo `#A855F7` | 14% | 3 |
| Lendário | Amarelo `#F5C542` | 7% | 4 |
| Mítico | Vermelho `#EF4444` | 2% | 5 |

- A primeira linha preserva o status principal do tipo do equipamento: armas recebem ataque, escudos defesa, botas velocidade, joias uma skill, e torso/pernas vida, mana ou resistência.
- Os status adicionais são sorteados sem repetição entre vida máxima, mana máxima, velocidade, resistências (físico, energia, terra, fogo e gelo) e skills (fist, club, sword, axe, distance, shielding, fishing e magic level). Eles também funcionam em outros equipamentos elegíveis.
- Bônus de vida, mana e resistência usam o percentual do tier; velocidade adicional usa 2% por tier; skills usam +1 por tier. O bônus principal de botas mantém sua faixa anterior de 1–2%, 3–4%, 5–6%, 7–8% ou 9–10%.
- O total de resistência continua limitado a 100%. Refino e raridade de ataque/defesa são somados uma única vez.
- Capacetes, mochilas, munição e outros itens empilháveis ficam fora do sorteio desta versão.

Percentuais de HP/mana usam os valores base e arredondam para cima; velocidade arredonda para o inteiro mais próximo. Bônus acompanham mudanças de nível e alterações dos máximos via Lua. Duas resistências do mesmo tipo se somam e são aplicadas ao dano restante após os efeitos nativos. Carregar armadura na mão não concede o bônus do slot de torso/pernas.

## Persistência e integração

A raridade pertence à instância do item. O atributo 39 guarda o tier e o status principal; o atributo 40 guarda os status adicionais em códigos compactos de cinco bits. Clones, salvamentos e transformações preservam ambos. Equipamentos salvos no formato antigo recebem status faltantes de forma determinística ao carregar, então o próximo salvamento os persiste sem mudar o tier ou o primeiro status. Os efeitos são derivados do equipamento, sem gravar bônus nos atributos base do personagem.

O opcode 127 envia tier e todos os status ao cliente. Atualizações de slots do inventário levam os metadados no mesmo pacote do item para evitar um quadro sem cor no login; containers continuam recebendo metadados junto com seu conteúdo. Consultas para páginas e mudanças individuais continuam usando tokens, e respostas antigas são descartadas. Tooltips listam os status completos; bordas e cores são restauradas após arrastar e limpas quando o item muda.

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

O binário anterior à raridade não entende os atributos 39 e 40. Não reinstalá-lo diretamente depois que itens raros forem salvos. `deploy/rarity-rollback-compat.patch` ensina o binário de recuperação a preservar ambos como dados opacos durante leitura, salvamento e transformação. Definir chance zero suspende novos sorteios, sem remover os atributos já existentes.

`deploy/rarity-rollback-compat.patch`, aplicado à base `64f50b8`, adiciona apenas leitura, escrita e preservação opaca da raridade nas transformações. Serve para compilar um binário de recuperação que conserva o banco atual sem aplicar os bônus novos. `tests/rarity-compat-tests.cpp` valida essa base com o patch. Use esse fallback em manutenção e restaure os scripts da versão anterior: ele não oferece as APIs Lua nem as proteções de venda da v44.

Backups de banco e configuração devem permanecer privados no host. Restaurar um banco antigo pode descartar progresso posterior; o fallback compatível evita essa exigência.
