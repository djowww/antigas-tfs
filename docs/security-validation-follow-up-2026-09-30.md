# Pendências de validação de segurança — acompanhamento de 30/09/2026

Este acompanhamento responde aos quatro itens da captura e ao aviso Lua. Ele
complementa [a validação anterior](security-validation-2026-09-30.md) e registra
o que foi revalidado agora, sem ampliar os resultados além das evidências.

## Staging e carga

- O staging isolado já está provisionado com banco, usuário SQL e usuário Linux
  próprios, sem cópia de dados de produção e com as portas do jogo restritas a
  loopback. No momento da inspeção, o serviço estava parado, o limite era 1 GiB
  e produção estava ativa.
- A meta documentada é **50 sessões sintéticas simultâneas**, com **30 segundos
  de permanência conjunta** após a rampa e as operações. A rodada anterior
  concluiu 50/50 sessões em 92,3 segundos, observou pico RSS de 1.723,57 MiB e
  encerrou o staging com recuperação da produção.
- Essa rodada usou o executável `5c78fec1…`, anterior ao executável atual de
  produção (`3335b197…`). Ela estabelece um alvo reproduzível, não um limite
  comercial de jogadores nem um resultado medido no binário NPC atual. O staging
  ainda continha o executável anterior e havia uma conexão TCP estabelecida em
  produção durante esta verificação; por isso não foi aberta outra janela longa
  de manutenção para repetir a carga.

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
- Isso não é um resultado CodeQL. O workflow CodeQL permanece habilitado, mas o
  GitHub informa que CodeQL para repositórios privados exige GitHub Code Security
  compatível. Os termos oficiais da CLI também vedam seu uso ligado a uma base
  privada sem a licença correspondente. Não alteramos a visibilidade do projeto
  nem tentamos contornar a restrição. Para fechar esse item é necessário habilitar
  uma licença compatível; até lá, o build/analisadores .NET são uma verificação
  local adicional, não um substituto equivalente.

Referências oficiais: [disponibilidade do CodeQL em repositórios privados](https://docs.github.com/en/code-security/concepts/code-scanning/codeql/codeql-cli)
e [termos da CLI](https://github.com/github/codeql-cli-binaries/blob/main/LICENSE.md).

## Resultado de publicação desta entrega

O serviço foi reiniciado em 30/09/2026 às 02:08 UTC. Ficou ativo com PID 150734,
zero reinícios automáticos e o mesmo SHA-256 (`3335b197c091211979b4d41109e984a4a6db44f86b4918b481724383c06a9792`) do binário implantado. As portas públicas 7173 e 7174
responderam após a subida. O log registrou “Antigas 7.4 Server Online!” e não
mostrou erro Lua nem o aviso antigo de loop na janela observada. O restart não
substitui a rodada de carga nem fecha a restrição de licença descritas acima.
