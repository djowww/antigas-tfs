# Cliente, launcher e site

O servidor apresenta as regras e a identidade Antigas 7.4, usando protocolo 772 (7.72) e extensões próprias. Os limites de versão estão em [src/definitions.h](../src/definitions.h). A compatibilidade exige os módulos, opcodes e chave pública esperados pelo servidor.

## Snapshot do cliente

[deploy/client-current/](../deploy/client-current/) contém arquivos selecionados de uma distribuição personalizada baseada em OTClient: inicialização, módulos Lua, layouts OTUI e estilos. Não inclui o código C++ completo do OTClient, seu executável nem todos os assets necessários para montar o cliente do zero.

Integre esses arquivos em uma base de cliente compatível e confira seus módulos e dependências. `init.lua` contém endpoints e uma chave RSA pública específicos da distribuição. Para uma instalação própria, ajuste os endpoints e use a chave pública correspondente à chave privada do servidor. O número de release do cliente é independente da versão de protocolo.

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

[deploy/site-public/](../deploy/site-public/) contém páginas públicas, estilos, traduções e um manifesto de release. Cadastro, conta e coins dependem de bibliotecas privadas externas, incluindo `security.php` e `pix.php`, e de tabelas e serviços de banco/pagamento que não estão integralmente incluídos aqui.

`ANTIGAS_WEB_LIB` permite indicar o diretório dessas bibliotecas. Disponibilize implementações compatíveis e suas configurações privadas antes de executar as páginas; copiar somente `site-public/` não completa a instalação. Revise também os links e o manifesto de downloads para sua distribuição.

As referências em [deploy/nginx/](../deploy/nginx/) e [deploy/systemd/](../deploy/systemd/) pressupõem uma infraestrutura específica. Revise caminhos, serviços e permissões ao adaptá-las. O [guia de deploy](../deploy/README.md) descreve o restante do diretório.
