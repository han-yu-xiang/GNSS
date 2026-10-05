[CmdletBinding()]
param(
    [string]$RunId,
    [switch]$Execute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$script:FrozenProjectRoot = 'E:\GNSS_Multipath_Project'
$script:FrozenSampleRateHz = 10230000
$script:FrozenSourceRelativePath = 'scripts\sage_pipeline\run_nav_sage_pipeline.m'
$script:FrozenSourceSha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
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
        [object]$MatlabProcessState
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
    $lockHash = (Get-FileHash -LiteralPath $GlobalLockPath -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
    if (Test-Path -LiteralPath $archivedLockPath) {
        throw "FAILURE_LOCK_DESTINATION_COLLISION path=$archivedLockPath"
    }
    Move-Item -LiteralPath $GlobalLockPath -Destination $archivedLockPath -ErrorAction Stop
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
    $receiptPath = Join-Path $receiptDirectory 'failure_receipt.json'
    $json = $failureReceipt | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText($receiptPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    return [pscustomobject]@{
        LockPath = $archivedLockPath
        ReceiptPath = $receiptPath
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

function Move-ValidatedStageOutput {
    param(
        [Parameter(Mandatory)][string]$StagingPath,
        [Parameter(Mandatory)][string]$FinalPath,
        [Parameter(Mandatory)][object]$Context
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
    $receiptPath = Join-Path $FinalPath 'relocation_receipt.json'
    $receiptJson = $receipt | ConvertTo-Json -Depth 6
    [System.IO.File]::WriteAllText($receiptPath, $receiptJson + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
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
    param([Parameter(Mandatory)][string]$RunId)

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
        StagingPath = $stagingPath
        FinalPath = $finalPath
        ManifestRow = $row
    }
}

function Invoke-FrozenSageRerunSingle {
    param(
        [Parameter(Mandatory)][string]$RunId,
        [Parameter(Mandatory)][bool]$ShouldExecute
    )

    $preflight = Get-FrozenSagePreflight -RunId $RunId
    Write-Output "PREFLIGHT_PASS run_id=$($preflight.RunId) scene=$($preflight.SceneId) prn=$($preflight.PrnLabel) channel=$($preflight.TrackingChannel) sample_rate_hz=$($preflight.SampleRateHz) mapping_warning=$($preflight.MappingWarning) resume=false"
    if (-not $ShouldExecute) {
        Write-Output 'VALIDATION_ONLY matlab_invoked=false raw_iq_content_read=false'
        return
    }

    $executionLogParent = Join-Path $preflight.ProjectRoot 'dataset_generation_logs\batch_sage_execution'
    if (-not (Test-Path -LiteralPath $executionLogParent -PathType Container)) {
        throw "EXECUTION_LOG_PARENT_MISSING path=$executionLogParent"
    }
    $globalLockPath = Get-FrozenSageTaskRunnerLockPath -ExecutionLogParent $executionLogParent -RunId $preflight.RunId
    $failureReceiptRoot = Join-Path $executionLogParent 'windows_runner_receipts'
    $lockStream = $null
    $lockOwned = $false
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
        $lockPayload = [ordered]@{
            run_id = $preflight.RunId
            scene_id = $preflight.SceneId
            prn = $preflight.Prn
            tracking_channel = $preflight.TrackingChannel
            mapping_warning = $preflight.MappingWarning
            resume = $false
            windows_identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
            powershell_version = $PSVersionTable.PSVersion.ToString()
            process_id = $PID
            started_utc = [System.DateTimeOffset]::UtcNow.ToString('o')
        }
        $lockWriter = [System.IO.StreamWriter]::new($lockStream, [System.Text.UTF8Encoding]::new($false), 1024, $true)
        $lockWriter.Write(($lockPayload | ConvertTo-Json -Depth 4))
        $lockWriter.Flush()
        $lockWriter.Dispose()

        $smoke = Invoke-FrozenMatlabBatch -MatlabPath $preflight.MatlabPath -Expression "disp('$script:StartupMarker')"
        [void](Assert-MatlabStartupSmoke -ExitCode $smoke.ExitCode -Output $smoke.Output)
        Write-Output "MATLAB_STARTUP_SMOKE_PASS marker=$script:StartupMarker exit_code=$($smoke.ExitCode)"

        $transportExpression = "a='F1023_V70_D0117_P2';b='TrackingChannel';c='E:/GNSS_Multipath_Project';assert(strcmp(a,'F1023_V70_D0117_P2'));assert(strcmp(b,'TrackingChannel'));assert(strcmp(c,'E:/GNSS_Multipath_Project'));disp('MATLAB_ARGUMENT_TRANSPORT_OK')"
        $transportSmoke = Invoke-FrozenMatlabBatch -MatlabPath $preflight.MatlabPath -Expression $transportExpression
        [void](Assert-MatlabArgumentTransportSmoke -ExitCode $transportSmoke.ExitCode -Stdout $transportSmoke.Stdout)
        Write-Output "MATLAB_ARGUMENT_TRANSPORT_SMOKE_PASS marker=$script:TransportMarker exit_code=$($transportSmoke.ExitCode)"

        $currentSourceHash = (Get-FileHash -LiteralPath (Join-Path $preflight.ProjectRoot $script:FrozenSourceRelativePath) -Algorithm SHA256).Hash.ToLowerInvariant()
        [void](Assert-FrozenSageHash -ActualHash $currentSourceHash -ExpectedHash $script:FrozenSourceSha256)
        [void](Assert-OutputNamespacesAbsent -StagingPath $preflight.StagingPath -FinalPath $preflight.FinalPath)
        Write-Output "EXECUTION_GATES_REVERIFIED frozen_sage_sha256=$currentSourceHash output_namespaces_absent=true"
        $expression = Get-FrozenSageMatlabExpression `
            -SceneId $preflight.SceneId `
            -Prn $preflight.Prn `
            -TrackingChannel $preflight.TrackingChannel `
            -ProjectRoot $preflight.ProjectRoot
        $rootForMatlab = $preflight.ProjectRoot.Replace('\', '/')
        $batchExpression = "cd('$rootForMatlab/scripts/sage_pipeline'); $expression"
        Write-Output "SAGE_EXECUTION_BEGIN run_id=$($preflight.RunId) scene=$($preflight.SceneId) prn=$($preflight.PrnLabel) channel=$($preflight.TrackingChannel) mapping_warning=$($preflight.MappingWarning) resume=false"
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
            FrozenSageSha256 = $postRunHash
            RawIqSizeBytes = $preflight.RawIqSizeBytes
            RawIqSha256 = $preflight.RawIqSha256
            RawIqSha256Status = $preflight.RawIqSha256Status
            MatlabProcessId = [int]$sageRun.ProcessId
            MatlabStartUtc = $sageRun.StartedUtc
            MatlabEndUtc = $sageRun.EndedUtc
            MatlabExitCode = $sageRun.ExitCode
        }
        $receipt = Move-ValidatedStageOutput -StagingPath $preflight.StagingPath -FinalPath $preflight.FinalPath -Context $context

        $lockStream.Dispose()
        $lockStream = $null
        Move-Item -LiteralPath $globalLockPath -Destination (Join-Path $preflight.FinalPath 'windows_runner_lock_receipt.json') -ErrorAction Stop
        $lockOwned = $false
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
                } elseif ($failureMessage -match '^MATLAB_ARGUMENT_TRANSPORT_FAILED') {
                    $failureReason = 'MATLAB_ARGUMENT_TRANSPORT_FAILURE'
                } elseif ($failureMessage -match '^MATLAB_STARTUP_SMOKE_FAILED') {
                    $failureReason = 'MATLAB_STARTUP_SMOKE_FAILURE'
                } elseif ($failureMessage -match '^FROZEN_SAGE_SOURCE_HASH_MISMATCH') {
                    $failureReason = 'FROZEN_SAGE_SOURCE_HASH_MISMATCH'
                } elseif ($failureMessage -match '^SAGE_MATLAB_EXIT_NONZERO') {
                    $failureReason = 'SAGE_MATLAB_FAILURE'
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
        if ($lockOwned -and $controlledFailure -and $null -ne $lockPayload) {
            $failureReceipt = Move-FrozenRunnerLockToFailureReceipt `
                -GlobalLockPath $globalLockPath `
                -ReceiptRoot $failureReceiptRoot `
                -LockPayload ([pscustomobject]$lockPayload) `
                -FailureReason $failureReason `
                -ErrorMessage $failureMessage `
                -MatlabProcessState ([pscustomobject]$matlabProcessState)
            $lockOwned = $false
            Write-Output "CONTROLLED_FAILURE_LOCK_ARCHIVED reason=$failureReason run_id=$($preflight.RunId) lock=$($failureReceipt.LockPath) receipt=$($failureReceipt.ReceiptPath) matlab_started=$($matlabProcessState.Started) matlab_process_id=$($matlabProcessState.ProcessId) matlab_exit_code=$($matlabProcessState.ExitCode) matlab_process_ended=$($matlabProcessState.ProcessEnded)"
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
    Invoke-FrozenSageRerunSingle -RunId $RunId -ShouldExecute:$Execute.IsPresent
}
