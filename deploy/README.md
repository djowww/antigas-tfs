# Arquivos usados na implantação atual

- `site-public/`: cópia versionada do site público atual. Bibliotecas privadas e credenciais ficam fora desta pasta.
- `systemd/graceful-stop.conf`: configuração operacional do encerramento gracioso.
- `systemd/staging-maintenance-recovery.sh`: recuperação da janela de carga isolada; execução manual exige nova janela coordenada.

As pastas de clientes, manifests e scripts de release específicos das versões já publicadas foram retirados daqui. Cópias locais verificadas estão em `../../backup/TFS-deploy-antigo-20260927/deploy/` e no inventário correspondente. Elas não são necessárias para iniciar o TFS, para a release atual do cliente v38 nem para publicar o site.

`../tests/` contém ferramentas de desenvolvimento, regressão e carga; não é carregado pelo servidor em produção nem incluído em pacotes de cliente/site.
