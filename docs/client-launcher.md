# Antigas client launcher

`AntigasLauncher.exe` checks `https://tibia74.tech/client-release.json` when it starts. It accepts the release only when the ECDSA P-256 signature is valid, downloads the versioned ZIP over HTTPS, checks its signed SHA-256, and validates every extracted path before installation. Downloads are restricted to the official host; the launcher does not execute downloaded scripts or request administrator access.

The small `Antigas-7.4-Update-vN.zip` intentionally omits `AntigasLauncher.exe`, so routine client updates stay close to the normal client package size. The launcher copies its current executable into the verified staging folder and starts that copy to apply the update after the original process exits. This lets it safely replace game files without holding them open. The full `Antigas-7.4-Launcher-vN.zip` bundle is linked from the website. For compatibility, `Antigas-7.4-Client-vN.zip` is also published as a full bundle so the update link in older clients installs the launcher during migration.

Before replacing a file, the updater copies its prior contents under `%LOCALAPPDATA%\AntigasLauncher\backups`. If installation fails, it restores the changed files. It keeps the three newest backups and preserves logs, screenshots, and user-data folders. If verification fails or the network is unavailable, an already installed client remains available to launch.

## Build and publish a release

Build the self-contained Windows launcher:

```powershell
dotnet publish deploy/launcher/AntigasLauncher/AntigasLauncher.csproj -c Release -r win-x64 --self-contained true -o .\launcher-publish /p:PublishSingleFile=true /p:IncludeNativeLibrariesForSelfExtract=true /p:EnableCompressionInSingleFile=true
```

Prepare a client source directory whose modules and assets are ready for release, then create both ZIPs and sign the update package:

```powershell
.\deploy\launcher\build-release.ps1 -Version 53 -ClientSource C:\path\to\client -LauncherExe .\launcher-publish\AntigasLauncher.exe -OutputDirectory .\release-v53
```

The script signs the smaller `Antigas-7.4-Update-vN.zip` for launcher updates and creates full `Antigas-7.4-Client-vN.zip` and `Antigas-7.4-Launcher-vN.zip` bundles. Publish the signed manifest as `client-release.json`, the update ZIP under its exact name, and link the launcher bundle from the website.

Release signatures use a non-exportable ECDSA key in the current Windows user's CNG key store. The corresponding public key in `deploy/launcher/release-public-key.txt` is pinned in the launcher. Keep the publishing Windows profile available for future releases; creating a replacement key would require distributing a new trusted launcher through the official site before existing launchers could accept it.

The self-contained launcher is currently unsigned with an Authenticode publisher certificate. Windows may show a SmartScreen reputation prompt for the initial download. The launcher's package-verification signature protects updates after that initial download.
