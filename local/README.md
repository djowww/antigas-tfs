# Teste local — servidor e cliente juntos

Este modo cria uma instalação independente. Nenhuma conta, senha, chave privada
ou progresso do servidor público acompanha o pacote.

## Windows: iniciar

1. Instale e abra o **Docker Desktop**, no modo de containers Linux. Essa é a
   dependência necessária para executar o servidor Linux e o banco no Windows.
2. Baixe e extraia o repositório, ou o pacote completo da release local.
3. Dê dois cliques em **START-LOCAL.cmd**. Na primeira vez, aguarde o download das
   imagens e a compilação. As seguintes partidas aproveitam o cache.
4. O cliente abre automaticamente. Entre com **conta `1`**, **senha `local123`**
   e o personagem **Local Adventurer**.

O repositório baixa o cliente da release e confere seu SHA-256. O pacote completo
já o inclui em `local/client/`. Não é preciso instalar compilador, PHP ou MySQL,
configurar chaves RSA ou importar SQL manualmente. A primeira preparação precisa
de internet. O cliente fornecido é Windows x64; o servidor em containers também
pode ser iniciado em Linux com `docker compose up -d --build --wait`.

## Endereços e dados

- Login: **127.0.0.1:17173**, protocolo **772** com a apresentação clássica 7.4.
- Jogo: **127.0.0.1:17174**. Essas portas evitam conflito com outras instalações
  que já utilizem 7171–7175.
- Banco: apenas na rede privada do Compose, sem porta publicada no computador.
- Conta de demonstração e credenciais de banco são públicas e exclusivas deste
  ambiente de teste. Não use este perfil para hospedar um servidor público.
- RSA: par novo por instalação, persistido no volume `local-keys`; apenas a parte
  pública é copiada para o cliente. Nunca se usa a chave do servidor público.
- Progresso: persiste no volume `local-db`. **STOP-LOCAL.cmd** para os serviços
  sem apagar os dados. Reiniciar o computador também não apaga esses volumes.

O site de cadastro, pagamentos, launcher de produção e bots autônomos não são
necessários nem iniciados neste modo. O cliente não consulta o atualizador de
produção. Use a conta pronta para explorar o servidor local.

## Se não iniciar

Abra o Docker Desktop e confirme que o modo Linux está funcionando. Execute
`docker compose logs --tail 60` na pasta do repositório para ver o diagnóstico.
Se as portas 17173/17174 já estiverem ocupadas, pare a instalação que as utiliza
antes de iniciar esta. Não é preciso desligar outros projetos Docker.

Para iniciar só o servidor, sem abrir o cliente:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File local/start.ps1 -NoClient
```

Não execute `docker compose down -v` se quiser conservar seus personagens.

## Empacotar outro cliente compatível

O código-fonte deste repositório não compila o executável OTClient. O cliente da
release é um binário pré-compilado com os assets e módulos da distribuição do
projeto. Avisos de autoria continuam em [NOTICE.md](../NOTICE.md).

Com uma distribuição completa disponível, `package-client.py` cria um ZIP limpo,
excluindo configurações pessoais da raiz e o launcher de produção:

```sh
python local/package-client.py CAMINHO_DO_CLIENTE Tibia74-Local-Client.zip
```
