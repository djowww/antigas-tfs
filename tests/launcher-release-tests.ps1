param([string]$OutputDirectory = [System.IO.Path]::GetTempPath())

$ErrorActionPreference = 'Stop'
$repo = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$builder = Join-Path $repo 'deploy\launcher\build-release.ps1'
$testRoot = Join-Path ([System.IO.Path]::GetFullPath($OutputDirectory)) ('antigas-release-tests-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
Add-Type -AssemblyName System.IO.Compression.FileSystem
$failures = [System.Collections.Generic.List[string]]::new()

function Assert-True([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}

function Test-Case([string]$Name, [scriptblock]$Body) {
    try {
        & $Body
        Write-Output "PASS $Name"
    } catch {
        $failures.Add("${Name}: $($_.Exception.Message)")
        Write-Output "FAIL ${Name}: $($_.Exception.Message)"
    }
}

function New-ClientSource([string]$Name, [string]$Init) {
    $source = Join-Path $testRoot $Name
    New-Item -ItemType Directory -Path $source,(Join-Path $source 'modules') -Force | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $source 'init.lua'), $Init)
    [System.IO.File]::WriteAllText((Join-Path $source 'client.version'), "66`n")
    [System.IO.File]::WriteAllText((Join-Path $source 'LEIA-ME.txt'), 'Old client v66 instructions')
    [System.IO.File]::WriteAllText((Join-Path $source 'Antigas_gl.exe'), 'INERT TEST FILE; NEVER EXECUTE')
    [System.IO.File]::WriteAllText((Join-Path $source 'modules\fixture.lua'), 'return true')
    return $source
}

function Invoke-Build([string]$Source, [string]$Output, [bool]$IncludeLauncher = $false) {
    $launcher = Join-Path $testRoot 'inert-launcher.exe'
    [System.IO.File]::WriteAllText($launcher, 'INERT TEST FILE; NEVER EXECUTE')
    # Block the external signing boundary; all copying, rewrites and ZIPs are real.
    # This local function prevents dotnet/ReleaseSigner and key access entirely.
    function dotnet {
        if ($args[0] -ne 'run' -or ($args -join ' ') -notmatch 'ReleaseSigner.*\bsign\b') {
            throw 'Unexpected external command in release test.'
        }
        $global:LASTEXITCODE = 0
    }
    $buildArgs = @{ Version = 67; ClientSource = $Source; LauncherExe = $launcher; OutputDirectory = $Output }
    if ($IncludeLauncher) { $buildArgs.IncludeLauncherInUpdate = $true }
    & $builder @buildArgs | Out-Null
}

function Read-Entry([System.IO.Compression.ZipArchive]$Archive, [string]$Name) {
    $entry = $Archive.GetEntry($Name)
    Assert-True ($null -ne $entry) "Missing ZIP entry: $Name"
    $reader = [System.IO.StreamReader]::new($entry.Open())
    try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
}

function Assert-Package([string]$Path, [bool]$HasLauncher) {
    $archive = [System.IO.Compression.ZipFile]::OpenRead($Path)
    try {
        $expected = @('init.lua', 'client.version', 'LEIA-ME.txt', 'Antigas_gl.exe', 'modules/fixture.lua')
        if ($HasLauncher) { $expected += 'AntigasLauncher.exe' }
        $actual = @($archive.Entries | ForEach-Object { $_.FullName })
        Assert-True ($actual.Count -eq $expected.Count) 'Unexpected ZIP file count.'
        foreach ($name in $expected) { Assert-True ($actual -ccontains $name) "Missing flat-root package file: $name" }
        Assert-True ((Read-Entry $archive 'client.version').Trim() -eq '67') 'Packaged client.version must be 67.'
        Assert-True ((Read-Entry $archive 'init.lua') -match '(?m)^APP_VERSION\s*=\s*67\b') 'Packaged APP_VERSION must be 67.'
        $readme = Read-Entry $archive 'LEIA-ME.txt'
        foreach ($kind in @('Launcher', 'Update', 'Client')) {
            Assert-True ($readme.Contains("Antigas-7.4-$kind-v67.zip")) "Packaged instructions must name $kind v67."
        }
        Assert-True (-not $readme.Contains('v66')) 'Packaged instructions retain the old version.'
    } finally { $archive.Dispose() }
}

