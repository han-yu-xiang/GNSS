[CmdletBinding()]
param(
    [string]$RunId,
    [string]$ExecutionPlanPath,
    [switch]$Execute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$script:FrozenProjectRoot = 'E:\GNSS_Multipath_Project'
$script:FrozenSampleRateHz = 10230000
$script:FrozenSourceRelativePath = 'scripts\sage_pipeline\run_nav_sage_pipeline.m'
$script:FrozenSourceSha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
$script:QualifiedCandidateSha256 = '5ea69f6b0ebc5e5be13cb109e4ec3eec30f377b52a5f22beed224164a035be3b'
$script:QualifiedProbeSha256 = 'bfe56ad02c99240257fddd212ba43ee5606a81740b3dda716c5947c433cbfa88'
$script:QualifiedSelectorSha256 = 'a40c6459e66a384e85053589b270c5d2e112363872153fbf46da5c56fd4bb1f5'
$script:ApprovedGpuProductionEntrySha256 = 'f9d1093baaad513acd1f45b7c6c4223d69e168c0e5c2c74fa818ef5378bf3cd5'
$script:ApprovedGpuSourceContractSha256 = 'c52210280d40b91a224da1e02ccfd38ba6225b65006ae4f356ce494f372e8644'
$script:ApprovedGpuExecutionPlanSha256 = '846eee3e7e1ddf66a275c4bb30c67b15b44781d835ee819905f8a0da980bd91f'
$script:ProductionGpuSourceContractRelativePath = 'experiments\sage_gpu\production_integration\PRODUCTION_GPU_SOURCE_CONTRACT.json'
$script:FrozenManifestRelativePath = 'reports\data_consolidation_20261003\MAINLINE_SAGE_1023_RERUN_MANIFEST.csv'
$script:FrozenNamespaceRoot = 'sage_results\rerun_20261003_frozen_v3'
$script:TransientNamespaceRoot = 'sage_results\nav_sage_v2'
$script:StartupMarker = 'MATLAB_STARTUP_OK'
$script:TransportMarker = 'MATLAB_ARGUMENT_TRANSPORT_OK'

function Assert-FrozenSageHash {
    param(
        [Parameter(Mandatory)][string]$ActualHash,
        [Parameter(Mandatory)][string]$ExpectedHash
    )

    if (-not [string]::Equals($ActualHash, $ExpectedHash, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "FROZEN_SAGE_SOURCE_HASH_MISMATCH expected=$ExpectedHash actual=$ActualHash"
    }
    return $true
}

function Assert-FrozenSageExecutionPlanPin {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$ExecutionPlanPath)

    if ([string]::IsNullOrWhiteSpace($script:ApprovedGpuExecutionPlanSha256)) {
        throw 'GPU_EXECUTION_PLAN_NOT_RELEASED approved_plan_sha256_is_empty'
    }
    if ($script:ApprovedGpuExecutionPlanSha256 -notmatch '^[0-9a-fA-F]{64}$') {
        throw 'GPU_EXECUTION_PLAN_RELEASE_PIN_INVALID'
    }
    if (-not (Test-Path -LiteralPath $ExecutionPlanPath -PathType Leaf)) {
        throw "GPU_EXECUTION_PLAN_NOT_FOUND path=$ExecutionPlanPath"
    }
    $actualHash = (Get-FileHash -LiteralPath $ExecutionPlanPath -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    if (-not [string]::Equals($actualHash, $script:ApprovedGpuExecutionPlanSha256, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "GPU_EXECUTION_PLAN_SHA_MISMATCH expected=$script:ApprovedGpuExecutionPlanSha256 actual=$actualHash"
    }
    return $actualHash
}

function Get-FrozenSageCanonicalTaskIdentitySha256 {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$RunId,
        [Parameter(Mandatory)][string]$SceneId,
        [Parameter(Mandatory)][string]$PrnLabel,
        [Parameter(Mandatory)][int]$TrackingChannel
    )

    if ($RunId -notmatch '^[A-Za-z0-9_.-]+$' -or
        $SceneId -notmatch '^[A-Za-z0-9_-]+$' -or $PrnLabel -notmatch '^G\d{2}$' -or
        $TrackingChannel -lt 0 -or $TrackingChannel -gt 32) {
        throw 'GPU_EXECUTION_PLAN_TASK_IDENTITY_INVALID'
    }
    $canonical = "run_id=$RunId`nscene_id=$SceneId`nprn=$PrnLabel`ntracking_channel=$TrackingChannel`n"
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($canonical)
    return [Convert]::ToHexString([System.Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
}

function Assert-FrozenSageGpuRuntimeReleasePins {
    [CmdletBinding()]
    param([Parameter(Mandatory)][string]$SourceContractPath)

    $productionEntryPath = Join-Path $PSScriptRoot 'run_nav_sage_pipeline_gpu_production.m'
    foreach ($source in @(
        @{ Field = 'source_contract_sha256'; Path = $SourceContractPath; Pin = $script:ApprovedGpuSourceContractSha256 },
        @{ Field = 'production_entry_sha256'; Path = $productionEntryPath; Pin = $script:ApprovedGpuProductionEntrySha256 }
    )) {
        if (-not (Test-Path -LiteralPath $source.Path -PathType Leaf)) {
            throw "GPU_SOURCE_IDENTITY_MISMATCH field=$($source.Field) source_missing=$($source.Path)"
        }
        $actual = (Get-FileHash -LiteralPath $source.Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
        if ([string]::IsNullOrWhiteSpace([string]$source.Pin) -or
            -not [string]::Equals($actual, [string]$source.Pin, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "GPU_SOURCE_IDENTITY_MISMATCH field=$($source.Field) pinned=$($source.Pin) actual=$actual"
        }
    }
    return $true
}

function Resolve-FrozenSageExecutionPlan {
    [CmdletBinding()]
    param(
        [AllowNull()][string]$ExecutionPlanPath,
        [Parameter(Mandatory)][string]$RunId,
        [Parameter(Mandatory)][string]$ManifestPath,
        [Parameter(Mandatory)][string]$SourceContractPath
    )

    if ([string]::IsNullOrWhiteSpace($ExecutionPlanPath)) {
        return [pscustomobject]@{
            ExecutionMode = 'CPU_FROZEN'
            ExecutionPlanSha256 = ''
            SourceManifestSha256 = ''
            GpuSourceContractSha256 = ''
            Resume = $false
            MaxParallelMatlab = 1
            AuthorizedRunIds = @()
            AuthorizedTasks = @()
        }
    }
    $planHash = Assert-FrozenSageExecutionPlanPin -ExecutionPlanPath $ExecutionPlanPath
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        throw "GPU_EXECUTION_PLAN_MANIFEST_NOT_FOUND path=$ManifestPath"
    }
    if (-not (Test-Path -LiteralPath $SourceContractPath -PathType Leaf)) {
        throw "GPU_EXECUTION_PLAN_SOURCE_CONTRACT_NOT_FOUND path=$SourceContractPath"
    }
    [void](Assert-FrozenSageGpuRuntimeReleasePins -SourceContractPath $SourceContractPath)
    $contractHash = (Get-FileHash -LiteralPath $SourceContractPath -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()

    $document = $null
    try {
        $planJson = [System.IO.File]::ReadAllText($ExecutionPlanPath)
        $document = [System.Text.Json.JsonDocument]::Parse($planJson)
        if ($document.RootElement.ValueKind -ne [System.Text.Json.JsonValueKind]::Object) {
            throw 'GPU_EXECUTION_PLAN_SCHEMA_INVALID root_must_be_object'
        }
        $properties = [System.Collections.Generic.Dictionary[string, System.Text.Json.JsonElement]]::new([System.StringComparer]::Ordinal)
        foreach ($property in $document.RootElement.EnumerateObject()) {
            if ($properties.ContainsKey($property.Name)) {
                throw "GPU_EXECUTION_PLAN_SCHEMA_INVALID duplicate_field=$($property.Name)"
            }
            $properties.Add($property.Name, $property.Value.Clone())
        }
        $requiredFields = @(
            'schema_version', 'execution_mode', 'source_manifest_sha256',
            'resume', 'max_parallel_matlab', 'authorized_tasks'
        )
        $missingFields = @($requiredFields | Where-Object { -not $properties.ContainsKey($_) })
        $unknownFields = @($properties.Keys | Where-Object { $_ -notin $requiredFields })
        if ($missingFields.Count -gt 0 -or $unknownFields.Count -gt 0) {
            throw "GPU_EXECUTION_PLAN_SCHEMA_INVALID missing=$($missingFields -join ',') unknown=$($unknownFields -join ',')"
        }

        foreach ($field in @('schema_version', 'execution_mode', 'source_manifest_sha256')) {
            if ($properties[$field].ValueKind -ne [System.Text.Json.JsonValueKind]::String) {
                throw "GPU_EXECUTION_PLAN_FIELD_TYPE_INVALID field=$field expected=string"
            }
        }
        if ($properties['resume'].ValueKind -ne [System.Text.Json.JsonValueKind]::False) {
            throw 'GPU_EXECUTION_PLAN_RESUME_NOT_ALLOWED expected=false'
        }
        if ($properties['max_parallel_matlab'].ValueKind -ne [System.Text.Json.JsonValueKind]::Number) {
            throw 'GPU_EXECUTION_PLAN_MAX_PARALLEL_INVALID expected_integer_1'
        }
        $maxParallel = 0
        if (-not $properties['max_parallel_matlab'].TryGetInt32([ref]$maxParallel) -or $maxParallel -ne 1) {
            throw "GPU_EXECUTION_PLAN_MAX_PARALLEL_MUST_BE_ONE actual=$($properties['max_parallel_matlab'].GetRawText())"
        }
        if ($properties['authorized_tasks'].ValueKind -ne [System.Text.Json.JsonValueKind]::Array) {
            throw 'GPU_EXECUTION_PLAN_AUTHORIZED_TASKS_INVALID expected_array'
        }
        $authorizedTasks = [System.Collections.Generic.List[object]]::new()
        foreach ($item in $properties['authorized_tasks'].EnumerateArray()) {
            if ($item.ValueKind -ne [System.Text.Json.JsonValueKind]::Object) {
                throw 'GPU_EXECUTION_PLAN_AUTHORIZED_TASKS_INVALID entries_must_be_objects'
            }
            $taskProperties = [System.Collections.Generic.Dictionary[string, System.Text.Json.JsonElement]]::new([System.StringComparer]::Ordinal)
            foreach ($field in $item.EnumerateObject()) {
                if ($taskProperties.ContainsKey($field.Name)) {
                    throw "GPU_EXECUTION_PLAN_AUTHORIZED_TASKS_INVALID duplicate_field=$($field.Name)"
                }
                $taskProperties.Add($field.Name, $field.Value.Clone())
            }
            $taskFields = @('run_id', 'task_identity_sha256')
            $missingTaskFields = @($taskFields | Where-Object { -not $taskProperties.ContainsKey($_) })
            $unknownTaskFields = @($taskProperties.Keys | Where-Object { $_ -notin $taskFields })
            if ($missingTaskFields.Count -gt 0 -or $unknownTaskFields.Count -gt 0) {
                throw "GPU_EXECUTION_PLAN_AUTHORIZED_TASKS_INVALID missing=$($missingTaskFields -join ',') unknown=$($unknownTaskFields -join ',')"
            }
            foreach ($field in $taskFields) {
                if ($taskProperties[$field].ValueKind -ne [System.Text.Json.JsonValueKind]::String) {
                    throw "GPU_EXECUTION_PLAN_AUTHORIZED_TASKS_INVALID field=$field expected=string"
                }
            }
            $taskRunId = $taskProperties['run_id'].GetString()
            $taskIdentity = $taskProperties['task_identity_sha256'].GetString()
            if ([string]::IsNullOrWhiteSpace($taskRunId) -or $taskIdentity -notmatch '^[0-9a-fA-F]{64}$') {
                throw 'GPU_EXECUTION_PLAN_AUTHORIZED_TASKS_INVALID run_id_or_identity_hash_invalid'
            }
            $authorizedTasks.Add([pscustomobject]@{ RunId = $taskRunId; TaskIdentitySha256 = $taskIdentity.ToLowerInvariant() })
        }
    } catch {
        if ($_.Exception.Message -match '^GPU_EXECUTION_PLAN_') { throw }
        throw "GPU_EXECUTION_PLAN_JSON_INVALID detail=$($_.Exception.Message)"
    } finally {
        if ($null -ne $document) { $document.Dispose() }
    }

    if ($properties['schema_version'].GetString() -cne 'frozen-sage-gpu-execution-plan-v2') {
        throw "GPU_EXECUTION_PLAN_SCHEMA_VERSION_UNSUPPORTED actual=$($properties['schema_version'].GetString())"
    }
    $executionMode = $properties['execution_mode'].GetString()
    if ($executionMode -cne 'GPU_STAGE2_QUALIFIED') {
        throw "GPU_EXECUTION_PLAN_UNKNOWN_EXECUTION_MODE actual=$executionMode"
    }
    if ($maxParallel -ne 1) {
        throw "GPU_EXECUTION_PLAN_MAX_PARALLEL_MUST_BE_ONE actual=$maxParallel"
    }

    $manifestHash = (Get-FileHash -LiteralPath $ManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $plannedManifestHash = $properties['source_manifest_sha256'].GetString()
    if ($plannedManifestHash -notmatch '^[0-9a-fA-F]{64}$' -or
        -not [string]::Equals($plannedManifestHash, $manifestHash, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "GPU_EXECUTION_PLAN_SOURCE_MANIFEST_SHA_MISMATCH expected=$manifestHash actual=$plannedManifestHash"
    }
    if ($authorizedTasks.Count -eq 0) {
        throw 'GPU_EXECUTION_PLAN_AUTHORIZED_TASKS_INVALID expected_nonempty_array'
    }
    $duplicateRunIds = @($authorizedTasks | Group-Object -Property RunId | Where-Object Count -gt 1 | ForEach-Object Name)
    if ($duplicateRunIds.Count -gt 0) {
        throw "GPU_EXECUTION_PLAN_DUPLICATE_AUTHORIZED_RUN_ID ids=$($duplicateRunIds -join ',')"
    }
    $manifestRows = @(Import-Csv -LiteralPath $ManifestPath -ErrorAction Stop)
    $requiredManifestFields = @('run_id', 'scene_id', 'prn', 'tracking_channel')
    if ($manifestRows.Count -eq 0) {
        throw 'GPU_EXECUTION_PLAN_MANIFEST_SCHEMA_INVALID empty_manifest'
    }
    $missingManifestFields = @($requiredManifestFields | Where-Object { $manifestRows[0].PSObject.Properties.Name -cnotcontains $_ })
    if ($missingManifestFields.Count -gt 0) {
        throw "GPU_EXECUTION_PLAN_MANIFEST_SCHEMA_INVALID missing=$($missingManifestFields -join ',')"
    }
    $authorizedMatches = @($authorizedTasks | Where-Object { [string]$_.RunId -ceq $RunId })
    if ($authorizedMatches.Count -ne 1) {
        throw "GPU_EXECUTION_PLAN_UNAUTHORIZED_RUN_ID run_id=$RunId matches=$($authorizedMatches.Count)"
    }
    $manifestRunIdCount = @($manifestRows | Where-Object { [string]$_.run_id -ceq $RunId }).Count
    if ($manifestRunIdCount -ne 1) {
        throw "GPU_EXECUTION_PLAN_MANIFEST_RUN_ID_NOT_UNIQUE run_id=$RunId count=$manifestRunIdCount"
    }
    $manifestRow = @($manifestRows | Where-Object { [string]$_.run_id -ceq $RunId })[0]
    $channel = 0
    if ([string]$manifestRow.scene_id -notmatch '^[A-Za-z0-9_-]+$' -or
        [string]$manifestRow.prn -notmatch '^G\d{2}$' -or
        -not [int]::TryParse([string]$manifestRow.tracking_channel, [ref]$channel) -or $channel -lt 0 -or $channel -gt 32) {
        throw "GPU_EXECUTION_PLAN_MANIFEST_TASK_IDENTITY_INVALID run_id=$RunId"
    }
    $manifestIdentity = Get-FrozenSageCanonicalTaskIdentitySha256 -RunId $RunId `
        -SceneId ([string]$manifestRow.scene_id) -PrnLabel ([string]$manifestRow.prn) -TrackingChannel $channel
    if (-not [string]::Equals($manifestIdentity, [string]$authorizedMatches[0].TaskIdentitySha256, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "GPU_EXECUTION_PLAN_TASK_IDENTITY_MISMATCH run_id=$RunId expected=$manifestIdentity actual=$($authorizedMatches[0].TaskIdentitySha256)"
    }

    $finalPlanHash = (Get-FileHash -LiteralPath $ExecutionPlanPath -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    if (-not [string]::Equals($finalPlanHash, $planHash, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'GPU_EXECUTION_PLAN_SHA_CHANGED_DURING_VALIDATION'
    }
    return [pscustomobject]@{
        ExecutionMode = $executionMode
        ExecutionPlanSha256 = $planHash
        SourceManifestSha256 = $manifestHash
        GpuSourceContractSha256 = $contractHash
        Resume = $false
        MaxParallelMatlab = 1
        AuthorizedRunIds = @($authorizedTasks | ForEach-Object { [string]$_.RunId })
        AuthorizedTasks = @($authorizedTasks.ToArray())
        TaskIdentitySha256 = $manifestIdentity
    }
}

function Get-FrozenSageGpuSourcePaths {
    $codeRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
    return [pscustomobject]@{
        CodeRoot = $codeRoot
        ProductionEntry = Join-Path $codeRoot 'scripts\sage_pipeline\run_nav_sage_pipeline_gpu_production.m'
        Candidate = Join-Path $codeRoot 'experiments\sage_gpu\full_task_candidate\run_nav_sage_pipeline_gpu_candidate.m'
        Probe = Join-Path $codeRoot 'experiments\sage_gpu\stage2_window_173_gpu_probe.m'
        Selector = Join-Path $codeRoot 'experiments\sage_gpu\selectSeparatedResidualCandidate.m'
        SourceContract = Join-Path $codeRoot $script:ProductionGpuSourceContractRelativePath
    }
}

function Assert-FrozenSageGpuSourceIdentity {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object]$ExecutionPlan,
        [Parameter(Mandatory)][string]$FrozenAuthorityPath,
        [Parameter(Mandatory)][string]$QualifiedCandidatePath,
        [Parameter(Mandatory)][string]$QualifiedProbePath,
        [Parameter(Mandatory)][string]$QualifiedSelectorPath,
        [Parameter(Mandatory)][string]$ProductionEntryPath,
        [Parameter(Mandatory)][string]$SourceContractPath
    )

    if ([string]$ExecutionPlan.ExecutionMode -cne 'GPU_STAGE2_QUALIFIED') {
        throw "GPU_SOURCE_IDENTITY_MISMATCH execution_mode=$($ExecutionPlan.ExecutionMode)"
    }
    $contractHash = (Get-FileHash -LiteralPath $SourceContractPath -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    if (-not [string]::Equals($contractHash, $script:ApprovedGpuSourceContractSha256, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "GPU_SOURCE_IDENTITY_MISMATCH field=source_contract_sha256 pinned=$script:ApprovedGpuSourceContractSha256 actual=$contractHash"
    }
    try {
        $contract = Get-Content -Raw -LiteralPath $SourceContractPath -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "GPU_SOURCE_IDENTITY_MISMATCH field=source_contract_json detail=$($_.Exception.Message)"
    }
    $required = @(
        'schema_version', 'frozen_authority_sha256', 'qualified_candidate_sha256',
        'qualified_probe_sha256', 'qualified_selector_sha256', 'production_entry_sha256'
    )
    $missing = @($required | Where-Object { $contract.PSObject.Properties.Name -cnotcontains $_ })
    if ($missing.Count -gt 0 -or $contract.schema_version -cne 'frozen-sage-production-gpu-source-contract-v1') {
        throw "GPU_SOURCE_IDENTITY_MISMATCH field=source_contract_schema missing=$($missing -join ',') schema=$($contract.schema_version)"
    }

    $identityFiles = @(
        @{ Field = 'frozen_authority_sha256'; Path = $FrozenAuthorityPath; Pin = $script:FrozenSourceSha256 },
        @{ Field = 'qualified_candidate_sha256'; Path = $QualifiedCandidatePath; Pin = $script:QualifiedCandidateSha256 },
        @{ Field = 'qualified_probe_sha256'; Path = $QualifiedProbePath; Pin = $script:QualifiedProbeSha256 },
        @{ Field = 'qualified_selector_sha256'; Path = $QualifiedSelectorPath; Pin = $script:QualifiedSelectorSha256 },
        @{ Field = 'production_entry_sha256'; Path = $ProductionEntryPath; Pin = $script:ApprovedGpuProductionEntrySha256 }
    )
    $actual = [ordered]@{}
    foreach ($item in $identityFiles) {
        if (-not (Test-Path -LiteralPath $item.Path -PathType Leaf)) {
            throw "GPU_SOURCE_IDENTITY_MISMATCH field=$($item.Field) source_missing=$($item.Path)"
        }
        $actualHash = (Get-FileHash -LiteralPath $item.Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
        $contractHashValue = [string]$contract.($item.Field)
        if ($contractHashValue -notmatch '^[0-9a-fA-F]{64}$' -or
            -not [string]::Equals($actualHash, $contractHashValue, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "GPU_SOURCE_IDENTITY_MISMATCH field=$($item.Field) contract=$contractHashValue actual=$actualHash"
        }
        if (-not [string]::IsNullOrEmpty([string]$item.Pin) -and
            -not [string]::Equals($actualHash, [string]$item.Pin, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "GPU_SOURCE_IDENTITY_MISMATCH field=$($item.Field) pinned=$($item.Pin) actual=$actualHash"
        }
        $actual[$item.Field] = $actualHash
    }
    return [pscustomobject]@{
        CodeRoot = [System.IO.Path]::GetFullPath((Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $ProductionEntryPath))))
        ProductionEntryPath = [System.IO.Path]::GetFullPath($ProductionEntryPath)
        SelectorPath = [System.IO.Path]::GetFullPath($QualifiedSelectorPath)
        SourceContractPath = [System.IO.Path]::GetFullPath($SourceContractPath)
        SourceContractSha256 = $contractHash
        FrozenAuthoritySha256 = $actual.frozen_authority_sha256
        QualifiedCandidateSha256 = $actual.qualified_candidate_sha256
        QualifiedProbeSha256 = $actual.qualified_probe_sha256
        QualifiedSelectorSha256 = $actual.qualified_selector_sha256
        ProductionEntrySha256 = $actual.production_entry_sha256
    }
}

function Assert-GpuMatlabAvailabilitySmoke {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][int]$ExitCode,
        [Parameter(Mandatory)][AllowEmptyString()][string]$Stdout
    )
    $markerPresent = $Stdout.Contains('GPU_PREFLIGHT_OK')
    $deviceName = @($Stdout -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object {
        -not [string]::IsNullOrWhiteSpace($_) -and $_ -ne 'GPU_PREFLIGHT_OK'
    } | Select-Object -Last 1) | Select-Object -First 1
    if ($ExitCode -ne 0 -or -not $markerPresent -or [string]::IsNullOrWhiteSpace([string]$deviceName)) {
        throw "GPU_NOT_AVAILABLE exit_code=$ExitCode marker_present=$markerPresent device_name_present=$(-not [string]::IsNullOrWhiteSpace([string]$deviceName))"
    }
    return [string]$deviceName
}

function Get-GpuMatlabAvailabilityExpression {
    return "assert(canUseGPU);d=gpuDevice();disp(d.Name);disp('GPU_PREFLIGHT_OK')"
}

function ConvertTo-MatlabCharLiteral {
    param([Parameter(Mandatory)][string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function Get-GpuSageMatlabExpression {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$SceneId,
        [Parameter(Mandatory)][int]$Prn,
        [Parameter(Mandatory)][int]$TrackingChannel,
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][string]$RunId,
        [Parameter(Mandatory)][string]$ExecutionPlanPath,
        [Parameter(Mandatory)][string]$ProductionEntryPath,
        [Parameter(Mandatory)][string]$SelectorPath
    )
    if ($SceneId -notmatch '^[A-Za-z0-9_-]+$' -or $Prn -lt 1 -or $Prn -gt 32 -or
        $TrackingChannel -lt 0 -or $TrackingChannel -gt 32 -or
        $RunId -notmatch '^[A-Za-z0-9_.-]+$' -or
        [string]::IsNullOrWhiteSpace($ExecutionPlanPath)) {
        throw 'GPU_MATLAB_INVOCATION_IDENTITY_INVALID'
    }
    $entryPath = [System.IO.Path]::GetFullPath($ProductionEntryPath).Replace('\', '/')
    $selectorPath = [System.IO.Path]::GetFullPath($SelectorPath).Replace('\', '/')
    $entryDirectory = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetFullPath($ProductionEntryPath)).Replace('\', '/')
    $selectorDirectory = [System.IO.Path]::GetDirectoryName([System.IO.Path]::GetFullPath($SelectorPath)).Replace('\', '/')
    $projectRoot = [System.IO.Path]::GetFullPath($ProjectRoot).Replace('\', '/')
    $planPath = [System.IO.Path]::GetFullPath($ExecutionPlanPath).Replace('\', '/')
    $matlabEntry = ConvertTo-MatlabCharLiteral $entryPath
    $matlabSelector = ConvertTo-MatlabCharLiteral $selectorPath
    $matlabEntryDirectory = ConvertTo-MatlabCharLiteral $entryDirectory
    $matlabSelectorDirectory = ConvertTo-MatlabCharLiteral $selectorDirectory
    $matlabScene = ConvertTo-MatlabCharLiteral $SceneId
    $matlabProjectRoot = ConvertTo-MatlabCharLiteral $projectRoot
    $matlabRunId = ConvertTo-MatlabCharLiteral $RunId
    $matlabPlanPath = ConvertTo-MatlabCharLiteral $planPath
    return "addpath($matlabEntryDirectory,'-begin');addpath($matlabSelectorDirectory,'-begin');assert(strcmpi(strrep(which('run_nav_sage_pipeline_gpu_production'),'\','/'),$matlabEntry),'GPU_PRODUCTION_ENTRY_RESOLUTION_MISMATCH');assert(strcmpi(strrep(which('selectSeparatedResidualCandidate'),'\','/'),$matlabSelector),'GPU_SELECTOR_RESOLUTION_MISMATCH');run_nav_sage_pipeline_gpu_production($matlabScene,$Prn,'TrackingChannel',$TrackingChannel,'ProjectRoot',$matlabProjectRoot,'Resume',false,'RunId',$matlabRunId,'ExecutionPlanPath',$matlabPlanPath)"
}

function Assert-FrozenSageManifestRow {
    param(
        [Parameter(Mandatory)][object]$Row,
        [Parameter(Mandatory)][string]$ExpectedRunId
    )

    if (-not [string]::Equals([string]$Row.run_id, $ExpectedRunId, [System.StringComparison]::Ordinal)) {
        throw "MANIFEST_ROW_MISMATCH field=run_id expected=$ExpectedRunId actual=$($Row.run_id)"
    }
    if ([string]$Row.scene_id -notmatch '^[A-Za-z0-9_-]+$') {
        throw "MANIFEST_ROW_INVALID_SCENE scene_id=$($Row.scene_id)"
    }
    if ([string]$Row.prn -notmatch '^G\d{2}$') {
        throw "MANIFEST_ROW_INVALID_PRN prn=$($Row.prn)"
    }
    $channel = 0
    if (-not [int]::TryParse([string]$Row.tracking_channel, [ref]$channel) -or $channel -lt 0 -or $channel -gt 32) {
        throw "MANIFEST_ROW_INVALID_CHANNEL channel=$($Row.tracking_channel)"
    }
    if ([string]$Row.mapping_warning -notin @('NONE', 'NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING')) {
        throw "MANIFEST_ROW_UNSUPPORTED_MAPPING_WARNING warning=$($Row.mapping_warning)"
    }
    if (-not [string]::Equals([string]$Row.frozen_sage_sha256, $script:FrozenSourceSha256, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "MANIFEST_ROW_MISMATCH field=frozen_sage_sha256 expected=$script:FrozenSourceSha256 actual=$($Row.frozen_sage_sha256)"
    }
    if (-not [string]::Equals([string]$Row.resume, 'false', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "MANIFEST_ROW_MISMATCH field=resume expected=false actual=$($Row.resume)"
    }
    if (-not [string]::Equals([string]$Row.execution_status, 'NOT_STARTED', [System.StringComparison]::Ordinal)) {
        throw "MANIFEST_ROW_MISMATCH field=execution_status expected=NOT_STARTED actual=$($Row.execution_status)"
    }

    $expectedNamespace = Join-Path 'scenes' (Join-Path ([string]$Row.scene_id) (
        Join-Path $script:FrozenNamespaceRoot ("{0}_ch{1}" -f [string]$Row.prn, $channel)))
    $actualNamespace = ([string]$Row.output_namespace).Replace('/', '\')
    if (-not [string]::Equals($actualNamespace, $expectedNamespace.Replace('/', '\'), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "MANIFEST_ROW_MISMATCH field=output_namespace expected=$expectedNamespace actual=$actualNamespace"
    }
    return $true
}

function Assert-RequiredInputFiles {
    param([Parameter(Mandatory)][string[]]$Paths)

    $missing = @($Paths | Where-Object { -not (Test-Path -LiteralPath $_ -PathType Leaf) })
    if ($missing.Count -gt 0) {
        throw ('REQUIRED_INPUT_MISSING ' + ($missing -join '; '))
    }
    return $true
}

function Assert-ApprovedExecutionEnvironment {
    param(
        [Parameter(Mandatory)][string]$Identity,
        [Parameter(Mandatory)][string]$PowerShellVersion,
        [Parameter(Mandatory)][bool]$IsAdministrator
    )

    if ($Identity -match '(?i)codexsandboxoffline') {
        throw "CODEX_SANDBOX_IDENTITY_DENIED identity=$Identity"
    }
    if (-not [string]::Equals($Identity, 'TJ-CHANNEL\Jing_', [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "UNAPPROVED_WINDOWS_IDENTITY expected=TJ-CHANNEL\Jing_ actual=$Identity"
    }
    if ([version]$PowerShellVersion -lt [version]'7.0') {
        throw "POWERSHELL_7_REQUIRED actual=$PowerShellVersion"
    }
    if ($IsAdministrator) {
        throw 'ADMINISTRATOR_SESSION_DENIED'
    }
    return $true
}

function Assert-OutputNamespacesAbsent {
    param(
        [Parameter(Mandatory)][string]$StagingPath,
        [Parameter(Mandatory)][string]$FinalPath
    )

    foreach ($path in @($StagingPath, $FinalPath)) {
        if (Test-Path -LiteralPath $path) {
            throw "OUTPUT_NAMESPACE_ALREADY_EXISTS path=$path"
        }
    }
    if (-not [string]::Equals((Split-Path -Qualifier $StagingPath), (Split-Path -Qualifier $FinalPath), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "OUTPUT_PATHS_NOT_ON_SAME_VOLUME staging=$StagingPath final=$FinalPath"
    }
    return $true
}

function Get-RequiredStageArtifactNames {
    return @(
        'stage0_nav_catalog.mat',
        'stage0_valid_symbols.csv',
        'stage0_valid_40ms_windows.csv',
        'stage1_nav_fast_scan.mat',
        'stage1_nav_fast_scan.csv',
        'stage2_nav_sage_L1_L4.mat',
        'stage2_model_orders.csv',
        'stage2_selected_windows.csv',
        'stage2_selected_paths.csv',
        'stage3_nav_persistence.mat',
        'stage3_persistence.csv',
        'stage3_reliable_centers.csv',
        'stage4_nav_joint_100ms.mat',
        'stage4_joint_summary.csv',
        'stage4_joint_paths.csv'
    )
}

function Get-FrozenSageTaskRunnerLockPath {
    param(
        [Parameter(Mandatory)][string]$ExecutionLogParent,
        [Parameter(Mandatory)][string]$RunId
    )
    $safeRunId = [regex]::Replace($RunId, '[^A-Za-z0-9_-]', '_')
    if ([string]::IsNullOrWhiteSpace($safeRunId)) { throw 'RUN_ID_REQUIRED_FOR_TASK_LOCK' }
    return Join-Path $ExecutionLogParent ('.windows_runner_active_{0}.lock' -f $safeRunId)
}

function Get-FrozenSageGpuGlobalLockPath {
    param([Parameter(Mandatory)][string]$ExecutionLogParent)
    return Join-Path $ExecutionLogParent '.gpu_stage2_qualified_active.lock'
}

function New-FrozenSageRunnerLockPayload {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object]$Preflight,
        [Parameter(Mandatory)][object]$ExecutionPlan
    )

    $payload = [ordered]@{
        run_id = [string]$Preflight.RunId
        scene_id = [string]$Preflight.SceneId
        prn = [int]$Preflight.Prn
        tracking_channel = [int]$Preflight.TrackingChannel
        mapping_warning = [string]$Preflight.MappingWarning
        resume = $false
    }
    if ([string]$Preflight.ExecutionMode -eq 'GPU_STAGE2_QUALIFIED') {
        $payload.execution_mode = 'GPU_STAGE2_QUALIFIED'
        $payload.execution_plan_sha256 = [string]$ExecutionPlan.ExecutionPlanSha256
        $payload.gpu_source_contract_sha256 = $script:ApprovedGpuSourceContractSha256
        $payload.production_gpu_entry_sha256 = $script:ApprovedGpuProductionEntrySha256
        $payload.frozen_authority_sha256 = $script:FrozenSourceSha256
        $payload.qualified_candidate_sha256 = $script:QualifiedCandidateSha256
        $payload.qualified_selector_sha256 = $script:QualifiedSelectorSha256
        $payload.qualified_probe_sha256 = $script:QualifiedProbeSha256
    }
    $payload.windows_identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $payload.powershell_version = $PSVersionTable.PSVersion.ToString()
    $payload.process_id = $PID
    $payload.started_utc = [System.DateTimeOffset]::UtcNow.ToString('o')
    return $payload
}

function New-FrozenSageGpuGlobalLock {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$ExecutionMode,
        [Parameter(Mandatory)][string]$LockPath,
        [Parameter(Mandatory)][object]$Payload
    )

    if ($ExecutionMode -ceq 'CPU_FROZEN') { return $null }
    if ($ExecutionMode -cne 'GPU_STAGE2_QUALIFIED') { throw "EXECUTION_MODE_UNSUPPORTED mode=$ExecutionMode" }
    $requiredFields = @('run_id', 'scene_id', 'prn', 'tracking_channel', 'execution_mode', 'execution_plan_sha256', 'process_id', 'started_utc')
    $payloadFields = if ($Payload -is [System.Collections.IDictionary]) { @($Payload.Keys | ForEach-Object { [string]$_ }) } else { @($Payload.PSObject.Properties.Name) }
    $missing = @($requiredFields | Where-Object { $payloadFields -cnotcontains $_ })
    if ($missing.Count -gt 0 -or [string]$Payload.execution_mode -cne 'GPU_STAGE2_QUALIFIED' -or
        [string]$Payload.execution_plan_sha256 -notmatch '^[0-9a-fA-F]{64}$') {
        throw "GPU_GLOBAL_LOCK_PAYLOAD_INVALID missing=$($missing -join ',')"
    }
    try {
        $stream = [System.IO.File]::Open($LockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
    } catch [System.IO.IOException] {
        throw "GPU_GLOBAL_LOCK_PRESENT path=$LockPath"
    }
    try {
        $writer = [System.IO.StreamWriter]::new($stream, [System.Text.UTF8Encoding]::new($false), 1024, $true)
        $writer.Write(($Payload | ConvertTo-Json -Depth 6))
        $writer.Flush()
        $writer.Dispose()
        return [pscustomobject]@{ Path = $LockPath; Stream = $stream; Payload = $Payload }
    } catch {
        $stream.Dispose()
        throw
    }
}

function Move-FrozenSageGpuGlobalLockToArchive {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$LockPath,
        [Parameter(Mandatory)][string]$DestinationPath,
        [Parameter(Mandatory)][object]$ExpectedPayload
    )

    if (-not (Test-Path -LiteralPath $LockPath -PathType Leaf)) { throw "OWNED_GPU_GLOBAL_LOCK_MISSING path=$LockPath" }
    if (Test-Path -LiteralPath $DestinationPath) { throw "GPU_GLOBAL_LOCK_ARCHIVE_COLLISION path=$DestinationPath" }
    $actualText = Get-Content -Raw -LiteralPath $LockPath -ErrorAction Stop
    $actualDocument = [System.Text.Json.JsonDocument]::Parse($actualText)
    try {
        $actual = $actualDocument.RootElement
        foreach ($field in @('run_id', 'scene_id', 'prn', 'tracking_channel', 'execution_mode', 'execution_plan_sha256', 'process_id', 'started_utc')) {
            $actualElement = [System.Text.Json.JsonElement]::new()
            if (-not $actual.TryGetProperty($field, [ref]$actualElement)) {
                throw "GPU_GLOBAL_LOCK_OWNERSHIP_MISMATCH field=$field"
            }
            $actualValue = if ($actualElement.ValueKind -eq [System.Text.Json.JsonValueKind]::String) {
                $actualElement.GetString()
            } else {
                $actualElement.ToString()
            }
            if ($field -eq 'started_utc') {
                $actualTime = [System.DateTimeOffset]::Parse($actualValue, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
                $expectedTime = ([System.DateTimeOffset]$ExpectedPayload.$field).ToUniversalTime()
                $matches = $actualTime.UtcDateTime.Ticks -eq $expectedTime.UtcDateTime.Ticks
            } else {
                $matches = [string]::Equals([string]$actualValue, [string]$ExpectedPayload.$field, [System.StringComparison]::Ordinal)
            }
            if (-not $matches) { throw "GPU_GLOBAL_LOCK_OWNERSHIP_MISMATCH field=$field" }
        }
    } finally {
        $actualDocument.Dispose()
    }
    $expectedHash = (Get-FileHash -LiteralPath $LockPath -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    $destinationParent = Split-Path -Parent $DestinationPath
    if (-not (Test-Path -LiteralPath $destinationParent -PathType Container)) {
        throw "GPU_GLOBAL_LOCK_ARCHIVE_PARENT_MISSING path=$destinationParent"
    }
    Move-Item -LiteralPath $LockPath -Destination $DestinationPath -ErrorAction Stop
    if ((Test-Path -LiteralPath $LockPath) -or -not (Test-Path -LiteralPath $DestinationPath -PathType Leaf)) {
        throw 'GPU_GLOBAL_LOCK_ARCHIVE_MOVE_UNVERIFIED'
    }
    $actualHash = (Get-FileHash -LiteralPath $DestinationPath -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    if ($actualHash -cne $expectedHash) { throw 'GPU_GLOBAL_LOCK_ARCHIVE_HASH_MISMATCH' }
    return [pscustomobject]@{ Path = $DestinationPath; Sha256 = $actualHash; MoveMethod = 'Move-Item' }
}

function Assert-StageOutputsComplete {
    param([Parameter(Mandatory)][string]$OutputPath)

    if (-not (Test-Path -LiteralPath $OutputPath -PathType Container)) {
        throw "SAGE_OUTPUT_DIRECTORY_MISSING path=$OutputPath"
    }
    $missingOrEmpty = foreach ($name in (Get-RequiredStageArtifactNames)) {
        $path = Join-Path $OutputPath $name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            $name
            continue
        }
        if ((Get-Item -LiteralPath $path).Length -le 0) {
            $name
        }
    }
    if (@($missingOrEmpty).Count -gt 0) {
        throw ('STAGE0_STAGE4_OUTPUT_INCOMPLETE missing_or_empty=' + (@($missingOrEmpty) -join ';'))
    }
    return $true
}

function Get-FrozenSageStage0FailureReason {
    param([Parameter(Mandatory)][string]$StagingPath)

    $symbolsPath = Join-Path $StagingPath 'stage0_valid_symbols.csv'
    $windowsPath = Join-Path $StagingPath 'stage0_valid_40ms_windows.csv'
    if (-not (Test-Path -LiteralPath $symbolsPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $windowsPath -PathType Leaf)) {
        return $null
    }
    try {
        $symbols = @(Import-Csv -LiteralPath $symbolsPath -ErrorAction Stop)
        $windows = @(Import-Csv -LiteralPath $windowsPath -ErrorAction Stop)
    } catch {
        return $null
    }
    if ($symbols.Count -eq 0) {
        return 'STAGE0_NO_VALID_NAV_SYMBOLS'
    }
    if ($windows.Count -eq 0) {
        return 'STAGE0_NO_VALID_40MS_WINDOWS'
    }
    return $null
}

function Assert-FrozenSageStage0Ready {
    param([Parameter(Mandatory)][string]$StagingPath)

    $failureReason = Get-FrozenSageStage0FailureReason -StagingPath $StagingPath
    if ($null -ne $failureReason) {
        throw "$failureReason scene-specific Stage0 catalog is empty; staging output remains available for classified handling."
    }
    return $true
}

function Get-FrozenSageRawIqMetadata {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][long]$ExpectedSizeBytes
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "RAW_IQ_MISSING path=$Path"
    }
    if ($ExpectedSizeBytes -le 0) {
        throw "RAW_IQ_AUDIT_SIZE_INVALID expected_size_bytes=$ExpectedSizeBytes"
    }
    $rawInfo = Get-Item -LiteralPath $Path
    if ($rawInfo.Length -le 0) {
        throw "RAW_IQ_EMPTY path=$Path"
    }
    if ([long]$rawInfo.Length -ne $ExpectedSizeBytes) {
        throw "RAW_IQ_SIZE_MISMATCH audit=$ExpectedSizeBytes actual=$($rawInfo.Length) path=$Path"
    }
    return [pscustomobject]@{
        RawIqSizeBytes = [long]$rawInfo.Length
        RawIqSha256 = ''
        RawIqSha256Status = 'NOT_RECOMPUTED'
    }
}

function Get-FrozenSageMatlabExpression {
    param(
        [Parameter(Mandatory)][string]$SceneId,
        [Parameter(Mandatory)][int]$Prn,
        [Parameter(Mandatory)][int]$TrackingChannel,
        [Parameter(Mandatory)][string]$ProjectRoot
    )

    if ($SceneId -notmatch '^[A-Za-z0-9_-]+$' -or $Prn -lt 1 -or $Prn -gt 32 -or $TrackingChannel -lt 0 -or $TrackingChannel -gt 32) {
        throw "MATLAB_INVOCATION_IDENTITY_INVALID scene=$SceneId prn=$Prn channel=$TrackingChannel"
    }
    $matlabRoot = $ProjectRoot.Replace('\', '/')
    return "run_nav_sage_pipeline('$SceneId',$Prn,'TrackingChannel',$TrackingChannel,'ProjectRoot','$matlabRoot','Resume',false)"
}

function Assert-MatlabStartupSmoke {
    param(
        [Parameter(Mandatory)][int]$ExitCode,
        [Parameter(Mandatory)][string]$Output
    )

    if ($ExitCode -ne 0 -or -not $Output.Contains($script:StartupMarker)) {
        throw "MATLAB_STARTUP_SMOKE_FAILED exit_code=$ExitCode marker_present=$($Output.Contains($script:StartupMarker))"
    }
    return $true
}

function Assert-MatlabArgumentTransportSmoke {
    param(
        [Parameter(Mandatory)][int]$ExitCode,
        [Parameter(Mandatory)][string]$Stdout
    )

    if ($ExitCode -ne 0 -or -not $Stdout.Contains($script:TransportMarker)) {
        throw "MATLAB_ARGUMENT_TRANSPORT_FAILED exit_code=$ExitCode stdout_marker_present=$($Stdout.Contains($script:TransportMarker))"
    }
    return $true
}

function New-FrozenMatlabProcessStartInfo {
    param(
        [Parameter(Mandatory)][string]$MatlabPath,
        [Parameter(Mandatory)][string]$Expression
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $MatlabPath
    $startInfo.WorkingDirectory = (Get-Location).Path
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    [void]$startInfo.ArgumentList.Add('-batch')
    [void]$startInfo.ArgumentList.Add($Expression)
    return $startInfo
}

function Move-FrozenRunnerLockToFailureReceipt {
    param(
        [Parameter(Mandatory)][string]$GlobalLockPath,
        [Parameter(Mandatory)][string]$ReceiptRoot,
        [Parameter(Mandatory)][object]$LockPayload,
        [Parameter(Mandatory)][string]$FailureReason,
        [Parameter(Mandatory)][string]$ErrorMessage,
        [object]$MatlabProcessState,
        [AllowNull()][string]$GpuGlobalLockPath = $null,
        [object]$GpuGlobalLockPayload = $null
    )

    if (-not (Test-Path -LiteralPath $GlobalLockPath -PathType Leaf)) {
        throw "OWNED_RUNNER_LOCK_MISSING path=$GlobalLockPath"
    }
    $currentLockText = Get-Content -Raw -LiteralPath $GlobalLockPath -ErrorAction Stop
    $currentLockDocument = [System.Text.Json.JsonDocument]::Parse($currentLockText)
    $lockStartedUtc = $null
    try {
        $currentLock = $currentLockDocument.RootElement
        foreach ($field in @('run_id', 'scene_id', 'prn', 'tracking_channel', 'process_id', 'started_utc')) {
            $actualElement = $currentLock.GetProperty($field)
            $actualValue = if ($actualElement.ValueKind -eq [System.Text.Json.JsonValueKind]::String) {
                $actualElement.GetString()
            } else {
                $actualElement.ToString()
            }
            if ($field -eq 'started_utc') {
                $expectedTime = ([System.DateTimeOffset]$LockPayload.$field).ToUniversalTime()
                $actualTime = [System.DateTimeOffset]::Parse($actualValue, [System.Globalization.CultureInfo]::InvariantCulture, [System.Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
                if ($actualTime.UtcDateTime.Ticks -ne $expectedTime.UtcDateTime.Ticks) {
                    throw "RUNNER_LOCK_OWNERSHIP_MISMATCH field=$field expected=$expectedTime actual=$actualValue"
                }
                $lockStartedUtc = $actualValue
            } elseif (-not [string]::Equals([string]$actualValue, [string]$LockPayload.$field, [System.StringComparison]::Ordinal)) {
                throw "RUNNER_LOCK_OWNERSHIP_MISMATCH field=$field expected=$($LockPayload.$field) actual=$actualValue"
            }
        }
    } finally {
        $currentLockDocument.Dispose()
    }
    if (-not (Test-Path -LiteralPath $ReceiptRoot -PathType Container)) {
        [void](New-Item -ItemType Directory -Path $ReceiptRoot -ErrorAction Stop)
    }

    $timestamp = [System.DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
    $receiptDirectory = Join-Path $ReceiptRoot ("{0}_controlled_failure_{1}" -f [string]$LockPayload.run_id, $timestamp)
    if (Test-Path -LiteralPath $receiptDirectory) {
        throw "FAILURE_RECEIPT_COLLISION path=$receiptDirectory"
    }
    [void](New-Item -ItemType Directory -Path $receiptDirectory -ErrorAction Stop)

    $archivedLockPath = Join-Path $receiptDirectory 'windows_runner_global_lock.json'
    $archivedGpuLockPath = Join-Path $receiptDirectory 'gpu_stage2_global_lock_receipt.json'
    if ($null -ne $GpuGlobalLockPayload -and
        ([string]::IsNullOrWhiteSpace($GpuGlobalLockPath) -or -not (Test-Path -LiteralPath $GpuGlobalLockPath -PathType Leaf))) {
        throw 'OWNED_GPU_GLOBAL_LOCK_MISSING'
    }
    $lockHash = (Get-FileHash -LiteralPath $GlobalLockPath -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    if (Test-Path -LiteralPath $archivedLockPath) {
        throw "FAILURE_LOCK_DESTINATION_COLLISION path=$archivedLockPath"
    }
    if ($null -ne $GpuGlobalLockPayload -and (Test-Path -LiteralPath $archivedGpuLockPath)) {
        throw "GPU_GLOBAL_LOCK_ARCHIVE_COLLISION path=$archivedGpuLockPath"
    }
    Move-Item -LiteralPath $GlobalLockPath -Destination $archivedLockPath -ErrorAction Stop
    $gpuLockArchive = $null
    if ($null -ne $GpuGlobalLockPayload) {
        if ([string]::IsNullOrWhiteSpace($GpuGlobalLockPath)) { throw 'OWNED_GPU_GLOBAL_LOCK_PATH_MISSING' }
        $gpuLockArchive = Move-FrozenSageGpuGlobalLockToArchive `
            -LockPath $GpuGlobalLockPath -DestinationPath $archivedGpuLockPath -ExpectedPayload $GpuGlobalLockPayload
    }
    $archivedUtc = [System.DateTimeOffset]::UtcNow.ToString('o')
    $mappingWarning = ''
    if ($LockPayload.PSObject.Properties.Name -contains 'mapping_warning') {
        $mappingWarning = [string]$LockPayload.mapping_warning
    }
    $failureReceipt = [ordered]@{
        failure_reason = $FailureReason
        error_message = $ErrorMessage
        run_id = [string]$LockPayload.run_id
        scene_id = [string]$LockPayload.scene_id
        prn = [int]$LockPayload.prn
        tracking_channel = [int]$LockPayload.tracking_channel
        mapping_warning = $mappingWarning
        old_pid = [int]$LockPayload.process_id
        matlab_started = [bool]($null -ne $MatlabProcessState -and $MatlabProcessState.Started)
        matlab_process_id = if ($null -ne $MatlabProcessState) { $MatlabProcessState.ProcessId } else { $null }
        matlab_exit_code = if ($null -ne $MatlabProcessState) { $MatlabProcessState.ExitCode } else { $null }
        matlab_process_ended = [bool]($null -ne $MatlabProcessState -and $MatlabProcessState.ProcessEnded)
        matlab_start_utc = if ($null -ne $MatlabProcessState) { $MatlabProcessState.StartedUtc } else { $null }
        matlab_end_utc = if ($null -ne $MatlabProcessState) { $MatlabProcessState.EndedUtc } else { $null }
        lock_started_utc = [string]$lockStartedUtc
        archived_utc = $archivedUtc
        source_path = $GlobalLockPath
        destination_path = $archivedLockPath
        move_method = 'Move-Item'
        lock_sha256 = $lockHash
    }
    foreach ($field in @(
        'execution_mode', 'execution_plan_sha256', 'gpu_source_contract_sha256',
        'production_gpu_entry_sha256', 'frozen_authority_sha256',
        'qualified_candidate_sha256', 'qualified_selector_sha256', 'qualified_probe_sha256'
    )) {
        if ($LockPayload.PSObject.Properties.Name -contains $field) {
            $failureReceipt[$field] = $LockPayload.$field
        }
    }
    if ($null -ne $gpuLockArchive) {
        $failureReceipt['gpu_global_lock_receipt_path'] = $gpuLockArchive.Path
        $failureReceipt['gpu_global_lock_receipt_sha256'] = $gpuLockArchive.Sha256
    }
    $receiptPath = Join-Path $receiptDirectory 'failure_receipt.json'
    $json = $failureReceipt | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText($receiptPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    return [pscustomobject]@{
        LockPath = $archivedLockPath
        ReceiptPath = $receiptPath
        GpuGlobalLockReceiptPath = if ($null -ne $gpuLockArchive) { $gpuLockArchive.Path } else { $null }
    }
}

function Get-DirectoryMetrics {
    param([Parameter(Mandatory)][string]$Path)

    $files = @(Get-ChildItem -LiteralPath $Path -File -Force -Recurse -ErrorAction Stop)
    $sum = ($files | Measure-Object -Property Length -Sum).Sum
    if ($null -eq $sum) {
        $sum = 0
    }
    return [pscustomobject]@{
        FileCount = [int]$files.Count
        Bytes = [long]$sum
    }
}

function Assert-FrozenSageGpuExecutionProvenance {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Directory,
        [Parameter(Mandatory)][object]$Context
    )

    $attemptPath = Join-Path $Directory 'gpu_execution_attempt.json'
    $runtimePath = Join-Path $Directory 'gpu_execution_provenance.json'
    foreach ($path in @($attemptPath, $runtimePath)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "GPU_EXECUTION_PROVENANCE_MISSING path=$path"
        }
    }
    try {
        $attempt = Get-Content -Raw -LiteralPath $attemptPath -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        $runtime = Get-Content -Raw -LiteralPath $runtimePath -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "GPU_EXECUTION_PROVENANCE_INVALID detail=$($_.Exception.Message)"
    }

    $expectedRunId = [string]$Context.RunId
    $expectedScene = [string]$Context.SceneId
    $expectedPrn = 'G{0:D2}' -f [int]$Context.Prn
    $expectedChannel = [int]$Context.TrackingChannel
    $expectedPlanSha = [string]$Context.ExecutionPlanSha256
    if ([string]::IsNullOrWhiteSpace($expectedRunId) -or
        $expectedPlanSha -notmatch '^[0-9a-fA-F]{64}$') {
        throw 'GPU_EXECUTION_PROVENANCE_EXPECTED_IDENTITY_INVALID'
    }

    $attemptFields = @(
        'run_id', 'scene_id', 'prn', 'tracking_channel', 'execution_mode',
        'execution_plan_sha256', 'gpu_source_contract_sha256',
        'frozen_authority_sha256', 'qualified_candidate_sha256',
        'qualified_probe_sha256', 'qualified_selector_sha256', 'resume',
        'attempt_timestamp', 'attempt_status'
    )
    $runtimeFields = @(
        'run_id', 'execution_mode', 'execution_plan_sha256',
        'gpu_source_contract_sha256', 'production_gpu_entry_sha256',
        'frozen_authority_sha256', 'qualified_candidate_sha256',
        'qualified_probe_sha256', 'qualified_selector_sha256',
        'gpu_identity', 'matlab_version', 'resume', 'execution_timestamp'
    )
    foreach ($field in $attemptFields) {
        if ($attempt.PSObject.Properties.Name -cnotcontains $field) {
            throw "GPU_ATTEMPT_PROVENANCE_SCHEMA_INVALID missing=$field"
        }
    }
    foreach ($field in $runtimeFields) {
        if ($runtime.PSObject.Properties.Name -cnotcontains $field) {
            throw "GPU_RUNTIME_PROVENANCE_SCHEMA_INVALID missing=$field"
        }
    }

    foreach ($record in @($attempt, $runtime)) {
        if ([string]$record.run_id -cne $expectedRunId -or
            [string]$record.execution_mode -cne 'GPU_STAGE2_QUALIFIED' -or
            [string]$record.execution_plan_sha256 -cne $expectedPlanSha -or
            [bool]$record.resume) {
            throw 'GPU_EXECUTION_PROVENANCE_IDENTITY_MISMATCH'
        }
        foreach ($fieldPin in @(
            @{ Field = 'gpu_source_contract_sha256'; Pin = $script:ApprovedGpuSourceContractSha256 },
            @{ Field = 'frozen_authority_sha256'; Pin = $script:FrozenSourceSha256 },
            @{ Field = 'qualified_candidate_sha256'; Pin = $script:QualifiedCandidateSha256 },
            @{ Field = 'qualified_probe_sha256'; Pin = $script:QualifiedProbeSha256 },
            @{ Field = 'qualified_selector_sha256'; Pin = $script:QualifiedSelectorSha256 }
        )) {
            if ([string]$record.($fieldPin.Field) -cne [string]$fieldPin.Pin) {
                throw "GPU_EXECUTION_PROVENANCE_SOURCE_MISMATCH field=$($fieldPin.Field)"
            }
        }
    }
    if ([string]$attempt.scene_id -cne $expectedScene -or
        [string]$attempt.prn -cne $expectedPrn -or
        [int]$attempt.tracking_channel -ne $expectedChannel -or
        [string]$attempt.attempt_status -cne 'AUTHORIZED' -or
        [string]$runtime.production_gpu_entry_sha256 -cne $script:ApprovedGpuProductionEntrySha256 -or
        [string]::IsNullOrWhiteSpace([string]$runtime.gpu_identity) -or
        [string]::IsNullOrWhiteSpace([string]$runtime.matlab_version)) {
        throw 'GPU_EXECUTION_PROVENANCE_IDENTITY_MISMATCH'
    }
    $attemptTime = [DateTimeOffset]::MinValue
    $runtimeTime = [DateTimeOffset]::MinValue
    if (-not [DateTimeOffset]::TryParse([string]$attempt.attempt_timestamp, [ref]$attemptTime) -or
        -not [DateTimeOffset]::TryParse([string]$runtime.execution_timestamp, [ref]$runtimeTime)) {
        throw 'GPU_EXECUTION_PROVENANCE_TIMESTAMP_INVALID'
    }
    return [pscustomobject]@{
        AttemptPath = $attemptPath
        RuntimePath = $runtimePath
        AttemptSha256 = (Get-FileHash -LiteralPath $attemptPath -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
        RuntimeSha256 = (Get-FileHash -LiteralPath $runtimePath -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    }
}

function Move-ValidatedStageOutput {
    param(
        [Parameter(Mandatory)][string]$StagingPath,
        [Parameter(Mandatory)][string]$FinalPath,
        [Parameter(Mandatory)][object]$Context,
        [string]$ExecutionMode = 'CPU_FROZEN'
    )

    if (-not (Test-Path -LiteralPath $StagingPath -PathType Container)) {
        throw "TRANSIENT_STAGING_OUTPUT_MISSING path=$StagingPath"
    }
    if (Test-Path -LiteralPath $FinalPath) {
        throw "OUTPUT_NAMESPACE_ALREADY_EXISTS path=$FinalPath"
    }
    if (-not [string]::Equals((Split-Path -Qualifier $StagingPath), (Split-Path -Qualifier $FinalPath), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "OUTPUT_PATHS_NOT_ON_SAME_VOLUME staging=$StagingPath final=$FinalPath"
    }
    if ($ExecutionMode -eq 'GPU_STAGE2_QUALIFIED') {
        [void](Assert-FrozenSageGpuExecutionProvenance -Directory $StagingPath -Context $Context)
    } elseif ($ExecutionMode -cne 'CPU_FROZEN') {
        throw "EXECUTION_MODE_UNSUPPORTED mode=$ExecutionMode"
    }

    $sourceMetrics = Get-DirectoryMetrics -Path $StagingPath
    $finalParent = Split-Path -Parent $FinalPath
    if (-not (Test-Path -LiteralPath $finalParent -PathType Container)) {
        [void](New-Item -ItemType Directory -Path $finalParent -ErrorAction Stop)
    }
    Move-Item -LiteralPath $StagingPath -Destination $FinalPath -ErrorAction Stop
    if (Test-Path -LiteralPath $StagingPath) {
        throw "STAGING_OUTPUT_REMAINS_AFTER_MOVE path=$StagingPath"
    }

    $destinationMetrics = Get-DirectoryMetrics -Path $FinalPath
    if ($sourceMetrics.FileCount -ne $destinationMetrics.FileCount -or $sourceMetrics.Bytes -ne $destinationMetrics.Bytes) {
        throw "RELOCATION_METRICS_MISMATCH source_files=$($sourceMetrics.FileCount) destination_files=$($destinationMetrics.FileCount) source_bytes=$($sourceMetrics.Bytes) destination_bytes=$($destinationMetrics.Bytes)"
    }
    $receipt = [ordered]@{
        scene_id = [string]$Context.SceneId
        prn = [string]$Context.Prn
        tracking_channel = [int]$Context.TrackingChannel
        frozen_sage_sha256 = [string]$Context.FrozenSageSha256
        raw_iq_size_bytes = [long]$Context.RawIqSizeBytes
        raw_iq_sha256 = [string]$Context.RawIqSha256
        raw_iq_sha256_status = [string]$Context.RawIqSha256Status
        execution_emitted_path = $StagingPath
        final_relocated_path = $FinalPath
        resume = $false
        matlab_start_utc = [string]$Context.MatlabStartUtc
        matlab_end_utc = [string]$Context.MatlabEndUtc
        matlab_process_id = if ($null -eq $Context.PSObject.Properties['MatlabProcessId']) { $null } else { [int]$Context.MatlabProcessId }
        source_file_count_before_move = $sourceMetrics.FileCount
        destination_file_count_after_move = $destinationMetrics.FileCount
        source_bytes_before_move = $sourceMetrics.Bytes
        destination_bytes_after_move = $destinationMetrics.Bytes
        relocation_status = 'VERIFIED_SAME_VOLUME_MOVE'
        matlab_exit_code = [int]$Context.MatlabExitCode
        startup_smoke_marker = $script:StartupMarker
    }
    if ($ExecutionMode -eq 'GPU_STAGE2_QUALIFIED') {
        $attemptPath = Join-Path $FinalPath 'gpu_execution_attempt.json'
        if (-not (Test-Path -LiteralPath $attemptPath -PathType Leaf)) {
            throw "GPU_EXECUTION_PROVENANCE_MISSING path=$attemptPath"
        }
        $provenancePath = Join-Path $FinalPath 'gpu_execution_provenance.json'
        if (-not (Test-Path -LiteralPath $provenancePath -PathType Leaf)) {
            throw "GPU_EXECUTION_PROVENANCE_MISSING path=$provenancePath"
        }
        $receipt['execution_mode'] = $ExecutionMode
        $receipt['gpu_execution_attempt_path'] = $attemptPath
        $receipt['gpu_execution_attempt_sha256'] = (Get-FileHash -LiteralPath $attemptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $receipt['gpu_execution_provenance_path'] = $provenancePath
        $receipt['gpu_execution_provenance_sha256'] = (Get-FileHash -LiteralPath $provenancePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $gpuLockReceiptPath = Join-Path $FinalPath 'gpu_stage2_global_lock_receipt.json'
        if (Test-Path -LiteralPath $gpuLockReceiptPath -PathType Leaf) {
            $receipt['gpu_global_lock_receipt_path'] = $gpuLockReceiptPath
            $receipt['gpu_global_lock_receipt_sha256'] = (Get-FileHash -LiteralPath $gpuLockReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    } elseif ($ExecutionMode -cne 'CPU_FROZEN') {
        throw "EXECUTION_MODE_UNSUPPORTED mode=$ExecutionMode"
    }
    $receiptPath = Join-Path $FinalPath 'relocation_receipt.json'
    $receiptJson = $receipt | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText($receiptPath, $receiptJson + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    return [pscustomobject]$receipt
}

function Add-FrozenSageGpuLockReferenceToRelocationReceipt {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$FinalPath,
        [Parameter(Mandatory)][string]$GpuGlobalLockReceiptPath
    )

    $receiptPath = Join-Path $FinalPath 'relocation_receipt.json'
    $expectedGpuLockPath = Join-Path $FinalPath 'gpu_stage2_global_lock_receipt.json'
    if (-not [string]::Equals([System.IO.Path]::GetFullPath($GpuGlobalLockReceiptPath),
            [System.IO.Path]::GetFullPath($expectedGpuLockPath), [System.StringComparison]::OrdinalIgnoreCase) -or
        -not (Test-Path -LiteralPath $receiptPath -PathType Leaf) -or
        -not (Test-Path -LiteralPath $GpuGlobalLockReceiptPath -PathType Leaf)) {
        throw 'GPU_GLOBAL_LOCK_RELOCATION_REFERENCE_INPUT_INVALID'
    }
    $receipt = Get-Content -Raw -LiteralPath $receiptPath -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    $receipt | Add-Member -NotePropertyName gpu_global_lock_receipt_path -NotePropertyValue $GpuGlobalLockReceiptPath -Force
    $receipt | Add-Member -NotePropertyName gpu_global_lock_receipt_sha256 -NotePropertyValue (
        (Get-FileHash -LiteralPath $GpuGlobalLockReceiptPath -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()) -Force
    $json = $receipt | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($receiptPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    return [pscustomobject]$receipt
}

function Resolve-ManifestInputPath {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][string]$ProjectRoot
    )

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $Path))
}

function Get-FrozenSagePreflight {
    param(
        [Parameter(Mandatory)][string]$RunId,
        [object]$ExecutionPlan = $null
    )

    $executionMode = if ($null -eq $ExecutionPlan) { 'CPU_FROZEN' } else { [string]$ExecutionPlan.ExecutionMode }

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    [void](Assert-ApprovedExecutionEnvironment -Identity $identity.Name `
        -PowerShellVersion $PSVersionTable.PSVersion.ToString() `
        -IsAdministrator $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator))

    if (-not [string]::Equals([System.IO.Path]::GetFullPath($script:FrozenProjectRoot), (Get-Location).Path, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "PROJECT_ROOT_MISMATCH expected=$script:FrozenProjectRoot actual=$((Get-Location).Path)"
    }

    $sourcePath = Join-Path $script:FrozenProjectRoot $script:FrozenSourceRelativePath
    $actualSourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    [void](Assert-FrozenSageHash -ActualHash $actualSourceHash -ExpectedHash $script:FrozenSourceSha256)

    $manifestPath = Join-Path $script:FrozenProjectRoot $script:FrozenManifestRelativePath
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        throw "RERUN_MANIFEST_MISSING path=$manifestPath"
    }
    $manifestRows = @(Import-Csv -LiteralPath $manifestPath)
    $targetRows = @($manifestRows | Where-Object { [string]$_.run_id -ceq $RunId })
    if ($targetRows.Count -ne 1) {
        throw "MANIFEST_TARGET_CARDINALITY_MISMATCH expected=1 actual=$($targetRows.Count) run_id=$RunId"
    }
    $row = $targetRows[0]
    [void](Assert-FrozenSageManifestRow -Row $row -ExpectedRunId $RunId)

    $datasetAuditPath = Join-Path $script:FrozenProjectRoot 'reports\data_consolidation_20261003\mainline_iq_gnss_sdr_dataset_audit.csv'
    if (-not (Test-Path -LiteralPath $datasetAuditPath -PathType Leaf)) {
        throw "DATASET_AUDIT_MISSING path=$datasetAuditPath"
    }
    $datasetRows = @(Import-Csv -LiteralPath $datasetAuditPath | Where-Object {
        [string]$_.dataset_id -ceq [string]$row.dataset_id
    })
    if ($datasetRows.Count -ne 1) {
        throw "DATASET_AUDIT_TARGET_CARDINALITY_MISMATCH expected=1 actual=$($datasetRows.Count) dataset_id=$($row.dataset_id)"
    }
    $datasetAuditRow = $datasetRows[0]
    if ([long]$datasetAuditRow.sample_rate_hz -ne $script:FrozenSampleRateHz) {
        throw "DATASET_AUDIT_SAMPLE_RATE_MISMATCH expected=$script:FrozenSampleRateHz actual=$($datasetAuditRow.sample_rate_hz)"
    }

    $metadataPath = Resolve-ManifestInputPath -Path ([string]$row.metadata_path) -ProjectRoot $script:FrozenProjectRoot
    if (-not (Test-Path -LiteralPath $metadataPath -PathType Leaf)) {
        throw "REQUIRED_INPUT_MISSING path=$metadataPath"
    }
    try {
        $metadata = Get-Content -Raw -LiteralPath $metadataPath -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "SCENE_METADATA_INVALID path=$metadataPath detail=$($_.Exception.Message)"
    }
    if ([string]$metadata.scene_id -ne [string]$row.scene_id -or [double]$metadata.signal.sample_rate_hz -ne $script:FrozenSampleRateHz) {
        throw "SCENE_METADATA_MISMATCH scene=$($metadata.scene_id) sample_rate_hz=$($metadata.signal.sample_rate_hz)"
    }
    $rawPath = Resolve-ManifestInputPath -Path ([string]$row.raw_path) -ProjectRoot $script:FrozenProjectRoot
    $metadataRawPath = [System.IO.Path]::GetFullPath([string]$metadata.raw_iq.path)
    if (-not [string]::Equals($rawPath, $metadataRawPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "RAW_PATH_METADATA_MISMATCH manifest=$rawPath metadata=$metadataRawPath"
    }
    $requiredPaths = @(
        $rawPath,
        $metadataPath,
        (Resolve-ManifestInputPath -Path ([string]$row.tracking_file) -ProjectRoot $script:FrozenProjectRoot),
        (Resolve-ManifestInputPath -Path ([string]$row.telemetry_file) -ProjectRoot $script:FrozenProjectRoot),
        (Resolve-ManifestInputPath -Path ([string]$row.rinex_nav_file) -ProjectRoot $script:FrozenProjectRoot),
        (Resolve-ManifestInputPath -Path ([string]$row.nmea_file) -ProjectRoot $script:FrozenProjectRoot)
    )
    [void](Assert-RequiredInputFiles -Paths $requiredPaths)
    $rawMetadata = Get-FrozenSageRawIqMetadata -Path $rawPath -ExpectedSizeBytes ([long]$datasetAuditRow.raw_size_bytes)

    $prn = [int]([string]$row.prn -replace '^G', '')
    $channel = [int]$row.tracking_channel
    $transientNamespace = Join-Path 'scenes' (Join-Path ([string]$row.scene_id) (
        Join-Path $script:TransientNamespaceRoot ([string]$row.prn)))
    $stagingPath = Join-Path $script:FrozenProjectRoot $transientNamespace
    $finalPath = Join-Path $script:FrozenProjectRoot ([string]$row.output_namespace)
    [void](Assert-OutputNamespacesAbsent -StagingPath $stagingPath -FinalPath $finalPath)

    $matlab = Get-Command -Name 'matlab' -CommandType Application -ErrorAction Stop
    if (-not (Test-Path -LiteralPath $matlab.Source -PathType Leaf)) {
        throw "MATLAB_EXECUTABLE_MISSING path=$($matlab.Source)"
    }
    return [pscustomobject]@{
        ProjectRoot = $script:FrozenProjectRoot
        RunId = [string]$row.run_id
        SceneId = [string]$row.scene_id
        Prn = $prn
        PrnLabel = [string]$row.prn
        TrackingChannel = $channel
        MappingWarning = [string]$row.mapping_warning
        SampleRateHz = $script:FrozenSampleRateHz
        FrozenSageSha256 = $actualSourceHash
        RawPath = $rawPath
        RawIqSizeBytes = $rawMetadata.RawIqSizeBytes
        RawIqSha256 = $rawMetadata.RawIqSha256
        RawIqSha256Status = $rawMetadata.RawIqSha256Status
        MatlabPath = $matlab.Source
        ExecutionMode = $executionMode
        ExecutionPlan = $ExecutionPlan
        GpuSourceIdentity = $null
        GpuIdentity = ''
        StagingPath = $stagingPath
        FinalPath = $finalPath
        ManifestRow = $row
    }
}

function Invoke-FrozenSageRerunSingle {
    param(
        [Parameter(Mandatory)][string]$RunId,
        [Parameter(Mandatory)][bool]$ShouldExecute,
        [AllowNull()][string]$PlanPath
    )

    $manifestPath = Join-Path $script:FrozenProjectRoot $script:FrozenManifestRelativePath
    $gpuPaths = Get-FrozenSageGpuSourcePaths
    $executionPlan = Resolve-FrozenSageExecutionPlan `
        -ExecutionPlanPath $PlanPath `
        -RunId $RunId `
        -ManifestPath $manifestPath `
        -SourceContractPath $gpuPaths.SourceContract
    $preflight = Get-FrozenSagePreflight -RunId $RunId -ExecutionPlan $executionPlan
    Write-Output "PREFLIGHT_PASS run_id=$($preflight.RunId) scene=$($preflight.SceneId) prn=$($preflight.PrnLabel) channel=$($preflight.TrackingChannel) sample_rate_hz=$($preflight.SampleRateHz) mapping_warning=$($preflight.MappingWarning) execution_mode=$($preflight.ExecutionMode) resume=false"
    if (-not $ShouldExecute) {
        Write-Output "VALIDATION_ONLY matlab_invoked=false raw_iq_content_read=false execution_mode=$($preflight.ExecutionMode)"
        return
    }

    $executionLogParent = Join-Path $preflight.ProjectRoot 'dataset_generation_logs\batch_sage_execution'
    if (-not (Test-Path -LiteralPath $executionLogParent -PathType Container)) {
        throw "EXECUTION_LOG_PARENT_MISSING path=$executionLogParent"
    }
    $globalLockPath = Get-FrozenSageTaskRunnerLockPath -ExecutionLogParent $executionLogParent -RunId $preflight.RunId
    $gpuGlobalLockPath = Get-FrozenSageGpuGlobalLockPath -ExecutionLogParent $executionLogParent
    $failureReceiptRoot = Join-Path $executionLogParent 'windows_runner_receipts'
    $lockStream = $null
    $lockOwned = $false
    $gpuLockStream = $null
    $gpuLockAcquired = $false
    $gpuLockPayload = $null
    $gpuLockReceiptPath = $null
    $gpuLockReceiptOwned = $false
    $lockPayload = $null
    $matlabProcessState = [ordered]@{
        Started = $false
        ProcessId = $null
        ExitCode = $null
        ProcessEnded = $false
        StartedUtc = $null
        EndedUtc = $null
    }
    $controlledFailure = $false
    $failureReason = 'CONTROLLED_WRAPPER_FAILURE'
    $failureMessage = ''
    try {
        try {
            $lockStream = [System.IO.File]::Open($globalLockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
            $lockOwned = $true
        } catch [System.IO.IOException] {
            throw "GLOBAL_SAGE_RUNNER_LOCK_PRESENT path=$globalLockPath"
        }
        $lockPayload = New-FrozenSageRunnerLockPayload -Preflight $preflight -ExecutionPlan $executionPlan
        $lockWriter = [System.IO.StreamWriter]::new($lockStream, [System.Text.UTF8Encoding]::new($false), 1024, $true)
        $lockWriter.Write(($lockPayload | ConvertTo-Json -Depth 4))
        $lockWriter.Flush()
        $lockWriter.Dispose()

        if ($preflight.ExecutionMode -eq 'GPU_STAGE2_QUALIFIED') {
            $gpuLockPayload = [pscustomobject]$lockPayload
            $gpuLock = New-FrozenSageGpuGlobalLock -ExecutionMode $preflight.ExecutionMode -LockPath $gpuGlobalLockPath -Payload $gpuLockPayload
            $gpuLockStream = $gpuLock.Stream
            $gpuLockAcquired = $true
            $currentPlan = Resolve-FrozenSageExecutionPlan -ExecutionPlanPath $PlanPath -RunId $preflight.RunId -ManifestPath $manifestPath -SourceContractPath $gpuPaths.SourceContract
            if ($currentPlan.ExecutionPlanSha256 -cne $executionPlan.ExecutionPlanSha256) {
                throw 'GPU_SOURCE_IDENTITY_MISMATCH execution plan changed after task authorization.'
            }
            $gpuSourceIdentity = Assert-FrozenSageGpuSourceIdentity `
                -ExecutionPlan $currentPlan `
                -FrozenAuthorityPath (Join-Path $script:FrozenProjectRoot $script:FrozenSourceRelativePath) `
                -QualifiedCandidatePath $gpuPaths.Candidate `
                -QualifiedProbePath $gpuPaths.Probe `
                -QualifiedSelectorPath $gpuPaths.Selector `
                -ProductionEntryPath $gpuPaths.ProductionEntry `
                -SourceContractPath $gpuPaths.SourceContract
            $preflight.GpuSourceIdentity = $gpuSourceIdentity
            $gpuSmoke = Invoke-FrozenMatlabBatch -MatlabPath $preflight.MatlabPath -Expression (Get-GpuMatlabAvailabilityExpression)
            $matlabProcessState = [ordered]@{
                Started = $true
                ProcessId = [int]$gpuSmoke.ProcessId
                ExitCode = [int]$gpuSmoke.ExitCode
                ProcessEnded = [bool]$gpuSmoke.ProcessEnded
                StartedUtc = [string]$gpuSmoke.StartedUtc
                EndedUtc = [string]$gpuSmoke.EndedUtc
            }
            $preflight.GpuIdentity = Assert-GpuMatlabAvailabilitySmoke -ExitCode $gpuSmoke.ExitCode -Stdout $gpuSmoke.Stdout
            Write-Output "GPU_PREFLIGHT_PASS identity=$($preflight.GpuIdentity) execution_mode=$($preflight.ExecutionMode)"
        }

        $smoke = Invoke-FrozenMatlabBatch -MatlabPath $preflight.MatlabPath -Expression "disp('$script:StartupMarker')"
        if ($preflight.ExecutionMode -eq 'GPU_STAGE2_QUALIFIED') {
            $matlabProcessState = [ordered]@{
                Started = $true; ProcessId = [int]$smoke.ProcessId; ExitCode = [int]$smoke.ExitCode
                ProcessEnded = [bool]$smoke.ProcessEnded; StartedUtc = [string]$smoke.StartedUtc; EndedUtc = [string]$smoke.EndedUtc
            }
        }
        [void](Assert-MatlabStartupSmoke -ExitCode $smoke.ExitCode -Output $smoke.Output)
        Write-Output "MATLAB_STARTUP_SMOKE_PASS marker=$script:StartupMarker exit_code=$($smoke.ExitCode)"

        $transportExpression = "a='F1023_V70_D0117_P2';b='TrackingChannel';c='E:/GNSS_Multipath_Project';assert(strcmp(a,'F1023_V70_D0117_P2'));assert(strcmp(b,'TrackingChannel'));assert(strcmp(c,'E:/GNSS_Multipath_Project'));disp('MATLAB_ARGUMENT_TRANSPORT_OK')"
        $transportSmoke = Invoke-FrozenMatlabBatch -MatlabPath $preflight.MatlabPath -Expression $transportExpression
        if ($preflight.ExecutionMode -eq 'GPU_STAGE2_QUALIFIED') {
            $matlabProcessState = [ordered]@{
                Started = $true; ProcessId = [int]$transportSmoke.ProcessId; ExitCode = [int]$transportSmoke.ExitCode
                ProcessEnded = [bool]$transportSmoke.ProcessEnded; StartedUtc = [string]$transportSmoke.StartedUtc; EndedUtc = [string]$transportSmoke.EndedUtc
            }
        }
        [void](Assert-MatlabArgumentTransportSmoke -ExitCode $transportSmoke.ExitCode -Stdout $transportSmoke.Stdout)
        Write-Output "MATLAB_ARGUMENT_TRANSPORT_SMOKE_PASS marker=$script:TransportMarker exit_code=$($transportSmoke.ExitCode)"

        $currentSourceHash = (Get-FileHash -LiteralPath (Join-Path $preflight.ProjectRoot $script:FrozenSourceRelativePath) -Algorithm SHA256).Hash.ToLowerInvariant()
        [void](Assert-FrozenSageHash -ActualHash $currentSourceHash -ExpectedHash $script:FrozenSourceSha256)
        [void](Assert-OutputNamespacesAbsent -StagingPath $preflight.StagingPath -FinalPath $preflight.FinalPath)
        Write-Output "EXECUTION_GATES_REVERIFIED frozen_sage_sha256=$currentSourceHash output_namespaces_absent=true execution_mode=$($preflight.ExecutionMode)"
        if ($preflight.ExecutionMode -eq 'GPU_STAGE2_QUALIFIED') {
            $currentPlan = Resolve-FrozenSageExecutionPlan `
                -ExecutionPlanPath $PlanPath `
                -RunId $preflight.RunId `
                -ManifestPath $manifestPath `
                -SourceContractPath $preflight.GpuSourceIdentity.SourceContractPath
            if ($currentPlan.ExecutionPlanSha256 -cne $preflight.ExecutionPlan.ExecutionPlanSha256) {
                throw 'GPU_SOURCE_IDENTITY_MISMATCH execution plan changed after preflight.'
            }
            $currentGpuIdentity = Assert-FrozenSageGpuSourceIdentity `
                -ExecutionPlan $currentPlan `
                -FrozenAuthorityPath (Join-Path $script:FrozenProjectRoot $script:FrozenSourceRelativePath) `
                -QualifiedCandidatePath $gpuPaths.Candidate `
                -QualifiedProbePath $gpuPaths.Probe `
                -QualifiedSelectorPath $gpuPaths.Selector `
                -ProductionEntryPath $gpuPaths.ProductionEntry `
                -SourceContractPath $gpuPaths.SourceContract
            $expression = Get-GpuSageMatlabExpression `
                -SceneId $preflight.SceneId `
                -Prn $preflight.Prn `
                -TrackingChannel $preflight.TrackingChannel `
                -ProjectRoot $preflight.ProjectRoot `
                -RunId $preflight.RunId `
                -ExecutionPlanPath $PlanPath `
                -ProductionEntryPath $currentGpuIdentity.ProductionEntryPath `
                -SelectorPath $currentGpuIdentity.SelectorPath
        } else {
            $expression = Get-FrozenSageMatlabExpression `
                -SceneId $preflight.SceneId `
                -Prn $preflight.Prn `
                -TrackingChannel $preflight.TrackingChannel `
                -ProjectRoot $preflight.ProjectRoot
        }
        $rootForMatlab = $preflight.ProjectRoot.Replace('\', '/')
        $batchExpression = "cd('$rootForMatlab/scripts/sage_pipeline'); $expression"
        Write-Output "SAGE_EXECUTION_BEGIN run_id=$($preflight.RunId) scene=$($preflight.SceneId) prn=$($preflight.PrnLabel) channel=$($preflight.TrackingChannel) mapping_warning=$($preflight.MappingWarning) execution_mode=$($preflight.ExecutionMode) resume=false"
        $sageRun = Invoke-FrozenMatlabBatch -MatlabPath $preflight.MatlabPath -Expression $batchExpression
        $matlabProcessState = [ordered]@{
            Started = $true
            ProcessId = [int]$sageRun.ProcessId
            ExitCode = [int]$sageRun.ExitCode
            ProcessEnded = [bool]$sageRun.ProcessEnded
            StartedUtc = [string]$sageRun.StartedUtc
            EndedUtc = [string]$sageRun.EndedUtc
        }
        if ($sageRun.ExitCode -ne 0) {
            $matlabFailureText = [string]$sageRun.Stdout + [string]$sageRun.Stderr
            $gpuFailure = [regex]::Match($matlabFailureText, 'GPU_(?:SOURCE_IDENTITY_MISMATCH|NOT_AVAILABLE|INITIALIZATION_FAILED|STAGE2_MATLAB_FAILURE)')
            if ($preflight.ExecutionMode -eq 'GPU_STAGE2_QUALIFIED' -and $gpuFailure.Success) {
                throw "$($gpuFailure.Value) exit_code=$($sageRun.ExitCode); staging output, if any, is preserved."
            }
            if ($preflight.ExecutionMode -eq 'GPU_STAGE2_QUALIFIED') {
                throw "GPU_STAGE2_MATLAB_FAILURE exit_code=$($sageRun.ExitCode); staging output, if any, is preserved."
            }
            throw "SAGE_MATLAB_EXIT_NONZERO exit_code=$($sageRun.ExitCode); staging output, if any, is preserved."
        }
        [void](Assert-StageOutputsComplete -OutputPath $preflight.StagingPath)
        [void](Assert-FrozenSageStage0Ready -StagingPath $preflight.StagingPath)

        $postRunHash = (Get-FileHash -LiteralPath (Join-Path $preflight.ProjectRoot $script:FrozenSourceRelativePath) -Algorithm SHA256).Hash.ToLowerInvariant()
        [void](Assert-FrozenSageHash -ActualHash $postRunHash -ExpectedHash $script:FrozenSourceSha256)
        $context = [pscustomobject]@{
            SceneId = $preflight.SceneId
            Prn = $preflight.Prn
            TrackingChannel = $preflight.TrackingChannel
            RunId = $preflight.RunId
            ExecutionPlanSha256 = if ($preflight.ExecutionMode -eq 'GPU_STAGE2_QUALIFIED') { [string]$preflight.ExecutionPlan.ExecutionPlanSha256 } else { '' }
            FrozenSageSha256 = $postRunHash
            RawIqSizeBytes = $preflight.RawIqSizeBytes
            RawIqSha256 = $preflight.RawIqSha256
            RawIqSha256Status = $preflight.RawIqSha256Status
            MatlabProcessId = [int]$sageRun.ProcessId
            MatlabStartUtc = $sageRun.StartedUtc
            MatlabEndUtc = $sageRun.EndedUtc
            MatlabExitCode = $sageRun.ExitCode
        }
        $receipt = Move-ValidatedStageOutput -StagingPath $preflight.StagingPath -FinalPath $preflight.FinalPath -Context $context -ExecutionMode $preflight.ExecutionMode
        if ($preflight.ExecutionMode -eq 'GPU_STAGE2_QUALIFIED') {
            $gpuLockReceiptPath = Join-Path $preflight.FinalPath 'gpu_stage2_global_lock_receipt.json'
            $gpuLockStream.Dispose()
            $gpuLockStream = $null
            [void](Move-FrozenSageGpuGlobalLockToArchive -LockPath $gpuGlobalLockPath -DestinationPath $gpuLockReceiptPath -ExpectedPayload $gpuLockPayload)
            $gpuLockAcquired = $false
            $gpuLockReceiptOwned = $true
            $receipt = Add-FrozenSageGpuLockReferenceToRelocationReceipt -FinalPath $preflight.FinalPath -GpuGlobalLockReceiptPath $gpuLockReceiptPath
        }

        $lockStream.Dispose()
        $lockStream = $null
        Move-Item -LiteralPath $globalLockPath -Destination (Join-Path $preflight.FinalPath 'windows_runner_lock_receipt.json') -ErrorAction Stop
        $lockOwned = $false
        $gpuLockReceiptOwned = $false
        Write-Output "RELOCATION_VERIFIED final_path=$($preflight.FinalPath) files=$($receipt.destination_file_count_after_move) bytes=$($receipt.destination_bytes_after_move)"
        Write-Output "FROZEN_SAGE_SHA_AFTER=$postRunHash"
    } catch {
        $caughtError = $_
        if ($caughtError.Exception -isnot [System.Management.Automation.PipelineStoppedException] -and
            $caughtError.Exception -isnot [System.OperationCanceledException]) {
            if ($lockOwned) {
                $controlledFailure = $true
                $failureMessage = $caughtError.Exception.Message
                $stage0FailureReason = Get-FrozenSageStage0FailureReason -StagingPath $preflight.StagingPath
                if ($null -ne $stage0FailureReason) {
                    $failureReason = $stage0FailureReason
                } elseif ($failureMessage -match '^GPU_GLOBAL_LOCK_PRESENT') {
                    $failureReason = 'GPU_GLOBAL_LOCK_PRESENT'
                } elseif ($failureMessage -match '^MATLAB_ARGUMENT_TRANSPORT_FAILED') {
                    $failureReason = 'MATLAB_ARGUMENT_TRANSPORT_FAILURE'
                } elseif ($failureMessage -match '^MATLAB_STARTUP_SMOKE_FAILED') {
                    $failureReason = 'MATLAB_STARTUP_SMOKE_FAILURE'
                } elseif ($failureMessage -match '^FROZEN_SAGE_SOURCE_HASH_MISMATCH') {
                    $failureReason = 'FROZEN_SAGE_SOURCE_HASH_MISMATCH'
                } elseif ($failureMessage -match '^SAGE_MATLAB_EXIT_NONZERO') {
                    $failureReason = 'SAGE_MATLAB_FAILURE'
                } elseif ($failureMessage -match '^GPU_(?:SOURCE_IDENTITY_MISMATCH|EXECUTION_PLAN_SHA_MISMATCH|EXECUTION_PLAN_SOURCE_CONTRACT_SHA_MISMATCH)') {
                    $failureReason = 'GPU_SOURCE_IDENTITY_MISMATCH'
                } elseif ($failureMessage -match '^GPU_NOT_AVAILABLE') {
                    $failureReason = 'GPU_NOT_AVAILABLE'
                } elseif ($failureMessage -match '^GPU_INITIALIZATION_FAILED') {
                    $failureReason = 'GPU_INITIALIZATION_FAILED'
                } elseif ($failureMessage -match '^GPU_STAGE2_MATLAB_FAILURE') {
                    $failureReason = 'GPU_STAGE2_MATLAB_FAILURE'
                } elseif ($failureMessage -match '^STAGE0_STAGE4_OUTPUT_INCOMPLETE') {
                    $failureReason = 'STAGE_OUTPUT_VALIDATION_FAILURE'
                }
            }
        }
        throw
    } finally {
        if ($null -ne $lockStream) {
            $lockStream.Dispose()
            $lockStream = $null
        }
        if ($null -ne $gpuLockStream) {
            $gpuLockStream.Dispose()
            $gpuLockStream = $null
        }
        if ($lockOwned -and $controlledFailure -and $null -ne $lockPayload -and
            (-not $matlabProcessState.Started -or $matlabProcessState.ProcessEnded)) {
            $ownedGpuLockSource = $null
            if ($gpuLockAcquired -and (Test-Path -LiteralPath $gpuGlobalLockPath -PathType Leaf)) {
                $ownedGpuLockSource = $gpuGlobalLockPath
            } elseif ($gpuLockReceiptOwned) {
                $candidateGpuLockPaths = @(
                    $gpuLockReceiptPath,
                    (Join-Path $preflight.StagingPath 'gpu_stage2_global_lock_receipt.json'),
                    (Join-Path $preflight.FinalPath 'gpu_stage2_global_lock_receipt.json')
                )
                foreach ($possiblePath in $candidateGpuLockPaths) {
                    if (-not [string]::IsNullOrWhiteSpace([string]$possiblePath) -and (Test-Path -LiteralPath $possiblePath -PathType Leaf)) {
                        $ownedGpuLockSource = $possiblePath
                        break
                    }
                }
            }
            $failureArguments = @{
                GlobalLockPath = $globalLockPath
                ReceiptRoot = $failureReceiptRoot
                LockPayload = [pscustomobject]$lockPayload
                FailureReason = $failureReason
                ErrorMessage = $failureMessage
                MatlabProcessState = [pscustomobject]$matlabProcessState
            }
            if ($null -ne $ownedGpuLockSource) {
                $failureArguments.GpuGlobalLockPath = $ownedGpuLockSource
                $failureArguments.GpuGlobalLockPayload = $gpuLockPayload
            }
            $failureReceipt = Move-FrozenRunnerLockToFailureReceipt @failureArguments
            $lockOwned = $false
            $gpuLockAcquired = $false
            $gpuLockReceiptOwned = $false
            Write-Output "CONTROLLED_FAILURE_LOCK_ARCHIVED reason=$failureReason run_id=$($preflight.RunId) lock=$($failureReceipt.LockPath) receipt=$($failureReceipt.ReceiptPath) matlab_started=$($matlabProcessState.Started) matlab_process_id=$($matlabProcessState.ProcessId) matlab_exit_code=$($matlabProcessState.ExitCode) matlab_process_ended=$($matlabProcessState.ProcessEnded)"
        } elseif ($lockOwned -and $controlledFailure -and $matlabProcessState.Started -and -not $matlabProcessState.ProcessEnded) {
            Write-Output "CONTROLLED_FAILURE_LOCK_RETAINED reason=RUNNER_PROCESS_END_UNCONFIRMED run_id=$($preflight.RunId) runner_lock=$globalLockPath gpu_lock=$gpuGlobalLockPath"
        }
    }
}

function Invoke-FrozenMatlabBatch {
    param(
        [Parameter(Mandatory)][string]$MatlabPath,
        [Parameter(Mandatory)][string]$Expression
    )

    $startInfo = New-FrozenMatlabProcessStartInfo -MatlabPath $MatlabPath -Expression $Expression
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $startedUtc = [System.DateTimeOffset]::UtcNow
    if (-not $process.Start()) {
        throw "MATLAB_PROCESS_START_FAILED path=$MatlabPath"
    }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $processEnded = $process.HasExited
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    $exitCode = $process.ExitCode
    $endedUtc = [System.DateTimeOffset]::UtcNow
    if (-not [string]::IsNullOrEmpty($stdout)) {
        [Console]::Out.Write($stdout)
    }
    if (-not [string]::IsNullOrEmpty($stderr)) {
        [Console]::Error.Write($stderr)
    }
    $combinedOutput = $stdout + $stderr
    return [pscustomobject]@{
        ExitCode = [int]$exitCode
        ProcessId = [int]$process.Id
        ProcessEnded = [bool]$processEnded
        Output = $combinedOutput
        Stdout = $stdout
        Stderr = $stderr
        StartedUtc = $startedUtc.ToString('o')
        EndedUtc = $endedUtc.ToString('o')
        DurationSeconds = [Math]::Round(($endedUtc - $startedUtc).TotalSeconds, 3)
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    if ([string]::IsNullOrWhiteSpace($RunId)) {
        throw 'RUN_ID_REQUIRED: pass one manifest run_id; no task is inferred.'
    }
    Invoke-FrozenSageRerunSingle -RunId $RunId -ShouldExecute:$Execute.IsPresent -PlanPath $ExecutionPlanPath
}
