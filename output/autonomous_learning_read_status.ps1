param(
    [string]$StatusPath = '/var/lib/autonomous-learning/status.json',
    [string]$HealthPath = '/var/lib/autonomous-health/health.json'
)

$result = [ordered]@{ at = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }
foreach ($entry in @(@{Name='learning';Path=$StatusPath}, @{Name='health';Path=$HealthPath})) {
    if (Test-Path -LiteralPath $entry.Path) {
        try {
            $value = Get-Content -LiteralPath $entry.Path -Raw | ConvertFrom-Json
            if ($entry.Name -eq 'learning') {
                $result[$entry.Name] = $value | Select-Object at,agents,shadow
            } else {
                $result[$entry.Name] = $value | Select-Object at,sample,population,sql_measured_at,error
            }
        } catch {
            $result[$entry.Name] = @{ error = 'invalid-json' }
        }
    } else {
        $result[$entry.Name] = @{ error = 'missing' }
    }
}
$result | ConvertTo-Json -Depth 8
