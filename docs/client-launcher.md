# Antigas client launcher

`AntigasLauncher.exe` checks `https://tibia74.tech/client-release.json` when it starts. It accepts the release only when the ECDSA P-256 signature is valid, downloads the versioned ZIP over HTTPS, checks its signed SHA-256, and validates every extracted path before installation. Downloads are restricted to the official host; the launcher does not execute downloaded scripts or request administrator access.

Routine `Antigas-7.4-Update-vN.zip` packages omit `AntigasLauncher.exe` to keep downloads small. For releases that change the launcher, `-IncludeLauncherInUpdate` includes its new executable inside the signed package. Existing launchers copy their current executable into staging only when the package omits it. In both cases, the staged executable applies the verified update after the original process exits. The full `Antigas-7.4-Launcher-vN.zip` bundle is linked from the website. For compatibility, `Antigas-7.4-Client-vN.zip` is also published as a full bundle so the update link in older clients installs the launcher during migration.

Before replacing a file, the updater copies its prior contents under `%LOCALAPPDATA%\AntigasLauncher\backups`. If installation fails, it restores the changed files. It keeps the three newest backups and preserves logs, screenshots, and user-data folders. If verification fails or the network is unavailable, an already installed client remains available to launch.

## Build and publish a release

Build the self-contained Windows launcher:

```powershell
dotnet publish deploy/launcher/AntigasLauncher/AntigasLauncher.csproj -c Release -r win-x64 --self-contained true -o .\launcher-publish /p:PublishSingleFile=true /p:IncludeNativeLibrariesForSelfExtract=true /p:EnableCompressionInSingleFile=true
```

Prepare a client source directory whose modules and assets are ready for release, then create both ZIPs and sign the update package:

```powershell
.\deploy\launcher\build-release.ps1 -Version 57 -ClientSource C:\path\to\client -LauncherExe .\launcher-publish\AntigasLauncher.exe -OutputDirectory .\release-v57 -IncludeLauncherInUpdate
```

The script signs `Antigas-7.4-Update-vN.zip` and creates full `Antigas-7.4-Client-vN.zip` and `Antigas-7.4-Launcher-vN.zip` bundles. Omit `-IncludeLauncherInUpdate` when the launcher executable is unchanged. Publish the signed manifest as `client-release.json`, the update ZIP under its exact name, and link the launcher bundle from the website.

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

## Release v57 — 2026-10-01

Launcher 1.1.0 uses a shared native theme for its main and installation windows: stone frames, a quiet night-sky banner, a parchment message panel, square beveled buttons, and a gold progress bar. Verdana/Georgia and a DPI-scaled table layout preserve the classic presentation without external assets or new dependencies. Button hover, pressed, disabled, and keyboard focus states are explicit. Existing update validation, download restrictions, rollback, and the installation closure guard are retained.

This release includes the new launcher in the signed Update ZIP, so existing v55/v56 launchers can install the new executable automatically. The post-update `--updated <valid version>` startup waits up to ten seconds for the helper to release its mutex; ordinary duplicate starts still fail immediately, and apply-update retains its existing two-minute wait.

All three ZIPs contain the same 686 files and have SHA-256 `e01148c860d60e1c25e2c924b8c21edaae8b3069526c987da96e58ded026d4ab`. Launcher SHA-256 is `d969dabc63aa7ece05b43cc755505954000f09771e35a73203a4a49fc011fe21`. Compared with v56, only the launcher and the three release metadata files change; all 682 game files, including the sidebar toolbar, remain identical. Archive paths, size limits, and the pinned ECDSA signature were reviewed before publication.

The website shares `classic-refinement.css` across the home, wiki, account, and coins pages. The existing sky, stone, parchment, crest, routes, translations, and form handlers are preserved. The refinement adds a 1100 px desktop frame, stone sidebar groups, inset selected tabs, readable news typography, and narrow-screen layouts. Stylesheet URLs use its content hash to avoid stale cached presentation.

The Release build completed with warning-as-error checks enabled. The main launcher was captured in its native 596×334 client area at the current desktop scale. Candidate web pages were visually reviewed in the browser at desktop width and at 375/320 px, including the anonymous account, wiki, and coins pages. No horizontal overflow was observed in those views; an inherited mobile wiki flex-basis gap was corrected. Other Windows DPI settings, authenticated account/payment states, and end-to-end updater integration were not exercised for this visual release.

The online site and all three v57 packages were installed with uploaded hash checks, PHP syntax checks, and the signed manifest switched last. Previous pages are backed up under `/opt/imperium772/backups/taste-v57-20261001T192344Z-9fe7a8/site`. The game service remained active with the same process. Local site/client/launcher copies were synchronized with backups; the public home page was captured after deployment with the new stylesheet hash and v57 download URL.
