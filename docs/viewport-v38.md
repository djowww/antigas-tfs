# Game View v38 — Classic / Widescreen

Publicado em 27/09/2026. Cliente e servidor atualizados juntos.

## Diagnóstico

O `gameMapPanel` já estava ancorado entre os painéis e acima do chat. As faixas
vinham da câmera fixa **15 × 11** com `keepAspectRatio=true`, não de uma margem
externa. O servidor transmitia uma matriz fixa **18 × 14**, incluindo margens de
caminhada; alterar apenas a UI não disponibilizaria mapa real adicional.

Arquivos de controle no cliente: `modules/game_interface/gameinterface.otui`,
`gameinterface.lua`, `widgets/uigamemap.lua`; câmera nativa `UIMap`/`MapView` do
OTCv8. A câmera nativa já permite preencher o retângulo mantendo escala uniforme
e recorte centralizado; não foi necessário recompilar os executáveis do cliente.

Referências primárias do comportamento nativo:
[UIMap](https://github.com/OTCv8/otcv8-dev/blob/master/src/client/uimap.cpp),
[MapView](https://github.com/OTCv8/otcv8-dev/blob/master/src/client/mapview.cpp),
[parser](https://github.com/OTCv8/otcv8-dev/blob/master/src/client/protocolgameparse.cpp).

## Implementação

- Options > Interface: Classic (15 × 11) / Widescreen (padrão).
- Options > Graphics: **Left panels / Right panels preservados** e testados.
- Câmera adaptativa com dimensões ímpares, limitada a **29 × 15 visíveis**.
- Área de envio limitada a **32 × 18** incluindo margens; negociação OTCv8 0x42,
  validada e limitada pelo servidor. Intervalo mínimo de 500 ms entre mudanças.
- A UI só expande após confirmação do servidor. Servidor sem suporte mantém Classic.
- Tiles/sprites com escala uniforme, câmera centralizada; chat, equipamentos,
  minimap e painéis não foram redesenhados. Nenhum sprite foi alterado.
- Faixas residuais de menos de um tile são tratadas por recorte simétrico nativo.
- Atualizações de jogadores alcançam a nova área; alcance original de combate,
  visão dos monstros e bloqueio de respawn permanecem limitados como antes.
- Snapshots expandidos usam mensagens por andar para evitar um mapa de vários
  andares exceder o limite antigo de 64 KiB. Andares muito densos têm fallback
  para atualizações individuais de tiles. Classic mantém o protocolo original.
- Corrigido desligamento dos callbacks de geometria e cancelamento dos eventos
  do viewport no logout; opções não sobrepõem Keyboard e Hotkeys.

## Validação

Servidor compilado com GCC 11.4 e LuaJIT, como o runtime oficial. Cliente testado
com seu executável OpenGL real, em mundo isolado com banco e RSA próprios,
exposto somente por loopback/SSH. Contas, mapa e comandos de QA não foram
instalados no servidor oficial nem incluídos no download.

| Caso | Resultado |
| --- | --- |
| 1366 × 768, monitor real | 21 × 11, tiles 56 × 56 px, bordas com mapa recebido |
| Layout interno 1920 × 1080 | 29 × 15; mapa recebido e projeção/cliques verificados |
| 1024 × 700, janela real | 17 × 11, tiles 49 × 49 px |
| Fullscreen e retorno | 1366 × 768, geometria/painéis preservados |
| Referências 19 × 13 e 21 × 15 | câmera, bordas e negociação corretas |
| Um painel esquerdo, dois direitos | quantidade preservada e viewport recalculada |
| Classic / servidor sem feature | retorno a 15 × 11 |
| NPC, monstro e jogador adicional | recebidos e presentes no Battle |
| HP e movimento na área ampliada | recebidos, incluindo jogador a 12 SQMs |
| Autowalk | destino alcançado; atualizações norte/oeste e sul/leste verificadas |
| Troca entre andares 7 e 8 | mapa completo, personagem centralizado |
| 8 andares, 4.608 tiles, 9 pilhas por tile | sem truncamento/desconexão; andares conferidos |
| Teste C++ dos pedidos | 65.536 combinações dentro dos limites |
| Política Lua de tamanho | 12.483 tamanhos, limites e dimensões ímpares |
| Sintaxe / logs da rodada final | sem erros |

**Limitação explícita:** não havia monitor Full HD. 1920 × 1080 foi validado
redimensionando a raiz da UI real para esse tamanho, inclusive a projeção de
cliques nos cantos, mas não foi uma inspeção visual integral em tela física Full HD.
Não foi alterada a resolução do Windows. A rodada com DirectX não foi executada.

Os testes anteriores tiveram falhas de fixture (NPC com nome de arquivo em
maiúsculas e jogador atacado pelo rato). Corrigidas no ambiente isolado e
reexecutadas; a rodada final completa passou. Não eram defeitos do viewport.

## Arquivos da mudança

Cliente (cópia versionada na release; snapshot arquivado localmente em
`../../backup/TFS-deploy-antigo-20260927/`):

- `init.lua`, `LEIA-ME.txt`;
- `modules/game_interface/{viewport.lua,interface.otmod,gameinterface.lua,gameinterface.otui}`;
- `modules/client_options/{options.lua,options.otui,viewport.otui}`.

Servidor: `src/{mapviewport.h,protocolgame.cpp,protocolgame.h,map.cpp,map.h,combat.cpp,spawn.cpp}`.
Testes: `tests/viewport-*`, `tests/viewport_qa.lua`.
Publicação: script de release v38 arquivado localmente com os demais artefatos antigos.

## Publicação e recuperação

- SHA-256 cliente v38: `4129423e0a36b03bb2ca265bfaa5fbe39665b9d262142d15e51ada26fa167eec`.
- SHA-256 TFS validado: `af27c7c444d3e511c74bf62d80cbb9b935a976596e438af59b7dce57c4225ca3`.
- Código-base da produção comparado integralmente ao HEAD anterior antes da troca.
- Reinício gracioso oficial em 27/09/2026, 13:14 BRT; havia zero jogadores.
- Backup no host: `/opt/antigas-viewport-v38/release-final/server-before` e
  `website-before`. O download v37 foi mantido.
- Testes de interface e relatórios brutos locais: `../../backup/Historico/viewport-v38/`.
- Para rollback, parar graciosamente o serviço, restaurar binário/fontes do backup
  com a propriedade `tfs74`, iniciar, e restaurar o link/manifest do site. Não
  restaurar banco nem dados de jogadores: esta release não mudou o schema.

## Reproduzir os testes puros

```sh
g++ -std=c++11 -Wall -Wextra tests/viewport-geometry.cpp -o /tmp/viewport-geometry
/tmp/viewport-geometry
luajit tests/viewport-policy.lua ../../backup/TFS-deploy-antigo-20260927/deploy/client-viewport-v38/modules/game_interface/viewport.lua
python3 tests/viewport-status.py 127.0.0.1 7173
```

Os testes de UI exigem o fixture isolado e o bootstrap `ViewportQA`; não execute
`viewport-ui-scenarios.lua` em conta real. O fixture gera credenciais exclusivas.
