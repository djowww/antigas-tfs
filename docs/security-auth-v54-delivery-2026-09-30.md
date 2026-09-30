# Entrega de segurança e launcher v54 — 30/09/2026 UTC

## Resultado desta entrega

As correções de login, consulta de banimento, parsing do primeiro pacote,
lifetime do ambiente Lua e fechamento do atualizador foram publicadas no
servidor. O launcher completo v54, o manifesto assinado e os links do site
foram publicados. O serviço de produção foi reiniciado às 05:27:48 UTC e
confirmou `Server Online` às 05:27:53 UTC, PID 4818, sem reinícios inesperados.

Este relatório fecha os ensaios descritos abaixo. A auditoria original de 34
fases continua com as lacunas documentadas em
[progresso da auditoria](security-audit-progress-2026-09-30.md).

## Código, CI e artefato promovido

- Fonte compilada: `a13c3b42b6eeede82cc003f6b20f1c53eeefa64e`.
- Checkout de merge do CI: `dd30e71a5795a984ec57d48a3a3a4e0542afe70d`;
  sua árvore foi comparada à fonte acima antes da promoção.
- [Builds e regressões do artefato](https://github.com/djowww/antigas-tfs/actions/runs/36671968916):
  sete jobs aprovados; 19/19 testes nativos em cada variante C++, incluindo
  ASan/UBSan com `halt_on_error=1` e TSan. Windows, fuzz smoke e regressões
  PHP/Lua/Python também passaram. Isso não representa cobertura de toda a partida.
- Artefato GitHub `11078757189`, ZIP SHA-256
  `aa4110a975aebc359b4c7bd6d243459aaa2c0250bf6eb64676641e7dfecefc95`.
- ELF de produção SHA-256
  `d74d3f2a4988940d149b1031f40c3052f018e96aa53ca974e965db079d394e13`.
- Em `217e85b`, os [builds](https://github.com/djowww/antigas-tfs/actions/runs/36672814222),
  [Cppcheck](https://github.com/djowww/antigas-tfs/actions/runs/36672814169) e
  [secret scan](https://github.com/djowww/antigas-tfs/actions/runs/36672814154)
  passaram novamente. Os fontes, CMake, workflows e testes executáveis são
  idênticos aos do artefato promovido; a diferença é documentação e a revisão
  de uma linha/hash da baseline Cppcheck. Os 47 diagnósticos não foram ocultados.
- [CodeQL](https://github.com/djowww/antigas-tfs/actions/runs/36672814245)
  falhou no upload porque code scanning não está habilitado/disponível neste
  repositório privado. Não é um check aprovado. As permissões do workflow já
  incluem `security-events: write`; a ativação depende de recurso/configuração
  externa do GitHub. Nenhuma licença foi contratada nem a visibilidade alterada.

As falhas intermediárias de fixture e UBSan foram preservadas no relatório de
progresso. Seus binários não foram promovidos. A falha UBSan levou à correção
real de lifetime, mantendo o sanitizador bloqueante.

## Staging e carga com o binário novo

Rodada executada de 05:24:21 a 05:26:59 UTC, exclusivamente no banco
`antigas_security_staging`, com usuário SQL e sistema separados, RSA própria e
portas 7175/7176 em loopback. Nenhuma conta ou personagem real foi copiado.
O systemd bloqueia o acesso do serviço aos arquivos e ambiente de produção.

A VPS de 4 GiB não comporta os dois mapas completos simultaneamente com margem
suficiente. A produção ficou em manutenção durante o ensaio, sob runner com
prazo de 570 s e recuperação independente em `ExecStopPost`.
O runner eleva temporariamente `MemoryMax` do staging de 1 GiB para 3 GiB
depois de parar produção, e o restaura para 1 GiB na recuperação.

| Ensaio | Resultado observado |
|---|---|
| Raridade no inventário | Passou, 34,48 s |
| Raridade no chão com ciclo físico do serviço | Passou, 17,67 s |
| Carga | 50/50 sessões autenticadas, mantidas simultaneamente por 30 s |
| Market | 20 criações, 20 preenchimentos, 40 registros de histórico, zero claims pendentes |
| Caça sintética | 10/10 alvos; 3/10 caçadores registraram morte de rat |
| Duração da carga | 92,6 s internos; subprocesso 94,71 s |
| RSS máximo do servidor de teste | 1.725,55 MiB |
| Encerramento | Gracioso com clientes ainda conectados |
| Recuperação | Três retornos zero; produção ativa, staging inativo |
| Limpeza do banco de teste | Zero contas e zero personagens restantes |

Este é um ensaio curto de 50 sessões, não uma comprovação de centenas de
jogadores, soak prolongado, todo o gameplay ou falha real de MariaDB na
autorização. As fixtures de erro de banimento exercitam código real com banco
simulado; não são uma falha de banco em produção.

## Atualizador assinado e instalação limpa

O harness Windows `LauncherIntegration` executou os sete controles contra uma
candidata assinada em HTTPS de staging e depois contra o manifesto oficial v54:

1. Assinatura ECDSA com chave pública fixada e manifesto HTTPS.
2. Download HTTPS e verificação do SHA-256 assinado.
3. Rejeição de manifesto adulterado.
4. Rejeição de traversal no ZIP.
5. Rejeição de adulteração depois da extração.
6. Instalação em diretório novo, hashes instalados e preservação de `userdata`.
7. Rollback integral após falha de instalação injetada.

O harness de lifecycle usa os métodos reais de WinForms sem mostrar janela ou
iniciar o jogo. Comprovou fechamento pendente bloqueado e liberação após falha
real de validação por arquivos inexistentes; falhou com a fonte anterior. A
revisão do guard cobre aplicação/rollback, e a integração acima testa rollback
separadamente. Não houve verificação visual da interface. Kill
forçado/perda de energia ainda exigem journal persistente e recuperação ao iniciar.

A comparação v53/v54 confirmou 682 arquivos idênticos. Mudaram somente
`AntigasLauncher.exe`, `client.version`, `APP_VERSION` em `init.lua` e
`LEIA-ME.txt`; executáveis DX/OpenGL e recursos de jogo são idênticos.
O Update ZIP não contém o launcher novo. Para receber a correção de fechamento
UPD-02, usuários de launchers antigos precisam instalar uma vez o
[bundle completo v54](https://tibia74.tech/Antigas-7.4-Launcher-v54.zip).

| Arquivo | SHA-256 / tamanho |
|---|---|
| Bundle Launcher/Client v54 | `0710bcae0ac83b0a08d3bfe042541a7b0a11760bae4a9fbd6be968e65e383d2d` / 72.784.396 bytes |
| Update v54 | `f45500bd2734ae9ad03b0033c978e4b0494929727abea9daae49589ed4ed6bd1` / 26.575.995 bytes |
| Launcher EXE | `3304d1460ce99f05983c3ac4bbaec1b48b3cf269dfb88cec22366c5b3a3333e0` |
| Manifesto assinado | `548b2a7633a20e46996f95e802e280a95e07655518ca47cae93d83fe720b84eb` |

## Publicação, aviso Lua e verificação externa

O publisher confirmou o hash exato do binário aprovado, o resultado de staging,
o manifesto candidato e os arquivos anteriores antes de alterar produção.
Foi executado sob serviço systemd independente com prazo e recuperação. O
backup foi retido em
`/opt/imperium772/backups/security-auth-v54-20260930T052743Z`.

Os listeners 7173/7174 foram conferidos como pertencentes ao MainPID do
serviço, com hash do executável em execução. O log de startup inspecionado não
continha erros, warnings ou o antigo aviso de loop em `ruleviolations.lua`.
A correção desse falso diagnóstico já estava no baseline: o callback só
compara o tipo da conta; o watchdog mede chamadas concluídas, sem afirmar que
interrompe scripts que nunca terminam.

Após a publicação, conexões TCP externas nas duas portas passaram. Home/wiki
retornaram HTTP 200 com User-Agent de navegador e links v54. O User-Agent
padrão de Python recebeu 403 nos documentos HTML; isso foi registrado, sem
alegar inspeção visual. Os bundles Launcher/Client foram baixados integralmente
por HTTPS e seus tamanhos/hashes conferidos. O manifesto oficial apresentou
v54 e o harness .NET concluiu a instalação/rollback com sucesso.

Uma leitura adicional às 05:39:23 UTC confirmou PID 4818, produção ativa,
NRestarts=0 e o mesmo hash de binário. O computador Windows não foi desligado
nem reiniciado.

## Evidências e limites

Os JSON sanitizados estão em [validation/security-auth-v54/](validation/security-auth-v54/).
Incluem execução/recuperação de staging, recibo de CI/artefato, publicação,
download público e comparação/verificação do pacote. São registros históricos,
não execuções automáticas dos testes atuais, e não contêm senhas ou chaves.
Os resultados individuais do harness HTTPS, log de startup e leitura de
05:39:23 foram observados na saída dos comandos pelo operador e registrados
na narrativa; esses quatro JSON não contêm cópia de todos esses outputs.
A [observação de host](host-security-observation-2026-09-30.md) registra
inventário parcial de dependências e pendências de SSH; não equivale a SBOM ou
scan de CVEs. CodeQL e proteção nativa da main continuam limitados pelo GitHub.
