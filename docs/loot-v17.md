# Correção do Loot — cliente v17

## Causa da regressão v16

O caminho real não estava coberto pelo teste anterior: a chamada direta ao callback ignorava `ProtocolGame:onExtendedOpcode`. Esse despachante convertia o pacote Lua em tabela; o novo módulo aceitava somente texto e descartava todos os avisos silenciosamente.

Além disso, o serializador efetivamente carregado pelo servidor usa chaves explícitas (`{[1] = "gold coin", [2] = 12, [3] = 3031}`), e não apenas o formato compacto assumido no teste. As duas incompatibilidades foram corrigidas.

## Alteração

- `registerExtendedOpcode` aceita um terceiro argumento opcional `raw=true`. Apenas Loot (122) e suprimentos (123) optam por receber o texto original, sem passar por `unserialize`. Os demais consumidores mantêm o comportamento anterior.
- O leitor limitado aceita os dois formatos de três campos, rejeita código adicional e preserva os limites de contagem e linhas. Nenhum código recebido nesses dois avisos é avaliado.
- O despachante conserva o texto original também para eventuais consumidores JSON. A opção raw é limpa ao desregistrar o callback.
- Cliente identificado como v17. Não houve alteração no protocolo do servidor, itens, banco de jogadores, economia, inventário ou Market.

## Verificação

Em mundo e banco isolados, usando o executável e os scripts atuais do servidor: personagem temporário abriu um cadáver, recolheu 12 e depois 8 gold e utilizou um mana fluid. Foram capturados os três avisos reais da rede. O total de 20 gold foi confirmado na posse do personagem e o cadáver ficou vazio. A conta temporária foi removida após encerramento seguro; nenhuma conta de jogador foi utilizada.

Esses pacotes foram reproduzidos pelo despachante real em uma cópia isolada do cliente, confirmando `20 x gold coin` e o suprimento na interface. O teste foi segmentado entre protocolo real do servidor e interface real do cliente; não foi uma sessão gráfica completa de caça.

Passaram 23 verificações do cliente (incluindo os pacotes capturados, janela aberta/fechada, reset, fim de sessão, recarga do módulo, limites, rejeição de código, compatibilidade legada e JSON), sete verificações do servidor isolado e a regressão da interface do Market. Logs do processo principal e do cliente v16 não continham erros: a regressão era descarte silencioso.

O teste anterior da v16 não demonstrava ausência de avaliação de Lua no caminho completo da rede, apesar da descrição em `stability-v16.md`. A nova verificação observa explicitamente que `unserialize` não é chamado para 122/123. Os outros opcodes legados não foram migrados nesta correção.

## Distribuição e recuperação

Pacote: `Antigas-7.4-Client-v17.zip`, SHA-256 `48137ae568ac8a0a31dd7651d3c570d71233cfb2329767622e4e51c45b15219d`.

Na publicação v17, os módulos alterados e seus testes foram mantidos como cópias auxiliares ao ZIP completo, não como cliente independente. Após a substituição dessa release, os snapshots e scripts correspondentes saíram de `deploy/` e foram arquivados localmente em `../../backup/TFS-deploy-antigo-20260927/`. O pacote histórico continua no arquivo Git; a publicação anterior do site foi salva em `/root/backups/client-loot-v17`.

É necessário fechar e abrir o cliente local atualizado, ou extrair o novo pacote para quem usa outra instalação. Contadores são de sessão: loot descartado pela v16 não pode ser reconstruído. Não houve reinício do servidor principal nesta correção.

Limitação preexistente, fora desta regressão: os avisos do servidor ainda são gerados pelos hooks legados de tentativa de movimento/uso. Estes contadores são informativos, não um registro contábil de transações; migrá-los para a conclusão bem-sucedida da ação exige uma validação própria.
