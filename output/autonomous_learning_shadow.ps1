param(
    [string]$StatePath = "$PSScriptRoot\autonomous-learning-shadow.db",
    [int]$Agents = 1,
    [int]$Steps = 200
)

$qaMarker = $env:QA_ONLY
if ($qaMarker -ne '1') { throw 'QA_ONLY=1 is required; shadow launcher refuses non-QA execution.' }
$qaHost = '127.0.0.1'
if ($Agents -lt 1 -or $Agents -gt 1) { throw 'Canary launcher accepts exactly one QA agent.' }
& python -m tools.autonomous_learning_simulation --agents $Agents --duration $Steps --seed 7 --state $StatePath
