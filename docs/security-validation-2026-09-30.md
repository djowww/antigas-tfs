# Validação de segurança — 30/09/2026 UTC

Este relatório complementa a auditoria original. Os testes são limitados aos
cenários descritos; não constituem garantia de ausência de vulnerabilidades.

## Correções

- O aviso de possível loop em `ruleviolations.lua` era atribuído incorretamente
  pelo hook global de linhas Lua. O callback apenas compara o tipo da conta.
  Removido o hook global; `LuaCallWatchdog` mede cada chamada protegida usando
  relógio monotônico e identifica chamadas concluídas com duração >= 1 s.
  Não interrompe scripts nem pretende detectar loops que nunca terminam.
- O atualizador Windows comparava caminhos de ZIP normalizados com separadores
  diferentes. A validação agora usa a mesma forma nas duas listas, mantendo as
  proteções contra traversal, arquivos extras e adulteração.
- Ativada a consulta de revogação de certificados HTTPS do launcher. Backups de
  atualização usam identificador único para evitar colisões no mesmo segundo.
- Corrigidas as fixtures de raridade e a leitura contínua das atualizações do
  mundo pelas sessões de caça/chat/caminhada do simulador. As sessões de Market
  mantêm um único leitor de recibos; nenhuma restrição do servidor foi relaxada.
- A captura de diagnóstico comprovou que a sessão sintética que saía durante
  a carga havia morrido para um Slime. A vida dos caçadores de teste passou de
  5.000 para 60.000, abaixo do limite de representação do protocolo clássico;
  permissões, monstros e personagens reais não foram alterados.

## Isolamento e recuperação

- Staging com banco/usuário SQL `antigas_security_staging`, usuário de sistema
  `tfs74-stage`, chave RSA própria e portas exclusivamente em loopback.
- Sem cópia de contas/personagens reais. Permissões SQL limitadas ao banco de
  teste; acesso do serviço aos arquivos de produção bloqueado pelo systemd.
- VPS com 4 GiB: mapa de produção e staging completo não cabem simultaneamente
  com margem suficiente. A rodada usa manutenção limitada, com recuperação
  independente em `ExecStopPost` e prazo máximo de 570 s.
- Ao terminar, staging fica parado com limite de 1 GiB e produção volta a subir.
  Nenhum desligamento ou reinício do computador Windows faz parte do processo.

## Evidências automatizadas

