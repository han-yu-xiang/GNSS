[CmdletBinding()]
param(
    [switch]$Execute
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$script:FrozenProjectRoot = 'E:\GNSS_Multipath_Project'
$script:FrozenSceneId = 'F1023_V70_D0117_P2'
$script:FrozenPrn = 28
$script:FrozenPrnLabel = 'G28'
$script:FrozenChannel = 1
$script:FrozenSampleRateHz = 10230000
$script:FrozenSourceRelativePath = 'scripts\sage_pipeline\run_nav_sage_pipeline.m'
$script:FrozenSourceSha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
$script:FrozenManifestRelativePath = 'reports\data_consolidation_20261003\MAINLINE_SAGE_1023_RERUN_MANIFEST.csv'
$script:FrozenRunId = 'run_20261003_F1023_V70_D0117_P2_G28_ch1'
$script:FrozenNamespace = 'scenes\F1023_V70_D0117_P2\sage_results\rerun_20261003_frozen_v3\G28_ch1'
$script:TransientNamespace = 'scenes\F1023_V70_D0117_P2\sage_results\nav_sage_v2\G28'
$script:StartupMarker = 'MATLAB_STARTUP_OK'

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
    param([Parameter(Mandatory)][object]$Row)

    $expected = @{
        run_id = $script:FrozenRunId
        scene_id = $script:FrozenSceneId
        prn = $script:FrozenPrnLabel
        tracking_channel = '1'
        mapping_warning = 'NONE'
        frozen_sage_sha256 = $script:FrozenSourceSha256
        output_namespace = $script:FrozenNamespace
        resume = 'false'
        execution_status = 'NOT_STARTED'
    }
    foreach ($field in $expected.Keys) {
        $actual = [string]$Row.$field
        if ($field -eq 'output_namespace') {
            $actual = $actual.Replace('/', '\')
        }
        if (-not [string]::Equals($actual, [string]$expected[$field], [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "MANIFEST_ROW_MISMATCH field=$field expected=$($expected[$field]) actual=$actual"
        }
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

function Get-FrozenSageMatlabExpression {
    return 'run_nav_sage_pipeline("F1023_V70_D0117_P2",28,"TrackingChannel",1,"ProjectRoot","E:/GNSS_Multipath_Project","Resume",false)'
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
        execution_emitted_path = $StagingPath
        final_relocated_path = $FinalPath
        resume = $false
        matlab_start_utc = [string]$Context.MatlabStartUtc
        matlab_end_utc = [string]$Context.MatlabEndUtc
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
    param([Parameter(Mandatory)][bool]$ComputeRawHash)

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
    $targetRows = @($manifestRows | Where-Object { [string]$_.run_id -eq $script:FrozenRunId })
    if ($targetRows.Count -ne 1) {
        throw "MANIFEST_TARGET_CARDINALITY_MISMATCH expected=1 actual=$($targetRows.Count) run_id=$script:FrozenRunId"
    }
    $row = $targetRows[0]
    [void](Assert-FrozenSageManifestRow -Row $row)

    $metadataPath = Resolve-ManifestInputPath -Path ([string]$row.metadata_path) -ProjectRoot $script:FrozenProjectRoot
    $metadata = Get-Content -Raw -LiteralPath $metadataPath | ConvertFrom-Json
    if ([string]$metadata.scene_id -ne $script:FrozenSceneId -or [double]$metadata.signal.sample_rate_hz -ne $script:FrozenSampleRateHz) {
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

    $stagingPath = Join-Path $script:FrozenProjectRoot $script:TransientNamespace
    $finalPath = Join-Path $script:FrozenProjectRoot $script:FrozenNamespace
    [void](Assert-OutputNamespacesAbsent -StagingPath $stagingPath -FinalPath $finalPath)

    $matlab = Get-Command -Name 'matlab' -CommandType Application -ErrorAction Stop
    if (-not (Test-Path -LiteralPath $matlab.Source -PathType Leaf)) {
        throw "MATLAB_EXECUTABLE_MISSING path=$($matlab.Source)"
    }
    $rawInfo = Get-Item -LiteralPath $rawPath
    if ($rawInfo.Length -le 0) {
        throw "RAW_IQ_EMPTY path=$rawPath"
    }
    $rawHash = if ($ComputeRawHash) {
        (Get-FileHash -LiteralPath $rawPath -Algorithm SHA256).Hash.ToLowerInvariant()
    } else {
        ''
    }
    return [pscustomobject]@{
        ProjectRoot = $script:FrozenProjectRoot
        RunId = $script:FrozenRunId
        SceneId = $script:FrozenSceneId
        Prn = $script:FrozenPrn
        PrnLabel = $script:FrozenPrnLabel
        TrackingChannel = $script:FrozenChannel
        SampleRateHz = $script:FrozenSampleRateHz
        FrozenSageSha256 = $actualSourceHash
        RawPath = $rawPath
        RawIqSizeBytes = [long]$rawInfo.Length
        RawIqSha256 = $rawHash
        MatlabPath = $matlab.Source
        StagingPath = $stagingPath
        FinalPath = $finalPath
        ManifestRow = $row
    }
}

function Invoke-FrozenSageRerunSingle {
    param([Parameter(Mandatory)][bool]$ShouldExecute)

    $preflight = Get-FrozenSagePreflight -ComputeRawHash $ShouldExecute
    Write-Output "PREFLIGHT_PASS run_id=$($preflight.RunId) scene=$($preflight.SceneId) prn=$($preflight.PrnLabel) channel=$($preflight.TrackingChannel) sample_rate_hz=$($preflight.SampleRateHz) resume=false"
    if (-not $ShouldExecute) {
        Write-Output 'VALIDATION_ONLY matlab_invoked=false raw_iq_content_read=false'
        return
    }

    $executionLogParent = Join-Path $preflight.ProjectRoot 'dataset_generation_logs\batch_sage_execution'
    if (-not (Test-Path -LiteralPath $executionLogParent -PathType Container)) {
        throw "EXECUTION_LOG_PARENT_MISSING path=$executionLogParent"
    }
    $globalLockPath = Join-Path $executionLogParent '.windows_runner_active.lock'
    $lockStream = $null
    try {
        try {
            $lockStream = [System.IO.File]::Open($globalLockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        } catch [System.IO.IOException] {
            throw "GLOBAL_SAGE_RUNNER_LOCK_PRESENT path=$globalLockPath"
        }
        $lockPayload = [ordered]@{
            run_id = $preflight.RunId
            scene_id = $preflight.SceneId
            prn = $preflight.Prn
            tracking_channel = $preflight.TrackingChannel
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

        $currentSourceHash = (Get-FileHash -LiteralPath (Join-Path $preflight.ProjectRoot $script:FrozenSourceRelativePath) -Algorithm SHA256).Hash.ToLowerInvariant()
        [void](Assert-FrozenSageHash -ActualHash $currentSourceHash -ExpectedHash $script:FrozenSourceSha256)
        $expression = Get-FrozenSageMatlabExpression
        $rootForMatlab = $preflight.ProjectRoot.Replace('\', '/')
        $batchExpression = "cd('$rootForMatlab/scripts/sage_pipeline'); $expression"
        Write-Output 'SAGE_EXECUTION_BEGIN only_authorized_scene=F1023_V70_D0117_P2 prn=28 channel=1 resume=false'
        $sageRun = Invoke-FrozenMatlabBatch -MatlabPath $preflight.MatlabPath -Expression $batchExpression
        if ($sageRun.ExitCode -ne 0) {
            throw "SAGE_MATLAB_EXIT_NONZERO exit_code=$($sageRun.ExitCode); staging output, if any, is preserved."
        }
        [void](Assert-StageOutputsComplete -OutputPath $preflight.StagingPath)

        $postRunHash = (Get-FileHash -LiteralPath (Join-Path $preflight.ProjectRoot $script:FrozenSourceRelativePath) -Algorithm SHA256).Hash.ToLowerInvariant()
        [void](Assert-FrozenSageHash -ActualHash $postRunHash -ExpectedHash $script:FrozenSourceSha256)
        $context = [pscustomobject]@{
            SceneId = $preflight.SceneId
            Prn = $preflight.Prn
            TrackingChannel = $preflight.TrackingChannel
            FrozenSageSha256 = $postRunHash
            RawIqSizeBytes = $preflight.RawIqSizeBytes
            RawIqSha256 = $preflight.RawIqSha256
            MatlabStartUtc = $sageRun.StartedUtc
            MatlabEndUtc = $sageRun.EndedUtc
            MatlabExitCode = $sageRun.ExitCode
        }
        $receipt = Move-ValidatedStageOutput -StagingPath $preflight.StagingPath -FinalPath $preflight.FinalPath -Context $context

        $lockStream.Dispose()
        $lockStream = $null
        Move-Item -LiteralPath $globalLockPath -Destination (Join-Path $preflight.FinalPath 'windows_runner_lock_receipt.json') -ErrorAction Stop
        Write-Output "RELOCATION_VERIFIED final_path=$($preflight.FinalPath) files=$($receipt.destination_file_count_after_move) bytes=$($receipt.destination_bytes_after_move)"
        Write-Output "FROZEN_SAGE_SHA_AFTER=$postRunHash"
    } finally {
        if ($null -ne $lockStream) {
            $lockStream.Dispose()
        }
    }
}

function Invoke-FrozenMatlabBatch {
    param(
        [Parameter(Mandatory)][string]$MatlabPath,
        [Parameter(Mandatory)][string]$Expression
    )

    $startedUtc = [System.DateTimeOffset]::UtcNow
    $outputLines = @(& $MatlabPath -batch $Expression 2>&1 | ForEach-Object {
        $line = [string]$_
        Write-Host $line
        $line
    })
    $exitCode = $LASTEXITCODE
    $endedUtc = [System.DateTimeOffset]::UtcNow
    return [pscustomobject]@{
        ExitCode = [int]$exitCode
        Output = $outputLines -join [Environment]::NewLine
        StartedUtc = $startedUtc.ToString('o')
        EndedUtc = $endedUtc.ToString('o')
        DurationSeconds = [Math]::Round(($endedUtc - $startedUtc).TotalSeconds, 3)
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-FrozenSageRerunSingle -ShouldExecute:$Execute.IsPresent
}
