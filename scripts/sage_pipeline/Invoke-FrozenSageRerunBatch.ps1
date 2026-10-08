[CmdletBinding()]
param(
    [switch]$ValidateOnly,
    [switch]$Execute,
    [string]$ExecutionPlanPath,
    [string]$ValidateRecoveryRunId,
    [string]$RecoverRunId,
    [switch]$ParallelPilot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$script:FrozenBatchRequestedValidateOnly = [bool]$ValidateOnly.IsPresent
$script:FrozenBatchRequestedExecute = [bool]$Execute.IsPresent
$script:FrozenBatchRequestedExecutionPlanPath = $ExecutionPlanPath

if (-not (Get-Command -Name 'Get-FrozenSagePreflight' -ErrorAction SilentlyContinue)) {
    . (Join-Path $PSScriptRoot 'Invoke-FrozenSageRerunSingle.ps1')
}
$ExecutionPlanPath = $script:FrozenBatchRequestedExecutionPlanPath

$script:FrozenBatchProjectRoot = 'E:\GNSS_Multipath_Project'
$script:FrozenBatchManifestRelativePath = 'reports\data_consolidation_20261003\MAINLINE_SAGE_1023_RERUN_MANIFEST.csv'
$script:FrozenBatchAuditRelativePath = 'reports\data_consolidation_20261003\mainline_iq_gnss_sdr_dataset_audit.csv'
$script:FrozenBatchSummaryRelativePath = 'reports\data_consolidation_20261003\MAINLINE_SAGE_1023_BATCH_RERUN_SUMMARY.csv'
$script:FrozenBatchBaselineReportRelativePath = 'reports\data_consolidation_20261003\MAINLINE_SAGE_BASELINE_RERUN_20261003.md'
$script:FrozenBatchExpectedTaskCount = 89
$script:FrozenBatchBaselineRunId = 'run_20261003_F1023_V70_D0117_P2_G28_ch1'
$script:FrozenBatchDiagnosticRoot = 'sage_results\rerun_20261003_frozen_v3_failed'
$script:FrozenBatchOwnedLockPath = ''

function Get-FrozenSageBatchSummaryColumns {
    return @(
        'run_id', 'scene_id', 'prn', 'tracking_channel', 'mapping_warning', 'execution_status',
        'matlab_exit_code', 'stage0_valid_nav_symbols', 'stage0_valid_40ms_windows',
        'stage1_scanned_windows', 'stage2_evaluated_windows', 'stage2_selected_path_count',
        'direct_path_count', 'stage2_mpc_count', 'stage3_persistence_row_count',
        'stage3_persistent_mpc_count', 'stage4_joint_result_count', 'stage4_confirmed_mpc_count',
        'output_namespace', 'frozen_sage_sha256', 'failure_reason'
    )
}

function Resolve-FrozenSageBatchMode {
    param(
        [Parameter(Mandatory)][bool]$ValidateOnly,
        [Parameter(Mandatory)][bool]$Execute
    )
    if ($ValidateOnly -eq $Execute) {
        throw 'SELECT_EXACTLY_ONE_MODE: pass -ValidateOnly or -Execute.'
    }
    if ($Execute) { return 'EXECUTE' }
    return 'VALIDATE_ONLY'
}

function Resolve-FrozenSageBatchExecutionPlan {
    [CmdletBinding()]
    param(
        [AllowNull()][string]$ExecutionPlanPath,
        [Parameter(Mandatory)][string]$ManifestPath,
        [Parameter(Mandatory)][string]$SourceContractPath,
        [Parameter(Mandatory)][object[]]$ManifestRows
    )

    if ([string]::IsNullOrWhiteSpace($ExecutionPlanPath)) {
        return [pscustomobject]@{
            ExecutionPlan = [pscustomobject]@{
                ExecutionMode = 'CPU_FROZEN'; ExecutionPlanSha256 = ''
                SourceManifestSha256 = ''; GpuSourceContractSha256 = ''
                Resume = $false; MaxParallelMatlab = 1; AuthorizedRunIds = @()
                AuthorizedTasks = @()
            }
            AuthorizedRunIds = @()
        }
    }
    [void](Assert-FrozenSageExecutionPlanPin -ExecutionPlanPath $ExecutionPlanPath)
    [void](Assert-FrozenSageGpuRuntimeReleasePins -SourceContractPath $SourceContractPath)
    if (-not (Test-Path -LiteralPath $ExecutionPlanPath -PathType Leaf)) {
        throw "GPU_EXECUTION_PLAN_NOT_FOUND path=$ExecutionPlanPath"
    }
    try {
        $planDocument = Get-Content -Raw -LiteralPath $ExecutionPlanPath -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "GPU_EXECUTION_PLAN_JSON_INVALID detail=$($_.Exception.Message)"
    }
    if ($planDocument.PSObject.Properties.Name -cnotcontains 'authorized_tasks' -or
        $null -eq $planDocument.authorized_tasks) {
        throw 'GPU_EXECUTION_PLAN_AUTHORIZED_TASKS_INVALID expected_nonempty_array'
    }
    $authorizedTasks = @($planDocument.authorized_tasks)
    $authorizedIds = @($authorizedTasks | ForEach-Object { [string]$_.run_id })
    if ($authorizedTasks.Count -eq 0 -or $authorizedIds -contains '') {
        throw 'GPU_EXECUTION_PLAN_AUTHORIZED_TASKS_INVALID expected_nonempty_task_objects'
    }
    $duplicateRunIds = @($authorizedIds | Group-Object | Where-Object Count -gt 1 | ForEach-Object Name)
    if ($duplicateRunIds.Count -gt 0) {
        throw "GPU_EXECUTION_PLAN_DUPLICATE_AUTHORIZED_RUN_ID ids=$($duplicateRunIds -join ',')"
    }
    $validatedPlan = $null
    foreach ($authorizedId in $authorizedIds) {
        $rowCount = @($ManifestRows | Where-Object { [string]$_.run_id -ceq $authorizedId }).Count
        if ($rowCount -ne 1) {
            throw "GPU_EXECUTION_PLAN_MANIFEST_RUN_ID_NOT_UNIQUE run_id=$authorizedId count=$rowCount"
        }
        $resolved = Resolve-FrozenSageExecutionPlan `
            -ExecutionPlanPath $ExecutionPlanPath `
            -RunId $authorizedId `
            -ManifestPath $ManifestPath `
            -SourceContractPath $SourceContractPath
        if ($null -eq $validatedPlan) { $validatedPlan = $resolved }
    }
    $batchBaseline = $script:FrozenBatchBaselineRunId
    if ($authorizedIds -ccontains $batchBaseline) {
        throw "GPU_EXECUTION_PLAN_RUN_ID_ALREADY_COMPLETE run_id=$batchBaseline"
    }
    $validatedPlan | Add-Member -NotePropertyName AuthorizedRunIds -NotePropertyValue $authorizedIds -Force
    $validatedPlan | Add-Member -NotePropertyName AuthorizedTasks -NotePropertyValue $authorizedTasks -Force
    return [pscustomobject]@{
        ExecutionPlan = $validatedPlan
        AuthorizedRunIds = $authorizedIds
    }
}

function Assert-FrozenSageGpuParallelPilotNotAllowed {
    param([AllowNull()][string]$ExecutionPlanPath)
    if ([string]::IsNullOrWhiteSpace($ExecutionPlanPath)) { return $true }
    [void](Assert-FrozenSageExecutionPlanPin -ExecutionPlanPath $ExecutionPlanPath)
    $sourcePaths = Get-FrozenSageGpuSourcePaths
    [void](Assert-FrozenSageGpuRuntimeReleasePins -SourceContractPath $sourcePaths.SourceContract)
    if (-not (Test-Path -LiteralPath $ExecutionPlanPath -PathType Leaf)) {
        throw "GPU_EXECUTION_PLAN_NOT_FOUND path=$ExecutionPlanPath"
    }
    try {
        $plan = Get-Content -Raw -LiteralPath $ExecutionPlanPath -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    } catch {
        throw "GPU_EXECUTION_PLAN_JSON_INVALID detail=$($_.Exception.Message)"
    }
    if ([string]$plan.execution_mode -ceq 'GPU_STAGE2_QUALIFIED') {
        throw 'GPU_PARALLEL_PILOT_NOT_ALLOWED max_parallel_matlab_must_be_1'
    }
    return $true
}

function Assert-FrozenSageNoActiveRunnerLocks {
    param([Parameter(Mandatory)][string]$ProjectRoot)

    $candidatePaths = @(
        (Join-Path $ProjectRoot 'scripts\sage_pipeline\.windows_runner_active.lock'),
        (Join-Path $ProjectRoot 'scripts\sage_pipeline\.unattended_runner_active.lock'),
        (Join-Path $ProjectRoot 'dataset_generation_logs\batch_sage_execution\.windows_runner_active.lock'),
        (Join-Path $ProjectRoot 'dataset_generation_logs\batch_sage_execution\.frozen_sage_batch_active.lock'),
        (Join-Path $ProjectRoot 'scripts\sage_pipeline\.frozen_sage_batch_active.lock')
    )
    $present = @($candidatePaths | Where-Object {
        (Test-Path -LiteralPath $_ -PathType Leaf) -and
        -not [string]::Equals($_, $script:FrozenBatchOwnedLockPath, [System.StringComparison]::OrdinalIgnoreCase)
    })
    $taskLockDirectory = Join-Path $ProjectRoot 'dataset_generation_logs\batch_sage_execution'
    if (Test-Path -LiteralPath $taskLockDirectory -PathType Container) {
        $present += @(Get-ChildItem -LiteralPath $taskLockDirectory -Filter '.windows_runner_active_*.lock' -File -ErrorAction Stop |
            ForEach-Object { $_.FullName } | Where-Object {
                -not [string]::Equals($_, $script:FrozenBatchOwnedLockPath, [System.StringComparison]::OrdinalIgnoreCase)
            })
    }
    if ($present.Count -gt 0) {
        throw ('ACTIVE_RUNNER_LOCK_PRESENT paths=' + ($present -join ';'))
    }
    return $true
}

function ConvertTo-FrozenSageInteger {
    param(
        [Parameter(Mandatory)][AllowEmptyString()][string]$Value,
        [Parameter(Mandatory)][string]$FieldName
    )

    $parsed = 0L
    if (-not [long]::TryParse($Value, [System.Globalization.NumberStyles]::Integer,
            [System.Globalization.CultureInfo]::InvariantCulture, [ref]$parsed)) {
        throw "STAGE_CSV_INVALID_INTEGER field=$FieldName value=$Value"
    }
    return $parsed
}

function Import-FrozenSageStageCsv {
    param(
        [Parameter(Mandatory)][string]$OutputPath,
        [Parameter(Mandatory)][string]$FileName,
        [Parameter(Mandatory)][string[]]$RequiredColumns
    )

    $path = Join-Path $OutputPath $FileName
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "STAGE_CSV_MISSING path=$path"
    }
    $headerLine = Get-Content -LiteralPath $path -TotalCount 1 -ErrorAction Stop
    if ([string]::IsNullOrWhiteSpace($headerLine)) {
        throw "STAGE_CSV_HEADER_MISSING path=$path"
    }
    $headers = @($headerLine.TrimStart([char]0xFEFF).Split(',') | ForEach-Object { $_.Trim().Trim('"') })
    foreach ($required in $RequiredColumns) {
        if ($headers -notcontains $required) {
            throw "STAGE_CSV_SCHEMA_MISMATCH file=$FileName missing_column=$required"
        }
    }
    return @(Import-Csv -LiteralPath $path -ErrorAction Stop)
}

function Get-FrozenSageTaskMetrics {
    param([Parameter(Mandatory)][string]$OutputPath)

    $stage0Symbols = @(Import-FrozenSageStageCsv -OutputPath $OutputPath -FileName 'stage0_valid_symbols.csv' -RequiredColumns @('symbol_id'))
    $stage0Windows = @(Import-FrozenSageStageCsv -OutputPath $OutputPath -FileName 'stage0_valid_40ms_windows.csv' -RequiredColumns @('window_id'))
    $stage1 = @(Import-FrozenSageStageCsv -OutputPath $OutputPath -FileName 'stage1_nav_fast_scan.csv' -RequiredColumns @('window_id'))
    $stage2Orders = @(Import-FrozenSageStageCsv -OutputPath $OutputPath -FileName 'stage2_model_orders.csv' -RequiredColumns @('window_id'))
    $stage2Paths = @(Import-FrozenSageStageCsv -OutputPath $OutputPath -FileName 'stage2_selected_paths.csv' -RequiredColumns @('window_id', 'path_id', 'is_multipath'))
    $stage3Rows = @(Import-FrozenSageStageCsv -OutputPath $OutputPath -FileName 'stage3_persistence.csv' -RequiredColumns @('center_window_id', 'multipath_id', 'persistence_pass'))
    $stage4Summary = @(Import-FrozenSageStageCsv -OutputPath $OutputPath -FileName 'stage4_joint_summary.csv' -RequiredColumns @('center_window_id', 'joint_valid', 'joint_multipath_count', 'joint_selected_L'))
    $stage4Paths = @(Import-FrozenSageStageCsv -OutputPath $OutputPath -FileName 'stage4_joint_paths.csv' -RequiredColumns @('center_window_id', 'path_id', 'is_multipath'))

    $stage2WindowIds = @($stage2Orders | ForEach-Object { [string]$_.window_id } | Sort-Object -Unique)
    $directPaths = @($stage2Paths | Where-Object {
        (ConvertTo-FrozenSageInteger -Value ([string]$_.is_multipath) -FieldName 'stage2_selected_paths.is_multipath') -eq 0
    })
    $multipathRows = @($stage2Paths | Where-Object {
        (ConvertTo-FrozenSageInteger -Value ([string]$_.is_multipath) -FieldName 'stage2_selected_paths.is_multipath') -eq 1
    })
    if (($directPaths.Count + $multipathRows.Count) -ne $stage2Paths.Count) {
        throw 'STAGE2_PATH_CLASSIFICATION_MISMATCH is_multipath must be exactly 0 or 1.'
    }

    $stage2MpcByKey = @{}
    foreach ($path in $multipathRows) {
        $windowId = ConvertTo-FrozenSageInteger -Value ([string]$path.window_id) -FieldName 'stage2_selected_paths.window_id'
        $pathId = ConvertTo-FrozenSageInteger -Value ([string]$path.path_id) -FieldName 'stage2_selected_paths.path_id'
        $key = '{0}:{1}' -f $windowId, $pathId
        if ($stage2MpcByKey.ContainsKey($key)) {
            throw "STAGE2_PATH_IDENTITY_DUPLICATE key=$key"
        }
        $stage2MpcByKey[$key] = $path
    }

    $stage3PersistentKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $stage3SeenKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($row in $stage3Rows) {
        $center = ConvertTo-FrozenSageInteger -Value ([string]$row.center_window_id) -FieldName 'stage3_persistence.center_window_id'
        $multipathId = ConvertTo-FrozenSageInteger -Value ([string]$row.multipath_id) -FieldName 'stage3_persistence.multipath_id'
        $pass = ConvertTo-FrozenSageInteger -Value ([string]$row.persistence_pass) -FieldName 'stage3_persistence.persistence_pass'
        $key = '{0}:{1}' -f $center, ($multipathId + 1)
        if (-not $stage3SeenKeys.Add($key)) {
            throw "STAGE3_PATH_IDENTITY_DUPLICATE key=$key"
        }
        if ($pass -eq 1 -and $stage2MpcByKey.ContainsKey($key)) {
            [void]$stage3PersistentKeys.Add($key)
        }
    }

    $stage4SummaryByCenter = @{}
    foreach ($row in $stage4Summary) {
        $center = ConvertTo-FrozenSageInteger -Value ([string]$row.center_window_id) -FieldName 'stage4_joint_summary.center_window_id'
        $key = [string]$center
        if ($stage4SummaryByCenter.ContainsKey($key)) {
            throw "STAGE4_SUMMARY_CENTER_DUPLICATE center_window_id=$center"
        }
        $stage4SummaryByCenter[$key] = $row
    }
    $stage4PathByKey = @{}
    foreach ($row in $stage4Paths) {
        $center = ConvertTo-FrozenSageInteger -Value ([string]$row.center_window_id) -FieldName 'stage4_joint_paths.center_window_id'
        $pathId = ConvertTo-FrozenSageInteger -Value ([string]$row.path_id) -FieldName 'stage4_joint_paths.path_id'
        $isMultipath = ConvertTo-FrozenSageInteger -Value ([string]$row.is_multipath) -FieldName 'stage4_joint_paths.is_multipath'
        $key = '{0}:{1}' -f $center, $pathId
        if ($stage4PathByKey.ContainsKey($key)) {
            throw "STAGE4_PATH_IDENTITY_DUPLICATE key=$key"
        }
        $stage4PathByKey[$key] = [pscustomobject]@{ IsMultipath = $isMultipath }
    }

    $stage4ConfirmedCount = 0
    foreach ($key in $stage3PersistentKeys) {
        $parts = $key.Split(':')
        $center = [string]$parts[0]
        $pathId = [long]$parts[1]
        if (-not $stage4SummaryByCenter.ContainsKey($center) -or -not $stage4PathByKey.ContainsKey($key)) {
            continue
        }
        $joint = $stage4SummaryByCenter[$center]
        $jointValid = ConvertTo-FrozenSageInteger -Value ([string]$joint.joint_valid) -FieldName 'stage4_joint_summary.joint_valid'
        $jointMpcCount = ConvertTo-FrozenSageInteger -Value ([string]$joint.joint_multipath_count) -FieldName 'stage4_joint_summary.joint_multipath_count'
        $jointSelectedL = ConvertTo-FrozenSageInteger -Value ([string]$joint.joint_selected_L) -FieldName 'stage4_joint_summary.joint_selected_L'
        if ($jointValid -eq 1 -and $jointMpcCount -gt 0 -and $jointSelectedL -ge $pathId -and
            $stage4PathByKey[$key].IsMultipath -eq 1) {
            $stage4ConfirmedCount++
        }
    }

    return [pscustomobject][ordered]@{
        stage0_valid_nav_symbols = [long]$stage0Symbols.Count
        stage0_valid_40ms_windows = [long]$stage0Windows.Count
        stage1_scanned_windows = [long]$stage1.Count
        stage2_evaluated_windows = [long]$stage2WindowIds.Count
        stage2_selected_path_count = [long]$stage2Paths.Count
        direct_path_count = [long]$directPaths.Count
        stage2_mpc_count = [long]$multipathRows.Count
        stage3_persistence_row_count = [long]$stage3Rows.Count
        stage3_persistent_mpc_count = [long]$stage3PersistentKeys.Count
        stage4_joint_result_count = [long]$stage4Summary.Count
        stage4_confirmed_mpc_count = [long]$stage4ConfirmedCount
    }
}