- [CI do commit 64482f7](https://github.com/djowww/antigas-tfs/actions/runs/36652765952):
  sete jobs aprovados, incluindo builds completos release/hardened, CTest com
  ASan/UBSan e TSan, fuzz smoke do parser, Lua/Python/PHP e launcher Windows.
  Sanitizadores e fuzzing cobrem seus alvos de teste, não toda a partida online.
- [Secret scan](https://github.com/djowww/antigas-tfs/actions/runs/36652765798): aprovado.
- 39 regressões Python locais aprovadas; compilação da integração do launcher
  sem avisos/erros; testes de I/O limitado aprovados; PHP alterado passa `php -l`.
- Binário Linux testado oriundo do [CI 6c90b37](https://github.com/djowww/antigas-tfs/actions/runs/36651946923),
  SHA-256 `5c78fec16976577a639c4fcbb10e1ce524906d3b94e7290e0f010dfc763b72cd`.
  As alterações posteriores desta entrega não modificam suas fontes C++.

## Rodada dinâmica aprovada

Execução `antigas-security-validation-20260930-v5`, de 01:19:42 a 01:22:18 UTC:

| Cenário | Resultado |
|---|---|
| Raridade de inventário/equipamento, atributos e relogin | Aprovado, 34,48 s |
| Item raro solto/recolhido, mochila fechada, troca de conexão e persistência | Aprovado, 17,72 s; ciclo físico executado |
| Carga | 50/50 sessões distintas; 30 s de permanência conjunta após a rampa/operações |
| Market | 20 ofertas criadas, 20 negociações, 40 históricos; zero entregas pendentes e zero ofertas ativas antes do desligamento |
| Tráfego adicional | 10 alvos de caça, chat e caminhada; 4 caçadores com morte de rato registrada |
| Desligamento | Serviço recebeu parada com clientes ainda conectados; encerramento gracioso e limpeza das contas de teste concluídos |
| Duração da carga | 92,3 s; subprocesso completo 94,44 s |
| Memória | Pico RSS observado de 1.723,57 MiB no staging completo |
| Recuperação | Três ações com código 0; produção ativa e staging inativo |

Tentativas anteriores foram preservadas, não contabilizadas como sucesso:
fixture de raridade desatualizada, piso não reconhecido e morte do caçador por
Slime. O teste agora falha se o ciclo físico de chão for pulado. A rodada final
usa personagens comuns com vida sintética maior, sem alterar regras do servidor.
Não houve falha/crash do processo de staging nessas tentativas.

## Launcher assinado v53

O teste de integração Windows usou a implementação real do atualizador, uma
instalação temporária limpa e um manifesto de staging HTTPS assinado pela chave
já fixada no launcher. Os sete controles passaram para v52 e para a candidata v53:
assinatura, download/hash, rejeição de manifesto inválido, rejeição de traversal,
rejeição de adulteração após extração, instalação completa preservando userdata e
rollback com falha injetada após três escritas. O rollback compara conteúdos
anteriores diferentes dos novos e confirma a remoção de arquivo antes inexistente.

- Update v53: `0c98e896c670fb8f21c09faf0d5fdb791efe1f35646b1434c2f26190cb95a325`.
- Launcher/Client v53: `e9baa08813eb6ef5b56325b42cadb55d52b16ebb4f8d64b571ff6f00c2f31e56`.
- O executável antigo contém o erro de caminhos: baixar o pacote completo v53
  uma vez é necessário para instalações afetadas. O código corrigido fica no
  novo launcher; os binários do jogo permanecem os da release oficial anterior.
- Não foi realizada inspeção visual da janela do launcher ou do cliente.

## Limitação externa: CodeQL

O [run CodeQL](https://github.com/djowww/antigas-tfs/actions/runs/36652765801)
falhou porque code scanning não está habilitado no repositório privado.
A API também confirmou essa restrição. É necessário disponibilizar/habilitar
GitHub Code Security compatível com esse repositório; não houve contratação,
mudança de visibilidade ou desativação do workflow para ocultar o resultado.
Executar CLI local em código privado também depende dos termos/licença aplicáveis.
Os analisadores de segurança do .NET foram habilitados e passaram, mas não são
equivalentes a um resultado CodeQL aprovado.

Referências: [disponibilidade do code scanning](https://docs.github.com/en/code-security/concepts/code-scanning/code-scanning),
[CodeQL CLI](https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-cli).

## Publicação verificada

- Serviço de produção reiniciado às 01:23:18 UTC e online às 01:23:23 UTC;
  hash do executável em execução igual ao artefato testado.
- Inicialização sem o antigo aviso de loop e sem erros Lua nos logs observados.
- Conexões TCP externas às portas 7173/7174 confirmadas.
- Homepage, wiki, manifesto v53 e os três ZIPs respondem HTTP 200; os dois links
  de download apontam para v53. Um cliente HTTP com User-Agent Python padrão
  recebe 403 pela política do site; a verificação com User-Agent de navegador
  e o próprio download HTTPS do launcher funcionaram.
- Repetidos os sete testes de integração Windows contra o manifesto oficial
  publicado v53: todos aprovados.
- Backup anterior preservado no VPS em
  `/opt/imperium772/backups/security-validation-20260930`.
- Staging encerrado, limite de memória restaurado a 1 GiB, banco de teste com
  zero contas, zero jogadores e zero sessões online após limpeza.
- Relatórios, tentativas e métricas preservados em
  `/opt/antigas-security-validation-20260930` e no diretório local da tarefa.

## Escopo que continua fora desta rodada

Teste prolongado de capacidade, latências percentis, falhas deliberadas de banco,
restauração integral de backup, pentest externo e validação de todos os achados
residuais da auditoria original. A carga sintética curta não estabelece limite
comercial de jogadores simultâneos.
