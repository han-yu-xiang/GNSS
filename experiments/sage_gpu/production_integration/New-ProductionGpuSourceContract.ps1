[CmdletBinding()]
param(
    [string]$FrozenAuthorityPath = 'E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_nav_sage_pipeline.m',
    [string]$QualifiedCandidatePath = (Join-Path $PSScriptRoot '..\full_task_candidate\run_nav_sage_pipeline_gpu_candidate.m'),
    [string]$QualifiedProbePath = (Join-Path $PSScriptRoot '..\stage2_window_173_gpu_probe.m'),
    [string]$QualifiedSelectorPath = (Join-Path $PSScriptRoot '..\selectSeparatedResidualCandidate.m'),
    [string]$ProductionEntryPath = (Join-Path $PSScriptRoot '..\..\..\scripts\sage_pipeline\run_nav_sage_pipeline_gpu_production.m'),
    [string]$OutputPath = (Join-Path $PSScriptRoot 'PRODUCTION_GPU_SOURCE_CONTRACT.json')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-ContractFunctionBlocks {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "SOURCE_CONTRACT_INPUT_MISSING path=$Path"
    }
    $source = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $Path).Path)
    $matches = [regex]::Matches($source, '(?m)^[\t ]*function\b')
    $blocks = [System.Collections.Generic.List[object]]::new()
    for ($index = 0; $index -lt $matches.Count; $index++) {
        $start = $matches[$index].Index
        $end = if ($index + 1 -lt $matches.Count) { $matches[$index + 1].Index } else { $source.Length }
        $rawText = $source.Substring($start, $end - $start).TrimEnd([char[]]@("`r", "`n"))
        $openParen = $rawText.IndexOf('(')
        if ($openParen -lt 0) { throw "SOURCE_CONTRACT_FUNCTION_UNPARSEABLE path=$Path offset=$start" }
        $prefix = $rawText.Substring(0, $openParen)
        $nameMatch = [regex]::Match($prefix, '(?<name>[A-Za-z][A-Za-z0-9_]*)[\t ]*$')
        if (-not $nameMatch.Success) { throw "SOURCE_CONTRACT_FUNCTION_NAME_UNPARSEABLE path=$Path offset=$start" }
        $normalized = ($rawText -replace "`r`n?", "`n").TrimEnd([char[]]@("`n"))
        $rawHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.UTF8Encoding]::new($false).GetBytes($rawText))).ToLowerInvariant()
        $normalizedHash = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData([Text.UTF8Encoding]::new($false).GetBytes($normalized))).ToLowerInvariant()
        $blocks.Add([pscustomobject]@{ Name = $nameMatch.Groups['name'].Value; RawSha256 = $rawHash; NormalizedSha256 = $normalizedHash })
    }
    if ($blocks.Count -eq 0) { throw "SOURCE_CONTRACT_FUNCTIONS_MISSING path=$Path" }
    return $blocks.ToArray()
}

$expectedFrozenSha = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
$expectedCandidateSha = '5ea69f6b0ebc5e5be13cb109e4ec3eec30f377b52a5f22beed224164a035be3b'
$expectedProbeSha = 'bfe56ad02c99240257fddd212ba43ee5606a81740b3dda716c5947c433cbfa88'
$expectedSelectorSha = 'a40c6459e66a384e85053589b270c5d2e112363872153fbf46da5c56fd4bb1f5'
$gatherPinnedSha = 'e888255d30e77a5e1231f44e3d07b566df3fa74d55358d03b4732791bcc45571'

function Get-ContractFileSha256 {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "SOURCE_CONTRACT_INPUT_MISSING path=$Path"
    }
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