function Get-FrozenSageRetentionRatio {
    param(
        [Parameter(Mandatory)][long]$Numerator,
        [Parameter(Mandatory)][long]$Denominator
    )

    if ($Numerator -lt 0 -or $Denominator -lt 0 -or $Numerator -gt $Denominator) {
        throw "RETENTION_COUNTS_INVALID numerator=$Numerator denominator=$Denominator"
    }
    if ($Denominator -eq 0) {
        return 'NA'
    }
    return ($Numerator / [double]$Denominator).ToString('0.########', [System.Globalization.CultureInfo]::InvariantCulture)
}

function Write-FrozenSageBatchSummary {
    param(
        [Parameter(Mandatory)][string]$SummaryPath,
        [Parameter(Mandatory)][object[]]$Rows,
        [Parameter(Mandatory)][AllowEmptyString()][string]$ExpectedCurrentHash
    )

    $columns = @(Get-FrozenSageBatchSummaryColumns)
    $runIds = @($Rows | ForEach-Object { [string]$_.run_id })
    if ($runIds.Count -ne @($runIds | Sort-Object -Unique).Count) {
        throw 'BATCH_SUMMARY_DUPLICATE_RUN_ID'
    }
    $parent = Split-Path -Parent $SummaryPath
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        throw "BATCH_SUMMARY_PARENT_MISSING path=$parent"
    }

    if (Test-Path -LiteralPath $SummaryPath -PathType Leaf) {
        if ([string]::IsNullOrWhiteSpace($ExpectedCurrentHash)) {
            throw "BATCH_SUMMARY_ALREADY_EXISTS_UNOWNED path=$SummaryPath"
        }
        $actual = (Get-FileHash -LiteralPath $SummaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if (-not [string]::Equals($actual, $ExpectedCurrentHash, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "BATCH_SUMMARY_OWNERSHIP_HASH_MISMATCH expected=$ExpectedCurrentHash actual=$actual"
        }
    } elseif (-not [string]::IsNullOrWhiteSpace($ExpectedCurrentHash)) {
        throw "BATCH_SUMMARY_MISSING_EXPECTED_PRIOR_HASH hash=$ExpectedCurrentHash"
    }

    $normalizedRows = foreach ($row in $Rows) {
        $values = [ordered]@{}
        foreach ($column in $columns) {
            $property = $row.PSObject.Properties[$column]
            $values[$column] = if ($null -eq $property -or $null -eq $property.Value) { '' } else { $property.Value }
        }
        [pscustomobject]$values
    }
    $tempPath = Join-Path $parent ('.{0}.{1}.pending' -f (Split-Path -Leaf $SummaryPath), [guid]::NewGuid().ToString('N'))
    $normalizedRows | Export-Csv -LiteralPath $tempPath -NoTypeInformation -Encoding utf8NoBOM -ErrorAction Stop
    if (Test-Path -LiteralPath $SummaryPath -PathType Leaf) {
        [System.IO.File]::Move($tempPath, $SummaryPath, $true)
    } else {
        [System.IO.File]::Move($tempPath, $SummaryPath, $false)
    }
    $newHash = (Get-FileHash -LiteralPath $SummaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
    return [pscustomobject]@{ Sha256 = $newHash; RowCount = $Rows.Count; Path = $SummaryPath }
}

function Get-FrozenSageBaselineSummaryRow {
    param(
        [Parameter(Mandatory)][object]$ManifestRow,
        [Parameter(Mandatory)][string]$OutputPath,
        [Parameter(Mandatory)][string]$RegressionReportPath
    )

    if ([string]$ManifestRow.run_id -cne $script:FrozenBatchBaselineRunId -or
        [string]$ManifestRow.scene_id -cne 'F1023_V70_D0117_P2' -or
        [string]$ManifestRow.prn -cne 'G28' -or [int]$ManifestRow.tracking_channel -ne 1) {
        throw 'BASELINE_MANIFEST_IDENTITY_MISMATCH'
    }
    if (-not (Test-Path -LiteralPath $RegressionReportPath -PathType Leaf) -or
        -not (Select-String -LiteralPath $RegressionReportPath -Pattern '^BASELINE_REGRESSION=PASS_EXACT\s*$' -Quiet)) {
        throw 'BASELINE_REGRESSION_NOT_PASS_EXACT'
    }
    [void](Assert-StageOutputsComplete -OutputPath $OutputPath)
    $receiptPath = Join-Path $OutputPath 'relocation_receipt.json'
    if (-not (Test-Path -LiteralPath $receiptPath -PathType Leaf)) {
        throw "BASELINE_RELOCATION_RECEIPT_MISSING path=$receiptPath"
    }
    $receipt = Get-Content -Raw -LiteralPath $receiptPath | ConvertFrom-Json -ErrorAction Stop
    $expectedFinal = [System.IO.Path]::GetFullPath((Join-Path $script:FrozenBatchProjectRoot ([string]$ManifestRow.output_namespace)))
    $receiptFinal = [string]$receipt.final_relocated_path
    if (-not [System.IO.Path]::IsPathRooted($receiptFinal)) {
        $receiptFinal = Join-Path $script:FrozenBatchProjectRoot $receiptFinal
    }
    if (-not [string]::Equals([System.IO.Path]::GetFullPath($receiptFinal), $expectedFinal, [System.StringComparison]::OrdinalIgnoreCase) -or
        [string]$receipt.scene_id -cne [string]$ManifestRow.scene_id -or [int]$receipt.prn -ne 28 -or
        [int]$receipt.tracking_channel -ne 1 -or [string]$receipt.frozen_sage_sha256 -cne [string]$ManifestRow.frozen_sage_sha256 -or
        [string]$receipt.relocation_status -cne 'VERIFIED_SAME_VOLUME_MOVE' -or [bool]$receipt.resume -or
        [int]$receipt.matlab_exit_code -ne 0) {
        throw 'BASELINE_RELOCATION_RECEIPT_MISMATCH'
    }
    $metrics = Get-FrozenSageTaskMetrics -OutputPath $OutputPath
    if ($metrics.stage0_valid_nav_symbols -le 0 -or $metrics.stage0_valid_40ms_windows -le 0) {
        throw 'BASELINE_STAGE0_EMPTY'
    }
    return New-FrozenSageBatchSummaryRow -ManifestRow $ManifestRow -Status 'ALREADY_COMPLETE' -Metrics $metrics -MatlabExitCode 0 -FailureReason ''
}

function Get-FrozenSageFailureDisposition {
    param(
        [Parameter(Mandatory)][string]$FailureReason,
        [Parameter(Mandatory)][bool]$RunnerProcessEnded,
        [Parameter(Mandatory)][bool]$MatlabStarted,
        [Parameter(Mandatory)][bool]$MatlabProcessEnded
    )

    if (-not $RunnerProcessEnded) {
        return 'STOP_BATCH'
    }
    if ($FailureReason -in @(
        'GPU_GLOBAL_LOCK_PRESENT', 'GPU_SOURCE_IDENTITY_MISMATCH', 'GPU_NOT_AVAILABLE',
        'GPU_INITIALIZATION_FAILED', 'GPU_STAGE2_MATLAB_FAILURE'
    )) {
        return 'STOP_BATCH'
    }
    $inputFailures = @(
        'REQUIRED_INPUT_MISSING', 'RAW_IQ_MISSING', 'RAW_IQ_EMPTY', 'RAW_IQ_SIZE_MISMATCH',
        'SCENE_METADATA_MISMATCH', 'SCENE_METADATA_INVALID', 'RAW_PATH_METADATA_MISMATCH'
    )
    if ($FailureReason -in $inputFailures -and -not $MatlabStarted) {
        return 'CONTINUE_TASK'
    }
    if ($FailureReason -in @('STAGE0_NO_VALID_NAV_SYMBOLS', 'STAGE0_NO_VALID_40MS_WINDOWS') -and
        $MatlabStarted -and $MatlabProcessEnded) {
        return 'CONTINUE_TASK'
    }
    return 'STOP_BATCH'
}

function Get-FrozenSageDirectoryMetrics {
    param([Parameter(Mandatory)][string]$Path)

    $allItems = @(Get-ChildItem -LiteralPath $Path -Force -Recurse -ErrorAction Stop)
    $reparsePoints = @($allItems | Where-Object { ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 })
    if ($reparsePoints.Count -gt 0) {
        throw "FAILED_STAGING_REPARSE_POINT_FOUND path=$($reparsePoints[0].FullName)"
    }
    $files = @($allItems | Where-Object { -not $_.PSIsContainer })
    $bytes = [long]0
    foreach ($file in $files) { $bytes += [long]$file.Length }
    return [pscustomobject]@{ FileCount = [int]$files.Count; ByteCount = $bytes }
}

function Move-FrozenSageFailedStaging {
    param(
        [Parameter(Mandatory)][string]$StagingPath,
        [Parameter(Mandatory)][string]$FinalDestinationPath,
        [Parameter(Mandatory)][string]$DiagnosticDestinationPath,
        [Parameter(Mandatory)][string]$SceneId,
        [Parameter(Mandatory)][string]$PrnLabel,
        [Parameter(Mandatory)][int]$TrackingChannel,
        [Parameter(Mandatory)][string]$RunId,
        [Parameter(Mandatory)][string]$FailureReason,
        [Parameter(Mandatory)][bool]$RunnerProcessEnded,
        [Parameter(Mandatory)][bool]$MatlabStarted,
        [Parameter(Mandatory)][int]$MatlabProcessId,
        [Parameter(Mandatory)][bool]$MatlabProcessEnded,
        [Parameter(Mandatory)][int]$MatlabExitCode
    )

    $disposition = Get-FrozenSageFailureDisposition -FailureReason $FailureReason -RunnerProcessEnded $RunnerProcessEnded `
        -MatlabStarted $MatlabStarted -MatlabProcessEnded $MatlabProcessEnded
    if ($disposition -ne 'CONTINUE_TASK' -or -not $MatlabStarted -or -not $MatlabProcessEnded -or
        $FailureReason -notin @('STAGE0_NO_VALID_NAV_SYMBOLS', 'STAGE0_NO_VALID_40MS_WINDOWS')) {
        throw "FAILED_STAGING_MOVE_NOT_AUTHORIZED disposition=$disposition reason=$FailureReason"
    }
    if (-not (Test-Path -LiteralPath $StagingPath -PathType Container)) {
        throw "FAILED_STAGING_SOURCE_MISSING path=$StagingPath"
    }
    if (Test-Path -LiteralPath $FinalDestinationPath) {
        throw "FAILED_STAGING_FINAL_DESTINATION_EXISTS path=$FinalDestinationPath"
    }
    if (Test-Path -LiteralPath $DiagnosticDestinationPath) {
        throw "FAILED_STAGING_DIAGNOSTIC_DESTINATION_EXISTS path=$DiagnosticDestinationPath"
    }
    if (-not [string]::Equals((Split-Path -Qualifier $StagingPath), (Split-Path -Qualifier $DiagnosticDestinationPath), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "FAILED_STAGING_MOVE_CROSS_VOLUME source=$StagingPath destination=$DiagnosticDestinationPath"
    }
    $sourceFull = [System.IO.Path]::GetFullPath($StagingPath).TrimEnd('\')
    foreach ($candidate in @($FinalDestinationPath, $DiagnosticDestinationPath)) {
        $candidateFull = [System.IO.Path]::GetFullPath($candidate).TrimEnd('\')
        if ($candidateFull.StartsWith($sourceFull + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "FAILED_STAGING_DESTINATION_INSIDE_SOURCE destination=$candidateFull"
        }
    }
    $sourceMetrics = Get-FrozenSageDirectoryMetrics -Path $StagingPath
    $diagnosticParent = Split-Path -Parent $DiagnosticDestinationPath
    if (-not (Test-Path -LiteralPath $diagnosticParent -PathType Container)) {
        [void](New-Item -ItemType Directory -Path $diagnosticParent -ErrorAction Stop)
    }
    if (Test-Path -LiteralPath $DiagnosticDestinationPath) {
        throw "FAILED_STAGING_DIAGNOSTIC_DESTINATION_COLLISION path=$DiagnosticDestinationPath"
    }
    $failureUtc = [System.DateTimeOffset]::UtcNow
    Move-Item -LiteralPath $StagingPath -Destination $DiagnosticDestinationPath -ErrorAction Stop
    if ((Test-Path -LiteralPath $StagingPath) -or -not (Test-Path -LiteralPath $DiagnosticDestinationPath -PathType Container)) {
        throw 'FAILED_STAGING_MOVE_VERIFICATION_FAILED'
    }
    $destinationMetrics = Get-FrozenSageDirectoryMetrics -Path $DiagnosticDestinationPath
    if ($sourceMetrics.FileCount -ne $destinationMetrics.FileCount -or $sourceMetrics.ByteCount -ne $destinationMetrics.ByteCount) {
        throw "FAILED_STAGING_MOVE_METRICS_MISMATCH source_files=$($sourceMetrics.FileCount) destination_files=$($destinationMetrics.FileCount) source_bytes=$($sourceMetrics.ByteCount) destination_bytes=$($destinationMetrics.ByteCount)"
    }
    $receiptPath = Join-Path $DiagnosticDestinationPath 'failure_quarantine_receipt.json'
    if (Test-Path -LiteralPath $receiptPath) {
        throw "FAILED_STAGING_RECEIPT_COLLISION path=$receiptPath"
    }
    $receipt = [ordered]@{
        scene_id = $SceneId
        prn = $PrnLabel
        tracking_channel = $TrackingChannel
        run_id = $RunId
        failure_timestamp_utc = $failureUtc.ToString('o')
        failure_reason = $FailureReason
        source_staging_path = $StagingPath
        diagnostic_destination = $DiagnosticDestinationPath
        file_count = $sourceMetrics.FileCount
        byte_count = $sourceMetrics.ByteCount
        destination_file_count = $destinationMetrics.FileCount
        destination_byte_count = $destinationMetrics.ByteCount
        runner_process_ended = $RunnerProcessEnded
        matlab_started = $MatlabStarted
        matlab_process_id = $MatlabProcessId
        matlab_process_ended = $MatlabProcessEnded
        matlab_exit_code = $MatlabExitCode
        move_method = 'Move-Item'
        resume = $false
        failed_staging_reused_as_input = $false
    }
    [System.IO.File]::WriteAllText($receiptPath, ($receipt | ConvertTo-Json -Depth 5) + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    return [pscustomobject]@{
        DiagnosticDestination = $DiagnosticDestinationPath
        ReceiptPath = $receiptPath
        FileCount = $sourceMetrics.FileCount
        ByteCount = $sourceMetrics.ByteCount
    }
}

function New-FrozenSageBatchSummaryRow {
    param(
        [Parameter(Mandatory)][object]$ManifestRow,
        [Parameter(Mandatory)][string]$Status,
        [object]$Metrics,
        [AllowNull()][object]$MatlabExitCode,
        [string]$FailureReason = ''
    )

    $row = [ordered]@{
        run_id = [string]$ManifestRow.run_id
        scene_id = [string]$ManifestRow.scene_id
        prn = [string]$ManifestRow.prn
        tracking_channel = [string]$ManifestRow.tracking_channel
        mapping_warning = [string]$ManifestRow.mapping_warning
        execution_status = $Status
        matlab_exit_code = if ($null -eq $MatlabExitCode) { '' } else { [string]$MatlabExitCode }
        stage0_valid_nav_symbols = ''
        stage0_valid_40ms_windows = ''
        stage1_scanned_windows = ''
        stage2_evaluated_windows = ''
        stage2_selected_path_count = ''
        direct_path_count = ''
        stage2_mpc_count = ''
        stage3_persistence_row_count = ''
        stage3_persistent_mpc_count = ''
        stage4_joint_result_count = ''
        stage4_confirmed_mpc_count = ''
        output_namespace = [string]$ManifestRow.output_namespace
        frozen_sage_sha256 = [string]$ManifestRow.frozen_sage_sha256
        failure_reason = $FailureReason
    }
    if ($null -ne $Metrics) {
        foreach ($name in @($Metrics.PSObject.Properties.Name)) { $row[$name] = [string]$Metrics.$name }
    }
    return [pscustomobject]$row
}

function Get-FrozenSageBatchAggregates {
    param([Parameter(Mandatory)][object[]]$Rows)

    $completed = @($Rows | Where-Object { [string]$_.execution_status -in @('ALREADY_COMPLETE', 'COMPLETE') })
    $attempted = @($Rows | Where-Object { [string]$_.execution_status -in @('IN_PROGRESS', 'COMPLETE', 'FAILED') -and [string]$_.execution_status -ne 'ALREADY_COMPLETE' })
    $failed = @($Rows | Where-Object { [string]$_.execution_status -eq 'FAILED' })
    $warnings = @($Rows | Where-Object { [string]$_.mapping_warning -eq 'NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING' })
    $warningAttempted = @($warnings | Where-Object { [string]$_.execution_status -in @('IN_PROGRESS', 'COMPLETE', 'FAILED') })
    $warningCompleted = @($warnings | Where-Object { [string]$_.execution_status -eq 'COMPLETE' })
    $warningFailed = @($warnings | Where-Object { [string]$_.execution_status -eq 'FAILED' })
    $sums = @{}
    foreach ($field in @('direct_path_count', 'stage2_mpc_count', 'stage3_persistent_mpc_count', 'stage4_confirmed_mpc_count')) {
        $sum = [long]0
        foreach ($row in $completed) {
            if (-not [string]::IsNullOrWhiteSpace([string]$row.$field)) { $sum += [long]$row.$field }
        }
        $sums[$field] = $sum
    }
    $newComplete = @($Rows | Where-Object { [string]$_.execution_status -eq 'COMPLETE' }).Count
    $totalComplete = $completed.Count
    $stage2ToStage3 = Get-FrozenSageRetentionRatio -Numerator $sums.stage3_persistent_mpc_count -Denominator $sums.stage2_mpc_count
    $stage3ToStage4 = Get-FrozenSageRetentionRatio -Numerator $sums.stage4_confirmed_mpc_count -Denominator $sums.stage3_persistent_mpc_count
    return [pscustomobject][ordered]@{
        TOTAL_PLANNED = $Rows.Count
        ALREADY_COMPLETE = @($Rows | Where-Object { [string]$_.execution_status -eq 'ALREADY_COMPLETE' }).Count
        NEW_ATTEMPTED = $attempted.Count
        NEW_COMPLETE = $newComplete
        FAILED = $failed.Count
        TOTAL_COMPLETE = $totalComplete
        MAPPING_WARNING_ATTEMPTED = $warningAttempted.Count
        MAPPING_WARNING_COMPLETE = $warningCompleted.Count
        MAPPING_WARNING_FAILED = $warningFailed.Count
        TOTAL_DIRECT_PATH_ROWS = $sums.direct_path_count
        TOTAL_STAGE2_MPC = $sums.stage2_mpc_count
        TOTAL_STAGE3_PERSISTENT_MPC = $sums.stage3_persistent_mpc_count
        TOTAL_STAGE4_CONFIRMED_MPC = $sums.stage4_confirmed_mpc_count
        STAGE2_TO_STAGE3_RETENTION = $stage2ToStage3
        STAGE3_TO_STAGE4_RETENTION = $stage3ToStage4
        MODELING_POPULATION = 'ALL_STAGE2_MULTIPATH'
        STAGE3_MODELING_GATE = 'NO'
        STAGE4_MODELING_GATE = 'NO'
        CIR_BULK_EXPORT = 'NO'
        CIR_REVIEW_BRANCH = ''
        CIR_REVIEW_COMMIT = ''
        _pending = @($Rows | Where-Object { [string]$_.execution_status -eq 'PENDING' }).Count
    }
}

function Get-FrozenSagePlanScopeCompletion {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object[]]$Rows,
        [Parameter(Mandatory)][string[]]$AuthorizedRunIds,
        [string]$StopReason = ''
    )

    if ($AuthorizedRunIds.Count -eq 0 -or $AuthorizedRunIds.Count -ne @($AuthorizedRunIds | Sort-Object -Unique).Count) {
        throw 'GPU_EXECUTION_PLAN_AUTHORIZED_RUN_IDS_INVALID'
    }
    $authorizedRows = foreach ($runId in $AuthorizedRunIds) {
        $matches = @($Rows | Where-Object { [string]$_.run_id -ceq [string]$runId })
        if ($matches.Count -ne 1) {
            throw "GPU_EXECUTION_PLAN_SUMMARY_RUN_ID_NOT_UNIQUE run_id=$runId count=$($matches.Count)"
        }
        $matches[0]
    }
    $authorizedComplete = @($authorizedRows | Where-Object { [string]$_.execution_status -ceq 'COMPLETE' }).Count
    $authorizedFailed = @($authorizedRows | Where-Object { [string]$_.execution_status -ceq 'FAILED' }).Count
    $authorizedPending = @($authorizedRows | Where-Object { [string]$_.execution_status -in @('PENDING', 'IN_PROGRESS') }).Count
    $globalAggregates = Get-FrozenSageBatchAggregates -Rows $Rows

    if (-not [string]::IsNullOrWhiteSpace($StopReason)) {
        $finalStatus = 'STOPPED'
        $resolvedStopReason = $StopReason
    } elseif ($authorizedPending -gt 0) {
        $finalStatus = 'STOPPED'
        $resolvedStopReason = 'PLAN_SCOPE_INCOMPLETE'
    } elseif ($authorizedFailed -gt 0) {
        $finalStatus = 'PLAN_SCOPE_COMPLETED_WITH_FAILURES'
        $resolvedStopReason = ''
    } else {
        $finalStatus = 'PLAN_SCOPE_COMPLETED'
        $resolvedStopReason = ''
    }

    return [pscustomobject][ordered]@{
        FinalStatus = $finalStatus
        StopReason = $resolvedStopReason
        AuthorizedTaskCount = $AuthorizedRunIds.Count
        AuthorizedCompleteCount = $authorizedComplete
        AuthorizedFailedCount = $authorizedFailed
        GlobalCompleteCount = $globalAggregates.TOTAL_COMPLETE
        GlobalPendingCount = $globalAggregates._pending
    }
}

function Format-FrozenSageBatchAggregates {
    param([Parameter(Mandatory)][object]$Aggregates)
    foreach ($property in $Aggregates.PSObject.Properties) {
        if ($property.Name.StartsWith('_')) { continue }
        '{0}={1}' -f $property.Name, $property.Value
    }
    '20_46_MHZ_EXECUTED=NO'
    'BUSINESS_BRANCH_COMMIT_PUSH=NO'
}

function Get-FrozenSageTaskSpecificInputReason {
    param([Parameter(Mandatory)][string]$Text)
    foreach ($reason in @('REQUIRED_INPUT_MISSING', 'RAW_IQ_MISSING', 'RAW_IQ_EMPTY', 'RAW_IQ_SIZE_MISMATCH', 'SCENE_METADATA_MISMATCH', 'SCENE_METADATA_INVALID', 'RAW_PATH_METADATA_MISMATCH')) {
        if ($Text -match ('(?m)(?:^|\s|\[ERROR\]\s*)' + [regex]::Escape($reason) + '(?:\s|$)')) { return $reason }
    }
    return $null
}

function Assert-FrozenSageNoMatlabProcess {
    $active = @(Get-Process -Name 'MATLAB' -ErrorAction SilentlyContinue)
    if ($active.Count -gt 0) {
        throw ('ACTIVE_MATLAB_PROCESS_PRESENT pids=' + (($active | ForEach-Object { $_.Id }) -join ','))
    }
    return $true
}

function Get-FrozenSageBatchManifestContext {
    param([Parameter(Mandatory)][string]$ProjectRoot)

    $manifestPath = Join-Path $ProjectRoot $script:FrozenBatchManifestRelativePath
    $auditPath = Join-Path $ProjectRoot $script:FrozenBatchAuditRelativePath
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf) -or -not (Test-Path -LiteralPath $auditPath -PathType Leaf)) {
        throw 'BATCH_MANIFEST_OR_DATASET_AUDIT_MISSING'
    }
    $rows = @(Import-Csv -LiteralPath $manifestPath -ErrorAction Stop)
    if ($rows.Count -ne $script:FrozenBatchExpectedTaskCount) {
        throw "BATCH_MANIFEST_ROW_COUNT_MISMATCH expected=$script:FrozenBatchExpectedTaskCount actual=$($rows.Count)"
    }
    $runIds = @($rows | ForEach-Object { [string]$_.run_id })
    $keyIds = @($rows | ForEach-Object { '{0}|{1}|{2}' -f $_.scene_id, $_.prn, $_.tracking_channel })
    if ($runIds.Count -ne @($runIds | Sort-Object -Unique).Count -or $keyIds.Count -ne @($keyIds | Sort-Object -Unique).Count) {
        throw 'BATCH_MANIFEST_DUPLICATE_TASK_IDENTITY'
    }
    $baseline = @($rows | Where-Object { [string]$_.run_id -ceq $script:FrozenBatchBaselineRunId })
    if ($baseline.Count -ne 1) { throw "BATCH_BASELINE_ROW_CARDINALITY expected=1 actual=$($baseline.Count)" }
    foreach ($row in $rows) { [void](Assert-FrozenSageManifestRow -Row $row -ExpectedRunId ([string]$row.run_id)) }
    $warnings = @($rows | Where-Object { [string]$_.mapping_warning -eq 'NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING' })
    if ($warnings.Count -ne 4) { throw "BATCH_MAPPING_WARNING_COUNT_MISMATCH expected=4 actual=$($warnings.Count)" }
    $otherWarnings = @($rows | Where-Object { [string]$_.mapping_warning -notin @('NONE', 'NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING') })
    if ($otherWarnings.Count -gt 0) { throw 'BATCH_UNSUPPORTED_MAPPING_WARNING_PRESENT' }
    return [pscustomobject]@{ Rows = $rows; Baseline = $baseline[0]; ManifestPath = $manifestPath; AuditPath = $auditPath }
}

function Read-And-ValidateExistingFrozenSageBatchSummary {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$SummaryPath,
        [Parameter(Mandatory)][object[]]$ManifestRows,
        [string[]]$AuthorizedRunIds = @()
    )

    if (-not (Test-Path -LiteralPath $SummaryPath -PathType Leaf)) {
        throw "BATCH_SUMMARY_MISSING path=$SummaryPath"
    }
    if ($ManifestRows.Count -ne $script:FrozenBatchExpectedTaskCount) {
        throw "BATCH_SUMMARY_MANIFEST_ROW_COUNT_MISMATCH expected=$($script:FrozenBatchExpectedTaskCount) actual=$($ManifestRows.Count)"
    }

    $manifestRunIds = @($ManifestRows | ForEach-Object { [string]$_.run_id })
    $manifestRunIdSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($runId in $manifestRunIds) {
        if ([string]::IsNullOrEmpty($runId)) { throw 'BATCH_SUMMARY_MANIFEST_RUN_ID_MISSING' }
        if (-not $manifestRunIdSet.Add($runId)) { throw 'BATCH_SUMMARY_MANIFEST_DUPLICATE_RUN_ID' }
    }

    $hashBeforeRead = (Get-FileHash -LiteralPath $SummaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $summaryRows = @(Import-Csv -LiteralPath $SummaryPath -ErrorAction Stop)
    if ($summaryRows.Count -ne $script:FrozenBatchExpectedTaskCount) {
        throw "BATCH_SUMMARY_ROW_COUNT_MISMATCH expected=$($script:FrozenBatchExpectedTaskCount) actual=$($summaryRows.Count)"
    }

    $expectedColumns = @(Get-FrozenSageBatchSummaryColumns)
    $actualColumns = @($summaryRows[0].PSObject.Properties.Name)
    if (($actualColumns -join ',') -cne ($expectedColumns -join ',')) {
        throw 'BATCH_SUMMARY_SCHEMA_MISMATCH'
    }

    $summaryRunIds = @($summaryRows | ForEach-Object { [string]$_.run_id })
    $summaryRunIdSet = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($runId in $summaryRunIds) {
        if ([string]::IsNullOrEmpty($runId)) { throw 'BATCH_SUMMARY_RUN_ID_MISSING' }
        if (-not $summaryRunIdSet.Add($runId)) { throw 'BATCH_SUMMARY_DUPLICATE_RUN_ID' }
    }

    if ($summaryRunIdSet.Count -ne $manifestRunIdSet.Count) { throw 'BATCH_SUMMARY_RUN_ID_SET_MISMATCH' }
    foreach ($runId in $manifestRunIds) {
        if (-not $summaryRunIdSet.Contains($runId)) { throw 'BATCH_SUMMARY_RUN_ID_SET_MISMATCH' }
    }
    foreach ($runId in $summaryRunIds) {
        if (-not $manifestRunIdSet.Contains($runId)) { throw 'BATCH_SUMMARY_RUN_ID_SET_MISMATCH' }
    }

    $expectedSummaryRunIds = @($script:FrozenBatchBaselineRunId) + @(
        $manifestRunIds | Where-Object { $_ -cne $script:FrozenBatchBaselineRunId }
    )
    if ($expectedSummaryRunIds.Count -ne $summaryRunIds.Count) { throw 'BATCH_SUMMARY_RUN_ID_SET_MISMATCH' }
    for ($index = 0; $index -lt $expectedSummaryRunIds.Count; $index++) {
        if ($summaryRunIds[$index] -cne $expectedSummaryRunIds[$index]) {
            throw "BATCH_SUMMARY_CANONICAL_ORDER_MISMATCH index=$($index + 1) expected=$($expectedSummaryRunIds[$index]) actual=$($summaryRunIds[$index])"
        }
    }

    $identityFields = @('run_id', 'scene_id', 'prn', 'tracking_channel', 'mapping_warning', 'output_namespace', 'frozen_sage_sha256')
    foreach ($summaryRow in $summaryRows) {
        $matchingManifestRows = @($ManifestRows | Where-Object { [string]$_.run_id -ceq [string]$summaryRow.run_id })
        if ($matchingManifestRows.Count -ne 1) {
            throw "BATCH_SUMMARY_MANIFEST_RUN_ID_CARDINALITY run_id=$($summaryRow.run_id) expected=1 actual=$($matchingManifestRows.Count)"
        }
        $manifestRow = $matchingManifestRows[0]
        foreach ($field in $identityFields) {
            $summaryProperty = $summaryRow.PSObject.Properties[$field]
            $manifestProperty = $manifestRow.PSObject.Properties[$field]
            if ($null -eq $summaryProperty -or $null -eq $manifestProperty -or
                [string]$summaryProperty.Value -cne [string]$manifestProperty.Value) {
                throw "BATCH_SUMMARY_MANIFEST_IDENTITY_MISMATCH field=$field run_id=$($manifestRow.run_id)"
            }
        }
    }

    $baselineRows = @($summaryRows | Where-Object { [string]$_.run_id -ceq $script:FrozenBatchBaselineRunId })
    if ($baselineRows.Count -ne 1 -or [string]$baselineRows[0].execution_status -cne 'ALREADY_COMPLETE') {
        throw 'BATCH_SUMMARY_BASELINE_STATUS_INVALID expected=ALREADY_COMPLETE'
    }

    foreach ($row in $summaryRows) {
        $runId = [string]$row.run_id
        $status = [string]$row.execution_status
        if ($runId -ceq $script:FrozenBatchBaselineRunId) { continue }
        if ($status -cnotin @('COMPLETE', 'PENDING')) {
            throw "BATCH_SUMMARY_STATUS_NOT_RESUMABLE run_id=$runId status=$status"
        }
    }

    $authorizedIds = @($AuthorizedRunIds)
    if ($authorizedIds.Count -ne @($authorizedIds | Sort-Object -Unique).Count) {
        throw 'GPU_EXECUTION_PLAN_DUPLICATE_AUTHORIZED_RUN_ID'
    }
    foreach ($runId in $authorizedIds) {
        $matchingRows = @($summaryRows | Where-Object { [string]$_.run_id -ceq [string]$runId })
        if ($matchingRows.Count -ne 1 -or [string]$matchingRows[0].execution_status -cne 'PENDING') {
            $status = if ($matchingRows.Count -eq 1) { [string]$matchingRows[0].execution_status } else { 'MISSING_OR_DUPLICATE' }
            throw "GPU_EXECUTION_PLAN_TASK_NOT_PENDING run_id=$runId status=$status"
        }
    }

    $validatedHash = (Get-FileHash -LiteralPath $SummaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if (-not [string]::Equals($hashBeforeRead, $validatedHash, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "BATCH_SUMMARY_CHANGED_DURING_VALIDATION before=$hashBeforeRead after=$validatedHash"
    }
    return [pscustomobject]@{
        SummaryRows = $summaryRows
        Sha256 = $validatedHash
        RowCount = $summaryRows.Count
        BaselineCount = $baselineRows.Count
        CompleteCount = @($summaryRows | Where-Object { [string]$_.execution_status -eq 'COMPLETE' }).Count
        PendingCount = @($summaryRows | Where-Object { [string]$_.execution_status -eq 'PENDING' }).Count
    }
}

function Resolve-FrozenSageBatchSummaryState {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$SummaryPath,
        [Parameter(Mandatory)][object[]]$ManifestRows,
        [Parameter(Mandatory)][object]$BaselineSummaryRow,
        [Parameter(Mandatory)][bool]$PlanProvided,
        [string[]]$AuthorizedRunIds = @()
    )

    if ((Test-Path -LiteralPath $SummaryPath) -and -not (Test-Path -LiteralPath $SummaryPath -PathType Leaf)) {
        throw "BATCH_SUMMARY_PATH_NOT_FILE path=$SummaryPath"
    }
    $allNewRows = @($ManifestRows | Where-Object { [string]$_.run_id -cne $script:FrozenBatchBaselineRunId })
    $authorizedIds = @($AuthorizedRunIds)
    if ($PlanProvided) {
        if ($authorizedIds.Count -eq 0) { throw 'GPU_EXECUTION_PLAN_HAS_NO_PENDING_MANIFEST_RUN_IDS' }
        if ($authorizedIds.Count -ne @($authorizedIds | Sort-Object -Unique).Count) {
            throw 'GPU_EXECUTION_PLAN_DUPLICATE_AUTHORIZED_RUN_ID'
        }
        if ($authorizedIds -ccontains $script:FrozenBatchBaselineRunId) {
            throw "GPU_EXECUTION_PLAN_RUN_ID_ALREADY_COMPLETE run_id=$script:FrozenBatchBaselineRunId"
        }
        $executionRows = foreach ($runId in $authorizedIds) {
            $matchingRows = @($allNewRows | Where-Object { [string]$_.run_id -ceq [string]$runId })
            if ($matchingRows.Count -ne 1) {
                throw "GPU_EXECUTION_PLAN_MANIFEST_RUN_ID_NOT_UNIQUE run_id=$runId count=$($matchingRows.Count)"
            }
            $matchingRows[0]
        }
    } else {
        if ($authorizedIds.Count -gt 0) { throw 'GPU_AUTHORIZED_RUN_IDS_REQUIRE_EXECUTION_PLAN' }
        $executionRows = @($allNewRows)
    }

    if (Test-Path -LiteralPath $SummaryPath -PathType Leaf) {
        if (-not $PlanProvided) {
            throw "BATCH_SUMMARY_ALREADY_EXISTS path=$SummaryPath; an explicit validated execution plan is required to continue."
        }
        $validated = Read-And-ValidateExistingFrozenSageBatchSummary `
            -SummaryPath $SummaryPath -ManifestRows $ManifestRows -AuthorizedRunIds $authorizedIds
        $summaryRows = [System.Collections.Generic.List[object]]::new()
        foreach ($row in $validated.SummaryRows) { $summaryRows.Add($row) }
        return [pscustomobject]@{
            IsExistingSummary = $true
            SummaryRows = $summaryRows
            ExpectedCurrentHash = $validated.Sha256
            AllNewRows = $allNewRows
            ExecutionRows = @($executionRows)
            SummaryValidation = $validated
        }
    }

    $summaryRows = [System.Collections.Generic.List[object]]::new()
    $summaryRows.Add($BaselineSummaryRow)
    foreach ($row in $allNewRows) {
        $summaryRows.Add((New-FrozenSageBatchSummaryRow -ManifestRow $row -Status 'PENDING'))
    }
    return [pscustomobject]@{
        IsExistingSummary = $false
        SummaryRows = $summaryRows
        ExpectedCurrentHash = ''
        AllNewRows = $allNewRows
        ExecutionRows = @($executionRows)
        SummaryValidation = $null
    }
}

function Get-FrozenSageTaskPaths {
    param(
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][object]$ManifestRow
    )
    $staging = Join-Path $ProjectRoot ('scenes\{0}\sage_results\nav_sage_v2\{1}' -f [string]$ManifestRow.scene_id, [string]$ManifestRow.prn)
    $final = Join-Path $ProjectRoot ([string]$ManifestRow.output_namespace)
    return [pscustomobject]@{ StagingPath = $staging; FinalPath = $final }
}

