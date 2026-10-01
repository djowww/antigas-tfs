# Observação de host — 30/09/2026 UTC

Leitura administrativa autorizada, sem alterar SSH, firewall, chaves ou banco.
Esta evidência complementa o hardening já aplicado e não constitui um scan de CVEs.

A leitura abaixo é anterior ao deploy. Após a entrega v54, às 05:39:23 UTC,
produção estava ativa com PID 4818, NRestarts=0 e binário
`d74d3f2a4988940d149b1031f40c3052f018e96aa53ca974e965db079d394e13`.
Os detalhes do ensaio e da publicação estão na
[entrega v54](security-auth-v54-delivery-2026-09-30.md).
Durante o ensaio, após parar produção, o runner elevou temporariamente o limite
de memória do staging para 3 GiB; na recuperação restaurou o limite de 1 GiB.

- Produção observada às 04:47 UTC: ativa, PID 3560, NRestarts=0, binário `fdec99926b45a3e8f1d3866c59c92654de3197c251b2debd612a35c83330eb27`.
- Staging: inativo, usuário `tfs74-stage`, MemoryMax=1 GiB. Drop-in bloqueia o acesso do serviço aos arquivos de produção, ambiente de produção, chave/public assets externos e site.
- Portas: jogo 7173/7174 público; MariaDB 3306 somente 127.0.0.1; staging sem listener quando parado. Durante testes, o runner exige suas portas em loopback.
- UFW: ativo. SSH e jogo permitidos; web 80/443 limitada aos ranges configurados de Cloudflare IPv4/IPv6. Em 30/09/2026, a lista versionada em `deploy/nginx/antigas-cloudflare-realip.conf` foi comparada com as listas oficiais IPv4/IPv6 e coincidiu exatamente (15 + 7 redes). A configuração efetivamente instalada no host não foi relida nesta retomada.
- Arquivos: ambiente produção e chave RSA 0640 root:tfs74; ambiente staging 0600 root:root. Nenhum conteúdo de senha/chave foi incluído neste relatório.
- Usuário SQL staging existe apenas para 127.0.0.1. A consulta `mysql.db` mostrou permissões para o banco escapado `antigas_security_staging`. Essa leitura parcial não substitui uma prova integral de todos os privilégios globais/rotinas.
- Biblioteca SQL efetivamente linkada: libmariadb.so.3. Também estão linkadas LuaJIT, pugixml, GMP, Boost filesystem, libstdc++, libc, zlib e OpenSSL 3.

## Pendência de SSH

`sshd -T` confirmou `PermitRootLogin=yes`, `PasswordAuthentication=yes`,
`PubkeyAuthentication=yes`, `PermitEmptyPasswords=no` e `MaxAuthTries=6`.
A conexão por chave cifrada foi confirmada. Login root por senha ainda está
habilitado e exposto pelo firewall; é uma superfície a reduzir com rollback
independente e uma segunda conexão comprovada após a mudança. Não foi feita
alteração de SSH durante a rodada de validação/deploy.

## Inventário parcial de versões

| Pacote | Versão observada |
|---|---|
| libluajit-5.1-2 | 2.1.0~beta3+dfsg-6ubuntu0.1 |
| libpugixml1v5 | 1.12.1-1 |
| libmariadb3 / mariadb-server | 1:10.6.23-0ubuntu0.22.04.1 |
| libgmp10 | 2:6.2.1+dfsg-3ubuntu1 |
| libboost-filesystem1.74.0 | 1.74.0-14ubuntu3 |
| libstdc++6 / libgcc-s1 | 12.3.0-1ubuntu1~22.04.3 |
| libc6 | 2.35-0ubuntu3.15 |
| zlib1g | 1:1.2.11.dfsg-2ubuntu9.2 |
| libssl3 | 3.0.2-0ubuntu1.30 |
| nginx | 1.18.0-6ubuntu14.21 |
| openssh-server | 1:8.9p1-3ubuntu0.17 |
| systemd | 249.11-0ubuntu3.22 |

O inventário foi produzido por dpkg-query às 04:52:07 UTC. Versões de Ubuntu
podem conter backports; o número upstream não basta para decidir vulnerabilidade.
Ainda falta consultar os advisories do fornecedor e gerar um SBOM completo,
incluindo cliente, NuGet, bibliotecas vendorizadas e dependências transitivas.