$frozenSha = Get-ContractFileSha256 -Path $FrozenAuthorityPath
$candidateSha = Get-ContractFileSha256 -Path $QualifiedCandidatePath
$probeSha = Get-ContractFileSha256 -Path $QualifiedProbePath
$selectorSha = Get-ContractFileSha256 -Path $QualifiedSelectorPath
foreach ($check in @(
    @{ Name = 'frozen_authority'; Actual = $frozenSha; Expected = $expectedFrozenSha },
    @{ Name = 'qualified_candidate'; Actual = $candidateSha; Expected = $expectedCandidateSha },
    @{ Name = 'qualified_probe'; Actual = $probeSha; Expected = $expectedProbeSha },
    @{ Name = 'qualified_selector'; Actual = $selectorSha; Expected = $expectedSelectorSha }
)) {
    if ($check.Actual -cne $check.Expected) {
        throw "SOURCE_CONTRACT_PIN_MISMATCH name=$($check.Name) expected=$($check.Expected) actual=$($check.Actual)"
    }
}

$frozenBlocks = @(Get-ContractFunctionBlocks -Path $FrozenAuthorityPath)
$candidateBlocks = @(Get-ContractFunctionBlocks -Path $QualifiedCandidatePath)
$productionBlocks = @(Get-ContractFunctionBlocks -Path $ProductionEntryPath)
$frozenByName = @{}
foreach ($block in $frozenBlocks) { $frozenByName[[string]$block.Name] = $block }
$candidateByName = @{}
foreach ($block in $candidateBlocks) { $candidateByName[[string]$block.Name] = $block }
$productionByName = @{}
foreach ($block in $productionBlocks) { $productionByName[[string]$block.Name] = $block }

$gpuFunctionNames = @(
    'fitAllOrdersGpu', 'initializeResidualPathGpu', 'runSageGpu',
    'evaluateModelGpu', 'gridSearchPathGpu', 'refinePathGpu',
    'scoreReplicaBatchGpu', 'makeReplicaBatchGpu', 'buildReplicasGpu',
    'solveAmplitudesGpu', 'synthesizeGpu', 'residualRssGpu',
    'replicaCoherenceGpu', 'ensureGpuPathState', 'pathAlphaGpu',
    'gatherGpuFit', 'gpuProbeToCpu'
)
$productionPlumbingNames = @(
    'run_nav_sage_pipeline_gpu_production', 'parsePipelineInputs',
    'resolveInputs', 'fitAllOrders', 'assertProductionGpuInputIdentity',
    'assertProductionGpuRunContextIdentity', 'assertProductionGpuAvailability',
    'initializeProductionGpuDevice', 'writeGpuExecutionProvenance',
    'computeFileSha256', 'validateProductionGpuExecutionPlan',
    'computeCanonicalGpuTaskIdentitySha256', 'getProductionGpuRuntimeLockPath',
    'acquireProductionGpuRuntimeLock', 'releaseProductionGpuRuntimeLock',
    'writeGpuExecutionAttempt'
)
$frozenFunctionAliases = [ordered]@{
    run_nav_sage_pipeline = 'run_nav_sage_pipeline_gpu_production'
}

foreach ($frozenName in $frozenByName.Keys) {
    $productionName = if ($frozenFunctionAliases.Contains($frozenName)) {
        [string]$frozenFunctionAliases[$frozenName]
    } else { [string]$frozenName }
    if (-not $productionByName.ContainsKey($productionName)) {
        throw "SOURCE_CONTRACT_FROZEN_FUNCTION_MISSING frozen=$frozenName expected_production=$productionName"
    }
    $actualBlock = $productionByName[$productionName]
    if ($frozenName -eq 'run_nav_sage_pipeline') { continue }
    if ($actualBlock.RawSha256 -cne $frozenByName[$frozenName].RawSha256 -and
        $frozenName -notin @('parsePipelineInputs', 'resolveInputs', 'fitAllOrders')) {
        throw "SOURCE_CONTRACT_UNAPPROVED_FROZEN_CHANGE function=$frozenName frozen=$($frozenByName[$frozenName].RawSha256) production=$($actualBlock.RawSha256)"
    }
}

