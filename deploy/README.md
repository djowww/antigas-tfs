# Arquivos usados na implantação atual

- `site-public/`: cópia versionada do site público atual, alinhado ao cliente v41. Bibliotecas privadas e credenciais ficam fora desta pasta.
- `client-current/`: fontes atuais dos módulos Achievements/menu e bibliotecas usadas em suas regressões; não contém releases antigos.
- `systemd/graceful-stop.conf`: configuração operacional do encerramento gracioso.
- `systemd/staging-maintenance-recovery.sh`: recuperação da janela de carga isolada; execução manual exige nova janela coordenada.

As pastas antigas de clientes, manifests e scripts de release foram arquivadas em `../../backup/TFS-deploy-antigo-20260927/deploy/` e relacionadas no inventário correspondente. Elas não são necessárias para iniciar o TFS nem para publicar o cliente v41 e o site.

`../tests/` contém ferramentas de desenvolvimento, regressão e carga; não é carregado pelo servidor em produção nem incluído em pacotes de cliente/site.