function Assert-FrozenSageAllOutputNamespacesAbsent {
    param(
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][object[]]$ManifestRows,
        [Parameter(Mandatory)][string]$BaselineRunId
    )
    $checkedStage = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($row in $ManifestRows | Where-Object { [string]$_.run_id -cne $BaselineRunId }) {
        $paths = Get-FrozenSageTaskPaths -ProjectRoot $ProjectRoot -ManifestRow $row
        if (Test-Path -LiteralPath $paths.FinalPath) {
            throw "OUTPUT_NAMESPACE_ALREADY_EXISTS path=$($paths.FinalPath)"
        }
        if ($checkedStage.Add($paths.StagingPath) -and (Test-Path -LiteralPath $paths.StagingPath)) {
            throw "LEGACY_STAGING_NAMESPACE_ALREADY_EXISTS path=$($paths.StagingPath)"
        }
    }
    return $true
}

function Start-FrozenSageSingleTaskProcess {
    param(
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][string]$RunId,
        [AllowNull()][string]$ExecutionPlanPath
    )
    $childPowerShell = Join-Path $PSHOME 'pwsh.exe'
    if (-not (Test-Path -LiteralPath $childPowerShell -PathType Leaf)) { throw "POWERSHELL_CHILD_EXECUTABLE_MISSING path=$childPowerShell" }
    $singleRunner = Join-Path $PSScriptRoot 'Invoke-FrozenSageRerunSingle.ps1'
    if (-not (Test-Path -LiteralPath $singleRunner -PathType Leaf)) { throw "SINGLE_TASK_RUNNER_MISSING path=$singleRunner" }
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $childPowerShell
    $startInfo.WorkingDirectory = $ProjectRoot
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    foreach ($argument in @('-NoProfile', '-File', $singleRunner, '-RunId', $RunId)) { [void]$startInfo.ArgumentList.Add($argument) }
    if (-not [string]::IsNullOrWhiteSpace($ExecutionPlanPath)) {
        [void]$startInfo.ArgumentList.Add('-ExecutionPlanPath')
        [void]$startInfo.ArgumentList.Add([System.IO.Path]::GetFullPath($ExecutionPlanPath))
    }
    [void]$startInfo.ArgumentList.Add('-Execute')
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    if (-not $process.Start()) { throw "SINGLE_TASK_RUNNER_START_FAILED run_id=$RunId" }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $ended = $process.HasExited
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    return [pscustomobject]@{
        ProcessId = [int]$process.Id
        ProcessEnded = [bool]$ended
        ExitCode = [int]$process.ExitCode
        Stdout = $stdout
        Stderr = $stderr
        CombinedOutput = $stdout + [Environment]::NewLine + $stderr
    }
}

