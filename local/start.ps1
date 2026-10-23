param([switch]$NoClient)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root
function Invoke-LocalCompose {
    & docker compose @args
    if ($LASTEXITCODE -ne 0) { throw 'Docker failed. Check the message above. Saved data was not deleted.' }
}
try {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw 'Install and open Docker Desktop (Linux containers) first.' }
    & docker info *> $null
    if ($LASTEXITCODE -ne 0) { throw 'Open Docker Desktop and wait for it to finish starting.' }
    Write-Host 'Starting local database and server. The first build takes several minutes.'
    Invoke-LocalCompose up -d --build --wait --wait-timeout 600
    if ($NoClient) { Write-Host 'Server ready. Account: 1 / local123'; exit 0 }
    $client = Join-Path $PSScriptRoot 'client'
    if (-not (Test-Path -LiteralPath (Join-Path $client 'Antigas_dx.exe'))) {
        $manifest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'client-release.json') -Raw | ConvertFrom-Json
        $archive = Join-Path $env:TEMP ('tibia74-local-' + [guid]::NewGuid().ToString('N') + '.zip')
        Write-Host 'Downloading the local test client...'
        Invoke-WebRequest -Uri $manifest.url -OutFile $archive -UseBasicParsing
        if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne $manifest.sha256) { throw 'Client checksum mismatch. Download rejected.' }
        New-Item -ItemType Directory -Path $client -Force | Out-Null
        Expand-Archive -LiteralPath $archive -DestinationPath $client -Force
    }
    $modulus = (Invoke-LocalCompose exec -T server cat /local-state/public-modulus.txt | Out-String).Trim()
    if ($modulus -notmatch '^\d{308,309}$') { throw 'Could not obtain the local server public key.' }
    $init = Join-Path $client 'init.lua'
    $text = Get-Content -LiteralPath $init -Raw
    $text = [regex]::Replace($text, 'ANTIGAS_RSA_PUBLIC_KEY = "[^"]+"', ('ANTIGAS_RSA_PUBLIC_KEY = "' + $modulus + '"'))
    [IO.File]::WriteAllText($init, $text, (New-Object Text.UTF8Encoding($false)))
    Write-Host 'Ready! Account: 1 | Password: local123 | Character: Local Adventurer'
    Start-Process -FilePath (Join-Path $client 'Antigas_dx.exe') -WorkingDirectory $client
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host 'Diagnostics: docker compose logs --tail 60'
    exit 1
}
