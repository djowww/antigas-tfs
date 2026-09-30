# Pendências de validação de segurança — acompanhamento de 30/09/2026

Este acompanhamento responde aos quatro itens da captura e ao aviso Lua. Ele
complementa [a validação anterior](security-validation-2026-09-30.md) e registra
o que foi revalidado agora, sem ampliar os resultados além das evidências.

## Staging e carga

- O staging isolado usa banco, usuário SQL e usuário Linux próprios, sem cópia
  dos dados de produção. Suas portas de jogo ficam em loopback. A rodada foi
  executada sob `systemd-run` com limite de 570 segundos e recuperação
  independente por `ExecStopPost`.
- A validação completa passou no mesmo binário que estava em produção, SHA-256
  `3335b197c091211979b4d41109e984a4a6db44f86b4918b481724383c06a9792`:
  `rarity-live.py` em 34,53 s, `ground-rarity-live.py` em 17,69 s e
  `load-test-50.py` em 95,38 s. A carga abriu 50 sessões sintéticas, com a meta
  de 30 segundos de permanência conjunta; o relatório do teste registrou 50/50
  logins, 30 s de monitoração simultânea, 10/10 alvos de caça, 20 anúncios de
  mercado criados e concluídos, 40 entradas de histórico e zero resgates
  pendentes. O teste de carga levou 92,8 s e terminou com limpeza completa. O
  pico RSS observado foi 1.722,89 MiB.
- A recuperação independente retornou `[0, 0, 0]`: staging parado, `MemoryMax`
  restaurado a 1 GiB e produção reiniciada e ativa. O banco descartável terminou
  sem contas ou personagens de teste persistidos. A rodada é uma medição desse
  ambiente e desse binário; não define capacidade comercial nem garantia de
  simultaneidade para a infraestrutura em geral.

## Hardening do serviço em produção

- Depois da aprovação em staging, foi instalado o drop-in
  `/etc/systemd/system/imperium772.service.d/security-hardening.conf` e o
  serviço foi reiniciado em 30/09/2026 às 02:46:53 UTC.
- `systemd-analyze security` caiu de `8.4 EXPOSED` para `3.8 OK`. O serviço
  agora usa `ProtectSystem=strict`, grava apenas em
  `/opt/imperium772/server`, não recebe capacidades Linux, mantém
  `NoNewPrivileges=1` e seccomp ativo. O processo iniciou com `CapEff=0`,
  `CapBnd=0` e `NRestarts=0`.
- O processo manteve o mesmo SHA-256 testado em staging, abriu as portas 7173 e
  7174 e registrou “Antigas 7.4 Server Online!”. A checagem externa confirmou
  ambas as portas acessíveis e `https://tibia74.tech/` respondeu HTTP 200.
- O trecho de inicialização após o restart não contém o aviso anterior de loop
  Lua em `ruleviolations.lua`. A saída de `systemd-analyze verify` mostrou apenas
  um aviso preexistente e alheio ao serviço: a diretiva `RestartMode` de
  `snapd.service` não é reconhecida por esta versão do systemd.

## Verificação do atualizador

- A rodada de staging com pacote assinado e instalação limpa permanece registrada
  no relatório anterior.
- Repetimos agora o harness de integração contra o manifesto HTTPS publicado,
  versão 53, usando uma instalação temporária descartável. Passaram: assinatura
  ECDSA fixada, download e SHA-256, rejeição de manifesto adulterado, rejeição de
  ZIP com traversal, rejeição de arquivo alterado após extração, instalação limpa
  com hashes e dados do usuário preservados e rollback após falha injetada.
  Diretório temporário, instalação, downloads e backup de teste foram removidos
  pelo próprio harness.

## Aviso Lua e análise C#

- `ruleviolations.lua` contém somente o predicado de permissão do canal. O aviso
  de loop vinha da atribuição incorreta do hook global Lua, removido na correção
  anterior; a medição atual observa a duração de chamadas protegidas sem atribuir
  o aviso à linha de outro callback nem interromper scripts. Após o restart desta
  entrega, os logs de inicialização não devem conter o aviso antigo.
- O build Release normal do launcher passou com zero avisos e erros, e a
  regressão de leitura limitada do manifesto passou. Uma execução exploratória
  com todas as regras .NET `latest-all` encontrou 59 diagnósticos: principalmente
  `ConfigureAwait` em fluxos WinForms, propriedade de descarte de controles
  geridos pelo formulário e captura ampla usada para rollback/erro de interface.
  Não a tornamos bloqueante: com `TreatWarningsAsErrors` ela quebraria a build e
  exigiria revisão caso a caso. Essa execução não é equivalente a CodeQL.
- O teste de integração do launcher, repetido agora contra o manifesto oficial
  v53 em HTTPS, passou os sete controles: assinatura/hash, manifesto adulterado,
  path traversal, adulteração após extração, instalação limpa, preservação de
  userdata e rollback. Todos os arquivos temporários foram limpos.
- Isso não é um resultado CodeQL. O workflow existe no repositório, mas o GitHub
  não executou a análise porque code scanning está desabilitado para este
  repositório privado. A documentação do GitHub limita o uso do CodeQL CLI em
  repositórios privados a organizações com GitHub Code Security compatível; os
  termos da CLI também reservam análise automatizada de bases fechadas a uma
  licença comercial GHAS. Não alteramos a visibilidade do projeto nem tentamos
  contornar a restrição. O item só fecha com uma licença compatível habilitada;
  build e analisadores .NET são checagens locais adicionais, não um resultado
  equivalente ao CodeQL.

Referências oficiais: [disponibilidade do CodeQL em repositórios privados](https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-cli)
e [termos da CLI](https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md).

## Resultado desta entrega

Os testes de staging, hardening, restart e verificações externas passaram. A
análise CodeQL segue pendente pela licença/configuração do repositório privado;
esta pendência está explicitamente separada dos controles que passaram.
