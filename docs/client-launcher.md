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
.\deploy\launcher\build-release.ps1 -Version 56 -ClientSource C:\path\to\client -LauncherExe .\launcher-publish\AntigasLauncher.exe -OutputDirectory .\release-v56
```

The script signs the smaller `Antigas-7.4-Update-vN.zip` for launcher updates and creates full `Antigas-7.4-Client-vN.zip` and `Antigas-7.4-Launcher-vN.zip` bundles. Publish the signed manifest as `client-release.json`, the update ZIP under its exact name, and link the launcher bundle from the website.

Release signatures use a non-exportable ECDSA key in the current Windows user's CNG key store. The corresponding public key in `deploy/launcher/release-public-key.txt` is pinned in the launcher. Keep the publishing Windows profile available for future releases; creating a replacement key would require distributing a new trusted launcher through the official site before existing launchers could accept it.

The self-contained launcher is currently unsigned with an Authenticode publisher certificate. Windows may show a SmartScreen reputation prompt for the initial download. The launcher's package-verification signature protects updates after that initial download.

## Release v54

The update window refuses normal X/Alt+F4 closure while validation, file installation or rollback is running. This does not protect against forced process termination or power loss. Existing launchers are preserved by the smaller Update ZIP, so receiving this launcher fix requires downloading the full v54 Launcher/Client bundle once. The signed v54 candidate passed the isolated HTTPS integration harness; publication is recorded in the security audit addendum.

## Release v55 — 2026-10-01

This release carries the stricter official-host and package-path validation in `ReleaseService`. The v55 bundle was based on the published v54 bundle; comparison found changes only to `AntigasLauncher.exe`, `client.version`, `APP_VERSION` in `init.lua`, and `LEIA-ME.txt`. The other 682 files are unchanged. The update manifest is signed with the existing pinned ECDSA release key.

## Release v56 — 2026-10-01

The visible sidebar toolbar in `modules/game_playerbars/playerbars.otui` now uses quieter neutral borders for normal/hover, restrained amber for real selected states, and consistent pressed/disabled overrides. Icon dimensions, positions, sprites, button hit areas, and Lua actions remain unchanged. Pressing a button does not shift its contents.

The package was built from the official signed v55 Update ZIP. Archive comparison found exactly four changed files: `playerbars.otui`, `init.lua` (release number only), `client.version`, and `LEIA-ME.txt` (release references only). All other 681 Update files and 682 full-bundle files, including the launcher and game binaries, are unchanged. The existing pinned ECDSA key signed the v56 manifest.

Published artifact SHA-256 values:

- Update ZIP: `79b69c6454cc0b5e4ddc2e450ebb0721529fe8c0090787ef09325fb1661f27f9`.
- Launcher and Client full bundles: `35204e3c76891eb110de64c084dc15331eb833e876ec8c76ab97dab8f978003f`.
- Toolbar file: `dd7eee9d2106d806ccf5c0880414ea3651e1b46198fb4d034178b397ec478cf0`.

Deployment verified all six uploaded files by hash and checked PHP syntax before switching the public manifest last. The previous pages are backed up under `/opt/imperium772/backups/toolbar-v56-20261001T185344Z/site`; v55 packages remain available. The game service remained active with the same process throughout publication. The local client, launcher, and website copies were synchronized with backups.

These checks verify release contents and delivery. Native visual inspection and checks at different display scales remain pending because client-window activation was unavailable; no visual verification is claimed.
