param(
    [switch]$RebuildFinal,
    [string]$PythonPath = (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'),
    [string]$NodePath = (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe')
)
$ErrorActionPreference = 'Stop'
$deliveryDir = $PSScriptRoot
$projectDir = Split-Path -Parent $deliveryDir
foreach ($runtime in @($PythonPath,$NodePath)) {
    if (-not (Test-Path -LiteralPath $runtime -PathType Leaf)) { throw "Missing runtime: $runtime" }
}
$requiredFiles = @(
    (Join-Path $projectDir 'user_retention_cohort.csv'),
    (Join-Path $projectDir 'behavior_flow\primary_candidate_outcomes.csv'),
    (Join-Path $deliveryDir 'sample_size_results.json')
)
foreach ($file in $requiredFiles) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing input: $file" }
}
$env:PYTHONIOENCODING = 'utf-8'
function Invoke-DeliveryPython([string]$ScriptName, [string[]]$ScriptArgs = @()) {
    Write-Output "Running $ScriptName"
    & $PythonPath (Join-Path $deliveryDir $ScriptName) @ScriptArgs
    if ($LASTEXITCODE -ne 0) { throw "$ScriptName failed with exit code $LASTEXITCODE" }
}
Write-Output "OneDrive preflight passed: $projectDir"
if ($RebuildFinal) {
    $matplotlibDir = Join-Path (Split-Path -Parent $projectDir) 'cohort_v1\tmp\python_deps\matplotlib'
    $artifactDir = Join-Path $projectDir 'statistics\node_modules\@oai\artifact-tool'
    foreach ($dependency in @($matplotlibDir,$artifactDir)) {
        if (-not (Test-Path -LiteralPath $dependency -PathType Container)) { throw "Missing authoring dependency: $dependency" }
    }
    Invoke-DeliveryPython 'extract_primary_event_times.py'
    & $PythonPath (Join-Path $projectDir 'corrections\analyze_robustness.py')
    if ($LASTEXITCODE -ne 0) { throw 'Robustness analysis failed' }
    Invoke-DeliveryPython 'prepare_final_delivery.py'
    Invoke-DeliveryPython 'build_final_report.py'
    $marker = Join-Path $env:USERPROFILE '.codex\plugins\cache\openai-primary-runtime\spreadsheets\26.1011.11113\skills\spreadsheets\container_tools\mark_artifact_operation_started.mjs'
    if (-not (Test-Path -LiteralPath $marker -PathType Leaf)) { throw "Missing spreadsheet operation marker: $marker" }
    $kind = if (Test-Path -LiteralPath (Join-Path $deliveryDir 'A1_실험표본수와_기간산정.xlsx')) { 'edit' } else { 'create' }
    & $NodePath $marker --operation-kind $kind --expected-output-count 1 --output-format xlsx
    if ($LASTEXITCODE -ne 0) { throw 'Spreadsheet marker failed' }
    & $NodePath (Join-Path $deliveryDir 'build_sample_workbook.mjs')
    if ($LASTEXITCODE -ne 0) { throw 'Spreadsheet creation failed' }
}
if ($RebuildFinal) {
    Invoke-DeliveryPython 'verify_planning_calculations.py' @('--write-validation')
    Invoke-DeliveryPython 'verify_measurement_reference.py' @('--write-validation')
    Invoke-DeliveryPython 'verify_semantic_integrity.py' @('--write-validation')
    Invoke-DeliveryPython 'verify_final_delivery.py' @('--build-manifest')
} else {
    $manifestPath = Join-Path $deliveryDir 'final_delivery_manifest.json'
    $beforeHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash
    Invoke-DeliveryPython 'verify_final_delivery.py'
    Invoke-DeliveryPython 'verify_planning_calculations.py'
    Invoke-DeliveryPython 'verify_measurement_reference.py'
    Invoke-DeliveryPython 'verify_semantic_integrity.py'
    $afterHash = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash
    if ($beforeHash -ne $afterHash) { throw 'Read-only audit changed manifest' }
    $auditDir = Join-Path $projectDir 'corrections\audits'
    New-Item -ItemType Directory -Force -Path $auditDir | Out-Null
    $audit = @{ utc = [DateTime]::UtcNow.ToString('o'); mode = 'read_only_package_audit'; manifest_sha256 = $afterHash; passed = $true }
    $auditPath = Join-Path $auditDir (([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfff')) + '.json')
    $audit | ConvertTo-Json | Set-Content -LiteralPath $auditPath -Encoding UTF8
    Write-Output "Read-only audit saved outside package: $auditPath"
}
Invoke-DeliveryPython 'validate_experiment_config.py'
Write-Output 'Final package verification passed. No service experiment was launched.'
