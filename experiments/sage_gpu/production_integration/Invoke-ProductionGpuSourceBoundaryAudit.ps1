[CmdletBinding()]
param(
    [string]$FrozenAuthorityPath,
    [string]$QualifiedCandidatePath,
    [string]$QualifiedProbePath,
    [string]$QualifiedSelectorPath,
    [string]$ProductionEntryPath,
    [string]$SourceContractPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-ProductionGpuSha256 {
    param([Parameter(Mandatory)][string]$LiteralPath)
    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
        throw "AUDIT_SOURCE_FILE_MISSING path=$LiteralPath"
    }
    return (Get-FileHash -LiteralPath $LiteralPath -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-ProductionGpuUtf8Sha256 {
    param([Parameter(Mandatory)][string]$Text)
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($Text)
    return [Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
}

function Get-ProductionGpuFunctionBlocks {
    param([Parameter(Mandatory)][string]$LiteralPath)
    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
        throw "AUDIT_SOURCE_FILE_MISSING path=$LiteralPath"
    }
    $source = [System.IO.File]::ReadAllText((Resolve-Path -LiteralPath $LiteralPath).Path)
    $functionMatches = [regex]::Matches($source, '(?m)^[\t ]*function\b')
    if ($functionMatches.Count -eq 0) { throw "AUDIT_MATLAB_FUNCTIONS_MISSING path=$LiteralPath" }
    $blocks = [System.Collections.Generic.List[object]]::new()
    for ($index = 0; $index -lt $functionMatches.Count; $index++) {
        $start = $functionMatches[$index].Index
        $end = if ($index + 1 -lt $functionMatches.Count) { $functionMatches[$index + 1].Index } else { $source.Length }
        $rawText = $source.Substring($start, $end - $start).TrimEnd([char[]]@("`r", "`n"))
        $openParen = $rawText.IndexOf('(')
        if ($openParen -lt 0) { throw "AUDIT_FUNCTION_SIGNATURE_UNPARSEABLE path=$LiteralPath offset=$start" }
        $prefix = $rawText.Substring(0, $openParen)
        $nameMatch = [regex]::Match($prefix, '(?<name>[A-Za-z][A-Za-z0-9_]*)[\t ]*$')
        if (-not $nameMatch.Success) { throw "AUDIT_FUNCTION_NAME_UNPARSEABLE path=$LiteralPath offset=$start" }
        $normalized = ($rawText -replace "`r`n?", "`n").TrimEnd([char[]]@("`n"))
        $blocks.Add([pscustomobject]@{
            Name = $nameMatch.Groups['name'].Value
            RawText = $rawText
            RawSha256 = Get-ProductionGpuUtf8Sha256 -Text $rawText
            NormalizedSha256 = Get-ProductionGpuUtf8Sha256 -Text $normalized
        })
    }
    return $blocks.ToArray()
}

function Add-ProductionGpuAuditDiff {
    param(
        [System.Collections.Generic.List[object]]$Diffs,
        [Parameter(Mandatory)][string]$Code,
        [Parameter(Mandatory)][string]$Detail
    )
    $Diffs.Add([pscustomobject]@{ Code = $Code; Detail = $Detail })
}

function Get-ProductionGpuFunctionByName {
    param(
        [Parameter(Mandatory)][object[]]$Blocks,
        [Parameter(Mandatory)][string]$Name
    )
    $matches = @($Blocks | Where-Object { [string]$_.Name -ceq $Name })
    if ($matches.Count -ne 1) { return $null }
    return $matches[0]
}

$script:ProductionGpuExpectedAlias = [ordered]@{
    run_nav_sage_pipeline = 'run_nav_sage_pipeline_gpu_production'
}
$script:ProductionGpuChangedFrozenFunctions = @(
    'run_nav_sage_pipeline_gpu_production', 'parsePipelineInputs', 'resolveInputs', 'fitAllOrders'
)
$script:ProductionGpuQualifiedFunctionOrder = @(
    'fitAllOrdersGpu', 'initializeResidualPathGpu', 'runSageGpu',
    'evaluateModelGpu', 'gridSearchPathGpu', 'refinePathGpu',
    'scoreReplicaBatchGpu', 'makeReplicaBatchGpu', 'buildReplicasGpu',
    'solveAmplitudesGpu', 'synthesizeGpu', 'residualRssGpu',
    'replicaCoherenceGpu', 'ensureGpuPathState', 'pathAlphaGpu',
    'gatherGpuFit', 'gpuProbeToCpu'
)
$script:ProductionGpuPlumbingTailOrder = @(
    'assertProductionGpuInputIdentity', 'assertProductionGpuRunContextIdentity',
    'assertProductionGpuAvailability', 'initializeProductionGpuDevice',
    'writeGpuExecutionProvenance', 'computeFileSha256',
    'validateProductionGpuExecutionPlan', 'computeCanonicalGpuTaskIdentitySha256',
    'getProductionGpuRuntimeLockPath', 'acquireProductionGpuRuntimeLock',
    'releaseProductionGpuRuntimeLock', 'writeGpuExecutionAttempt'
)
$script:ProductionGpuAllowedPlumbing = @(
    'run_nav_sage_pipeline_gpu_production', 'parsePipelineInputs', 'resolveInputs',
    'fitAllOrders', 'assertProductionGpuInputIdentity',
    'assertProductionGpuRunContextIdentity', 'assertProductionGpuAvailability',
    'initializeProductionGpuDevice', 'writeGpuExecutionProvenance', 'computeFileSha256',
    'validateProductionGpuExecutionPlan', 'computeCanonicalGpuTaskIdentitySha256',
    'getProductionGpuRuntimeLockPath', 'acquireProductionGpuRuntimeLock',
    'releaseProductionGpuRuntimeLock', 'writeGpuExecutionAttempt'
)
$script:ProductionGpuExpectedFileHashes = @{
    frozen_authority_sha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
    qualified_candidate_sha256 = '5ea69f6b0ebc5e5be13cb109e4ec3eec30f377b52a5f22beed224164a035be3b'
    qualified_probe_sha256 = 'bfe56ad02c99240257fddd212ba43ee5606a81740b3dda716c5947c433cbfa88'
    qualified_selector_sha256 = 'a40c6459e66a384e85053589b270c5d2e112363872153fbf46da5c56fd4bb1f5'
}
$script:ProductionGpuGatherPinnedSha256 = 'e888255d30e77a5e1231f44e3d07b566df3fa74d55358d03b4732791bcc45571'

function Invoke-ProductionGpuSourceBoundaryAudit {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$FrozenAuthorityPath,
        [Parameter(Mandatory)][string]$QualifiedCandidatePath,
        [Parameter(Mandatory)][string]$QualifiedProbePath,
        [Parameter(Mandatory)][string]$QualifiedSelectorPath,
        [Parameter(Mandatory)][string]$ProductionEntryPath,
        [Parameter(Mandatory)][string]$SourceContractPath
    )

    $diffs = [System.Collections.Generic.List[object]]::new()
    try {
        $contract = Get-Content -Raw -LiteralPath $SourceContractPath -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $requiredContractFields = @(
            'schema_version', 'frozen_authority_sha256', 'qualified_candidate_sha256',
            'qualified_probe_sha256', 'qualified_selector_sha256', 'production_entry_sha256',
            'frozen_function_order', 'frozen_function_aliases',
            'expected_production_function_order', 'function_contracts', 'exact_pinned_blocks'
        )
        $contractFieldNames = @($contract.PSObject.Properties.Name)
        $missingFields = @($requiredContractFields | Where-Object { $_ -notin $contractFieldNames })
        $unknownFields = @($contractFieldNames | Where-Object { $_ -notin $requiredContractFields })
        if ($contract.schema_version -cne 'frozen-sage-production-gpu-source-contract-v1' -or
            $missingFields.Count -gt 0 -or $unknownFields.Count -gt 0) {
            Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'SOURCE_CONTRACT_SCHEMA_INVALID' `
                -Detail "schema=$($contract.schema_version) missing=$($missingFields -join ',') unknown=$($unknownFields -join ',')"
        }

        $identityInputs = @(
            @{ Field = 'frozen_authority_sha256'; Path = $FrozenAuthorityPath },
            @{ Field = 'qualified_candidate_sha256'; Path = $QualifiedCandidatePath },
            @{ Field = 'qualified_probe_sha256'; Path = $QualifiedProbePath },
            @{ Field = 'qualified_selector_sha256'; Path = $QualifiedSelectorPath },
            @{ Field = 'production_entry_sha256'; Path = $ProductionEntryPath }
        )
        foreach ($identity in $identityInputs) {
            try {
                $actualHash = Get-ProductionGpuSha256 -LiteralPath $identity.Path
                $expectedHash = [string]$contract.($identity.Field)
                $authorityPin = [string]$script:ProductionGpuExpectedFileHashes[$identity.Field]
                if ($expectedHash -notmatch '^[0-9a-fA-F]{64}$' -or
                    -not [string]::Equals($actualHash, $expectedHash, [System.StringComparison]::OrdinalIgnoreCase)) {
                    Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'SOURCE_FILE_SHA_MISMATCH' `
                        -Detail "field=$($identity.Field) expected=$expectedHash actual=$actualHash"
                }
                if (-not [string]::IsNullOrEmpty($authorityPin) -and
                    -not [string]::Equals($actualHash, $authorityPin, [System.StringComparison]::OrdinalIgnoreCase)) {
                    Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'SOURCE_FILE_AUTHORITY_PIN_MISMATCH' `
                        -Detail "field=$($identity.Field) pinned=$authorityPin actual=$actualHash"
                }
            } catch {
                Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'SOURCE_FILE_MISSING_OR_UNREADABLE' `
                    -Detail "field=$($identity.Field) detail=$($_.Exception.Message)"
            }
        }

        $frozenBlocks = @(Get-ProductionGpuFunctionBlocks -LiteralPath $FrozenAuthorityPath)
        $candidateBlocks = @(Get-ProductionGpuFunctionBlocks -LiteralPath $QualifiedCandidatePath)
        $productionBlocks = @(Get-ProductionGpuFunctionBlocks -LiteralPath $ProductionEntryPath)
        $frozenNames = @($frozenBlocks | ForEach-Object { $_.Name })
        $productionNames = @($productionBlocks | ForEach-Object { $_.Name })
        $expectedFrozenNames = @($contract.frozen_function_order | ForEach-Object { [string]$_ })
        $expectedProductionNames = @($contract.expected_production_function_order | ForEach-Object { [string]$_ })
        if (@($frozenNames | Group-Object | Where-Object Count -gt 1).Count -gt 0) {
            Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'FROZEN_FUNCTION_DUPLICATE' -Detail ($frozenNames -join ',')
        }
        if (@($productionNames | Group-Object | Where-Object Count -gt 1).Count -gt 0) {
            Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'PRODUCTION_FUNCTION_DUPLICATE' -Detail ($productionNames -join ',')
        }
        if (($frozenNames -join "`n") -cne ($expectedFrozenNames -join "`n")) {
            Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'FROZEN_FUNCTION_ORDER_OR_SET_MISMATCH' `
                -Detail "expected=$($expectedFrozenNames -join ',') actual=$($frozenNames -join ',')"
        }
        if (($productionNames -join "`n") -cne ($expectedProductionNames -join "`n")) {
            Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'PRODUCTION_FUNCTION_ORDER_OR_SET_MISMATCH' `
                -Detail "expected=$($expectedProductionNames -join ',') actual=$($productionNames -join ',')"
        }

        $aliases = @{}
        foreach ($property in $contract.frozen_function_aliases.PSObject.Properties) {
            $aliases[[string]$property.Name] = [string]$property.Value
        }
        if ($aliases.Count -ne $script:ProductionGpuExpectedAlias.Count -or
            $aliases['run_nav_sage_pipeline'] -cne $script:ProductionGpuExpectedAlias.run_nav_sage_pipeline) {
            Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'FROZEN_FUNCTION_ALIAS_POLICY_MISMATCH' `
                -Detail "actual=$($contract.frozen_function_aliases | ConvertTo-Json -Compress)"
        }
        $pinnedBlockNames = @($contract.exact_pinned_blocks.PSObject.Properties.Name)
        if ($pinnedBlockNames.Count -ne 1 -or $pinnedBlockNames[0] -cne 'gatherGpuFit' -or
            [string]$contract.exact_pinned_blocks.gatherGpuFit -cne $script:ProductionGpuGatherPinnedSha256) {
            Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'EXACT_PINNED_BLOCK_POLICY_MISMATCH' `
                -Detail "actual=$($contract.exact_pinned_blocks | ConvertTo-Json -Compress)"
        }
        $canonicalProductionNames = @(
            $expectedFrozenNames | ForEach-Object {
                if ($script:ProductionGpuExpectedAlias.Contains($_)) { $script:ProductionGpuExpectedAlias[$_] } else { [string]$_ }
            }
        ) + $script:ProductionGpuQualifiedFunctionOrder + $script:ProductionGpuPlumbingTailOrder
        if (($canonicalProductionNames -join "`n") -cne ($expectedProductionNames -join "`n")) {
            Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'PRODUCTION_FUNCTION_POLICY_ORDER_MISMATCH' `
                -Detail "expected=$($canonicalProductionNames -join ',') contract=$($expectedProductionNames -join ',')"
        }
        foreach ($frozenName in $frozenNames) {
            $productionName = if ($aliases.ContainsKey($frozenName)) { $aliases[$frozenName] } else { $frozenName }
            if ($productionName -notin $productionNames) {
                Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'FROZEN_FUNCTION_MISSING_IN_PRODUCTION' `
                    -Detail "frozen=$frozenName expected_production=$productionName"
            }
        }

        $functionContracts = @($contract.function_contracts)
        $contractNames = @($functionContracts | ForEach-Object { [string]$_.name })
        if (@($contractNames | Group-Object | Where-Object Count -gt 1).Count -gt 0) {
            Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'SOURCE_CONTRACT_FUNCTION_DUPLICATE' -Detail ($contractNames -join ',')
        }
        if (($contractNames -join "`n") -cne ($productionNames -join "`n")) {
            Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'SOURCE_CONTRACT_FUNCTION_SET_OR_ORDER_MISMATCH' `
                -Detail "contract=$($contractNames -join ',') production=$($productionNames -join ',')"
        }

        foreach ($functionContract in $functionContracts) {
            $name = [string]$functionContract.name
            $classification = [string]$functionContract.classification
            $contractPropertyNames = @($functionContract.PSObject.Properties.Name)
            $missingContractProperties = @(@('name', 'classification', 'source', 'sha256') | Where-Object { $_ -notin $contractPropertyNames })
            if ($contractPropertyNames.Count -ne 4 -or
                $missingContractProperties.Count -gt 0) {
                Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'SOURCE_CONTRACT_FUNCTION_SCHEMA_INVALID' -Detail "function=$name fields=$($contractPropertyNames -join ',')"
                continue
            }
            $expectedClassification = if ($name -in $script:ProductionGpuQualifiedFunctionOrder) {
                if ($name -eq 'gatherGpuFit') { 'EXACT_PINNED' } else { 'MUST_MATCH_QUALIFIED_GPU_RAW' }
            } elseif ($name -in $script:ProductionGpuAllowedPlumbing) {
                'ALLOWED_PRODUCTION_PLUMBING'
            } elseif ($name -in $expectedFrozenNames) {
                'MUST_BE_BYTE_IDENTICAL_TO_FROZEN'
            } else {
                ''
            }
            if ([string]::IsNullOrEmpty($expectedClassification) -or $classification -cne $expectedClassification) {
                Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'SOURCE_CONTRACT_FUNCTION_POLICY_MISMATCH' `
                    -Detail "function=$name expected=$expectedClassification actual=$classification"
                continue
            }
            $expectedSource = switch ($expectedClassification) {
                'MUST_BE_BYTE_IDENTICAL_TO_FROZEN' { 'frozen' }
                'MUST_MATCH_QUALIFIED_GPU_RAW' { 'qualified_candidate' }
                'EXACT_PINNED' { 'qualified_candidate' }
                'ALLOWED_PRODUCTION_PLUMBING' { 'production' }
            }
            if ([string]$functionContract.source -cne $expectedSource -or
                [string]$functionContract.sha256 -notmatch '^[0-9a-fA-F]{64}$') {
                Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'SOURCE_CONTRACT_FUNCTION_SOURCE_INVALID' `
                    -Detail "function=$name expected_source=$expectedSource actual_source=$($functionContract.source) sha256=$($functionContract.sha256)"
                continue
            }
            $productionBlock = Get-ProductionGpuFunctionByName -Blocks $productionBlocks -Name $name
            if ($null -eq $productionBlock) {
                Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'PRODUCTION_FUNCTION_MISSING_OR_AMBIGUOUS' -Detail "function=$name"
                continue
            }
            if ($productionBlock.RawSha256 -cne [string]$functionContract.sha256 -and
                $classification -eq 'ALLOWED_PRODUCTION_PLUMBING') {
                Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'ALLOWED_PRODUCTION_PLUMBING_CHANGED' `
                    -Detail "function=$name expected=$($functionContract.sha256) actual=$($productionBlock.RawSha256)"
                continue
            }
            switch ($classification) {
                'MUST_BE_BYTE_IDENTICAL_TO_FROZEN' {
                    $frozenBlock = Get-ProductionGpuFunctionByName -Blocks $frozenBlocks -Name $name
                    if ($null -eq $frozenBlock -or
                        $frozenBlock.RawSha256 -cne $productionBlock.RawSha256 -or
                        $functionContract.source -cne 'frozen' -or
                        [string]$functionContract.sha256 -cne $frozenBlock.RawSha256) {
                        Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'FROZEN_FUNCTION_RAW_HASH_MISMATCH' `
                            -Detail "function=$name frozen=$(if($null -eq $frozenBlock){'MISSING'}else{$frozenBlock.RawSha256}) production=$($productionBlock.RawSha256) contract=$($functionContract.sha256)"
                    }
                }
                'MUST_MATCH_QUALIFIED_GPU_RAW' {
                    $candidateBlock = Get-ProductionGpuFunctionByName -Blocks $candidateBlocks -Name $name
                    if ($null -eq $candidateBlock -or
                        $candidateBlock.RawSha256 -cne $productionBlock.RawSha256 -or
                        $functionContract.source -cne 'qualified_candidate' -or
                        [string]$functionContract.sha256 -cne $candidateBlock.RawSha256) {
                        Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'QUALIFIED_GPU_FUNCTION_RAW_HASH_MISMATCH' `
                            -Detail "function=$name candidate=$(if($null -eq $candidateBlock){'MISSING'}else{$candidateBlock.RawSha256}) production=$($productionBlock.RawSha256) contract=$($functionContract.sha256)"
                    }
                }
                'EXACT_PINNED' {
                    $candidateBlock = Get-ProductionGpuFunctionByName -Blocks $candidateBlocks -Name $name
                    $pinnedHash = [string]$contract.exact_pinned_blocks.($name)
                    if ($null -eq $candidateBlock -or
                        $candidateBlock.RawSha256 -cne $productionBlock.RawSha256 -or
                        [string]$functionContract.sha256 -cne $productionBlock.RawSha256 -or
                        [string]::IsNullOrWhiteSpace($pinnedHash) -or
                        $candidateBlock.NormalizedSha256 -cne $pinnedHash -or
                        $productionBlock.NormalizedSha256 -cne $pinnedHash) {
                        Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'EXACT_PINNED_FUNCTION_MISMATCH' `
                            -Detail "function=$name pinned=$pinnedHash candidate=$(if($null -eq $candidateBlock){'MISSING'}else{$candidateBlock.NormalizedSha256}) production=$($productionBlock.NormalizedSha256)"
                    }
                }
                'ALLOWED_PRODUCTION_PLUMBING' {
                    if ($functionContract.source -cne 'production') {
                        Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'PRODUCTION_PLUMBING_SOURCE_INVALID' -Detail "function=$name source=$($functionContract.source)"
                    }
                }
                default {
                    Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'SOURCE_CONTRACT_CLASSIFICATION_UNKNOWN' `
                        -Detail "function=$name classification=$classification"
                }
            }
        }
    } catch {
        Add-ProductionGpuAuditDiff -Diffs $diffs -Code 'SOURCE_AUDIT_INPUT_INVALID' `
            -Detail "detail=$($_.Exception.Message) line=$($_.InvocationInfo.ScriptLineNumber) stack=$($_.ScriptStackTrace)"
    }

    return [pscustomobject]@{
        Status = if ($diffs.Count -eq 0) { 'PASS' } else { 'BLOCKED' }
        UnexpectedDiffCount = $diffs.Count
        Rows = @($diffs.ToArray())
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    $audit = Invoke-ProductionGpuSourceBoundaryAudit `
        -FrozenAuthorityPath $FrozenAuthorityPath `
        -QualifiedCandidatePath $QualifiedCandidatePath `
        -QualifiedProbePath $QualifiedProbePath `
        -QualifiedSelectorPath $QualifiedSelectorPath `
        -ProductionEntryPath $ProductionEntryPath `
        -SourceContractPath $SourceContractPath
    Write-Output "STATUS=$($audit.Status)"
    Write-Output "UNEXPECTED_DIFF_COUNT=$($audit.UnexpectedDiffCount)"
    foreach ($row in $audit.Rows) { Write-Output "$($row.Code) $($row.Detail)" }
    if ($audit.Status -ne 'PASS') { exit 1 }
}