function Assert-FrozenSageSuccessfulTask {
    param(
        [Parameter(Mandatory)][object]$ManifestRow,
        [Parameter(Mandatory)][object]$ChildResult,
        [Parameter(Mandatory)][string]$ProjectRoot,
        [string]$ExecutionMode = 'CPU_FROZEN'
    )
    if (-not $ChildResult.ProcessEnded -or $ChildResult.ExitCode -ne 0) {
        throw "SINGLE_TASK_RUNNER_FAILED exit_code=$($ChildResult.ExitCode) process_ended=$($ChildResult.ProcessEnded)"
    }
    $output = [string]$ChildResult.CombinedOutput
    foreach ($marker in @('PREFLIGHT_PASS', 'MATLAB_STARTUP_SMOKE_PASS', 'MATLAB_ARGUMENT_TRANSPORT_SMOKE_PASS', 'EXECUTION_GATES_REVERIFIED', 'SAGE_EXECUTION_BEGIN', 'RELOCATION_VERIFIED')) {
        if (-not $output.Contains($marker)) { throw "SINGLE_TASK_SUCCESS_MARKER_MISSING marker=$marker run_id=$($ManifestRow.run_id)" }
    }
    if (-not $output.Contains("mapping_warning=$($ManifestRow.mapping_warning)") -or -not $output.Contains('resume=false')) {
        throw "SINGLE_TASK_WARNING_OR_RESUME_EVIDENCE_MISSING run_id=$($ManifestRow.run_id)"
    }
    if (-not $output.Contains("FROZEN_SAGE_SHA_AFTER=$($ManifestRow.frozen_sage_sha256)")) {
        throw "SINGLE_TASK_POST_RUN_HASH_EVIDENCE_MISSING run_id=$($ManifestRow.run_id)"
    }
    if ($ExecutionMode -eq 'GPU_STAGE2_QUALIFIED' -and
        (-not $output.Contains('GPU_PREFLIGHT_PASS') -or
         -not $output.Contains('execution_mode=GPU_STAGE2_QUALIFIED'))) {
        throw "GPU_TASK_SUCCESS_MARKER_MISSING run_id=$($ManifestRow.run_id)"
    }
    $paths = Get-FrozenSageTaskPaths -ProjectRoot $ProjectRoot -ManifestRow $ManifestRow
    [void](Assert-StageOutputsComplete -OutputPath $paths.FinalPath)
    [void](Assert-FrozenSageStage0Ready -StagingPath $paths.FinalPath)
    $receiptPath = Join-Path $paths.FinalPath 'relocation_receipt.json'
    $lockReceiptPath = Join-Path $paths.FinalPath 'windows_runner_lock_receipt.json'
    if (-not (Test-Path -LiteralPath $receiptPath -PathType Leaf) -or -not (Test-Path -LiteralPath $lockReceiptPath -PathType Leaf)) {
        throw "SINGLE_TASK_RELOCATION_RECEIPT_MISSING run_id=$($ManifestRow.run_id)"
    }
    $receipt = Get-Content -Raw -LiteralPath $receiptPath | ConvertFrom-Json -ErrorAction Stop
    $expectedFinalPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot ([string]$ManifestRow.output_namespace)))
    $receiptFinalPath = [System.IO.Path]::GetFullPath([string]$receipt.final_relocated_path)
    $matlabStartUtc = [System.DateTimeOffset]::MinValue
    $matlabEndUtc = [System.DateTimeOffset]::MinValue
    if ([int]$receipt.matlab_process_id -le 0 -or
        -not [System.DateTimeOffset]::TryParse([string]$receipt.matlab_start_utc, [ref]$matlabStartUtc) -or
        -not [System.DateTimeOffset]::TryParse([string]$receipt.matlab_end_utc, [ref]$matlabEndUtc) -or
        $matlabEndUtc -le $matlabStartUtc) {
        throw "SINGLE_TASK_MATLAB_PROCESS_EVIDENCE_INVALID run_id=$($ManifestRow.run_id)"
    }
    if ([string]$receipt.relocation_status -cne 'VERIFIED_SAME_VOLUME_MOVE' -or [int]$receipt.matlab_exit_code -ne 0 -or
        [bool]$receipt.resume -or [string]$receipt.frozen_sage_sha256 -cne [string]$ManifestRow.frozen_sage_sha256 -or
        [string]$receipt.scene_id -cne [string]$ManifestRow.scene_id -or [int]$receipt.prn -ne [int]([string]$ManifestRow.prn -replace '^G', '') -or
        [int]$receipt.tracking_channel -ne [int]$ManifestRow.tracking_channel -or
        -not [string]::Equals($receiptFinalPath, $expectedFinalPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "SINGLE_TASK_RELOCATION_RECEIPT_INVALID run_id=$($ManifestRow.run_id)"
    }
    if ($ExecutionMode -eq 'GPU_STAGE2_QUALIFIED') {
        $provenancePath = Join-Path $paths.FinalPath 'gpu_execution_provenance.json'
        if ([string]$receipt.execution_mode -cne 'GPU_STAGE2_QUALIFIED' -or
            -not [string]::Equals([System.IO.Path]::GetFullPath([string]$receipt.gpu_execution_provenance_path),
                [System.IO.Path]::GetFullPath($provenancePath), [System.StringComparison]::OrdinalIgnoreCase) -or
            -not (Test-Path -LiteralPath $provenancePath -PathType Leaf) -or
            [string]$receipt.gpu_execution_provenance_sha256 -cne
                (Get-FileHash -LiteralPath $provenancePath -Algorithm SHA256).Hash.ToLowerInvariant()) {
            throw "GPU_TASK_PROVENANCE_RECEIPT_INVALID run_id=$($ManifestRow.run_id)"
        }
    } elseif ($receipt.PSObject.Properties.Name -contains 'execution_mode') {
        throw "CPU_TASK_RECEIPT_HAS_GPU_FIELDS run_id=$($ManifestRow.run_id)"
    }
    $lockReceipt = Get-Content -Raw -LiteralPath $lockReceiptPath | ConvertFrom-Json -ErrorAction Stop
    if ([string]$lockReceipt.run_id -cne [string]$ManifestRow.run_id -or [string]$lockReceipt.scene_id -cne [string]$ManifestRow.scene_id -or
        [int]$lockReceipt.prn -ne [int]([string]$ManifestRow.prn -replace '^G', '') -or
        [int]$lockReceipt.tracking_channel -ne [int]$ManifestRow.tracking_channel -or
        [int]$lockReceipt.process_id -ne [int]$ChildResult.ProcessId -or
        [string]$lockReceipt.mapping_warning -cne [string]$ManifestRow.mapping_warning -or [bool]$lockReceipt.resume) {
        throw "SINGLE_TASK_RUNNER_LOCK_RECEIPT_INVALID run_id=$($ManifestRow.run_id)"
    }
    $metrics = Get-FrozenSageTaskMetrics -OutputPath $paths.FinalPath
    if ($metrics.stage0_valid_nav_symbols -le 0 -or $metrics.stage0_valid_40ms_windows -le 0) { throw 'STAGE0_SCIENTIFIC_FAILURE_AFTER_RELOCATION' }
    $sourceHash = (Get-FileHash -LiteralPath (Join-Path $ProjectRoot 'scripts\sage_pipeline\run_nav_sage_pipeline.m') -Algorithm SHA256).Hash.ToLowerInvariant()
    [void](Assert-FrozenSageHash -ActualHash $sourceHash -ExpectedHash ([string]$ManifestRow.frozen_sage_sha256))
    if (Test-Path -LiteralPath $paths.StagingPath) { throw "STAGING_REMAINS_AFTER_RELOCATION path=$($paths.StagingPath)" }
    return [pscustomobject]@{ OutputPath = $paths.FinalPath; Metrics = $metrics; Receipt = $receipt }
}

function Get-FrozenSageFailureEvidence {
    param(
        [Parameter(Mandatory)][object]$ManifestRow,
        [Parameter(Mandatory)][object]$ChildResult
    )
    $text = [string]$ChildResult.CombinedOutput
    $marker = [regex]::Match($text, '(?m)^CONTROLLED_FAILURE_LOCK_ARCHIVED\s+reason=(?<reason>\S+)\s+run_id=(?<run>\S+).*?receipt=(?<receipt>\S+)\s+matlab_started=(?<started>True|False)\s+matlab_process_id=(?<pid>\S+)\s+matlab_exit_code=(?<exit>\S+)\s+matlab_process_ended=(?<ended>True|False)\s*$')
    if ($marker.Success) {
        if ($marker.Groups['run'].Value -cne [string]$ManifestRow.run_id) { throw 'FAILURE_RECEIPT_RUN_ID_MISMATCH' }
        $receiptPath = $marker.Groups['receipt'].Value
        if (-not (Test-Path -LiteralPath $receiptPath -PathType Leaf)) { throw "FAILURE_RECEIPT_MISSING path=$receiptPath" }
        $receipt = Get-Content -Raw -LiteralPath $receiptPath | ConvertFrom-Json -ErrorAction Stop
        if ([string]$receipt.run_id -cne [string]$ManifestRow.run_id -or [int]$receipt.old_pid -ne [int]$ChildResult.ProcessId -or
            [string]$receipt.failure_reason -cne $marker.Groups['reason'].Value) { throw 'FAILURE_RECEIPT_IDENTITY_MISMATCH' }
        return [pscustomobject]@{
            FailureReason = [string]$receipt.failure_reason
            MatlabStarted = [bool]$receipt.matlab_started
            MatlabProcessId = if ($null -eq $receipt.matlab_process_id) { -1 } else { [int]$receipt.matlab_process_id }
            MatlabProcessEnded = [bool]$receipt.matlab_process_ended
            MatlabExitCode = if ($null -eq $receipt.matlab_exit_code) { -1 } else { [int]$receipt.matlab_exit_code }
            ReceiptPath = $receiptPath
            FailureTimestampUtc = [string]$receipt.archived_utc
        }
    }
    $gpuFailure = [regex]::Match($text, 'GPU_(?:GLOBAL_LOCK_PRESENT|SOURCE_IDENTITY_MISMATCH|NOT_AVAILABLE|INITIALIZATION_FAILED|STAGE2_MATLAB_FAILURE)')
    if ($gpuFailure.Success) {
        return [pscustomobject]@{
            FailureReason = $gpuFailure.Value
            MatlabStarted = $false; MatlabProcessId = -1
            MatlabProcessEnded = $false; MatlabExitCode = -1
            ReceiptPath = ''; FailureTimestampUtc = [System.DateTimeOffset]::UtcNow.ToString('o')
        }
    }
    $reason = Get-FrozenSageTaskSpecificInputReason -Text $text
    if ($null -ne $reason -and -not $text.Contains('PREFLIGHT_PASS')) {
        return [pscustomobject]@{
            FailureReason = $reason; MatlabStarted = $false; MatlabProcessId = -1
            MatlabProcessEnded = $false; MatlabExitCode = -1; ReceiptPath = ''; FailureTimestampUtc = [System.DateTimeOffset]::UtcNow.ToString('o')
        }
    }
    return [pscustomobject]@{
        FailureReason = 'UNCLASSIFIED_OR_SYSTEMIC_RUNNER_FAILURE'; MatlabStarted = $false; MatlabProcessId = -1
        MatlabProcessEnded = $false; MatlabExitCode = [int]$ChildResult.ExitCode; ReceiptPath = ''; FailureTimestampUtc = [System.DateTimeOffset]::UtcNow.ToString('o')
    }
}

