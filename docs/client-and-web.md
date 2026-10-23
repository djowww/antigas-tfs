# Cliente, launcher e site

O projeto se chama Tibia 7.4 - A classic rpg version, anteriormente Antigas. O cliente distribuído e os serviços existentes ainda podem apresentar o nome anterior e utilizam extensões próprias. A compatibilidade exige os módulos, opcodes e chave pública esperados pelo servidor.

## Snapshot do cliente

[deploy/client-current/](../deploy/client-current/) contém arquivos selecionados de uma distribuição personalizada baseada em OTClient: inicialização, módulos Lua, layouts OTUI e estilos. Não inclui o código C++ completo do OTClient, seu executável nem todos os assets necessários para montar o cliente do zero.

O snapshot versionado agora usa o perfil local, com login em `127.0.0.1:17173`. O iniciador [START-LOCAL.cmd](../START-LOCAL.cmd) obtém o cliente completo da release e copia para ele a chave pública gerada pelo servidor local. O placeholder RSA do snapshot não é uma chave utilizável antes dessa preparação. Consulte o [guia local](../local/README.md). Para hospedar outro ambiente, ajuste os endpoints e a chave pública correspondente. O número de release do cliente é independente da versão de protocolo.

Copie também `client.version` ao integrar o snapshot: o launcher consulta esse marcador antes de `APP_VERSION` em `init.lua`. O empacotador atualiza ambos e as instruções com a versão solicitada; cada execução exige uma pasta de saída nova.

## Launcher Windows

O [projeto do launcher](../deploy/launcher/AntigasLauncher/AntigasLauncher.csproj) usa Windows Forms, .NET 10 e runtime `win-x64`. Em Windows com o SDK .NET 10, execute na raiz do repositório:

```powershell
dotnet build deploy/launcher/AntigasLauncher/AntigasLauncher.csproj --configuration Release
dotnet build tools/ReleaseSigner/ReleaseSigner.csproj --configuration Release
```

Para publicar uma distribuição independente do runtime instalado:

```powershell
dotnet publish deploy/launcher/AntigasLauncher/AntigasLauncher.csproj --configuration Release --runtime win-x64 --self-contained true --output build/launcher-publish
```

O projeto já configura publicação em arquivo único. [build-release.ps1](../deploy/launcher/build-release.ps1) empacota uma distribuição de cliente fornecida separadamente; não compila o OTClient nem obtém os assets ausentes.

O launcher busca um manifesto por HTTPS e verifica sua assinatura ECDSA P-256 com a chave pública fixada em [ReleaseService.cs](../deploy/launcher/AntigasLauncher/ReleaseService.cs). Depois verifica o SHA-256 assinado do ZIP e valida os caminhos extraídos. O código restringe hosts e nomes de pacotes; publicar para outro domínio ou outra chave exige ajustar e distribuir um launcher compatível.

[tools/ReleaseSigner/](../tools/ReleaseSigner/) contém o assinador. A chave privada fica no armazenamento CNG do usuário Windows e não está incluída aqui. [release-public-key.txt](../deploy/launcher/release-public-key.txt) contém somente a chave pública de verificação. A assinatura dos pacotes é distinta da assinatura Authenticode de um executável Windows.

## Site PHP

[deploy/site-public/](../deploy/site-public/) contém páginas públicas, estilos, traduções e um manifesto de release. Cadastro e conta dependem da biblioteca privada externa `security.php` e de tabelas de banco que não estão integralmente incluídas aqui. O blog funciona sem essas bibliotecas. A rota `coins.php` é uma página informativa sem compras: não carrega bibliotecas de pagamento, não cria pedidos e não exibe dados do recebedor nem códigos de cobrança.

`ANTIGAS_WEB_LIB` permite indicar o diretório dessas bibliotecas. Disponibilize implementações compatíveis e suas configurações privadas antes de executar as páginas; copiar somente `site-public/` não completa a instalação. Revise também os links e o manifesto de downloads para sua distribuição.

As referências em [deploy/nginx/](../deploy/nginx/) e [deploy/systemd/](../deploy/systemd/) pressupõem uma infraestrutura específica. Revise caminhos, serviços e permissões ao adaptá-las. O [guia de deploy](../deploy/README.md) descreve o restante do diretório.
