# Raridade de equipamentos

## Regras

O núcleo atual mantém a raridade como metadados persistentes e identidade visual. Desde a integração das regras clássicas auditadas, esses metadados **não concedem bônus numéricos** de ataque, defesa, vida, mana, velocidade, skills ou resistência. Atributos de refino e efeitos nativos dos equipamentos continuam seguindo suas próprias regras. Os testes verificam essa separação sem reativar os bônus antigos.

Cada equipamento elegível criado pelo loot de monstros pode receber uma raridade. A quantidade de status por item corresponde ao tier: incomum 1, raro 2, épico 3, lendário 4 e mítico 5. Cada item recebe status distintos, sem repetição no mesmo item. A configuração `itemRarityLootChance` usa escala de 0 a 10000; o padrão 1000 representa 10% dos equipamentos elegíveis. As chances originais de cada item no loot continuam valendo.

| Raridade | Identidade visual | Peso entre os itens com raridade | Status por item |
|---|---|---:|---:|
| Incomum | Jade; 1 marca | 50% | 1 |
| Raro | Azul aço; 2 marcas | 27% | 2 |
| Épico | Lavanda; 3 marcas | 14% | 3 |
| Lendário | Ouro antigo; 4 marcas | 7% | 4 |
| Mítico | Carmim; 5 marcas | 2% | 5 |

- A primeira linha preserva o status principal do tipo do equipamento: armas recebem ataque, escudos defesa, botas velocidade, joias uma skill, e torso/pernas vida, mana ou resistência.
- Os status adicionais são sorteados sem repetição entre vida máxima, mana máxima, velocidade, resistências (físico, energia, terra, fogo e gelo) e skills (fist, club, sword, axe, distance, shielding, fishing e magic level). Esses campos são preservados nos equipamentos elegíveis, sem aplicação numérica no personagem.
- Os valores armazenados e apresentados usam o percentual do tier para vida, mana e resistência; velocidade adicional usa 2% por tier; skills usam +1 por tier. O campo principal de botas varia entre 1–2%, 3–4%, 5–6%, 7–8% ou 9–10%, conforme o tier. Esses valores descrevem os metadados, não aumentos efetivos.
- Ataque e defesa efetivos preservam os atributos nativos ou refinados do item, sem somar os campos de raridade.
- Capacetes, mochilas, munição e outros itens empilháveis ficam fora do sorteio.

Equipar, retirar ou transformar um item raro, subir ou perder níveis e alterar máximos via Lua não deve introduzir bônus numéricos de raridade. Efeitos nativos, como a skill de um anel equipado, continuam sendo aplicados e removidos normalmente, uma única vez.

## Identificação no cliente

O módulo `game_rarityvisuals` identifica os tiers por cores e marcas nos slots do inventário e dos containers, além de efeitos nos itens no chão. Tooltips apresentam os atributos completos. Os efeitos visuais não alteram as chances ou os atributos dos itens.

Corpos ainda não abertos recebem uma indicação visual até o servidor confirmar a abertura. Essa indicação não representa a quantidade de itens restantes no corpo.

## Persistência e integração

A raridade pertence à instância do item. O atributo 39 guarda o tier e o status principal; o atributo 40 guarda os status adicionais em códigos compactos de cinco bits. Clones, salvamentos e transformações preservam ambos. Equipamentos salvos no formato antigo recebem status faltantes de forma determinística ao carregar, então o próximo salvamento os persiste sem mudar o tier ou o primeiro status. Nenhum bônus de raridade é gravado nos atributos base do personagem.

O opcode 127 envia tier e todos os status ao cliente. Atualizações de slots do inventário levam os metadados no mesmo pacote do item para evitar um quadro sem cor no login; containers continuam recebendo metadados junto com seu conteúdo. Consultas para páginas e mudanças individuais continuam usando tokens, e respostas antigas são descartadas. Tooltips listam os status completos; bordas e cores são restauradas após arrastar e limpas quando o item muda.

O Market atual representa ofertas por tipo/quantidade e não suporta atributos da instância; portanto recusa itens raros e refinados. Vendas a NPCs também protegem raros contra consumo por ID. Entregas de quests mantêm a regra original de aceitação de itens.

## Testes reproduzíveis

```sh
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release -DTFS_BUILD_RARITY_TESTS=ON
cmake --build build --parallel 1
ctest --test-dir build --output-on-failure
```

O teste C++ usa o núcleo real, `items.srv`, vocações e uma definição de NPC; não inicia mundo, banco ou listeners. Abrange atributos persistidos, refino, ausência de efeitos numéricos da raridade sobre dano/resistência/evolução, chamadas Lua, loot e os caminhos de equipar/retirar/transformar anéis com efeitos nativos.

As suítes [`rarity-ui-tests.lua`](../tests/rarity-ui-tests.lua) e [`rarity-economy-tests.lua`](../tests/rarity-economy-tests.lua) exercitam os scripts com objetos simulados. [`rarity-ui-runner.py`](../tests/rarity-ui-runner.py) executa os cenários Lua 5.2 e LuaJIT via Lupa.

## Compatibilidade dos dados

Itens raros persistem os atributos 39 e 40. Uma versão do servidor que não conheça esses atributos pode perder os metadados ao carregar ou salvar itens. Mudanças no formato precisam preservar os dois atributos. Definir `itemRarityLootChance = 0` suspende novos sorteios e mantém a raridade dos itens existentes.