function New-FrozenSageBatchLock {
    param(
        [Parameter(Mandatory)][string]$LockPath,
        [string]$ProjectRoot = $script:FrozenBatchProjectRoot
    )
    $payload = [ordered]@{
        process_id = $PID
        windows_identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        started_utc = [System.DateTimeOffset]::UtcNow.ToString('o')
        summary_path = Join-Path $ProjectRoot $script:FrozenBatchSummaryRelativePath
        frozen_source_sha256 = $script:FrozenSourceSha256
        resume = $false
        task_serialization = 'COORDINATOR_OWNS_SUMMARY;PER_RUN_WORKER_LOCKS'
    }
    $stream = [System.IO.File]::Open($LockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try {
        $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes(($payload | ConvertTo-Json -Depth 4) + [Environment]::NewLine)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally { $stream.Dispose() }
    return [pscustomobject]$payload
}

function Move-FrozenSageBatchLockToReceipt {
    param(
        [Parameter(Mandatory)][string]$LockPath,
        [Parameter(Mandatory)][string]$ReceiptRoot,
        [Parameter(Mandatory)][string]$FinalStatus,
        [Parameter(Mandatory)][string]$StopReason,
        [Parameter(Mandatory)][object]$Aggregates,
        [AllowNull()][object]$PlanScopeSummary = $null
    )
    if (-not (Test-Path -LiteralPath $LockPath -PathType Leaf)) { throw "BATCH_LOCK_MISSING path=$LockPath" }
    $timestamp = [System.DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
    $receiptDirectory = Join-Path $ReceiptRoot ("frozen_sage_batch_{0}_{1}" -f $FinalStatus.ToLowerInvariant(), $timestamp)
    if (Test-Path -LiteralPath $receiptDirectory) { throw "BATCH_RECEIPT_COLLISION path=$receiptDirectory" }
    [void](New-Item -ItemType Directory -Path $receiptDirectory -ErrorAction Stop)
    $lockDestination = Join-Path $receiptDirectory 'batch_active.lock'
    Move-Item -LiteralPath $LockPath -Destination $lockDestination -ErrorAction Stop
    $receipt = [ordered]@{
        final_status = $FinalStatus
        stop_reason = $StopReason
        completed_utc = [System.DateTimeOffset]::UtcNow.ToString('o')
        source_lock_path = $LockPath
        archived_lock_path = $lockDestination
        move_method = 'Move-Item'
        aggregate_status = $Aggregates
    }
    if ($null -ne $PlanScopeSummary) {
        $receipt['authorized_task_count'] = $PlanScopeSummary.AuthorizedTaskCount
        $receipt['authorized_complete_count'] = $PlanScopeSummary.AuthorizedCompleteCount
        $receipt['global_complete_count'] = $PlanScopeSummary.GlobalCompleteCount
        $receipt['global_pending_count'] = $PlanScopeSummary.GlobalPendingCount
    }
    $receiptPath = Join-Path $receiptDirectory 'batch_receipt.json'
    [System.IO.File]::WriteAllText($receiptPath, ($receipt | ConvertTo-Json -Depth 8) + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    return $receiptPath
}

function Select-FrozenSageParallelPilotTasks {
    param(
        [Parameter(Mandatory)][object[]]$ManifestRows,
        [Parameter(Mandatory)][object[]]$SummaryRows,
        [Parameter(Mandatory)][ValidateRange(1, 2)][int]$MaxParallel
    )
    if ($MaxParallel -ne 2) { throw 'PARALLEL_PILOT_MAX_PARALLEL_MUST_EQUAL_2' }
    $summaryByRunId = @{}
    foreach ($summary in $SummaryRows) {
        $runId = [string]$summary.run_id
        if ($summaryByRunId.ContainsKey($runId)) { throw "BATCH_SUMMARY_DUPLICATE_RUN_ID run_id=$runId" }
        $summaryByRunId[$runId] = $summary
    }
    $selected = [System.Collections.Generic.List[object]]::new()
    $stagingKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($row in $ManifestRows) {
        $runId = [string]$row.run_id
        if (-not $summaryByRunId.ContainsKey($runId) -or [string]$summaryByRunId[$runId].execution_status -cne 'PENDING') { continue }
        if ([string]$row.mapping_warning -cne 'NONE') { continue }
        if ($runId -ceq $script:FrozenBatchBaselineRunId) { continue }
        [void](Assert-FrozenSageManifestRow -Row $row -ExpectedRunId $runId)
        $key = '{0}|{1}' -f [string]$row.scene_id, [string]$row.prn
        if (-not $stagingKeys.Add($key)) { continue }
        $selected.Add($row)
        if ($selected.Count -eq $MaxParallel) { break }
    }
    if ($selected.Count -ne $MaxParallel) {
        throw "PARALLEL_PILOT_INSUFFICIENT_DISTINCT_READY_TASKS required=$MaxParallel available=$($selected.Count)"
    }
    return @($selected)
}

function New-FrozenSageSingleTaskProcessStartInfo {
    param(
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][string]$RunId,
        [AllowNull()][string]$ExecutionPlanPath
    )
    $childPowerShell = Join-Path $PSHOME 'pwsh.exe'
    if (-not (Test-Path -LiteralPath $childPowerShell -PathType Leaf)) {
        throw "POWERSHELL_CHILD_EXECUTABLE_MISSING path=$childPowerShell"
    }
    $singleRunner = Join-Path $PSScriptRoot 'Invoke-FrozenSageRerunSingle.ps1'
    if (-not (Test-Path -LiteralPath $singleRunner -PathType Leaf)) { throw "SINGLE_TASK_RUNNER_MISSING path=$singleRunner" }
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $childPowerShell
    $startInfo.WorkingDirectory = $ProjectRoot
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    foreach ($argument in @('-NoProfile', '-File', $singleRunner, '-RunId', $RunId)) {
        [void]$startInfo.ArgumentList.Add($argument)
    }
    if (-not [string]::IsNullOrWhiteSpace($ExecutionPlanPath)) {
        [void]$startInfo.ArgumentList.Add('-ExecutionPlanPath')
        [void]$startInfo.ArgumentList.Add([System.IO.Path]::GetFullPath($ExecutionPlanPath))
    }
    [void]$startInfo.ArgumentList.Add('-Execute')
    return $startInfo
}

function Start-FrozenSageSingleTaskProcessAsync {
    param(
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][string]$RunId,
        [AllowNull()][string]$ExecutionPlanPath
    )
    $startInfo = New-FrozenSageSingleTaskProcessStartInfo -ProjectRoot $ProjectRoot -RunId $RunId -ExecutionPlanPath $ExecutionPlanPath
    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $startedUtc = [System.DateTimeOffset]::UtcNow
    if (-not $process.Start()) { throw "SINGLE_TASK_RUNNER_START_FAILED run_id=$RunId" }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    return [pscustomobject]@{
        RunId = $RunId
        Process = $process
        ProcessId = [int]$process.Id
        StartedUtc = $startedUtc
        StdoutTask = $stdoutTask
        StderrTask = $stderrTask
    }
}

function Complete-FrozenSageSingleTaskProcessAsync {
    param([Parameter(Mandatory)][object]$Worker)
    $Worker.Process.WaitForExit()
    $endedUtc = [System.DateTimeOffset]::UtcNow
    $processEnded = [bool]$Worker.Process.HasExited
    $stdout = $Worker.StdoutTask.GetAwaiter().GetResult()
    $stderr = $Worker.StderrTask.GetAwaiter().GetResult()
    return [pscustomobject]@{
        RunId = [string]$Worker.RunId
        ProcessId = [int]$Worker.ProcessId
        ProcessEnded = $processEnded
        ExitCode = if ($processEnded) { [int]$Worker.Process.ExitCode } else { -1 }
        StartedUtc = $Worker.StartedUtc.ToString('o')
        EndedUtc = $endedUtc.ToString('o')
        Stdout = $stdout
        Stderr = $stderr
        CombinedOutput = $stdout + [Environment]::NewLine + $stderr
    }
}

function Invoke-FrozenSageBatchPostRunRecovery {
    param(
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][string]$RunId,
        [switch]$ValidateOnly
    )
    if ($RunId -cne 'run_20261003_F1023_V120_D0121_P2_G03_ch2') {
        throw "RECOVERY_RUN_ID_NOT_APPROVED run_id=$RunId"
    }
    [void](Assert-FrozenSageNoActiveRunnerLocks -ProjectRoot $ProjectRoot)
    [void](Assert-FrozenSageNoMatlabProcess)

    $sourcePath = Join-Path $ProjectRoot 'scripts\sage_pipeline\run_nav_sage_pipeline.m'
    $sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    [void](Assert-FrozenSageHash -ActualHash $sourceHash -ExpectedHash $script:FrozenSourceSha256)
    $manifestContext = Get-FrozenSageBatchManifestContext -ProjectRoot $ProjectRoot
    $manifestMatches = @($manifestContext.Rows | Where-Object { [string]$_.run_id -ceq $RunId })
    if ($manifestMatches.Count -ne 1) { throw "RECOVERY_MANIFEST_ROW_CARDINALITY expected=1 actual=$($manifestMatches.Count)" }
    $manifestRow = $manifestMatches[0]
    [void](Assert-FrozenSageManifestRow -Row $manifestRow -ExpectedRunId $RunId)
    if ([string]$manifestRow.scene_id -cne 'F1023_V120_D0121_P2' -or [string]$manifestRow.prn -cne 'G03' -or
        [int]$manifestRow.tracking_channel -ne 2 -or [string]$manifestRow.mapping_warning -cne 'NONE' -or
        [string]$manifestRow.resume -cne 'false') {
        throw 'RECOVERY_MANIFEST_IDENTITY_MISMATCH'
    }

    $summaryPath = Join-Path $ProjectRoot $script:FrozenBatchSummaryRelativePath
    if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) { throw 'RECOVERY_BATCH_SUMMARY_MISSING' }
    $summaryHashBefore = (Get-FileHash -LiteralPath $summaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $summaryRows = @(Import-Csv -LiteralPath $summaryPath -ErrorAction Stop)
    if ($summaryRows.Count -ne $script:FrozenBatchExpectedTaskCount) {
        throw "RECOVERY_SUMMARY_ROW_COUNT_MISMATCH expected=$($script:FrozenBatchExpectedTaskCount) actual=$($summaryRows.Count)"
    }
    $summaryRunIds = @($summaryRows | ForEach-Object { [string]$_.run_id })
    $manifestRunIds = @($manifestContext.Rows | ForEach-Object { [string]$_.run_id })
    if ($summaryRunIds.Count -ne @($summaryRunIds | Sort-Object -Unique).Count -or
        (@(Compare-Object -ReferenceObject $manifestRunIds -DifferenceObject $summaryRunIds).Count -ne 0)) {
        throw 'RECOVERY_SUMMARY_RUN_ID_SET_MISMATCH_OR_DUPLICATE'
    }
    $targetSummaryRows = @($summaryRows | Where-Object { [string]$_.run_id -ceq $RunId })
    if ($targetSummaryRows.Count -ne 1) { throw "RECOVERY_SUMMARY_TARGET_CARDINALITY expected=1 actual=$($targetSummaryRows.Count)" }
    $summaryRow = $targetSummaryRows[0]
    if ([string]$summaryRow.execution_status -cne 'FAILED' -or [string]$summaryRow.failure_reason -cne 'POST_RUN_VALIDATION_FAILURE' -or
        [string]$summaryRow.scene_id -cne [string]$manifestRow.scene_id -or [string]$summaryRow.prn -cne [string]$manifestRow.prn -or
        [int]$summaryRow.tracking_channel -ne [int]$manifestRow.tracking_channel -or
        [string]$summaryRow.output_namespace -cne [string]$manifestRow.output_namespace -or
        [string]$summaryRow.frozen_sage_sha256 -cne [string]$manifestRow.frozen_sage_sha256) {
        throw 'RECOVERY_SUMMARY_TARGET_STATE_OR_IDENTITY_MISMATCH'
    }
    if (@($summaryRows | Where-Object { [string]$_.execution_status -eq 'ALREADY_COMPLETE' }).Count -ne 1 -or
        @($summaryRows | Where-Object { [string]$_.execution_status -eq 'COMPLETE' }).Count -ne 0 -or
        @($summaryRows | Where-Object { [string]$_.execution_status -eq 'FAILED' }).Count -ne 1 -or
        @($summaryRows | Where-Object { [string]$_.execution_status -eq 'PENDING' }).Count -ne 87 -or
        @($summaryRows | Where-Object { [string]$_.execution_status -notin @('ALREADY_COMPLETE', 'COMPLETE', 'FAILED', 'PENDING') }).Count -ne 0) {
        throw 'RECOVERY_SUMMARY_STATUS_COUNTS_NOT_APPROVED'
    }

    $failureReceiptPath = Join-Path $ProjectRoot 'dataset_generation_logs\batch_sage_execution\frozen_sage_batch_receipts\frozen_sage_batch_stopped_20261004T130609973Z\batch_receipt.json'
    if (-not (Test-Path -LiteralPath $failureReceiptPath -PathType Leaf)) { throw 'RECOVERY_ORIGINAL_FALSE_FAILURE_RECEIPT_MISSING' }
    $failureReceipt = Get-Content -Raw -LiteralPath $failureReceiptPath -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
    $failureStopReason = [string]$failureReceipt.stop_reason
    if ([string]$failureReceipt.final_status -cne 'STOPPED' -or
        -not $failureStopReason.Contains('FROZEN_SAGE_SOURCE_HASH_MISMATCH') -or
        -not $failureStopReason.Contains('[string]@{') -or
        -not $failureStopReason.Contains("actual=$sourceHash") -or
        -not $failureStopReason.Contains("frozen_sage_sha256=$sourceHash")) {
        throw 'RECOVERY_ORIGINAL_FALSE_FAILURE_EVIDENCE_UNEXPECTED'
    }

    $paths = Get-FrozenSageTaskPaths -ProjectRoot $ProjectRoot -ManifestRow $manifestRow
    if (Test-Path -LiteralPath $paths.StagingPath) { throw "RECOVERY_STAGING_PATH_STILL_EXISTS path=$($paths.StagingPath)" }
    [void](Assert-StageOutputsComplete -OutputPath $paths.FinalPath)
    [void](Assert-FrozenSageStage0Ready -StagingPath $paths.FinalPath)
    $contextPath = Join-Path $paths.FinalPath 'run_context.json'
    $relocationPath = Join-Path $paths.FinalPath 'relocation_receipt.json'
    $runnerReceiptPath = Join-Path $paths.FinalPath 'windows_runner_lock_receipt.json'
    foreach ($receiptFile in @($contextPath, $relocationPath, $runnerReceiptPath)) {
        if (-not (Test-Path -LiteralPath $receiptFile -PathType Leaf)) { throw "RECOVERY_REQUIRED_RECEIPT_MISSING path=$receiptFile" }
    }
    $runContext = Get-Content -Raw -LiteralPath $contextPath | ConvertFrom-Json -ErrorAction Stop
    $expectedStagingPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot ('scenes\{0}\sage_results\nav_sage_v2\{1}' -f $manifestRow.scene_id, $manifestRow.prn)))
    if ([string]$runContext.sceneId -cne [string]$manifestRow.scene_id -or [string]$runContext.prnLabel -cne 'G03' -or
        [int]$runContext.prn -ne 3 -or [int]$runContext.trackingChannel -ne 2 -or
        [double]$runContext.samplingRateHz -ne 10230000 -or
        -not [string]::Equals([System.IO.Path]::GetFullPath([string]$runContext.outputDir), $expectedStagingPath, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw 'RECOVERY_RUN_CONTEXT_IDENTITY_MISMATCH'
    }

    $relocation = Get-Content -Raw -LiteralPath $relocationPath | ConvertFrom-Json -ErrorAction Stop
    $expectedFinalPath = [System.IO.Path]::GetFullPath($paths.FinalPath)
    $receiptFinalPath = [System.IO.Path]::GetFullPath([string]$relocation.final_relocated_path)
    if ([string]$relocation.scene_id -cne [string]$manifestRow.scene_id -or [int]$relocation.prn -ne 3 -or
        [int]$relocation.tracking_channel -ne 2 -or [string]$relocation.frozen_sage_sha256 -cne $sourceHash -or
        [bool]$relocation.resume -or [int]$relocation.matlab_exit_code -ne 0 -or
        [string]$relocation.relocation_status -cne 'VERIFIED_SAME_VOLUME_MOVE' -or
        -not [string]::Equals($receiptFinalPath, $expectedFinalPath, [System.StringComparison]::OrdinalIgnoreCase) -or
        [long]$relocation.source_file_count_before_move -ne 21 -or [long]$relocation.destination_file_count_after_move -ne 21 -or
        [long]$relocation.source_bytes_before_move -ne 753870 -or [long]$relocation.destination_bytes_after_move -ne 753870) {
        throw 'RECOVERY_RELOCATION_RECEIPT_INVALID'
    }
    $runnerReceipt = Get-Content -Raw -LiteralPath $runnerReceiptPath | ConvertFrom-Json -ErrorAction Stop
    if ([string]$runnerReceipt.run_id -cne $RunId -or [string]$runnerReceipt.scene_id -cne [string]$manifestRow.scene_id -or
        [int]$runnerReceipt.prn -ne 3 -or [int]$runnerReceipt.tracking_channel -ne 2 -or
        [string]$runnerReceipt.mapping_warning -cne 'NONE' -or [bool]$runnerReceipt.resume -or [int]$runnerReceipt.process_id -le 0) {
        throw 'RECOVERY_RUNNER_RECEIPT_INVALID'
    }

    $metrics = Get-FrozenSageTaskMetrics -OutputPath $paths.FinalPath
    $expectedMetrics = [ordered]@{
        stage0_valid_nav_symbols = 232; stage0_valid_40ms_windows = 230; stage1_scanned_windows = 230
        stage2_evaluated_windows = 96; stage2_selected_path_count = 142; direct_path_count = 96; stage2_mpc_count = 46
        stage3_persistence_row_count = 46; stage3_persistent_mpc_count = 9; stage4_joint_result_count = 8; stage4_confirmed_mpc_count = 0
    }
    foreach ($field in $expectedMetrics.Keys) {
        if ([long]$metrics.$field -ne [long]$expectedMetrics[$field]) {
            throw "RECOVERY_STAGE_METRIC_MISMATCH field=$field expected=$($expectedMetrics[$field]) actual=$($metrics.$field)"
        }
    }

    if ($ValidateOnly) {
        return [pscustomobject]@{
            G03RecoveryValidation = 'PASS'
            SummaryRecovery = 'NOT_STARTED_READ_ONLY_VALIDATION'
            RunId = $RunId
            SummaryStatusBefore = 'FAILED'
            SummaryRowCount = $summaryRows.Count
            FrozenShaActual = $sourceHash
            FrozenShaExpected = [string]$manifestRow.frozen_sage_sha256
            Metrics = $metrics
            FailureProvenanceReceipt = $failureReceiptPath
        }
    }

    $executionLogParent = Join-Path $ProjectRoot 'dataset_generation_logs\batch_sage_execution'
    $activeLockPath = Join-Path $executionLogParent '.frozen_sage_batch_active.lock'
    $batchLock = New-FrozenSageBatchLock -LockPath $activeLockPath -ProjectRoot $ProjectRoot
    $script:FrozenBatchOwnedLockPath = $activeLockPath
    $summaryWrite = $null
    $recoveryReceiptPath = ''
    $status = 'STOPPED'
    $stopReason = ''
    try {
        $summaryRow.execution_status = 'COMPLETE'
        $summaryRow.matlab_exit_code = '0'
        foreach ($field in $metrics.PSObject.Properties.Name) { $summaryRow.$field = [string]$metrics.$field }
        $summaryRow.failure_reason = ''
        $summaryWrite = Write-FrozenSageBatchSummary -SummaryPath $summaryPath -Rows $summaryRows -ExpectedCurrentHash $summaryHashBefore
        $afterRows = @(Import-Csv -LiteralPath $summaryPath -ErrorAction Stop)
        if ($afterRows.Count -ne $script:FrozenBatchExpectedTaskCount -or
            @($afterRows | Where-Object { [string]$_.run_id -ceq $RunId -and [string]$_.execution_status -ceq 'COMPLETE' }).Count -ne 1 -or
            @($afterRows | ForEach-Object { [string]$_.run_id } | Sort-Object -Unique).Count -ne $script:FrozenBatchExpectedTaskCount) {
            throw 'RECOVERY_SUMMARY_POST_WRITE_VALIDATION_FAILED'
        }
        $aggregates = Get-FrozenSageBatchAggregates -Rows $afterRows
        if ($aggregates.ALREADY_COMPLETE -ne 1 -or $aggregates.NEW_COMPLETE -ne 1 -or $aggregates._pending -ne 87 -or $aggregates.FAILED -ne 0) {
            throw 'RECOVERY_SUMMARY_POST_WRITE_COUNTS_MISMATCH'
        }
        $recoveryDirectory = Join-Path $executionLogParent ('frozen_sage_postrun_recovery_{0}_{1}' -f
            [System.DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'), [guid]::NewGuid().ToString('N'))
        if (Test-Path -LiteralPath $recoveryDirectory) { throw "RECOVERY_RECEIPT_DIRECTORY_COLLISION path=$recoveryDirectory" }
        [void](New-Item -ItemType Directory -Path $recoveryDirectory -ErrorAction Stop)
        $recoveryReceiptPath = Join-Path $recoveryDirectory 'recovery_receipt.json'
        $recoveryReceipt = [ordered]@{
            run_id = $RunId
            previous_summary_status = 'FAILED'
            recovered_summary_status = 'COMPLETE'
            recovery_reason = 'POSTRUN_SHA_VALIDATOR_PARAMETER_BINDING_FALSE_FAILURE'
            scientific_execution_status = 'SUCCESS'
            matlab_exit_code = 0
            stage_outputs_complete = 'YES'
            relocation_verified = 'YES'
            frozen_sha_actual = $sourceHash
            frozen_sha_expected = [string]$manifestRow.frozen_sage_sha256
            sage_rerun_performed = $false
            previous_failure_reason = 'POST_RUN_VALIDATION_FAILURE'
            previous_failure_receipt = $failureReceiptPath
            previous_failure_provenance_retained = $true
            summary_sha256_before = $summaryHashBefore
            summary_sha256_after = $summaryWrite.Sha256
            summary_row_count = $afterRows.Count
            recovered_utc = [System.DateTimeOffset]::UtcNow.ToString('o')
            metrics = $metrics
        }
        $receiptStream = [System.IO.File]::Open($recoveryReceiptPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        try {
            $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes(($recoveryReceipt | ConvertTo-Json -Depth 8) + [Environment]::NewLine)
            $receiptStream.Write($bytes, 0, $bytes.Length)
            $receiptStream.Flush($true)
        } finally { $receiptStream.Dispose() }
        $status = 'RECOVERED'
        Write-Verbose "G03_RECOVERY_VALIDATION=PASS run_id=$RunId"
        Write-Verbose "G03_SUMMARY_RECOVERY=PASS status=COMPLETE receipt=$recoveryReceiptPath"
    } catch {
        $stopReason = "POSTRUN_RECOVERY_FAILED:$($_.Exception.Message)"
        throw
    } finally {
        try {
            $currentRows = @(Import-Csv -LiteralPath $summaryPath -ErrorAction SilentlyContinue)
            $aggregates = if ($currentRows.Count -gt 0) { Get-FrozenSageBatchAggregates -Rows $currentRows } else { [pscustomobject]@{} }
            $receiptRoot = Join-Path $executionLogParent 'frozen_sage_batch_receipts'
            if (-not (Test-Path -LiteralPath $receiptRoot -PathType Container)) { [void](New-Item -ItemType Directory -Path $receiptRoot -ErrorAction Stop) }
            if (Test-Path -LiteralPath $activeLockPath -PathType Leaf) {
                $lockReceiptPath = Move-FrozenSageBatchLockToReceipt -LockPath $activeLockPath -ReceiptRoot $receiptRoot `
                    -FinalStatus $status -StopReason $(if ($stopReason -eq '') { 'NONE' } else { $stopReason }) -Aggregates $aggregates
                Write-Verbose "RECOVERY_COORDINATOR_LOCK_RECEIPT=$lockReceiptPath"
            }
        } finally { $script:FrozenBatchOwnedLockPath = '' }
    }
    return [pscustomobject]@{
        G03RecoveryValidation = 'PASS'
        SummaryRecovery = 'PASS'
        RecoveryReceipt = $recoveryReceiptPath
        SummaryPath = $summaryPath
        SummaryRowCount = $script:FrozenBatchExpectedTaskCount
    }
}

function Invoke-FrozenSageParallelPilot {
    param(
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][ValidateRange(2, 2)][int]$MaxParallel
    )
    if (-not [string]::Equals([System.IO.Path]::GetFullPath($ProjectRoot), (Get-Location).Path, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "PROJECT_ROOT_MISMATCH expected=$ProjectRoot actual=$((Get-Location).Path)"
    }
    [void](Assert-FrozenSageNoActiveRunnerLocks -ProjectRoot $ProjectRoot)
    [void](Assert-FrozenSageNoMatlabProcess)
    $sourcePath = Join-Path $ProjectRoot 'scripts\sage_pipeline\run_nav_sage_pipeline.m'
    $sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    [void](Assert-FrozenSageHash -ActualHash $sourceHash -ExpectedHash $script:FrozenSourceSha256)

    $context = Get-FrozenSageBatchManifestContext -ProjectRoot $ProjectRoot
    $summaryPath = Join-Path $ProjectRoot $script:FrozenBatchSummaryRelativePath
    if (-not (Test-Path -LiteralPath $summaryPath -PathType Leaf)) { throw 'PARALLEL_PILOT_SUMMARY_MISSING' }
    $summaryHash = (Get-FileHash -LiteralPath $summaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $summaryRows = @(Import-Csv -LiteralPath $summaryPath -ErrorAction Stop)
    if ($summaryRows.Count -ne $script:FrozenBatchExpectedTaskCount) { throw 'PARALLEL_PILOT_SUMMARY_ROW_COUNT_MISMATCH' }
    $summaryRunIds = @($summaryRows | ForEach-Object { [string]$_.run_id })
    $manifestRunIds = @($context.Rows | ForEach-Object { [string]$_.run_id })
    if ($summaryRunIds.Count -ne @($summaryRunIds | Sort-Object -Unique).Count -or
        (@(Compare-Object -ReferenceObject $manifestRunIds -DifferenceObject $summaryRunIds).Count -ne 0)) {
        throw 'PARALLEL_PILOT_SUMMARY_RUN_ID_SET_MISMATCH'
    }
    $g03Rows = @($summaryRows | Where-Object { [string]$_.run_id -ceq 'run_20261003_F1023_V120_D0121_P2_G03_ch2' })
    if ($g03Rows.Count -ne 1 -or [string]$g03Rows[0].execution_status -cne 'COMPLETE' -or
        @($summaryRows | Where-Object { [string]$_.execution_status -eq 'ALREADY_COMPLETE' }).Count -ne 1 -or
        @($summaryRows | Where-Object { [string]$_.execution_status -eq 'COMPLETE' }).Count -ne 1 -or
        @($summaryRows | Where-Object { [string]$_.execution_status -eq 'PENDING' }).Count -ne 87 -or
        @($summaryRows | Where-Object { [string]$_.execution_status -eq 'FAILED' }).Count -ne 0 -or
        @($summaryRows | Where-Object { [string]$_.execution_status -eq 'IN_PROGRESS' }).Count -ne 0) {
        throw 'PARALLEL_PILOT_REQUIRES_RECOVERED_SUMMARY_STATE'
    }
    $selected = @(Select-FrozenSageParallelPilotTasks -ManifestRows $context.Rows -SummaryRows $summaryRows -MaxParallel $MaxParallel)
    if ($selected.Count -ne 2 -or @($selected | ForEach-Object run_id | Sort-Object -Unique).Count -ne 2) {
        throw 'PARALLEL_PILOT_DUPLICATE_DISPATCH_SELECTION'
    }
    $stagingKeys = @($selected | ForEach-Object { '{0}|{1}' -f $_.scene_id, $_.prn })
    if (@($stagingKeys | Sort-Object -Unique).Count -ne 2) { throw 'PARALLEL_PILOT_STAGING_KEY_COLLISION' }
    $preflights = @{}
    foreach ($row in $selected) {
        [void](Assert-FrozenSageManifestRow -Row $row -ExpectedRunId ([string]$row.run_id))
        $preflight = Get-FrozenSagePreflight -RunId ([string]$row.run_id)
        if ([string]$preflight.MappingWarning -cne 'NONE' -or [long]$preflight.SampleRateHz -ne $script:FrozenSampleRateHz) {
            throw "PARALLEL_PILOT_TASK_NOT_READY run_id=$($row.run_id)"
        }
        $preflights[[string]$row.run_id] = $preflight
    }
    [void](Assert-FrozenSageAllOutputNamespacesAbsent -ProjectRoot $ProjectRoot -ManifestRows $selected -BaselineRunId '__NO_BASELINE__')
    [void](Assert-FrozenSageNoActiveRunnerLocks -ProjectRoot $ProjectRoot)
    [void](Assert-FrozenSageNoMatlabProcess)

    $executionLogParent = Join-Path $ProjectRoot 'dataset_generation_logs\batch_sage_execution'
    $activeLockPath = Join-Path $executionLogParent '.frozen_sage_batch_active.lock'
    $batchLock = New-FrozenSageBatchLock -LockPath $activeLockPath -ProjectRoot $ProjectRoot
    $script:FrozenBatchOwnedLockPath = $activeLockPath
    $batchLockSafeToMove = $true
    $summaryConflict = $false
    $stagingCollision = $false
    $duplicateDispatch = $false
    $overlapConfirmed = $false
    $maxSimultaneousMatlab = 0
    $batchStatus = 'PILOT_FAILED'
    $stopReason = ''
    $workers = [System.Collections.Generic.List[object]]::new()
    $completedWorkers = @{}
    $validatedTasks = @{}
    $taskStatuses = @{}
    $pilotReceiptPath = ''
    try {
        foreach ($row in $selected) {
            $summaryRow = @($summaryRows | Where-Object { [string]$_.run_id -ceq [string]$row.run_id })[0]
            $summaryRow.execution_status = 'IN_PROGRESS'
            $taskStatuses[[string]$row.run_id] = 'IN_PROGRESS'
        }
        try {
            $checkpoint = Write-FrozenSageBatchSummary -SummaryPath $summaryPath -Rows $summaryRows -ExpectedCurrentHash $summaryHash
            $summaryHash = $checkpoint.Sha256
        } catch {
            $summaryConflict = $true
            throw
        }

        foreach ($row in $selected) {
            try {
                $worker = Start-FrozenSageSingleTaskProcessAsync -ProjectRoot $ProjectRoot -RunId ([string]$row.run_id)
                $workers.Add($worker)
                Write-Host ("PILOT_WORKER_STARTED run_id={0} worker_pid={1} scene={2} prn={3} channel={4} mapping_warning=NONE resume=false" -f `
                    $row.run_id, $worker.ProcessId, $row.scene_id, $row.prn, $row.tracking_channel)
            } catch {
                $taskStatuses[[string]$row.run_id] = 'FAILED'
                $summaryRow = @($summaryRows | Where-Object { [string]$_.run_id -ceq [string]$row.run_id })[0]
                $summaryRow.execution_status = 'FAILED'
                $summaryRow.failure_reason = 'SINGLE_TASK_RUNNER_START_FAILURE'
                $stopReason = "RUNNER_START_FAILURE:$($row.run_id):$($_.Exception.Message)"
                break
            }
        }

        $lastProgressUtc = [System.DateTimeOffset]::UtcNow
        while ($completedWorkers.Count -lt $workers.Count) {
            foreach ($worker in $workers) {
                $runId = [string]$worker.RunId
                if ($completedWorkers.ContainsKey($runId)) { continue }
                if ($worker.Process.HasExited) {
                    $completedWorkers[$runId] = Complete-FrozenSageSingleTaskProcessAsync -Worker $worker
                    Write-Host ("PILOT_WORKER_ENDED run_id={0} worker_pid={1} exit_code={2} process_ended={3}" -f `
                        $runId, $completedWorkers[$runId].ProcessId, $completedWorkers[$runId].ExitCode, $completedWorkers[$runId].ProcessEnded)
                }
            }
            if ($completedWorkers.Count -lt $workers.Count) {
                $now = [System.DateTimeOffset]::UtcNow
                if (($now - $lastProgressUtc).TotalSeconds -ge 20) {
                    $runningIds = @($workers | Where-Object { -not $_.Process.HasExited } | ForEach-Object RunId)
                    Write-Host ("PILOT_WORKERS_STILL_RUNNING run_ids={0}" -f ($runningIds -join ','))
                    [Console]::Out.Flush()
                    $lastProgressUtc = $now
                }
                Start-Sleep -Seconds 2
            }
        }
        if ($workers.Count -ne $selected.Count) {
            $batchLockSafeToMove = $false
            if ($stopReason -eq '') { $stopReason = 'PILOT_WORKER_COUNT_INCOMPLETE' }
        }
        foreach ($row in $selected) {
            $runId = [string]$row.run_id
            $summaryRow = @($summaryRows | Where-Object { [string]$_.run_id -ceq $runId })[0]
            if (-not $completedWorkers.ContainsKey($runId)) {
                if ([string]$summaryRow.execution_status -eq 'IN_PROGRESS') {
                    $summaryRow.execution_status = 'FAILED'
                    $summaryRow.failure_reason = 'RUNNER_PROCESS_END_UNCONFIRMED'
                    $taskStatuses[$runId] = 'FAILED'
                }
                $batchLockSafeToMove = $false
                if ($stopReason -eq '') { $stopReason = "RUNNER_PROCESS_END_UNCONFIRMED:$runId" }
                continue
            }
            $child = $completedWorkers[$runId]
            if (-not $child.ProcessEnded) {
                $summaryRow.execution_status = 'FAILED'
                $summaryRow.failure_reason = 'RUNNER_PROCESS_END_UNCONFIRMED'
                $taskStatuses[$runId] = 'FAILED'
                $batchLockSafeToMove = $false
                if ($stopReason -eq '') { $stopReason = "RUNNER_PROCESS_END_UNCONFIRMED:$runId" }
                continue
            }
            if ($child.ExitCode -eq 0) {
                try {
                    $validated = Assert-FrozenSageSuccessfulTask -ManifestRow $row -ChildResult $child -ProjectRoot $ProjectRoot
                    $summaryRow.execution_status = 'COMPLETE'
                    $summaryRow.matlab_exit_code = '0'
                    foreach ($field in $validated.Metrics.PSObject.Properties.Name) { $summaryRow.$field = [string]$validated.Metrics.$field }
                    $summaryRow.failure_reason = ''
                    $validatedTasks[$runId] = $validated
                    $taskStatuses[$runId] = 'COMPLETE'
                } catch {
                    $summaryRow.execution_status = 'FAILED'
                    $summaryRow.failure_reason = 'POST_RUN_VALIDATION_FAILURE'
                    $taskStatuses[$runId] = 'FAILED'
                    if ($stopReason -eq '') { $stopReason = "POST_RUN_VALIDATION_FAILURE:${runId}:$($_.Exception.Message)" }
                }
                continue
            }
            try {
                $failureEvidence = Get-FrozenSageFailureEvidence -ManifestRow $row -ChildResult $child
                $disposition = Get-FrozenSageFailureDisposition -FailureReason $failureEvidence.FailureReason `
                    -RunnerProcessEnded $child.ProcessEnded -MatlabStarted $failureEvidence.MatlabStarted `
                    -MatlabProcessEnded $failureEvidence.MatlabProcessEnded
                $summaryRow.execution_status = 'FAILED'
                $summaryRow.matlab_exit_code = if ($failureEvidence.MatlabExitCode -ge 0) { [string]$failureEvidence.MatlabExitCode } else { '' }
                $summaryRow.failure_reason = [string]$failureEvidence.FailureReason
                $taskStatuses[$runId] = 'FAILED'
                if ($failureEvidence.FailureReason -in @('STAGE0_NO_VALID_NAV_SYMBOLS', 'STAGE0_NO_VALID_40MS_WINDOWS') -and
                    $disposition -eq 'CONTINUE_TASK') {
                    $paths = Get-FrozenSageTaskPaths -ProjectRoot $ProjectRoot -ManifestRow $row
                    if (Test-Path -LiteralPath $paths.StagingPath -PathType Container) {
                        $timestampPart = [System.DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
                        $diagnostic = Join-Path $ProjectRoot (Join-Path ([string]$row.scene_id) (
                            Join-Path $script:FrozenBatchDiagnosticRoot (
                                Join-Path ("{0}_ch{1}" -f [string]$row.prn, [string]$row.tracking_channel) (
                                    '{0}_{1}' -f [string]$row.run_id, $timestampPart))))
                        [void](Move-FrozenSageFailedStaging -StagingPath $paths.StagingPath -FinalDestinationPath $paths.FinalPath `
                            -DiagnosticDestinationPath $diagnostic -SceneId ([string]$row.scene_id) -PrnLabel ([string]$row.prn) `
                            -TrackingChannel ([int]$row.tracking_channel) -RunId $runId -FailureReason $failureEvidence.FailureReason `
                            -RunnerProcessEnded $child.ProcessEnded -MatlabStarted $failureEvidence.MatlabStarted `
                            -MatlabProcessId ([int]$failureEvidence.MatlabProcessId) -MatlabProcessEnded $failureEvidence.MatlabProcessEnded `
                            -MatlabExitCode ([int]$failureEvidence.MatlabExitCode))
                    }
                }
                if ($disposition -eq 'STOP_BATCH' -and $stopReason -eq '') {
                    $stopReason = "CLASSIFIED_SYSTEMIC_FAILURE:${runId}:$($failureEvidence.FailureReason)"
                }
            } catch {
                $summaryRow.execution_status = 'FAILED'
                $summaryRow.failure_reason = 'FAILURE_EVIDENCE_OR_QUARANTINE_UNSAFE'
                $taskStatuses[$runId] = 'FAILED'
                if ($stopReason -eq '') { $stopReason = "FAILURE_HANDLING_STOP:${runId}:$($_.Exception.Message)" }
            }
        }

        try {
            $checkpoint = Write-FrozenSageBatchSummary -SummaryPath $summaryPath -Rows $summaryRows -ExpectedCurrentHash $summaryHash
            $summaryHash = $checkpoint.Sha256
        } catch {
            $summaryConflict = $true
            throw
        }
        [void](Assert-FrozenSageNoMatlabProcess)
        [void](Assert-FrozenSageNoActiveRunnerLocks -ProjectRoot $ProjectRoot)

        $overlap = $false
        $matlabProcesses = @()
        foreach ($row in $selected) {
            $runId = [string]$row.run_id
            if (-not $validatedTasks.ContainsKey($runId)) { continue }
            $receipt = $validatedTasks[$runId].Receipt
            $start = [System.DateTimeOffset]::Parse([string]$receipt.matlab_start_utc)
            $end = [System.DateTimeOffset]::Parse([string]$receipt.matlab_end_utc)
            $matlabProcesses += [pscustomobject]@{ RunId = $runId; ProcessId = [int]$receipt.matlab_process_id; Start = $start; End = $end }
        }
        if ($matlabProcesses.Count -eq 2 -and $matlabProcesses[0].ProcessId -ne $matlabProcesses[1].ProcessId) {
            $overlap = ($matlabProcesses[0].Start -lt $matlabProcesses[1].End -and $matlabProcesses[1].Start -lt $matlabProcesses[0].End)
        }
        $overlapConfirmed = $overlap
        $maxSimultaneousMatlab = if ($overlap) { 2 } elseif ($matlabProcesses.Count -gt 0) { 1 } else { 0 }
        $pilotPass = ($workers.Count -eq 2 -and $taskStatuses.Count -eq 2 -and
            @($taskStatuses.Values | Where-Object { $_ -eq 'COMPLETE' }).Count -eq 2 -and
            $overlapConfirmed -and -not $stagingCollision -and -not $duplicateDispatch -and -not $summaryConflict)
        $batchStatus = if ($pilotPass) { 'PILOT_PASS' } else { 'PILOT_FAILED' }
        if (-not $pilotPass -and $stopReason -eq '') { $stopReason = 'PILOT_ACCEPTANCE_CRITERIA_NOT_MET' }

        $aggregates = Get-FrozenSageBatchAggregates -Rows $summaryRows
        $pilotReceiptRoot = Join-Path $executionLogParent 'frozen_sage_parallel_pilot_receipts'
        if (-not (Test-Path -LiteralPath $pilotReceiptRoot -PathType Container)) { [void](New-Item -ItemType Directory -Path $pilotReceiptRoot -ErrorAction Stop) }
        $pilotDirectory = Join-Path $pilotReceiptRoot ('pilot_{0}_{1}' -f [System.DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ'), [guid]::NewGuid().ToString('N'))
        if (Test-Path -LiteralPath $pilotDirectory) { throw "PILOT_RECEIPT_COLLISION path=$pilotDirectory" }
        [void](New-Item -ItemType Directory -Path $pilotDirectory -ErrorAction Stop)
        $pilotReceiptPath = Join-Path $pilotDirectory 'pilot_receipt.json'
        $taskReceiptRows = foreach ($row in $selected) {
            $runId = [string]$row.run_id
            $validated = $validatedTasks[$runId]
            $worker = @($workers | Where-Object { [string]$_.RunId -ceq $runId }) | Select-Object -First 1
            [pscustomobject]@{
                run_id = $runId
                scene_id = [string]$row.scene_id
                prn = [string]$row.prn
                channel = [int]$row.tracking_channel
                staging_key = '{0}|{1}' -f [string]$row.scene_id, [string]$row.prn
                execution_status = [string]$taskStatuses[$runId]
                worker_process_id = if ($null -ne $worker) { [int]$worker.ProcessId } else { $null }
                matlab_process_id = if ($null -ne $validated) { [int]$validated.Receipt.matlab_process_id } else { $null }
                matlab_start_utc = if ($null -ne $validated) { [string]$validated.Receipt.matlab_start_utc } else { '' }
                matlab_end_utc = if ($null -ne $validated) { [string]$validated.Receipt.matlab_end_utc } else { '' }
                final_output = if ($null -ne $validated) { [string]$validated.OutputPath } else { '' }
            }
        }
        $pilotReceipt = [ordered]@{
            pilot_status = if ($pilotPass) { 'PASS' } else { 'FAIL' }
            max_parallel = 2
            worker_count = $workers.Count
            tasks = @($taskReceiptRows)
            overlap_confirmed = [bool]$overlapConfirmed
            max_simultaneous_matlab_processes = [int]$maxSimultaneousMatlab
            staging_collision = [bool]$stagingCollision
            duplicate_dispatch = [bool]$duplicateDispatch
            summary_write_conflict = [bool]$summaryConflict
            summary_sha256_after = $summaryHash
            summary_status_counts = $aggregates
            stop_reason = $stopReason
            completed_utc = [System.DateTimeOffset]::UtcNow.ToString('o')
            additional_tasks_scheduled = 0
            other_tasks_started_after_pilot = $false
        }
        $pilotStream = [System.IO.File]::Open($pilotReceiptPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
        try {
            $pilotBytes = [System.Text.UTF8Encoding]::new($false).GetBytes(($pilotReceipt | ConvertTo-Json -Depth 10) + [Environment]::NewLine)
            $pilotStream.Write($pilotBytes, 0, $pilotBytes.Length)
            $pilotStream.Flush($true)
        } finally { $pilotStream.Dispose() }
    } catch {
        if ($stopReason -eq '') { $stopReason = "PARALLEL_PILOT_COORDINATOR_FAILURE:$($_.Exception.Message)" }
        if ($workers.Count -gt 0 -and $completedWorkers.Count -lt $workers.Count) { $batchLockSafeToMove = $false }
        throw
    } finally {
        if ($batchLockSafeToMove) {
            try {
                $currentRows = @(Import-Csv -LiteralPath $summaryPath -ErrorAction SilentlyContinue)
                $finalAggregates = if ($currentRows.Count -gt 0) { Get-FrozenSageBatchAggregates -Rows $currentRows } else { [pscustomobject]@{} }
                $receiptRoot = Join-Path $executionLogParent 'frozen_sage_batch_receipts'
                if (-not (Test-Path -LiteralPath $receiptRoot -PathType Container)) { [void](New-Item -ItemType Directory -Path $receiptRoot -ErrorAction Stop) }
                if (Test-Path -LiteralPath $activeLockPath -PathType Leaf) {
                    $lockReceiptPath = Move-FrozenSageBatchLockToReceipt -LockPath $activeLockPath -ReceiptRoot $receiptRoot `
                        -FinalStatus $batchStatus -StopReason $(if ($stopReason -eq '') { 'NONE' } else { $stopReason }) -Aggregates $finalAggregates
                    Write-Host "PILOT_COORDINATOR_LOCK_RECEIPT=$lockReceiptPath"
                }
            } catch { Write-Host "PILOT_BATCH_LOCK_RETAINED reason=$($_.Exception.Message)" }
        } else { Write-Host "PILOT_BATCH_LOCK_RETAINED path=$activeLockPath reason=WORKER_END_UNCONFIRMED" }
        $script:FrozenBatchOwnedLockPath = ''
    }
    return [pscustomobject]@{
        ParallelPilot = if ($batchStatus -eq 'PILOT_PASS') { 'PASS' } else { 'FAIL' }
        MaxParallel = 2
        SelectedRunIds = @($selected | ForEach-Object run_id)
        PilotReceipt = $pilotReceiptPath
        OverlapConfirmed = $overlapConfirmed
        MaxSimultaneousMatlabProcesses = $maxSimultaneousMatlab
        StagingCollision = $stagingCollision
        DuplicateDispatch = $duplicateDispatch
        SummaryWriteConflict = $summaryConflict
        SummaryAggregates = Get-FrozenSageBatchAggregates -Rows @(Import-Csv -LiteralPath $summaryPath)
    }
}

function Invoke-FrozenSageRerunBatch {
    param(
        [Parameter(Mandatory)][bool]$ShouldExecute,
        [AllowNull()][string]$PlanPath
    )

    $projectRoot = $script:FrozenBatchProjectRoot
    if (-not [string]::Equals([System.IO.Path]::GetFullPath($projectRoot), (Get-Location).Path, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "PROJECT_ROOT_MISMATCH expected=$projectRoot actual=$((Get-Location).Path)"
    }
    [void](Assert-FrozenSageNoActiveRunnerLocks -ProjectRoot $projectRoot)
    [void](Assert-FrozenSageNoMatlabProcess)
    $sourcePath = Join-Path $projectRoot 'scripts\sage_pipeline\run_nav_sage_pipeline.m'
    $sourceHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
    [void](Assert-FrozenSageHash -ActualHash $sourceHash -ExpectedHash $script:FrozenSourceSha256)

    $context = Get-FrozenSageBatchManifestContext -ProjectRoot $projectRoot
    $manifestPath = Join-Path $projectRoot $script:FrozenBatchManifestRelativePath
    $gpuPaths = Get-FrozenSageGpuSourcePaths
    $planResolution = Resolve-FrozenSageBatchExecutionPlan `
        -ExecutionPlanPath $PlanPath `
        -ManifestPath $manifestPath `
        -SourceContractPath $gpuPaths.SourceContract `
        -ManifestRows $context.Rows
    $executionPlan = $planResolution.ExecutionPlan
    $baselineOutput = Join-Path $projectRoot ([string]$context.Baseline.output_namespace)
    $baselineReport = Join-Path $projectRoot $script:FrozenBatchBaselineReportRelativePath
    $baselineSummary = Get-FrozenSageBaselineSummaryRow -ManifestRow $context.Baseline -OutputPath $baselineOutput -RegressionReportPath $baselineReport
    $summaryPath = Join-Path $projectRoot $script:FrozenBatchSummaryRelativePath
    $planProvided = -not [string]::IsNullOrWhiteSpace($PlanPath)
    $summaryState = Resolve-FrozenSageBatchSummaryState `
        -SummaryPath $summaryPath `
        -ManifestRows $context.Rows `
        -BaselineSummaryRow $baselineSummary `
        -PlanProvided $planProvided `
        -AuthorizedRunIds $planResolution.AuthorizedRunIds
    $allNewRows = @($summaryState.AllNewRows)
    $newRows = @($summaryState.ExecutionRows)
    if ($planProvided -and $newRows.Count -eq 0) { throw 'GPU_EXECUTION_PLAN_HAS_NO_PENDING_MANIFEST_RUN_IDS' }
    $scopeRows = if ($planProvided) {
        @($context.Baseline) + @($newRows)
    } else {
        @($context.Rows)
    }
    [void](Assert-FrozenSageAllOutputNamespacesAbsent -ProjectRoot $projectRoot -ManifestRows $scopeRows -BaselineRunId $script:FrozenBatchBaselineRunId)

    if (-not $ShouldExecute) {
        $preflightFailures = [System.Collections.Generic.List[string]]::new()
        foreach ($row in $newRows) {
            try {
                $preflight = Get-FrozenSagePreflight -RunId ([string]$row.run_id) -ExecutionPlan $executionPlan
                if ([string]$preflight.MappingWarning -cne [string]$row.mapping_warning) { throw 'MANIFEST_MAPPING_WARNING_CHANGED' }
            } catch {
                $reason = Get-FrozenSageTaskSpecificInputReason -Text $_.Exception.Message
                if ($null -ne $reason) { $preflightFailures.Add("$($row.run_id):$reason") } else { throw }
            }
        }
        [void](Assert-FrozenSageNoActiveRunnerLocks -ProjectRoot $projectRoot)
        [void](Assert-FrozenSageNoMatlabProcess)
        $summaryMode = if ($summaryState.IsExistingSummary) { 'EXISTING_PLAN_SCOPED' } else { 'FRESH_SUMMARY' }
        $globalPending = @($summaryState.SummaryRows | Where-Object { [string]$_.execution_status -eq 'PENDING' }).Count
        Write-Output "VALIDATION_ONLY tasks=$($newRows.Count) manifest_tasks=$($allNewRows.Count) baseline=ALREADY_COMPLETE mapping_warnings=$(@($newRows | Where-Object { $_.mapping_warning -ne 'NONE' }).Count) matlab_invoked=false raw_iq_content_read=false execution_mode=$($executionPlan.ExecutionMode) summary_mode=$summaryMode global_pending=$globalPending"
        foreach ($row in $newRows) {
            $summaryRow = @($summaryState.SummaryRows | Where-Object { [string]$_.run_id -ceq [string]$row.run_id }) | Select-Object -First 1
            Write-Output "PLAN_TASK run_id=$($row.run_id) status=$($summaryRow.execution_status)"
        }
        if ($preflightFailures.Count -gt 0) { $preflightFailures | ForEach-Object { Write-Output "TASK_SPECIFIC_PREFLIGHT_FAILURE $_" } }
        return
    }

    $executionLogParent = Join-Path $projectRoot 'dataset_generation_logs\batch_sage_execution'
    if (-not (Test-Path -LiteralPath $executionLogParent -PathType Container)) { throw "BATCH_EXECUTION_LOG_PARENT_MISSING path=$executionLogParent" }
    $activeLockPath = Join-Path $executionLogParent '.frozen_sage_batch_active.lock'
    $batchLock = New-FrozenSageBatchLock -LockPath $activeLockPath
    $script:FrozenBatchOwnedLockPath = $activeLockPath
    $batchLockSafeToMove = $true
    $summaryRows = $summaryState.SummaryRows
    $summaryHash = [string]$summaryState.ExpectedCurrentHash
    $stopReason = ''
    $batchStatus = 'STOPPED'
    $scopeCompletion = $null
    try {
        if (-not $summaryState.IsExistingSummary) {
            $checkpoint = Write-FrozenSageBatchSummary -SummaryPath $summaryPath -Rows @($summaryRows) -ExpectedCurrentHash ''
            $summaryHash = $checkpoint.Sha256
        }
        foreach ($manifestRow in $newRows) {
            $summaryRow = @($summaryRows | Where-Object { [string]$_.run_id -ceq [string]$manifestRow.run_id })[0]
            if ([string]$summaryRow.execution_status -ne 'PENDING') { throw "BATCH_TASK_NOT_PENDING run_id=$($manifestRow.run_id)" }
            $summaryRow.execution_status = 'IN_PROGRESS'
            $checkpoint = Write-FrozenSageBatchSummary -SummaryPath $summaryPath -Rows @($summaryRows) -ExpectedCurrentHash $summaryHash
            $summaryHash = $checkpoint.Sha256
            Write-Output "TASK_BEGIN run_id=$($manifestRow.run_id) scene=$($manifestRow.scene_id) prn=$($manifestRow.prn) channel=$($manifestRow.tracking_channel) mapping_warning=$($manifestRow.mapping_warning) resume=false"

            try {
                [void](Assert-FrozenSageNoActiveRunnerLocks -ProjectRoot $projectRoot)
                [void](Assert-FrozenSageNoMatlabProcess)
                $beforeHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
                [void](Assert-FrozenSageHash -ActualHash $beforeHash -ExpectedHash $script:FrozenSourceSha256)
                [void](Assert-FrozenSageManifestRow -Row $manifestRow -ExpectedRunId ([string]$manifestRow.run_id))
                $preflight = Get-FrozenSagePreflight -RunId ([string]$manifestRow.run_id) -ExecutionPlan $executionPlan
                if ([string]$preflight.MappingWarning -cne [string]$manifestRow.mapping_warning) { throw 'MANIFEST_MAPPING_WARNING_CHANGED' }
            } catch {
                $preflightMessage = $_.Exception.Message
                $taskInputReason = Get-FrozenSageTaskSpecificInputReason -Text $preflightMessage
                $summaryRow.execution_status = 'FAILED'
                $summaryRow.failure_reason = if ($null -ne $taskInputReason) { $taskInputReason } else { 'SYSTEMIC_PREFLIGHT_FAILURE' }
                $checkpoint = Write-FrozenSageBatchSummary -SummaryPath $summaryPath -Rows @($summaryRows) -ExpectedCurrentHash $summaryHash
                $summaryHash = $checkpoint.Sha256
                Write-Output "TASK_PREFLIGHT_FAILED run_id=$($manifestRow.run_id) reason=$($summaryRow.failure_reason)"
                if ($null -ne $taskInputReason) { continue }
                $stopReason = "PREFLIGHT_STOP:$($manifestRow.run_id):$preflightMessage"
                break
            }

            $batchLockSafeToMove = $false
            $child = $null
            try {
                $child = Start-FrozenSageSingleTaskProcess -ProjectRoot $projectRoot -RunId ([string]$manifestRow.run_id) -ExecutionPlanPath $PlanPath
            } finally {
                if ($null -ne $child -and $child.ProcessEnded) { $batchLockSafeToMove = $true }
            }
            if ($null -eq $child -or -not $child.ProcessEnded) {
                $summaryRow.execution_status = 'FAILED'
                $summaryRow.failure_reason = 'RUNNER_PROCESS_END_UNCONFIRMED'
                $checkpoint = Write-FrozenSageBatchSummary -SummaryPath $summaryPath -Rows @($summaryRows) -ExpectedCurrentHash $summaryHash
                $summaryHash = $checkpoint.Sha256
                $stopReason = "RUNNER_PROCESS_END_UNCONFIRMED:$($manifestRow.run_id)"
                break
            }

            if ($child.ExitCode -eq 0) {
                try {
                    $validated = Assert-FrozenSageSuccessfulTask -ManifestRow $manifestRow -ChildResult $child -ProjectRoot $projectRoot -ExecutionMode $executionPlan.ExecutionMode
                    $summaryRow.execution_status = 'COMPLETE'
                    $summaryRow.matlab_exit_code = '0'
                    foreach ($field in $validated.Metrics.PSObject.Properties.Name) { $summaryRow.$field = [string]$validated.Metrics.$field }
                    $summaryRow.failure_reason = ''
                    $checkpoint = Write-FrozenSageBatchSummary -SummaryPath $summaryPath -Rows @($summaryRows) -ExpectedCurrentHash $summaryHash
                    $summaryHash = $checkpoint.Sha256
                    Write-Output "TASK_COMPLETE run_id=$($manifestRow.run_id) stage0_symbols=$($validated.Metrics.stage0_valid_nav_symbols) stage0_windows=$($validated.Metrics.stage0_valid_40ms_windows) stage2_mpc=$($validated.Metrics.stage2_mpc_count) stage3_persistent=$($validated.Metrics.stage3_persistent_mpc_count) stage4_confirmed=$($validated.Metrics.stage4_confirmed_mpc_count)"
                } catch {
                    $summaryRow.execution_status = 'FAILED'
                    $summaryRow.failure_reason = 'POST_RUN_VALIDATION_FAILURE'
                    $checkpoint = Write-FrozenSageBatchSummary -SummaryPath $summaryPath -Rows @($summaryRows) -ExpectedCurrentHash $summaryHash
                    $summaryHash = $checkpoint.Sha256
                    $stopReason = "POST_RUN_VALIDATION_STOP:$($manifestRow.run_id):$($_.Exception.Message)"
                    break
                }
                continue
            }

            try {
                $failureEvidence = Get-FrozenSageFailureEvidence -ManifestRow $manifestRow -ChildResult $child
                $disposition = Get-FrozenSageFailureDisposition -FailureReason $failureEvidence.FailureReason `
                    -RunnerProcessEnded $child.ProcessEnded -MatlabStarted $failureEvidence.MatlabStarted `
                    -MatlabProcessEnded $failureEvidence.MatlabProcessEnded
                $summaryRow.execution_status = 'FAILED'
                $summaryRow.matlab_exit_code = if ($failureEvidence.MatlabExitCode -ge 0) { [string]$failureEvidence.MatlabExitCode } else { '' }
                $summaryRow.failure_reason = $failureEvidence.FailureReason
                if ($failureEvidence.FailureReason -in @('STAGE0_NO_VALID_NAV_SYMBOLS', 'STAGE0_NO_VALID_40MS_WINDOWS') -and
                    $disposition -eq 'CONTINUE_TASK') {
                    $paths = Get-FrozenSageTaskPaths -ProjectRoot $projectRoot -ManifestRow $manifestRow
                    if (Test-Path -LiteralPath $paths.StagingPath -PathType Container) {
                        $timestampPart = [System.DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
                        $diagnostic = Join-Path $projectRoot (Join-Path ([string]$manifestRow.scene_id) (
                            Join-Path $script:FrozenBatchDiagnosticRoot (
                                Join-Path ("{0}_ch{1}" -f [string]$manifestRow.prn, [string]$manifestRow.tracking_channel) (
                                    '{0}_{1}' -f [string]$manifestRow.run_id, $timestampPart))))
                        [void](Move-FrozenSageFailedStaging -StagingPath $paths.StagingPath -FinalDestinationPath $paths.FinalPath `
                            -DiagnosticDestinationPath $diagnostic -SceneId ([string]$manifestRow.scene_id) -PrnLabel ([string]$manifestRow.prn) `
                            -TrackingChannel ([int]$manifestRow.tracking_channel) -RunId ([string]$manifestRow.run_id) `
                            -FailureReason $failureEvidence.FailureReason -RunnerProcessEnded $child.ProcessEnded `
                            -MatlabStarted $failureEvidence.MatlabStarted -MatlabProcessId ([int]$failureEvidence.MatlabProcessId) `
                            -MatlabProcessEnded $failureEvidence.MatlabProcessEnded -MatlabExitCode ([int]$failureEvidence.MatlabExitCode))
                    }
                }
                $checkpoint = Write-FrozenSageBatchSummary -SummaryPath $summaryPath -Rows @($summaryRows) -ExpectedCurrentHash $summaryHash
                $summaryHash = $checkpoint.Sha256
                Write-Output "TASK_FAILED run_id=$($manifestRow.run_id) reason=$($failureEvidence.FailureReason) disposition=$disposition runner_ended=$($child.ProcessEnded) matlab_started=$($failureEvidence.MatlabStarted) matlab_ended=$($failureEvidence.MatlabProcessEnded)"
                if ($disposition -eq 'STOP_BATCH') {
                    $stopReason = "CLASSIFIED_SYSTEMIC_FAILURE:$($manifestRow.run_id):$($failureEvidence.FailureReason)"
                    break
                }
            } catch {
                $summaryRow.execution_status = 'FAILED'
                $summaryRow.failure_reason = 'FAILURE_EVIDENCE_OR_QUARANTINE_UNSAFE'
                $checkpoint = Write-FrozenSageBatchSummary -SummaryPath $summaryPath -Rows @($summaryRows) -ExpectedCurrentHash $summaryHash
                $summaryHash = $checkpoint.Sha256
                $stopReason = "FAILURE_HANDLING_STOP:$($manifestRow.run_id):$($_.Exception.Message)"
                break
            }
        }

        $aggregates = Get-FrozenSageBatchAggregates -Rows @($summaryRows)
        if ($planProvided) {
            $scopeCompletion = Get-FrozenSagePlanScopeCompletion `
                -Rows @($summaryRows) `
                -AuthorizedRunIds $planResolution.AuthorizedRunIds `
                -StopReason $stopReason
            $batchStatus = $scopeCompletion.FinalStatus
            if ([string]::IsNullOrWhiteSpace($stopReason) -and -not [string]::IsNullOrWhiteSpace($scopeCompletion.StopReason)) {
                $stopReason = $scopeCompletion.StopReason
            }
            Write-Output "$($scopeCompletion.FinalStatus) authorized=$($scopeCompletion.AuthorizedTaskCount) authorized_complete=$($scopeCompletion.AuthorizedCompleteCount) global_complete=$($scopeCompletion.GlobalCompleteCount) remaining_global_pending=$($scopeCompletion.GlobalPendingCount)"
        } else {
            $pendingRows = @($summaryRows | Where-Object { [string]$_.execution_status -eq 'PENDING' })
            if ($stopReason -eq '' -and $pendingRows.Count -eq 0) {
                $failedRows = @($summaryRows | Where-Object { [string]$_.execution_status -eq 'FAILED' })
                $batchStatus = if ($failedRows.Count -gt 0) { 'COMPLETED_WITH_FAILURES' } else { 'COMPLETED' }
            }
            elseif ($stopReason -eq '') { $stopReason = 'BATCH_TERMINATED_WITH_PENDING_TASKS' }
        }
        Write-Output '--- BATCH_AGGREGATES ---'
        Format-FrozenSageBatchAggregates -Aggregates $aggregates | ForEach-Object { Write-Output $_ }
        if ($stopReason -ne '') { Write-Output "STOP_BATCH reason=$stopReason" }
    } catch {
        $stopReason = "BATCH_COORDINATOR_EXCEPTION:$($_.Exception.Message)"
        $batchStatus = 'STOPPED'
        Write-Output "STOP_BATCH reason=$stopReason"
        $inProgress = @($summaryRows | Where-Object { [string]$_.execution_status -eq 'IN_PROGRESS' })
        foreach ($unfinished in $inProgress) {
            $unfinished.execution_status = 'FAILED'
            if ([string]::IsNullOrWhiteSpace([string]$unfinished.failure_reason)) {
                $unfinished.failure_reason = 'BATCH_COORDINATOR_EXCEPTION'
            }
        }
        if ($summaryHash -ne '' -and (Test-Path -LiteralPath $summaryPath -PathType Leaf)) {
            $checkpoint = Write-FrozenSageBatchSummary -SummaryPath $summaryPath -Rows @($summaryRows) -ExpectedCurrentHash $summaryHash
            $summaryHash = $checkpoint.Sha256
        }
    } finally {
        if ($batchLockSafeToMove) {
            try {
                $aggregates = Get-FrozenSageBatchAggregates -Rows @($summaryRows)
                if ($planProvided -and $null -eq $scopeCompletion) {
                    $scopeCompletion = Get-FrozenSagePlanScopeCompletion `
                        -Rows @($summaryRows) `
                        -AuthorizedRunIds $planResolution.AuthorizedRunIds `
                        -StopReason $stopReason
                    if ($batchStatus -eq 'STOPPED') { $batchStatus = $scopeCompletion.FinalStatus }
                }
                $receipts = Join-Path $executionLogParent 'frozen_sage_batch_receipts'
                if (-not (Test-Path -LiteralPath $receipts -PathType Container)) { [void](New-Item -ItemType Directory -Path $receipts -ErrorAction Stop) }
                if (Test-Path -LiteralPath $activeLockPath -PathType Leaf) {
                    $receipt = Move-FrozenSageBatchLockToReceipt `
                        -LockPath $activeLockPath -ReceiptRoot $receipts -FinalStatus $batchStatus `
                        -StopReason $stopReason -Aggregates $aggregates -PlanScopeSummary $scopeCompletion
                    $script:FrozenBatchOwnedLockPath = ''
                    Write-Output "BATCH_LOCK_MOVED_TO_RECEIPT path=$receipt"
                }
            } catch {
                Write-Output "BATCH_LOCK_RETAINED reason=$($_.Exception.Message)"
            }
        } else {
            Write-Output "BATCH_LOCK_RETAINED path=$activeLockPath reason=PROCESS_END_UNCONFIRMED"
        }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    if (-not [string]::IsNullOrWhiteSpace($ValidateRecoveryRunId)) {
        if ($ValidateOnly -or $Execute -or $ParallelPilot -or -not [string]::IsNullOrWhiteSpace($RecoverRunId) -or -not [string]::IsNullOrWhiteSpace($ExecutionPlanPath)) { throw 'RECOVERY_VALIDATION_MODE_CANNOT_BE_COMBINED_WITH_OTHER_MODES' }
        Invoke-FrozenSageBatchPostRunRecovery -ProjectRoot $script:FrozenBatchProjectRoot -RunId $ValidateRecoveryRunId -ValidateOnly
    } elseif (-not [string]::IsNullOrWhiteSpace($RecoverRunId)) {
        if ($ValidateOnly -or $Execute -or $ParallelPilot -or -not [string]::IsNullOrWhiteSpace($ExecutionPlanPath)) { throw 'RECOVERY_MODE_CANNOT_BE_COMBINED_WITH_OTHER_MODES' }
        Invoke-FrozenSageBatchPostRunRecovery -ProjectRoot $script:FrozenBatchProjectRoot -RunId $RecoverRunId
    } elseif ($ParallelPilot) {
        if ($ValidateOnly -or $Execute) { throw 'PARALLEL_PILOT_MODE_CANNOT_BE_COMBINED_WITH_SERIAL_MODES' }
        [void](Assert-FrozenSageGpuParallelPilotNotAllowed -ExecutionPlanPath $ExecutionPlanPath)
        Invoke-FrozenSageParallelPilot -ProjectRoot $script:FrozenBatchProjectRoot -MaxParallel 2
    } else {
        $requestedMode = Resolve-FrozenSageBatchMode -ValidateOnly $script:FrozenBatchRequestedValidateOnly -Execute $script:FrozenBatchRequestedExecute
        $shouldExecute = ($requestedMode -eq 'EXECUTE')
        Invoke-FrozenSageRerunBatch -ShouldExecute:$shouldExecute -PlanPath $ExecutionPlanPath
    }
}