foreach ($name in $gpuFunctionNames) {
    if (-not $candidateByName.ContainsKey($name) -or -not $productionByName.ContainsKey($name)) {
        throw "SOURCE_CONTRACT_GPU_FUNCTION_MISSING name=$name"
    }
    if ($candidateByName[$name].RawSha256 -cne $productionByName[$name].RawSha256) {
        throw "SOURCE_CONTRACT_GPU_RAW_MISMATCH name=$name candidate=$($candidateByName[$name].RawSha256) production=$($productionByName[$name].RawSha256)"
    }
}
if ($candidateByName['gatherGpuFit'].NormalizedSha256 -cne $gatherPinnedSha -or
    $productionByName['gatherGpuFit'].NormalizedSha256 -cne $gatherPinnedSha) {
    throw 'SOURCE_CONTRACT_GATHER_PIN_MISMATCH'
}

$functionContracts = [System.Collections.Generic.List[object]]::new()
foreach ($productionBlock in $productionBlocks) {
    $name = [string]$productionBlock.Name
    if ($name -in $gpuFunctionNames) {
        $classification = if ($name -eq 'gatherGpuFit') { 'EXACT_PINNED' } else { 'MUST_MATCH_QUALIFIED_GPU_RAW' }
        $source = 'qualified_candidate'
    } elseif ($name -in $productionPlumbingNames) {
        $classification = 'ALLOWED_PRODUCTION_PLUMBING'
        $source = 'production'
    } elseif ($frozenByName.ContainsKey($name)) {
        $classification = 'MUST_BE_BYTE_IDENTICAL_TO_FROZEN'
        $source = 'frozen'
    } else {
        throw "SOURCE_CONTRACT_UNCLASSIFIED_PRODUCTION_FUNCTION name=$name"
    }
    $functionContracts.Add([ordered]@{
        name = $name
        classification = $classification
        source = $source
        sha256 = $productionBlock.RawSha256
    })
}

$unexpectedNames = @($productionByName.Keys | Where-Object {
    $_ -notin $gpuFunctionNames -and
    $_ -notin $productionPlumbingNames -and
    -not $frozenByName.ContainsKey($_)
})
if ($unexpectedNames.Count -gt 0) {
    throw "SOURCE_CONTRACT_UNEXPECTED_PRODUCTION_FUNCTIONS names=$($unexpectedNames -join ',')"
}

$contract = [ordered]@{
    schema_version = 'frozen-sage-production-gpu-source-contract-v1'
    frozen_authority_sha256 = $frozenSha
    qualified_candidate_sha256 = $candidateSha
    qualified_probe_sha256 = $probeSha
    qualified_selector_sha256 = $selectorSha
    production_entry_sha256 = Get-ContractFileSha256 -Path $ProductionEntryPath
    frozen_function_order = @($frozenBlocks | ForEach-Object { [string]$_.Name })
    frozen_function_aliases = $frozenFunctionAliases
    expected_production_function_order = @($productionBlocks | ForEach-Object { [string]$_.Name })
    function_contracts = @($functionContracts.ToArray())
    exact_pinned_blocks = [ordered]@{ gatherGpuFit = $gatherPinnedSha }
}

$json = ConvertTo-Json -InputObject $contract -Depth 12
[System.IO.File]::WriteAllText(
    [System.IO.Path]::GetFullPath($OutputPath),
    $json + [Environment]::NewLine,
    [System.Text.UTF8Encoding]::new($false)
)
Write-Output "SOURCE_CONTRACT_CREATED path=$([System.IO.Path]::GetFullPath($OutputPath))"
Write-Output "SOURCE_CONTRACT_SHA256=$((Get-ContractFileSha256 -Path $OutputPath))"
Write-Output "FROZEN_FUNCTIONS=$($frozenBlocks.Count) PRODUCTION_FUNCTIONS=$($productionBlocks.Count)"