Test-Case 'snapshot metadata agrees with published manifest' {
    $manifest = [System.IO.File]::ReadAllText((Join-Path $repo 'deploy\site-public\client-release.json')) | ConvertFrom-Json
    $init = [System.IO.File]::ReadAllText((Join-Path $repo 'deploy\client-current\init.lua'))
    $match = [regex]::Match($init, '(?m)^APP_VERSION\s*=\s*(\d+)\b')
    Assert-True ($match.Success -and [int]$match.Groups[1].Value -eq $manifest.version) 'Snapshot APP_VERSION differs from published release.'
    $marker = Join-Path $repo 'deploy\client-current\client.version'
    Assert-True (Test-Path -LiteralPath $marker) 'Snapshot version marker is missing for direct integration.'
    Assert-True ([int][System.IO.File]::ReadAllText($marker).Trim() -eq $manifest.version) 'Snapshot client.version differs from published release.'
    $readme = [System.IO.File]::ReadAllText((Join-Path $repo 'deploy\client-current\LEIA-ME.txt'))
    foreach ($kind in @('Launcher', 'Update', 'Client')) {
        Assert-True ($readme.Contains("Antigas-7.4-$kind-v$($manifest.version).zip")) "Snapshot instructions must name current $kind download."
    }
}

Test-Case 'older input packages coherent metadata and default ZIP shapes' {
    $source = New-ClientSource 'older-source' "APP_VERSION = 66 -- fixture`n"
    $originalInit = [System.IO.File]::ReadAllText((Join-Path $source 'init.lua'))
    $output = Join-Path $testRoot 'older-output'
    Invoke-Build $source $output
    Assert-Package (Join-Path $output 'Antigas-7.4-Update-v67.zip') $false
    Assert-Package (Join-Path $output 'Antigas-7.4-Launcher-v67.zip') $true
    Assert-Package (Join-Path $output 'Antigas-7.4-Client-v67.zip') $true
    $bundleHash = (Get-FileHash -LiteralPath (Join-Path $output 'Antigas-7.4-Launcher-v67.zip') -Algorithm SHA256).Hash
    $legacyHash = (Get-FileHash -LiteralPath (Join-Path $output 'Antigas-7.4-Client-v67.zip') -Algorithm SHA256).Hash
    Assert-True ($bundleHash -eq $legacyHash) 'Legacy download must be the same complete bundle.'
    Assert-True ([System.IO.File]::ReadAllText((Join-Path $source 'init.lua')) -eq $originalInit) 'Builder modified ClientSource.'
}

Test-Case 'same-version input packages successfully' {
    $source = New-ClientSource 'same-source' "APP_VERSION = 67 -- fixture`n"
    $output = Join-Path $testRoot 'same-output'
    Invoke-Build $source $output
    Assert-Package (Join-Path $output 'Antigas-7.4-Update-v67.zip') $false
}

Test-Case 'opt-in update contains launcher' {
    $source = New-ClientSource 'launcher-source' "APP_VERSION = 66`n"
    $output = Join-Path $testRoot 'launcher-output'
    Invoke-Build $source $output $true
    Assert-Package (Join-Path $output 'Antigas-7.4-Update-v67.zip') $true
}

Test-Case 'missing APP_VERSION is rejected before packages are written' {
    $source = New-ClientSource 'missing-source' "SERVER_VERSION = 772`n"
    $output = Join-Path $testRoot 'missing-output'
    $rejected = $false
    try { Invoke-Build $source $output } catch {
        if ($_.Exception.Message -ne 'Could not locate APP_VERSION in init.lua.') { throw }
        $rejected = $true
    }
    Assert-True $rejected 'Builder accepted an input without APP_VERSION.'
    Assert-True (@(Get-ChildItem -LiteralPath $output -Filter '*.zip' -File).Count -eq 0) 'Invalid input created release ZIPs.'
}

Write-Output "Artifacts: $testRoot"
if ($failures.Count -gt 0) { throw "$($failures.Count) release regression test(s) failed." }
Write-Output 'PASS all 5 release regression tests; signer and executables never run.'
