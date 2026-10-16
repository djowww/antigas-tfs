param(
    [string]$ClientRoot = (Join-Path $PSScriptRoot '..\deploy\client-current')
)

$ErrorActionPreference = 'Stop'
$initPath = Join-Path $ClientRoot 'init.lua'
$loginPath = Join-Path $ClientRoot 'modules\client_entergame\entergame.lua'
$init = [System.IO.File]::ReadAllText($initPath)
$login = [System.IO.File]::ReadAllText($loginPath)

$configured = [regex]::Match($init, '(?m)^\s*OTClientV8Classic\s*=\s*"([^"]+)"')
if (-not $configured.Success) { throw 'Official login endpoint is missing from init.lua.' }

$allowed = [regex]::Match($login, "G\.host\s*~=\s*'([^']+)'\s+then")
if (-not $allowed.Success) { throw 'Classic login official-server guard is missing.' }

if ($allowed.Groups[1].Value -cne $configured.Groups[1].Value) {
    throw "Official login guard ($($allowed.Groups[1].Value)) differs from configured endpoint ($($configured.Groups[1].Value))."
}
if ($login -notmatch 'G\.host\s*=\s*Servers\s+and\s+Servers\[G\.server\]') {
    throw 'Classic login must use the configured server selection.'
}
if ($init -notmatch '(?m)^ALLOW_CUSTOM_SERVERS\s*=\s*false\b') {
    throw 'Official client unexpectedly allows custom servers.'
}

Write-Output "PASS official login endpoint: $($configured.Groups[1].Value)"
