[CmdletBinding()]
param(
    [switch]$CreateReleaseRequest,
    [switch]$ValidateOnly,
    [switch]$Execute,
    [switch]$ExecuteWorker,
    [switch]$ReadBackExistingPilot,
    [switch]$ReadBackWorker,
    [switch]$FinalizePilotAudit,
    [switch]$ConfirmPilot,
    [string]$ReleaseRoot,
    [string[]]$PilotRunIds,
    [string]$RequestManifest,
    [string]$ExpectedRequestSha256,
    [string]$RunId,
    [string]$TaskName
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:ProjectRoot = 'E:\GNSS_Multipath_Project'
$script:CodeRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$script:RunnerPath = $PSCommandPath
$script:ReleaseBase = Join-Path $script:ProjectRoot 'dataset_generation_logs\channel_modeling'
$script:BatchLogRoot = Join-Path $script:ProjectRoot 'dataset_generation_logs\batch_sage_execution'
$script:ManifestPath = Join-Path $script:ProjectRoot 'reports\data_consolidation_20261003\MAINLINE_SAGE_1023_RERUN_MANIFEST.csv'
$script:SummaryPath = Join-Path $script:ProjectRoot 'reports\data_consolidation_20261003\MAINLINE_SAGE_1023_BATCH_RERUN_SUMMARY.csv'
$script:CohortRoot = Join-Path $script:ProjectRoot 'dataset_generation_logs\channel_modeling\mainline_1023_cohort_v1_20261022T082520Z'
$script:GateARoot = Join-Path $script:ProjectRoot 'reports\data_consolidation_20261003\mainline_1023_model_v1\audit_20261022T074307Z'
$script:SceneMetadataPath = Join-Path $script:ProjectRoot 'dataset_generation_logs\production_planning_10mhz_20260812\scene_metadata_10MHz.csv'
$script:GateATaskAuditPath = Join-Path $script:GateARoot 'task_audit.csv'
$script:CohortPath = Join-Path $script:CohortRoot 'cohort.json'
$script:CirTasksPath = Join-Path $script:CohortRoot 'cir_tasks.json'
$script:CohortValidationPath = Join-Path $script:CohortRoot 'cohort_validation.json'
$script:ExporterPath = Join-Path $PSScriptRoot 'export_gnss_code_domain_cir.m'
$script:ValidatorPath = Join-Path $PSScriptRoot 'validate_gnss_code_domain_cir.m'
$script:FrozenSagePath = Join-Path $script:ProjectRoot 'scripts\sage_pipeline\run_nav_sage_pipeline.m'
$script:FrozenConfigPath = Join-Path $script:ProjectRoot 'scripts\sage_pipeline\core\default_sage_configuration.m'
$script:ExpectedFrozenSageSha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
$script:ExpectedConfigSha256 = 'ac06ad3191ca7ca05480fb84c0465a5082c157f4eaad1ae3018e26e1abed1319'
$script:ExpectedUser = 'TJ-CHANNEL\Jing_'
$script:DelayComparisonPath = Join-Path $script:ProjectRoot 'reports\data_consolidation_20261003\CIR_PRIMARY_DELAY_COMPARISON.csv'
$script:BaselineAuditPath = Join-Path $script:ProjectRoot 'reports\data_consolidation_20261003\BASELINE_CIR_EXPORT_AUDIT.md'
$script:ExistingPilotRunId = 'run_20261003_F1023_V70_D0117_P2_G28_ch1'
$script:ApprovedPilotIds = @(
    'run_20261003_F1023_V70_D0120_P1_G18_ch2',
    'run_20261003_F1023_V70_D0120_P5_G23_ch0'
)
$script:MinimumFreeReserveBytes = 100GB
$script:ExpectedStatusCounts = [ordered]@{
    ALREADY_COMPLETE = 1
    COMPLETE = 82
    FAILED = 2
    IN_PROGRESS = 0
    PENDING = 4
}

function Get-Sha256 {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Required provenance file is missing: $Path"
    }
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Write-JsonNew {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)]$Value)
    if (Test-Path -LiteralPath $Path) { throw "Refusing to overwrite evidence file: $Path" }
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $json = ConvertTo-Json -InputObject $Value -Depth 24
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
}

function Write-JsonReplace {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)]$Value)
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $tempPath = Join-Path $parent ([IO.Path]::GetRandomFileName())
    $json = ConvertTo-Json -InputObject $Value -Depth 24
    [System.IO.File]::WriteAllText($tempPath, $json + [Environment]::NewLine, [System.Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $tempPath -Destination $Path -Force
}

function Resolve-ProjectPath {
    param([Parameter(Mandatory)][string]$RelativePath)
    $normalized = $RelativePath.Replace('/', '\')
    $candidate = [IO.Path]::GetFullPath((Join-Path $script:ProjectRoot $normalized))
    $rootPrefix = $script:ProjectRoot.TrimEnd('\') + '\'
    if (-not $candidate.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Project-relative pin escapes the project root: $RelativePath"
    }
    $candidate
}

function Get-RelativeProjectPath {
    param([Parameter(Mandatory)][string]$Path)
    $full = [IO.Path]::GetFullPath($Path)
    $rootPrefix = $script:ProjectRoot.TrimEnd('\') + '\'
    if (-not $full.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Pinned file is outside the project root: $Path"
    }
    $full.Substring($rootPrefix.Length).Replace('\', '/')
}

function Get-JsonDocument {
    param([Parameter(Mandatory)][string]$Path)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { throw "Required JSON is missing: $Path" }
    Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
}

function ConvertTo-UtcDateTimeOffset {
    param([Parameter(Mandatory)]$Value)
    if ($Value -is [DateTime]) {
        return [DateTimeOffset]::new(([DateTime]$Value).ToUniversalTime())
    }
    [DateTimeOffset]::Parse([string]$Value, [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::RoundtripKind).ToUniversalTime()
}

function Get-UniqueRow {
    param(
        [Parameter(Mandatory)]$Rows,
        [Parameter(Mandatory)][string]$Property,
        [Parameter(Mandatory)][string]$Value,
        [Parameter(Mandatory)][string]$Description
    )
    $matches = @($Rows | Where-Object { [string]$_.$Property -eq $Value })
    if ($matches.Count -ne 1) { throw "$Description must have exactly one row for $Value; found $($matches.Count)." }
    $matches[0]
}

function Get-CurrentCountSnapshot {
    $manifest = @(Import-Csv -LiteralPath $script:ManifestPath)
    $summary = @(Import-Csv -LiteralPath $script:SummaryPath)
    if ($manifest.Count -ne 89 -or $summary.Count -ne 89) {
        throw "Manifest and Summary must each have 89 rows; got $($manifest.Count)/$($summary.Count)."
    }
    $manifestIds = @($manifest | ForEach-Object { [string]$_.run_id } | Sort-Object -Unique)
    $summaryIds = @($summary | ForEach-Object { [string]$_.run_id } | Sort-Object -Unique)
    if ($manifestIds.Count -ne 89 -or $summaryIds.Count -ne 89 -or
        @((Compare-Object -ReferenceObject $manifestIds -DifferenceObject $summaryIds)).Count -ne 0) {
        throw 'Manifest/Summary exact run_id identity sets do not match.'
    }
    $counts = [ordered]@{ ALREADY_COMPLETE = 0; COMPLETE = 0; FAILED = 0; IN_PROGRESS = 0; PENDING = 0 }
    foreach ($row in $summary) {
        $status = ([string]$row.execution_status).Trim().ToUpperInvariant()
        if (-not $counts.Contains($status)) { throw "Unknown/empty Summary execution_status for $($row.run_id): '$status'" }
        $counts[$status]++
    }
    foreach ($key in $script:ExpectedStatusCounts.Keys) {
        if ($counts[$key] -ne $script:ExpectedStatusCounts[$key]) {
            throw "Current Summary count $key=$($counts[$key]) differs from audited freeze $($script:ExpectedStatusCounts[$key])."
        }
    }
    [pscustomobject]@{
        manifest_rows = $manifest
        rows = $summary
        counts = $counts
        manifest_sha256 = Get-Sha256 $script:ManifestPath
        summary_sha256 = Get-Sha256 $script:SummaryPath
    }
}

function Get-TaskPin {
    param(
        [Parameter(Mandatory)][string]$Id,
        [Parameter(Mandatory)]$Cohort,
        [Parameter(Mandatory)]$CirTasks,
        [Parameter(Mandatory)]$GateRows,
        [Parameter(Mandatory)]$ManifestRows,
        [Parameter(Mandatory)]$SummaryRows,
        [Parameter(Mandatory)]$SceneRows
    )
    $cohortTask = Get-UniqueRow $Cohort.tasks 'run_id' $Id 'Cohort task'
    $cirTask = Get-UniqueRow $CirTasks.tasks 'run_id' $Id 'CIR task'
    $gate = Get-UniqueRow $GateRows 'run_id' $Id 'Gate A task audit'
    $manifest = Get-UniqueRow $ManifestRows 'run_id' $Id 'Mainline Manifest'
    $summary = Get-UniqueRow $SummaryRows 'run_id' $Id 'Mainline Summary'
    $scene = Get-UniqueRow $SceneRows 'scene_id' ([string]$cohortTask.scene_id) 'Scene metadata'
    if ([string]$cirTask.task_status -ne 'NEW_REQUIRED' -or
        [string]$cohortTask.source_summary_status -ne 'COMPLETE' -or
        [string]$summary.execution_status -ne 'COMPLETE' -or
        [string]$gate.audit_status -ne 'PASS') {
        throw "Pilot $Id is not a COMPLETE, Gate-A-PASS, NEW_REQUIRED identity."
    }
    if ([string]$cohortTask.mapping_warning -ne '' -and [string]$cohortTask.mapping_warning -ne 'NONE') {
        throw "Pilot $Id has a mapping warning and is not eligible."
    }
    if ([string]$cohortTask.scene_id -ne [string]$cirTask.scene_id -or
        [string]$cohortTask.prn -ne [string]$cirTask.prn -or
        [int]$cohortTask.tracking_channel -ne [int]$cirTask.tracking_channel -or
        [string]$cohortTask.output_namespace -ne [string]$cirTask.output_namespace) {
        throw "Cohort/cir_tasks identity mismatch for $Id."
    }
    foreach ($property in @('scene_id','prn','tracking_channel')) {
        if ([string]$manifest.$property -ne [string]$summary.$property -or
            [string]$manifest.$property -ne [string]$cohortTask.$property) {
            throw "Manifest/Summary/cohort identity mismatch for $Id ($property)."
        }
    }
    if ([string]$scene.raw_file_path -notmatch '^[A-Za-z]:\\' -or
        [long]$scene.raw_file_size_bytes -ne [long]$gate.raw_iq_size_bytes -or
        [double]$scene.sample_rate -ne 10230000) {
        throw "Unique scene metadata and same-run Gate A raw-size/sample-rate pins disagree for $Id."
    }
    $rawPath = [IO.Path]::GetFullPath(([string]$scene.raw_file_path).Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $rawPath -PathType Leaf)) { throw "Raw IQ file is missing for ${Id}: $rawPath" }
    $rawInfo = Get-Item -LiteralPath $rawPath
    if ([long]$rawInfo.Length -ne [long]$gate.raw_iq_size_bytes) {
        throw "Raw IQ current byte size differs from unique scene metadata/Gate A for $Id."
    }
    $stagePins = [ordered]@{}
    foreach ($entry in @(
        @{ Name = 'stage0_valid_windows'; Source = $cohortTask.stage_csvs.stage0_valid_windows },
        @{ Name = 'stage2_selected_paths'; Source = $cohortTask.stage_csvs.stage2_selected_paths }
    )) {
        $source = $entry.Source
        if ($null -eq $source) { throw "Missing frozen $($entry.Name) pin for $Id." }
        $path = Resolve-ProjectPath ([string]$source.path)
        $info = Get-Item -LiteralPath $path -ErrorAction Stop
        $hash = Get-Sha256 $path
        if ([long]$info.Length -ne [long]$source.size_bytes -or $hash -ne [string]$source.sha256) {
            throw "Frozen $($entry.Name) size/SHA mismatch for $Id."
        }
        $stagePins[$entry.Name] = [ordered]@{
            path = [string]$source.path
            size_bytes = [long]$source.size_bytes
            sha256 = [string]$source.sha256
            last_write_time_utc = $info.LastWriteTimeUtc.ToString('o')
        }
    }
    [pscustomobject]@{
        run_id = $Id
        scene_id = [string]$cohortTask.scene_id
        prn = [string]$cohortTask.prn
        tracking_channel = [int]$cohortTask.tracking_channel
        environment_class = [string]$gate.environment_class
        elevation_group = [string]$gate.elevation_group
        mean_elevation_deg = [double]$gate.mean_elevation_deg
        task_status = [string]$cirTask.task_status
        summary_status = [string]$summary.execution_status
        output_namespace = [string]$cohortTask.output_namespace
        sample_rate_hz = [long]$scene.sample_rate
        raw_iq_path = $rawPath
        raw_iq_size_bytes = [long]$gate.raw_iq_size_bytes
        stage0_window_count = [int]$cohortTask.stage_counts_from_gate_a.stage0_valid_40ms_windows
        stage2_selected_path_count = [int]$cohortTask.stage_counts_from_gate_a.stage2_selected_path_count
        stage_csvs = $stagePins
    }
}

function Test-TaskPinPropertyMatch {
    param([Parameter(Mandatory)][string]$Property, [AllowNull()]$PinnedValue, [AllowNull()]$RequestedValue)
    if ($null -eq $PinnedValue -or $null -eq $RequestedValue) { return $false }
    if ($Property -eq 'mean_elevation_deg') {
        try {
            return ([Math]::Abs([double]$PinnedValue - [double]$RequestedValue) -le 1e-10)
        } catch {
            return $false
        }
    }
    return ([string]$PinnedValue -eq [string]$RequestedValue)
}

function Get-SourcePins {
    $pins = [ordered]@{}
    $pins['scripts/channel_modeling/Invoke-Mainline1023CIRSingle.ps1'] = Get-Sha256 $script:RunnerPath
    $pins['scripts/channel_modeling/export_gnss_code_domain_cir.m'] = Get-Sha256 $script:ExporterPath
    $pins['scripts/channel_modeling/validate_gnss_code_domain_cir.m'] = Get-Sha256 $script:ValidatorPath
    $pins['scripts/sage_pipeline/run_nav_sage_pipeline.m'] = Get-Sha256 $script:FrozenSagePath
    $pins['scripts/sage_pipeline/core/default_sage_configuration.m'] = Get-Sha256 $script:FrozenConfigPath
    if ($pins['scripts/sage_pipeline/run_nav_sage_pipeline.m'] -ne $script:ExpectedFrozenSageSha256 -or
        $pins['scripts/sage_pipeline/core/default_sage_configuration.m'] -ne $script:ExpectedConfigSha256) {
        throw 'Frozen SAGE/configuration pins differ from the Task 3 release contract.'
    }
    $pins
}

function Assert-ReleaseRequestContract {
    param(
        [Parameter(Mandatory)]$Request,
        [Parameter(Mandatory)][System.Collections.IDictionary]$CurrentSourcePins
    )
    if ($Request.execution_policy -isnot [string] -or
        $Request.execution_policy -cne 'MANUAL_ONLY_SERIAL_ONE_TASK_PER_INVOCATION_NO_RETRY') {
        throw 'Release execution policy must remain manual-only, serial, one-task-per-invocation, and no-retry.'
    }
    if ($Request.resume -isnot [bool] -or $Request.resume -ne $false) {
        throw 'Release resume policy must remain false.'
    }
    if (($Request.max_parallel_matlab -isnot [int] -and
         $Request.max_parallel_matlab -isnot [long]) -or
        [long]$Request.max_parallel_matlab -ne 1) {
        throw 'Release max_parallel_matlab policy must remain exactly 1.'
    }
    if ($null -eq $Request.source_sha256) {
        throw 'Release source pin set is missing.'
    }
    $expectedPaths = @($CurrentSourcePins.Keys | ForEach-Object { [string]$_ } | Sort-Object -CaseSensitive)
    $providedPaths = @($Request.source_sha256.PSObject.Properties.Name | Sort-Object -CaseSensitive)
    if ($expectedPaths.Count -ne $providedPaths.Count -or
        ($expectedPaths -join "`n") -cne ($providedPaths -join "`n")) {
        throw 'Release source pin set is incomplete or contains unexpected keys.'
    }
    foreach ($sourcePath in $expectedPaths) {
        $requestedPin = $Request.source_sha256.$sourcePath
        if ($requestedPin -isnot [string] -or
            $CurrentSourcePins[$sourcePath] -isnot [string] -or
            $CurrentSourcePins[$sourcePath] -cne $requestedPin) {
            throw "Source SHA pin changed: $sourcePath"
        }
    }
}

function Get-StorageEventsSince {
    param([Parameter(Mandatory)][DateTimeOffset]$SinceUtc)
    $events = @(Get-WinEvent -FilterHashtable @{ LogName = 'System'; StartTime = $SinceUtc.UtcDateTime } -ErrorAction Stop)
    $badIds = @(7, 11, 15, 51, 55, 98, 129, 153, 157)
    $matching = @($events | Where-Object {
        $provider = [string]$_.ProviderName
        $isStorageProvider = $provider -match '(?i)disk|ntfs|stor|usb|kernel-pnp|volmgr|partmgr'
        $message = [string]$_.Message
        $mentionsTarget = $message -match '(?i)(E:|Kingston XS1000|VID_174C|PID_55AA)'
        $describesFailure = $message -match '(?i)(error|failed|failure|disconnect|surprise.?remov|device was not ready|bad block|I/O device error|reset to device|controller error|corrupt)'
        ($isStorageProvider -and $_.Id -in $badIds -and $_.Level -le 3) -or
        ($mentionsTarget -and $describesFailure)
    } | Select-Object TimeCreated, Id, ProviderName, LevelDisplayName, RecordId, Message)
    $matching
}

function Get-LiveExecutionState {
    param([string]$AllowedTaskName = '')
    $matlab = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '(?i)^matlab' })
    if ($matlab.Count -gt 0) {
        throw "MATLAB process already active; refusing concurrent CIR execution/validation: $($matlab.Id -join ',')."
    }
    $tasks = @(Get-ScheduledTask -ErrorAction Stop | Where-Object {
        $_.State -in @('Running','Queued') -and $_.TaskName -match '(?i)(SAGE|CIR)'
    })
    $unexpectedTasks = @($tasks | Where-Object { $_.TaskName -ne $AllowedTaskName })
    if ($unexpectedTasks.Count -gt 0) {
        throw "Another SAGE/CIR scheduled task is running: $($unexpectedTasks.TaskName -join ',')."
    }
    $lockPath = Join-Path $script:BatchLogRoot '.windows_runner_active.lock'
    if (Test-Path -LiteralPath $lockPath) {
        throw "Global SAGE/CIR execution lock exists; preserving it and refusing to proceed: $lockPath"
    }
}

function Assert-NoOtherExecutionProcess {
    param([string]$AllowedTaskName = '')
    $matlab = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '(?i)^matlab' })
    if ($matlab.Count -gt 0) { throw "MATLAB process became active before the worker acquired its execution slot: $($matlab.Id -join ',')." }
    $tasks = @(Get-ScheduledTask -ErrorAction Stop | Where-Object {
        $_.State -in @('Running','Queued') -and $_.TaskName -match '(?i)(SAGE|CIR)' -and $_.TaskName -ne $AllowedTaskName
    })
    if ($tasks.Count -gt 0) { throw "Another SAGE/CIR task became active before execution: $($tasks.TaskName -join ',')." }
}

function Get-VolumeBudget {
    param([Parameter(Mandatory)]$Cohort)
    $newTasks = @($Cohort.tasks | Where-Object { $_.source_summary_status -eq 'COMPLETE' })
    if ($newTasks.Count -ne 82) { throw "Expected 82 COMPLETE CIR-required cohort identities; found $($newTasks.Count)." }
    $baselinePath = Join-Path $script:ProjectRoot 'scenes\F1023_V70_D0117_P2\sage_results\rerun_20261003_frozen_v3\G28_ch1\G28_ch1_code_domain_cir.h5'
    $baselineLength = [long](Get-Item -LiteralPath $baselinePath).Length
    $baselineWindows = 898.0
    $bytesPerWindow = $baselineLength / $baselineWindows
    [long]$totalWindows = 0
    foreach ($newTask in $newTasks) { $totalWindows += [long]$newTask.stage_counts_from_gate_a.stage0_valid_40ms_windows }
    $estimatedBytes = [long][Math]::Ceiling($totalWindows * $bytesPerWindow * 1.25)
    $drive = [IO.DriveInfo]::new('E:\')
    $freeBytes = [long]$drive.AvailableFreeSpace
    $volume = Get-Volume -DriveLetter E -ErrorAction Stop
    $partition = Get-Partition -DriveLetter E -ErrorAction Stop
    $disk = Get-Disk -Number $partition.DiskNumber -ErrorAction Stop
    if ($disk.IsOffline -or $disk.IsReadOnly -or [string]$disk.OperationalStatus -ne 'Online' -or [string]$disk.HealthStatus -ne 'Healthy') {
        throw "E: Kingston physical disk is not Online/Healthy writable; preserving state. Health=$($disk.HealthStatus) Operational=$($disk.OperationalStatus)."
    }
    $requiredBytes = $estimatedBytes + [long]$script:MinimumFreeReserveBytes
    [pscustomobject]@{
        baseline_bytes = $baselineLength
        baseline_windows = [long]$baselineWindows
        estimated_bytes_per_window = [Math]::Ceiling($bytesPerWindow)
        new_required_task_count = $newTasks.Count
        new_required_windows = $totalWindows
        estimate_multiplier = 1.25
        estimated_new_cir_bytes = $estimatedBytes
        minimum_free_reserve_bytes = [long]$script:MinimumFreeReserveBytes
        current_e_free_bytes = $freeBytes
        required_current_free_bytes = $requiredBytes
        enough_space = ($freeBytes -ge $requiredBytes)
        storage_health = [ordered]@{
            volume_file_system = [string]$volume.FileSystem
            volume_health_status = [string]$volume.HealthStatus
            volume_operational_status = [string]$volume.OperationalStatus
            disk_number = [int]$disk.Number
            disk_friendly_name = [string]$disk.FriendlyName
            disk_bus_type = [string]$disk.BusType
            disk_health_status = [string]$disk.HealthStatus
            disk_operational_status = [string]$disk.OperationalStatus
            disk_is_offline = [bool]$disk.IsOffline
            disk_is_read_only = [bool]$disk.IsReadOnly
            accepted_preexisting_volume_warning = ([string]$volume.HealthStatus -eq 'Warning' -or [string]$volume.OperationalStatus -eq 'Full Repair Needed')
        }
    }
}

function Get-PilotAudit {
    param([Parameter(Mandatory)][string]$Root)
    $auditPath = Join-Path $Root 'pilot_audit.json'
    if (Test-Path -LiteralPath $auditPath -PathType Leaf) { return Get-JsonDocument $auditPath }
    [pscustomobject]@{ schema_version = 1; release_request_sha256 = ''; pilots = @() }
}

function Set-PilotAuditFinalAcceptance {
    param(
        [Parameter(Mandatory)][psobject]$Audit,
        [Parameter(Mandatory)]$FinalAcceptance
    )
    Add-Member -InputObject $Audit -MemberType NoteProperty -Name status `
        -Value 'PILOTS_PASS_BULK_BATCH_NOT_STARTED' -Force
    Add-Member -InputObject $Audit -MemberType NoteProperty -Name final_acceptance `
        -Value $FinalAcceptance -Force
    $Audit
}

function Assert-PilotSequenceReady {
    param([Parameter(Mandatory)]$Request, [Parameter(Mandatory)][string]$ForRunId)
    $requestPath = Join-Path ([string]$Request.release_root) 'release_request.json'
    $audit = Get-PilotAudit ([string]$Request.release_root)
    if ([string]$audit.release_request_sha256 -ne (Get-Sha256 $requestPath)) {
        throw 'pilot_audit.json is not bound to the immutable release request.'
    }
    if ($audit.baseline_readback.status -ne 'PASS') {
        throw 'The read-only G28/ch1 baseline read-back must PASS before either new pilot.'
    }
    if (@($audit.pilots | Where-Object { $_.status -ne 'PASS' }).Count -gt 0) {
        throw 'A prior pilot failed; batch is stopped and no later pilot may start.'
    }
    $firstPassed = @($audit.pilots | Where-Object { $_.run_id -eq $script:ApprovedPilotIds[0] -and $_.status -eq 'PASS' }).Count -eq 1
    $secondPassed = @($audit.pilots | Where-Object { $_.run_id -eq $script:ApprovedPilotIds[1] -and $_.status -eq 'PASS' }).Count -eq 1
    if ($ForRunId -eq $script:ApprovedPilotIds[0] -and ($firstPassed -or $secondPassed)) {
        throw 'Pilot sequence is already past its first run; no retry/order reversal.'
    }
    if ($ForRunId -eq $script:ApprovedPilotIds[1] -and (-not $firstPassed -or $secondPassed)) {
        throw 'The second pilot is allowed only once after the first pilot PASS receipt.'
    }
}

function Assert-NewPilotOutputNamespace {
    param([Parameter(Mandatory)]$Request, [Parameter(Mandatory)]$TaskPin)
    $runRoot = Join-Path (Join-Path $Request.release_root 'runs') $TaskPin.run_id
    if (Test-Path -LiteralPath $runRoot) { throw "Run namespace already exists; refusing retry or overwrite: $runRoot" }
    $sceneOutput = Resolve-ProjectPath $TaskPin.output_namespace
    $stem = "$($TaskPin.prn)_ch$($TaskPin.tracking_channel)_code_domain_cir"
    $targets = @((Join-Path $sceneOutput "$stem.h5"), (Join-Path $sceneOutput "${stem}_metadata.json"),
        (Join-Path $sceneOutput "$($TaskPin.prn)_ch$($TaskPin.tracking_channel)_primary_delay_comparison.csv"))
    foreach ($target in $targets) {
        if (Test-Path -LiteralPath $target) {
            throw "CIR must not overwrite an existing scientific-namespace output: $target"
        }
    }
}

function Get-ValidatedSnapshot {
    param([Parameter(Mandatory)][string]$RequestPath, [Parameter(Mandatory)][string]$ExpectedHash, [string]$ForRunId = '', [string]$AllowedTaskName = '', [switch]$SkipLockCheck)
    if (-not (Test-Path -LiteralPath $RequestPath -PathType Leaf)) { throw "Request manifest is missing: $RequestPath" }
    $actualHash = Get-Sha256 $RequestPath
    if ($actualHash -ne $ExpectedHash.ToLowerInvariant()) { throw 'Immutable request SHA256 does not match the caller pin.' }
    $request = Get-JsonDocument $RequestPath
    if ([string]$request.schema_version -ne '1' -or [string]$request.release_root -ne [IO.Path]::GetFullPath([string]$request.release_root)) {
        throw 'Malformed or noncanonical release request.'
    }
    $expectedRoot = [IO.Path]::GetFullPath($script:ReleaseBase).TrimEnd('\') + '\'
    $requestRoot = [IO.Path]::GetFullPath([string]$request.release_root)
    if (-not $requestRoot.StartsWith($expectedRoot, [StringComparison]::OrdinalIgnoreCase)) { throw 'Release root is outside the approved new-only CIR release directory.' }
    if ((Get-Sha256 $script:CohortPath) -ne [string]$request.inputs.cohort_sha256 -or
        (Get-Sha256 $script:CirTasksPath) -ne [string]$request.inputs.cir_tasks_sha256 -or
        (Get-Sha256 $script:CohortValidationPath) -ne [string]$request.inputs.cohort_validation_sha256 -or
        (Get-Sha256 $script:ManifestPath) -ne [string]$request.inputs.manifest_sha256 -or
        (Get-Sha256 $script:SummaryPath) -ne [string]$request.inputs.summary_sha256 -or
        (Get-Sha256 $script:SceneMetadataPath) -ne [string]$request.inputs.scene_metadata_sha256 -or
        (Get-Sha256 $script:GateATaskAuditPath) -ne [string]$request.inputs.gate_a_task_audit_sha256) {
        throw 'One or more pinned cohort, manifest, summary, scene-metadata, or Gate-A inputs changed.'
    }
    $currentSources = Get-SourcePins
    Assert-ReleaseRequestContract -Request $request -CurrentSourcePins $currentSources
    $cohort = Get-JsonDocument $script:CohortPath
    $cirTasks = Get-JsonDocument $script:CirTasksPath
    $cohortValidation = Get-JsonDocument $script:CohortValidationPath
    if ($cohort.eligible_count -ne 83 -or $cohort.excluded_count -ne 6 -or
        $cohortValidation.validation_status -ne 'PASS' -or $cohortValidation.gate_b_pass -ne $true -or
        $cohortValidation.hdf5_payload_opened -ne $false -or $cohortValidation.mat_payload_opened -ne $false -or
        $cohortValidation.raw_iq_content_read -ne $false -or $cohortValidation.raw_iq_hash_recomputed -ne $false) {
        throw 'Frozen 83-task cohort validation did not pass the expected no-payload/no-raw gate.'
    }
    $snapshot = Get-CurrentCountSnapshot
    if ($snapshot.manifest_sha256 -ne [string]$request.inputs.manifest_sha256 -or
        $snapshot.summary_sha256 -ne [string]$request.inputs.summary_sha256) {
        throw 'Current Manifest/Summary content differs from the request snapshot.'
    }
    $gateRows = @(Import-Csv -LiteralPath $script:GateATaskAuditPath)
    $summaryRows = @($snapshot.rows)
    $sceneRows = @(Import-Csv -LiteralPath $script:SceneMetadataPath)
    $resolvedPins = @()
    foreach ($requestedTask in $request.tasks) {
        $pin = Get-TaskPin ([string]$requestedTask.run_id) $cohort $cirTasks $gateRows $snapshot.manifest_rows $summaryRows $sceneRows
        foreach ($property in @('scene_id','prn','tracking_channel','raw_iq_path','raw_iq_size_bytes','environment_class','elevation_group','mean_elevation_deg','stage0_window_count','stage2_selected_path_count')) {
            if (-not (Test-TaskPinPropertyMatch $property $pin.$property $requestedTask.$property)) {
                throw "Request identity/provenance mismatch for $($requestedTask.run_id): $property"
            }
        }
        foreach ($stageName in @('stage0_valid_windows','stage2_selected_paths')) {
            if ([string]$pin.stage_csvs.$stageName.path -ne [string]$requestedTask.stage_csvs.$stageName.path -or
                [string]$pin.stage_csvs.$stageName.sha256 -ne [string]$requestedTask.stage_csvs.$stageName.sha256 -or
                [long]$pin.stage_csvs.$stageName.size_bytes -ne [long]$requestedTask.stage_csvs.$stageName.size_bytes) {
                throw "Frozen stage-input pin mismatch for $($requestedTask.run_id): $stageName"
            }
        }
        $resolvedPins += $pin
    }
    if (@($request.tasks).Count -ne 2 -or
        [string]$request.tasks[0].run_id -ne $script:ApprovedPilotIds[0] -or
        [string]$request.tasks[1].run_id -ne $script:ApprovedPilotIds[1] -or
        $request.tasks[0].scene_id -eq $request.tasks[1].scene_id -or
        $request.tasks[0].environment_class -ne 'Urban' -or $request.tasks[1].environment_class -ne 'Urban' -or
        $request.tasks[0].elevation_group -eq $request.tasks[1].elevation_group) {
        throw 'Release request must contain the two approved Urban tasks from distinct scenes and elevation groups.'
    }
    $auditPath = Join-Path ([string]$request.release_root) 'pilot_audit.json'
    $auditHasFailure = $false
    if (Test-Path -LiteralPath $auditPath -PathType Leaf) {
        $auditHasFailure = @((Get-PilotAudit ([string]$request.release_root)).pilots | Where-Object { $_.status -ne 'PASS' }).Count -gt 0
    }
    if ($auditHasFailure) {
        throw 'A prior pilot failure is recorded; no later task may continue.'
    }
    if ($ForRunId) {
        $requestedTask = @($request.tasks | Where-Object { $_.run_id -eq $ForRunId })
        if ($requestedTask.Count -ne 1) { throw "RunId is not one of the two pinned pilot identities: $ForRunId" }
        $targetPin = @($resolvedPins | Where-Object run_id -eq $ForRunId)[0]
        Assert-NewPilotOutputNamespace $request $targetPin
    }
    $budget = Get-VolumeBudget $cohort
    if (-not $budget.enough_space) {
        throw "E: free-space budget fails closed: free=$($budget.current_e_free_bytes), estimated=$($budget.estimated_new_cir_bytes), reserve=$($budget.minimum_free_reserve_bytes)."
    }
    foreach ($field in @('volume_file_system','volume_health_status','volume_operational_status','disk_number','disk_friendly_name','disk_bus_type','disk_health_status','disk_operational_status','disk_is_offline','disk_is_read_only')) {
        if ([string]$budget.storage_health.$field -ne [string]$request.space_budget_at_release.storage_health.$field) {
            throw "E: storage identity/health changed since release creation ($field); stopping before execution."
        }
    }
    if (-not $SkipLockCheck) { Get-LiveExecutionState -AllowedTaskName $AllowedTaskName }
    $since = ConvertTo-UtcDateTimeOffset $request.created_utc
    $storageEvents = @(Get-StorageEventsSince $since)
    if ($storageEvents.Count -gt 0) {
        $ids = ($storageEvents | ForEach-Object { "$( $_.TimeCreated.ToUniversalTime().ToString('o') )/$($_.Id)/$($_.ProviderName)/$($_.RecordId)" }) -join '; '
        throw "New matching System disk/USB events since request creation; stopping without execution: $ids"
    }
    [pscustomobject]@{
        request = $request
        request_sha256 = $actualHash
        task_pins = $resolvedPins
        selected_pin = if ($ForRunId) { @($resolvedPins | Where-Object run_id -eq $ForRunId)[0] } else { $null }
        counts = $snapshot.counts
        space_budget = $budget
        validated_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
        new_storage_events = @()
        matlab_invoked = $false
    }
}

function New-ReleaseRequest {
    if (-not $ReleaseRoot) { throw '-ReleaseRoot is required with -CreateReleaseRequest.' }
    if (@($PilotRunIds).Count -ne 2) { throw 'Exactly two -PilotRunIds are required.' }
    $fullRoot = [IO.Path]::GetFullPath($ReleaseRoot)
    $basePrefix = [IO.Path]::GetFullPath($script:ReleaseBase).TrimEnd('\') + '\'
    if (-not $fullRoot.StartsWith($basePrefix, [StringComparison]::OrdinalIgnoreCase) -or
        (Split-Path -Leaf $fullRoot) -notmatch '^mainline_1023_cir_v1_[A-Za-z0-9_]+$') {
        throw 'ReleaseRoot must be a unique mainline_1023_cir_v1_<UTC> directory directly under dataset_generation_logs/channel_modeling.'
    }
    if (Test-Path -LiteralPath $fullRoot) { throw "ReleaseRoot already exists; refusing overwrite: $fullRoot" }
    if (([string]$PilotRunIds[0] -ne $script:ApprovedPilotIds[0]) -or
        ([string]$PilotRunIds[1] -ne $script:ApprovedPilotIds[1])) {
        throw 'Pilot run IDs must exactly match the two Gate-A-supported Urban/different-elevation identities.'
    }
    $cohort = Get-JsonDocument $script:CohortPath
    $cirTasks = Get-JsonDocument $script:CirTasksPath
    $cohortValidation = Get-JsonDocument $script:CohortValidationPath
    if ($cohortValidation.validation_status -ne 'PASS' -or $cohortValidation.gate_b_pass -ne $true) { throw 'Frozen cohort Gate B is not PASS.' }
    $snapshot = Get-CurrentCountSnapshot
    $gateRows = @(Import-Csv -LiteralPath $script:GateATaskAuditPath)
    $sceneRows = @(Import-Csv -LiteralPath $script:SceneMetadataPath)
    Get-LiveExecutionState
    $storageNow = @(Get-StorageEventsSince ([DateTimeOffset]::UtcNow.AddMinutes(-5)))
    if ($storageNow.Count -gt 0) { throw 'Recent matching System storage event detected before release creation; preserve state and investigate.' }
    $tasks = @()
    foreach ($id in $PilotRunIds) {
        $tasks += Get-TaskPin $id $cohort $cirTasks $gateRows $snapshot.manifest_rows $snapshot.rows $sceneRows
    }
    if ($tasks[0].scene_id -eq $tasks[1].scene_id -or
        $tasks[0].environment_class -ne 'Urban' -or $tasks[1].environment_class -ne 'Urban' -or
        $tasks[0].elevation_group -eq $tasks[1].elevation_group) {
        throw 'Selected pilots must be distinct Urban scenes with distinct supported elevation groups.'
    }
    $baselineRun = $script:ExistingPilotRunId
    $baselineTask = Get-UniqueRow $cohort.tasks 'run_id' $baselineRun 'Existing G28 pilot cohort row'
    $baselineCir = Get-UniqueRow $cirTasks.tasks 'run_id' $baselineRun 'Existing G28 pilot cir_tasks row'
    $baselineSummary = Get-UniqueRow $snapshot.rows 'run_id' $baselineRun 'Existing G28 pilot Summary row'
    if ($baselineCir.task_status -ne 'EXISTING_VALIDATED' -or $baselineSummary.execution_status -ne 'ALREADY_COMPLETE') {
        throw 'Existing G28/ch1 pilot is not in its expected already-complete validated state.'
    }
    $baselineNamespace = Resolve-ProjectPath $baselineTask.output_namespace
    $baselineH5 = Join-Path $baselineNamespace 'G28_ch1_code_domain_cir.h5'
    $baselineMetadata = Join-Path $baselineNamespace 'G28_ch1_code_domain_cir_metadata.json'
    $baselineComparison = $script:DelayComparisonPath
    foreach ($path in @($baselineH5, $baselineMetadata, $baselineComparison)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Existing pilot read-back input is missing: $path" }
    }
    $baselineH5Info = Get-Item -LiteralPath $baselineH5
    $baselineMetadataJson = Get-JsonDocument $baselineMetadata
    if ($baselineMetadataJson.run_id -ne $baselineRun -or $baselineMetadataJson.stage0_window_count -ne 898 -or
        $baselineMetadataJson.cir_snapshot_count -ne 35920 -or $baselineMetadataJson.delay_grid_count -ne 451 -or
        $baselineMetadataJson.amplitude_reference_status -ne 'UNKNOWN_RECEIVER_GAIN_OR_AGC' -or
        $baselineMetadataJson.primary_delay_comparison.count -ne 54 -or
        [Math]::Abs([double]$baselineMetadataJson.primary_delay_comparison.max_abs_difference_samples - 32.5) -gt 1e-12 -or
        [Math]::Abs([double]$baselineMetadataJson.primary_delay_comparison.median_signed_difference_samples - 0.1) -gt 1e-12) {
        throw 'Existing G28 pilot metadata does not match its frozen identity/shape/unknown-amplitude baseline.'
    }
    $volumeBudget = Get-VolumeBudget $cohort
    if (-not $volumeBudget.enough_space) { throw 'E: does not meet the CIR forecast plus 100 GiB reserve.' }
    $createdUtc = [DateTimeOffset]::UtcNow
    $request = [ordered]@{
        schema_version = 1
        release_id = (Split-Path -Leaf $fullRoot)
        created_utc = $createdUtc.ToString('o')
        project_root = $script:ProjectRoot
        release_root = $fullRoot
        execution_policy = 'MANUAL_ONLY_SERIAL_ONE_TASK_PER_INVOCATION_NO_RETRY'
        mode = 'FROZEN_SAGE_CIR_STAGE2_EXPORT'
        scientific_algorithm_modified = $false
        resume = $false
        max_parallel_matlab = 1
        permitted_raw_iq_access = 'ONLY_THE_UNIQUE_SCENE_METADATA_ROW_FOR_THE_SELECTED_RUN_ID_DURING_CONFIRMED_PILOT_EXECUTION'
        inputs = [ordered]@{
            manifest_sha256 = $snapshot.manifest_sha256
            summary_sha256 = $snapshot.summary_sha256
            cohort_path = Get-RelativeProjectPath $script:CohortPath
            cohort_sha256 = Get-Sha256 $script:CohortPath
            cir_tasks_path = Get-RelativeProjectPath $script:CirTasksPath
            cir_tasks_sha256 = Get-Sha256 $script:CirTasksPath
            cohort_validation_path = Get-RelativeProjectPath $script:CohortValidationPath
            cohort_validation_sha256 = Get-Sha256 $script:CohortValidationPath
            gate_a_task_audit_path = Get-RelativeProjectPath $script:GateATaskAuditPath
            gate_a_task_audit_sha256 = Get-Sha256 $script:GateATaskAuditPath
            scene_metadata_path = Get-RelativeProjectPath $script:SceneMetadataPath
            scene_metadata_sha256 = Get-Sha256 $script:SceneMetadataPath
        }
        source_sha256 = Get-SourcePins
        status_counts_at_release = $snapshot.counts
        selected_pilot_policy = [ordered]@{
            environment_class = 'Urban'
            distinct_scenes = $true
            distinct_supported_elevation_groups = $true
            existing_pilot_read_only = $baselineRun
            selected_run_ids = @($PilotRunIds)
        }
        baseline_existing_pilot = [ordered]@{
            run_id = $baselineRun
            scene_id = [string]$baselineTask.scene_id
            prn = [string]$baselineTask.prn
            tracking_channel = [int]$baselineTask.tracking_channel
            output_namespace = [string]$baselineTask.output_namespace
            hdf5_path = Get-RelativeProjectPath $baselineH5
            hdf5_size_bytes = [long]$baselineH5Info.Length
            hdf5_last_write_time_utc = $baselineH5Info.LastWriteTimeUtc.ToString('o')
            metadata_path = Get-RelativeProjectPath $baselineMetadata
            metadata_sha256 = Get-Sha256 $baselineMetadata
            comparison_csv_path = Get-RelativeProjectPath $baselineComparison
            comparison_csv_sha256 = Get-Sha256 $baselineComparison
            baseline_audit_path = Get-RelativeProjectPath $script:BaselineAuditPath
            baseline_audit_sha256 = Get-Sha256 $script:BaselineAuditPath
            stage0_windows_path = [string]$baselineTask.stage_csvs.stage0_valid_windows.path
            stage0_windows_sha256 = [string]$baselineTask.stage_csvs.stage0_valid_windows.sha256
            stage2_selected_paths_path = [string]$baselineTask.stage_csvs.stage2_selected_paths.path
            stage2_selected_paths_sha256 = [string]$baselineTask.stage_csvs.stage2_selected_paths.sha256
        }
        space_budget_at_release = $volumeBudget
        minimum_free_reserve_bytes = [long]$script:MinimumFreeReserveBytes
        tasks = $tasks
    }
    New-Item -ItemType Directory -Path $fullRoot | Out-Null
    try {
        Write-JsonNew (Join-Path $fullRoot 'release_request.json') $request
        Write-JsonNew (Join-Path $fullRoot 'pilot_audit.json') ([ordered]@{
            schema_version = 1
            release_request_sha256 = Get-Sha256 (Join-Path $fullRoot 'release_request.json')
            pilots = @()
            baseline_readback = [ordered]@{ status = 'NOT_YET_RUN'; matlab_invoked = $false }
        })
    } catch {
        throw "Release root was created but request assembly failed; preserving the partial release evidence at $fullRoot. $($_.Exception.Message)"
    }
    "CIR_RELEASE_REQUEST=$((Join-Path $fullRoot 'release_request.json'))"
    "CIR_RELEASE_REQUEST_SHA256=$(Get-Sha256 (Join-Path $fullRoot 'release_request.json'))"
    "CIR_PILOT_SELECTION=$($PilotRunIds -join ',')"
    "CIR_SPACE_ESTIMATE_BYTES=$($volumeBudget.estimated_new_cir_bytes) E_FREE_BYTES=$($volumeBudget.current_e_free_bytes) RESERVE_BYTES=$($volumeBudget.minimum_free_reserve_bytes)"
}

function Invoke-ValidateOnly {
    if (-not $RequestManifest -or -not $ExpectedRequestSha256 -or -not $RunId) { throw '-RequestManifest, -ExpectedRequestSha256, and -RunId are required with -ValidateOnly.' }
    $validated = Get-ValidatedSnapshot $RequestManifest $ExpectedRequestSha256 $RunId
    $reportDirectory = Join-Path ([string]$validated.request.release_root) 'validate_only'
    $stamp = [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
    $reportPath = Join-Path $reportDirectory ("$RunId`_$stamp.json")
    $report = [ordered]@{
        validation_status = 'PASS'
        check = 'VALIDATE_ONLY_NO_MATLAB_NO_RAW_CONTENT'
        validated_at_utc = $validated.validated_at_utc
        request_path = [IO.Path]::GetFullPath($RequestManifest)
        request_sha256 = $validated.request_sha256
        run_id = $RunId
        identity = $validated.selected_pin
        current_summary_counts = $validated.counts
        space_budget = $validated.space_budget
        raw_content_read = $false
        raw_hash_recomputed = $false
        matlab_invoked = $false
        global_lock_exists = $false
        new_storage_events = @()
        target_run_namespace_absent = $true
        frozen_scientific_algorithm_modified = $false
    }
    Write-JsonNew $reportPath $report
    "VALIDATION_ONLY_OK run_id=$RunId"
    'MATLAB_INVOKED=false RAW_CONTENT_READ=false RAW_HASH_RECOMPUTED=false'
    "VALIDATION_REPORT=$reportPath"
}

function ConvertTo-MatlabString {
    param([Parameter(Mandatory)][string]$Value)
    "'" + $Value.Replace("'", "''") + "'"
}

function Get-MatlabExecutable {
    $path = 'D:\Program Files\Matlab\bin\matlab.exe'
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Pinned MATLAB executable is missing: $path" }
    $path
}

function Acquire-GlobalLock {
    $path = Join-Path $script:BatchLogRoot '.windows_runner_active.lock'
    if (-not (Test-Path -LiteralPath $script:BatchLogRoot -PathType Container)) { throw "Batch lock directory missing: $($script:BatchLogRoot)" }
    $stream = [IO.File]::Open($path, [IO.FileMode]::CreateNew, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $token = [Guid]::NewGuid().ToString('N')
    $owner = [ordered]@{ owner = 'Invoke-Mainline1023CIRSingle'; pid = $PID; token = $token; created_utc = [DateTimeOffset]::UtcNow.ToString('o') }
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes((ConvertTo-Json $owner -Compress))
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush($true)
    [pscustomobject]@{ path = $path; stream = $stream; token = $token; pid = $PID }
}

function Release-GlobalLock {
    param([Parameter(Mandatory)]$Lock)
    $Lock.stream.Dispose()
    if (-not (Test-Path -LiteralPath $Lock.path -PathType Leaf)) { return }
    try {
        $owner = Get-Content -LiteralPath $Lock.path -Raw -Encoding UTF8 | ConvertFrom-Json
        if ([string]$owner.token -eq [string]$Lock.token -and [int]$owner.pid -eq [int]$Lock.pid) {
            Remove-Item -LiteralPath $Lock.path -Force
        }
    } catch {
        # A lock whose ownership cannot be re-proven is preserved for manual inspection.
        Write-Warning "Global lock ownership could not be re-proven; preserved at $($Lock.path): $($_.Exception.Message)"
    }
}

function New-CirLaunchReservation {
    param(
        [Parameter(Mandatory)][string]$ReleaseRoot,
        [Parameter(Mandatory)][string]$ReservationRoot,
        [Parameter(Mandatory)][string]$RunId,
        [Parameter(Mandatory)][string]$RequestSha256
    )
    if ($RunId -notmatch '^run_[A-Za-z0-9_]+$' -or $RequestSha256 -notmatch '^[a-fA-F0-9]{64}$') {
        throw 'Launch reservation requires a canonical run_id and 64-character request SHA256.'
    }
    $launchRoot = [IO.Path]::GetFullPath($ReservationRoot)
    [IO.Directory]::CreateDirectory($launchRoot) | Out-Null
    $reservationPath = Join-Path $launchRoot "$RunId.launch_reservation.json"
    $stream = $null
    try {
        $stream = [IO.File]::Open($reservationPath, [IO.FileMode]::CreateNew,
            [IO.FileAccess]::Write, [IO.FileShare]::None)
        $record = [ordered]@{
            schema_version = 1
            run_id = $RunId
            release_root = [IO.Path]::GetFullPath($ReleaseRoot)
            request_sha256 = $RequestSha256.ToLowerInvariant()
            reserved_utc = [DateTimeOffset]::UtcNow.ToString('o')
            reservation_process_id = $PID
            automatic_retry = $false
        }
        $json = ConvertTo-Json -InputObject $record -Depth 4
        $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($json + [Environment]::NewLine)
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } catch [IO.IOException] {
        throw "CIR launch already reserved or reservation could not be created; refusing duplicate/retry: $reservationPath. $($_.Exception.Message)"
    } finally {
        if ($null -ne $stream) { $stream.Dispose() }
    }
    $reservationPath
}

function Register-WorkerTask {
    param([Parameter(Mandatory)][string]$WorkerMode, [Parameter(Mandatory)][string]$RequestPath, [Parameter(Mandatory)][string]$RequestHash, [Parameter(Mandatory)][string]$TargetRunId)
    $currentUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    if ($currentUser -ine $script:ExpectedUser) { throw "Runner must execute as $($script:ExpectedUser), not $currentUser." }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principalCheck = [Security.Principal.WindowsPrincipal]::new($identity)
    if ($principalCheck.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'Elevated/admin execution is prohibited for CIR pilots.' }
    $suffix = [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ') + '_' + $TargetRunId.Substring($TargetRunId.Length - 8)
    $name = 'GNSS-CIR-Mainline1023-' + $suffix
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { throw "Unique scheduled-task name collision: $name" }
    $powershell = (Get-Command powershell.exe -ErrorAction Stop).Source
    $escapedScript = '"' + $PSCommandPath.Replace('"','\"') + '"'
    $escapedRequest = '"' + $RequestPath.Replace('"','\"') + '"'
    $arguments = "-NoProfile -ExecutionPolicy Bypass -File $escapedScript -$WorkerMode -ConfirmPilot -RequestManifest $escapedRequest -ExpectedRequestSha256 $RequestHash -RunId $TargetRunId -TaskName $name"
    $action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory $script:ProjectRoot
    $principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 12) -StartWhenAvailable:$false -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $name -Action $action -Principal $principal -Settings $settings -Description 'Manual-only, no-retry, limited-user GNSS CIR pilot/read-back.' | Out-Null
    try {
        Start-ScheduledTask -TaskName $name
    } catch {
        throw "Worker task registered but Start-ScheduledTask failed; preserve registration for diagnosis: $name. $($_.Exception.Message)"
    }
    [pscustomobject]@{ task_name = $name; user = $currentUser; logon_type = 'Interactive'; run_level = 'Limited'; max_instances = 1; restart_count = 0; task_name_exists = $true }
}

function Invoke-ExecuteRequest {
    if (-not $ConfirmPilot) { throw '-Execute requires the separate -ConfirmPilot acknowledgement.' }
    if (-not $RequestManifest -or -not $ExpectedRequestSha256 -or -not $RunId) { throw '-RequestManifest, -ExpectedRequestSha256, and -RunId are required with -Execute.' }
    $validated = Get-ValidatedSnapshot $RequestManifest $ExpectedRequestSha256 $RunId
    $latestValidation = @(Get-ChildItem -LiteralPath (Join-Path $validated.request.release_root 'validate_only') -Filter "$RunId`_*.json" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1)
    if ($latestValidation.Count -ne 1) { throw 'A fresh successful -ValidateOnly report for this exact run_id is required before execution.' }
    $validation = Get-JsonDocument $latestValidation[0].FullName
    if ($validation.validation_status -ne 'PASS' -or $validation.request_sha256 -ne $validated.request_sha256 -or $validation.run_id -ne $RunId -or $validation.matlab_invoked -ne $false) {
        throw 'The latest validation report does not authorize this exact request/run.'
    }
    Assert-PilotSequenceReady $validated.request $RunId
    if (@(Get-ScheduledTask -ErrorAction Stop | Where-Object { $_.State -in @('Running','Queued') -and $_.TaskName -match '(?i)(SAGE|CIR)' }).Count -gt 0) {
        throw 'Another SAGE/CIR scheduled task is active; refusing to queue a pilot.'
    }
    $null = New-CirLaunchReservation -ReleaseRoot $validated.request.release_root `
        -ReservationRoot (Join-Path $script:BatchLogRoot 'cir_launch_reservations') `
        -RunId $RunId -RequestSha256 $validated.request_sha256
    if (@(Get-ScheduledTask -ErrorAction Stop | Where-Object { $_.State -in @('Running','Queued') -and $_.TaskName -match '(?i)(SAGE|CIR)' }).Count -gt 0) {
        throw 'Another SAGE/CIR scheduled task became active after launch reservation; reservation is preserved and the pilot will not be retried.'
    }
    $task = Register-WorkerTask 'ExecuteWorker' ([IO.Path]::GetFullPath($RequestManifest)) $validated.request_sha256 $RunId
    $record = [ordered]@{
        task_name = $task.task_name
        run_id = $RunId
        request_sha256 = $validated.request_sha256
        created_utc = [DateTimeOffset]::UtcNow.ToString('o')
        normal_user = $task.user
        logon_type = $task.logon_type
        run_level = $task.run_level
        maximum_instances = 1
        automatic_retry = $false
        matlab_launched_by = 'Scheduled limited-user ExecuteWorker only'
    }
    $startedPath = Join-Path (Join-Path $validated.request.release_root 'launch_records') "$($task.task_name).json"
    Write-JsonNew $startedPath $record
    "CIR_WORKER_TASK_STARTED=$($task.task_name)"
    "CIR_TASK_RECORD=$startedPath"
}

function New-MatlabDriver {
    param([Parameter(Mandatory)]$Validated, [Parameter(Mandatory)][string]$RunRoot, [Parameter(Mandatory)][string]$AttemptRoot)
    $task = $Validated.selected_pin
    $h5Path = Join-Path $AttemptRoot "$($task.prn)_ch$($task.tracking_channel)_code_domain_cir.h5"
    $metadataPath = Join-Path $AttemptRoot "$($task.prn)_ch$($task.tracking_channel)_code_domain_cir_metadata.json"
    $comparisonPath = Join-Path $AttemptRoot "$($task.prn)_ch$($task.tracking_channel)_primary_delay_comparison.csv"
    $resultPath = Join-Path $AttemptRoot 'matlab_result.json'
    $stage0 = Resolve-ProjectPath $task.stage_csvs.stage0_valid_windows.path
    $stage2 = Resolve-ProjectPath $task.stage_csvs.stage2_selected_paths.path
    $sceneMetadata = Resolve-ProjectPath $Validated.request.inputs.scene_metadata_path
    $payload = [ordered]@{
        project_root = $script:ProjectRoot
        run_id = $task.run_id
        scene_id = $task.scene_id
        prn = $task.prn
        tracking_channel = $task.tracking_channel
        sample_rate_hz = $task.sample_rate_hz
        frozen_sage_sha256 = $script:ExpectedFrozenSageSha256
        raw_iq_size_bytes = $task.raw_iq_size_bytes
        scene_metadata_sha256 = $Validated.request.inputs.scene_metadata_sha256
        cohort_json_path = $Validated.request.inputs.cohort_path
        cohort_sha256 = $Validated.request.inputs.cohort_sha256
        cir_tasks_json_path = $Validated.request.inputs.cir_tasks_path
        cir_tasks_sha256 = $Validated.request.inputs.cir_tasks_sha256
    }
    $payloadJson = ConvertTo-Json -InputObject $payload -Compress -Depth 8
    $payloadMatlab = ConvertTo-MatlabString $payloadJson
    $pathExporter = ConvertTo-MatlabString $script:ExporterPath
    $pathValidator = ConvertTo-MatlabString $script:ValidatorPath
    $pathFrozen = ConvertTo-MatlabString (Split-Path -Parent $script:FrozenSagePath)
    $pathFrozenCore = ConvertTo-MatlabString (Split-Path -Parent $script:FrozenConfigPath)
    $pathChannel = ConvertTo-MatlabString $PSScriptRoot
    $pathProject = ConvertTo-MatlabString $script:ProjectRoot
    $pathOutput = ConvertTo-MatlabString $AttemptRoot
    $pathRaw = ConvertTo-MatlabString $task.raw_iq_path
    $pathStage0 = ConvertTo-MatlabString $stage0
    $pathStage2 = ConvertTo-MatlabString $stage2
    $pathScene = ConvertTo-MatlabString $sceneMetadata
    $pathH5 = ConvertTo-MatlabString $h5Path
    $pathMetadata = ConvertTo-MatlabString $metadataPath
    $pathComparison = ConvertTo-MatlabString $comparisonPath
    $pathResult = ConvertTo-MatlabString $resultPath
    $pathSage = ConvertTo-MatlabString $script:FrozenSagePath
    $pathConfig = ConvertTo-MatlabString $script:FrozenConfigPath
    $sourceExpected = $script:ExpectedFrozenSageSha256
    $configExpected = $script:ExpectedConfigSha256
    $text = @"
try
    restoredefaultpath;
    addpath($pathFrozen);
    addpath($pathFrozenCore);
    addpath($pathChannel);
    clear functions;
    assert(strcmpi(which('run_nav_sage_pipeline'), $pathSage), 'Frozen SAGE entry resolved to an unexpected file.');
    assert(strcmpi(which('default_sage_configuration'), $pathConfig), 'Frozen SAGE config resolved to an unexpected file.');
    assert(strcmpi(which('export_gnss_code_domain_cir'), $pathExporter), 'CIR exporter resolved to an unexpected file.');
    assert(strcmpi(which('validate_gnss_code_domain_cir'), $pathValidator), 'CIR validator resolved to an unexpected file.');
    p = jsondecode($payloadMatlab);
    exportSummary = export_gnss_code_domain_cir($pathRaw, $pathStage0, $pathStage2, $pathScene, ...
        $pathH5, $pathMetadata, $pathComparison, p);
    validationSummary = validate_gnss_code_domain_cir($pathH5, $($task.stage0_window_count));
    metadata = jsondecode(fileread($pathMetadata));
    stage0 = readtable($pathStage0);
    pdpWindowIds = double(h5read($pathH5, '/pdp_window_id'));
    pdpTimes = double(h5read($pathH5, '/pdp_time_s'));
    pdpStarts = double(h5read($pathH5, '/pdp_start_sample_zero_based'));
    snapshotWindowIds = double(h5read($pathH5, '/window_id'));
    snapshotIndices = double(h5read($pathH5, '/snapshot_index_in_window'));
    snapshotTimes = double(h5read($pathH5, '/time_s'));
    snapshotStarts = double(h5read($pathH5, '/sample_start_zero_based'));
    assert(isequal(pdpWindowIds(:), double(stage0.window_id(:))));
    assert(isequal(pdpStarts(:), double(stage0.sample_start_zero_based(:))));
    assert(max(abs(pdpTimes(:)-double(stage0.recording_time_s(:)))) < 1e-12);
    [mapped, stage0Row] = ismember(snapshotWindowIds(:), double(stage0.window_id(:)));
    assert(all(mapped), 'CIR snapshots contain a window absent from Stage0.');
    expectedSnapshotStart = double(stage0.sample_start_zero_based(stage0Row(:))) + ...
        (double(snapshotIndices(:))-1) * 10230;
    assert(isequal(snapshotStarts(:), expectedSnapshotStart(:)));
    assert(max(abs(snapshotTimes(:)-expectedSnapshotStart(:)/10230000)) < 1e-12);
    assert(strcmp(metadata.run_id, p.run_id) && strcmp(metadata.scene_id, p.scene_id));
    assert(metadata.stage0_window_count == $($task.stage0_window_count));
    assert(metadata.cir_snapshot_count == 40 * metadata.stage0_window_count);
    assert(metadata.delay_grid_count == 451);
    assert(strcmp(metadata.amplitude_reference_status, 'UNKNOWN_RECEIVER_GAIN_OR_AGC'));
    axesAlignment = struct('pdp_windows_match_stage0',true, ...
        'pdp_time_and_start_match_stage0',true,'snapshots_map_to_stage0_by_window_id',true, ...
        'snapshot_indices_match_sample_and_time_axes',true);
    result = struct('status', 'PASS', 'run_id', p.run_id, 'scene_id', p.scene_id, ...
        'export_summary', exportSummary, 'validation_summary', validationSummary, ...
        'metadata', metadata, 'axes_alignment', axesAlignment, 'matlab_version', version, 'matlab_invoked', true, ...
        'raw_content_read', true, 'raw_hash_recomputed', false, 'scientific_algorithm_modified', false);
    writeJson($pathResult, result);
    fprintf('CIR_PILOT_QA=PASS run_id=%s\n', p.run_id);
catch ME
    failure = struct('status', 'FAILED', 'message', ME.message, 'identifier', ME.identifier, ...
        'stack', {ME.stack}, 'matlab_invoked', true, 'scientific_algorithm_modified', false);
    try, writeJson($pathResult, failure); catch, end
    rethrow(ME);
end

function writeJson(path, value)
    fid = fopen(path, 'w');
    assert(fid >= 0, 'Unable to create MATLAB result JSON.');
    cleanup = onCleanup(@() fclose(fid));
    fwrite(fid, jsonencode(value), 'char');
end
"@
    $driverPath = Join-Path $AttemptRoot 'run_cir_pilot.m'
    Write-JsonNew (Join-Path $AttemptRoot 'execution_request.json') ([ordered]@{
        run_id = $task.run_id
        scene_id = $task.scene_id
        raw_iq_path = $task.raw_iq_path
        raw_iq_size_bytes = $task.raw_iq_size_bytes
        stage0_path = $task.stage_csvs.stage0_valid_windows.path
        stage0_sha256 = $task.stage_csvs.stage0_valid_windows.sha256
        stage2_path = $task.stage_csvs.stage2_selected_paths.path
        stage2_sha256 = $task.stage_csvs.stage2_selected_paths.sha256
        outputs = [ordered]@{ hdf5 = $h5Path; metadata_json = $metadataPath; delay_comparison_csv = $comparisonPath }
        matlab_invoked_by = 'limited-user scheduled worker'
    })
    [IO.File]::WriteAllText($driverPath, $text.TrimStart(), [Text.UTF8Encoding]::new($false))
    [pscustomobject]@{ driver_path = $driverPath; result_path = $resultPath; hdf5_path = $h5Path; metadata_path = $metadataPath; comparison_path = $comparisonPath }
}

function Invoke-MatlabBatch {
    param([Parameter(Mandatory)][string]$DriverPath, [Parameter(Mandatory)][string]$AttemptRoot)
    $matlab = Get-MatlabExecutable
    $stdoutPath = Join-Path $AttemptRoot 'matlab_stdout.log'
    $stderrPath = Join-Path $AttemptRoot 'matlab_stderr.log'
    $startUtc = [DateTimeOffset]::UtcNow
    $psi = [Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = $matlab
    $matlabCommand = "run('" + $DriverPath.Replace('\','/') + "')"
    $psi.Arguments = '-logfile "' + $stdoutPath + '" -batch "' + $matlabCommand.Replace('"','\"') + '"'
    $psi.WorkingDirectory = $script:ProjectRoot
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $psi
    $stdout = [Text.StringBuilder]::new()
    $stderr = [Text.StringBuilder]::new()
    $stdoutTask = $null
    $stderrTask = $null
    $peakWorkingSet = [long]0
    if (-not $process.Start()) { throw 'MATLAB process failed to start.' }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    while (-not $process.WaitForExit(5000)) {
        try {
            $current = Get-Process -Id $process.Id -ErrorAction Stop
            if ([long]$current.WorkingSet64 -gt $peakWorkingSet) { $peakWorkingSet = [long]$current.WorkingSet64 }
        } catch { }
    }
    $process.WaitForExit()
    try { if ([long]$process.PeakWorkingSet64 -gt $peakWorkingSet) { $peakWorkingSet = [long]$process.PeakWorkingSet64 } } catch { }
    $outText = $stdoutTask.GetAwaiter().GetResult()
    $errText = $stderrTask.GetAwaiter().GetResult()
    [IO.File]::WriteAllText($stdoutPath, $outText, [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText($stderrPath, $errText, [Text.UTF8Encoding]::new($false))
    [pscustomobject]@{
        exit_code = [int]$process.ExitCode
        pid = [int]$process.Id
        started_utc = $startUtc.ToString('o')
        ended_utc = [DateTimeOffset]::UtcNow.ToString('o')
        elapsed_seconds = ([DateTimeOffset]::UtcNow - $startUtc).TotalSeconds
        peak_working_set_bytes_observed = $peakWorkingSet
        stdout_path = $stdoutPath
        stderr_path = $stderrPath
    }
}

function Update-PilotAudit {
    param([Parameter(Mandatory)][string]$Root, [Parameter(Mandatory)]$Entry)
    $path = Join-Path $Root 'pilot_audit.json'
    $audit = Get-PilotAudit $Root
    $existing = @($audit.pilots | Where-Object { $_.run_id -eq $Entry.run_id })
    if ($existing.Count -gt 0) { throw "Pilot audit already contains this run; no retry permitted: $($Entry.run_id)" }
    $audit.pilots = @($audit.pilots) + @($Entry)
    $audit.release_request_sha256 = Get-Sha256 (Join-Path $Root 'release_request.json')
    Write-JsonReplace $path $audit
}

function Invoke-ExecuteWorker {
    if (-not $ConfirmPilot) { throw 'Worker execution requires the launcher confirmation.' }
    $validated = Get-ValidatedSnapshot $RequestManifest $ExpectedRequestSha256 $RunId $TaskName -SkipLockCheck
    Assert-PilotSequenceReady $validated.request $RunId
    if ([Security.Principal.WindowsIdentity]::GetCurrent().Name -ine $script:ExpectedUser) { throw "Worker must run as $($script:ExpectedUser)." }
    $lock = $null
    $attemptRoot = $null
    $runRootOwned = $false
    $runRoot = Join-Path (Join-Path $validated.request.release_root 'runs') $RunId
    try {
        $lock = Acquire-GlobalLock
        if (Test-Path -LiteralPath $runRoot) { throw "Run root already exists; no retry/overwrite permitted: $runRoot" }
        Assert-NoOtherExecutionProcess -AllowedTaskName $TaskName
        $storageEventsAfterLock = @(Get-StorageEventsSince (ConvertTo-UtcDateTimeOffset $validated.request.created_utc))
        if ($storageEventsAfterLock.Count -gt 0) { throw 'New matching System disk/USB event appeared before MATLAB; stopping without science.' }
        New-Item -ItemType Directory -Path $runRoot | Out-Null
        $runRootOwned = $true
        $attemptRoot = Join-Path $runRoot 'attempt_01'
        New-Item -ItemType Directory -Path $attemptRoot | Out-Null
        Write-JsonNew (Join-Path $runRoot 'execution_started.json') ([ordered]@{
            run_id = $RunId
            request_sha256 = $validated.request_sha256
            started_utc = [DateTimeOffset]::UtcNow.ToString('o')
            attempt = 1
            resume = $false
            matlab_pids_before_start = @()
            global_lock_owner = [ordered]@{ path = $lock.path; pid = $lock.pid; token = $lock.token }
            scheduled_task_name = $TaskName
            current_user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
        })
        $driver = New-MatlabDriver $validated $runRoot $attemptRoot
        $matlabResult = Invoke-MatlabBatch $driver.driver_path $attemptRoot
        Write-JsonNew (Join-Path $runRoot 'matlab_exit_receipt.json') $matlabResult
        if ($matlabResult.exit_code -ne 0) { throw "MATLAB exited with code $($matlabResult.exit_code); attempt preserved and no retry permitted." }
        if (-not (Test-Path -LiteralPath $driver.result_path -PathType Leaf)) { throw 'MATLAB exited zero without a QA result receipt.' }
        $result = Get-JsonDocument $driver.result_path
        if ($result.status -ne 'PASS' -or $result.run_id -ne $RunId -or $result.metadata.amplitude_reference_status -ne 'UNKNOWN_RECEIVER_GAIN_OR_AGC') {
            throw 'MATLAB result identity/QA/amplitude status failed closed.'
        }
        foreach ($file in @($driver.hdf5_path,$driver.metadata_path,$driver.comparison_path)) {
            if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Required CIR output missing after MATLAB: $file" }
        }
        $outputs = @()
        foreach ($file in @($driver.hdf5_path,$driver.metadata_path,$driver.comparison_path)) {
            $fi = Get-Item -LiteralPath $file
            $outputs += [ordered]@{ path = Get-RelativeProjectPath $file; size_bytes = [long]$fi.Length; sha256 = Get-Sha256 $file }
        }
        $completion = [ordered]@{
            status = 'PASS'
            run_id = $RunId
            identity = $validated.selected_pin
            request_sha256 = $validated.request_sha256
            started_utc = $matlabResult.started_utc
            completed_utc = [DateTimeOffset]::UtcNow.ToString('o')
            attempt = 1
            resume = $false
            exit_code = 0
            matlab_pid = $matlabResult.pid
            elapsed_seconds = $matlabResult.elapsed_seconds
            peak_working_set_bytes_observed = $matlabResult.peak_working_set_bytes_observed
            hdf5_validation = $result.validation_summary
            export_summary = $result.export_summary
            metadata_summary = $result.metadata
            outputs = $outputs
            raw_content_read = $true
            raw_hash_recomputed = $false
            amplitude_reference_status = 'UNKNOWN_RECEIVER_GAIN_OR_AGC'
            published_to = 'new-only release root; original SAGE namespace unchanged'
            scientific_algorithm_modified = $false
        }
        Write-JsonNew (Join-Path $runRoot 'pilot_receipt.json') $completion
        Update-PilotAudit $validated.request.release_root ([ordered]@{
            run_id = $RunId
            status = 'PASS'
            receipt_path = Get-RelativeProjectPath (Join-Path $runRoot 'pilot_receipt.json')
            completed_utc = $completion.completed_utc
            hdf5_bytes = [long](Get-Item -LiteralPath $driver.hdf5_path).Length
            window_count = [int]$result.metadata.stage0_window_count
            bytes_per_window = [double]((Get-Item -LiteralPath $driver.hdf5_path).Length / [double]$result.metadata.stage0_window_count)
            elapsed_seconds = $matlabResult.elapsed_seconds
            peak_working_set_bytes_observed = $matlabResult.peak_working_set_bytes_observed
            primary_delay_comparison_count = $result.export_summary.primary_delay_comparison_count
            primary_delay_max_abs_samples = $result.export_summary.primary_delay_difference_max_abs_samples
            pdp_max_absolute_difference = $result.validation_summary.max_pdp_recomputation_difference
        })
        'CIR_PILOT_EXECUTION=PASS'
        "CIR_PILOT_RECEIPT=$(Join-Path $runRoot 'pilot_receipt.json')"
    } catch {
        $failedAt = [DateTimeOffset]::UtcNow.ToString('o')
        if ($runRootOwned) {
            $failurePath = Join-Path $runRoot 'pilot_failure_receipt.json'
        } else {
            $failureDirectory = Join-Path ([string]$validated.request.release_root) 'launch_failures'
            $failurePath = Join-Path $failureDirectory ("$RunId`_$([DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')).json")
        }
        if (-not (Test-Path -LiteralPath $failurePath)) {
            Write-JsonNew $failurePath ([ordered]@{
                status = 'FAILED_NO_RETRY'
                run_id = $RunId
                request_sha256 = $validated.request_sha256
                failed_utc = $failedAt
                error = $_.Exception.Message
                attempt_preserved = ($null -ne $attemptRoot)
                attempt_path = $attemptRoot
                no_automatic_retry = $true
            })
        }
        try { Update-PilotAudit $validated.request.release_root ([ordered]@{ run_id = $RunId; status = 'FAILED_NO_RETRY'; failure_receipt = Get-RelativeProjectPath $failurePath; failed_utc = $failedAt }) } catch { }
        Write-Error "CIR pilot failed and was preserved. No retry/next task: $failurePath. $($_.Exception.Message)"
        exit 1
    } finally {
        if ($lock) { Release-GlobalLock $lock }
    }
}

function Get-BaselineInputs {
    param([Parameter(Mandatory)]$Request)
    $baseline = $Request.baseline_existing_pilot
    $h5 = Resolve-ProjectPath $baseline.hdf5_path
    $metadata = Resolve-ProjectPath $baseline.metadata_path
    $comparison = Resolve-ProjectPath $baseline.comparison_csv_path
    $baselineAudit = Resolve-ProjectPath $baseline.baseline_audit_path
    $stage0 = Resolve-ProjectPath $baseline.stage0_windows_path
    $stage2 = Resolve-ProjectPath $baseline.stage2_selected_paths_path
    foreach ($path in @($h5,$metadata,$comparison,$baselineAudit,$stage0,$stage2)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "Existing pilot read-back file is missing: $path" }
    }
    $h5Info = Get-Item -LiteralPath $h5
    if ($baseline.hdf5_last_write_time_utc -is [DateTime]) {
        $expectedH5WriteUtc = ([DateTime]$baseline.hdf5_last_write_time_utc).ToUniversalTime()
    } else {
        $expectedH5WriteUtc = [DateTimeOffset]::Parse([string]$baseline.hdf5_last_write_time_utc).UtcDateTime
    }
    if ([long]$h5Info.Length -ne [long]$baseline.hdf5_size_bytes -or
        $h5Info.LastWriteTimeUtc.Ticks -ne $expectedH5WriteUtc.Ticks -or
        (Get-Sha256 $metadata) -ne [string]$baseline.metadata_sha256 -or
        (Get-Sha256 $comparison) -ne [string]$baseline.comparison_csv_sha256 -or
        (Get-Sha256 $baselineAudit) -ne [string]$baseline.baseline_audit_sha256 -or
        (Get-Sha256 $stage0) -ne [string]$baseline.stage0_windows_sha256 -or
        (Get-Sha256 $stage2) -ne [string]$baseline.stage2_selected_paths_sha256) {
        throw 'Existing G28/ch1 pilot metadata/CSV or HDF5 file metadata changed since the release snapshot.'
    }
    [pscustomobject]@{ h5 = $h5; metadata = $metadata; comparison = $comparison; baseline_audit = $baselineAudit; stage0 = $stage0; stage2 = $stage2 }
}

function Invoke-ReadBackExistingPilot {
    if (-not $RequestManifest -or -not $ExpectedRequestSha256) { throw '-RequestManifest and -ExpectedRequestSha256 are required for -ReadBackExistingPilot.' }
    if ($RunId -ne $script:ExistingPilotRunId) { throw "Read-back is restricted to the exact existing pilot $($script:ExistingPilotRunId)." }
    $validated = Get-ValidatedSnapshot $RequestManifest $ExpectedRequestSha256
    $files = Get-BaselineInputs $validated.request
    Get-LiveExecutionState
    $task = Register-WorkerTask 'ReadBackWorker' ([IO.Path]::GetFullPath($RequestManifest)) $validated.request_sha256 $RunId
    $started = [ordered]@{
        task_name = $task.task_name
        run_id = $RunId
        request_sha256 = $validated.request_sha256
        created_utc = [DateTimeOffset]::UtcNow.ToString('o')
        mode = 'READ_ONLY_EXISTING_HDF5_VALIDATION_AND_NUMERICAL_COMPARISON'
        normal_user = $task.user
        raw_iq_read = $false
        existing_hdf5_or_scientific_outputs_modified = $false
    }
    $path = Join-Path ([string]$validated.request.release_root) 'baseline_readback_scheduled_task.json'
    Write-JsonNew $path $started
    "CIR_BASELINE_READBACK_TASK=$($task.task_name)"
    "CIR_BASELINE_READBACK_RECORD=$path"
}

function New-BaselineReadbackDriver {
    param([Parameter(Mandatory)]$Validated, [Parameter(Mandatory)]$Files, [Parameter(Mandatory)][string]$OutputPath)
    $baseline = $Validated.request.baseline_existing_pilot
    $pathH5 = ConvertTo-MatlabString $Files.h5
    $pathMetadata = ConvertTo-MatlabString $Files.metadata
    $pathComparison = ConvertTo-MatlabString $Files.comparison
    $pathStage0 = ConvertTo-MatlabString $Files.stage0
    $pathStage2 = ConvertTo-MatlabString $Files.stage2
    $pathValidator = ConvertTo-MatlabString $script:ValidatorPath
    $pathOutput = ConvertTo-MatlabString $OutputPath
    $text = @"
try
    addpath($(ConvertTo-MatlabString $PSScriptRoot));
    clear functions;
    assert(strcmpi(which('validate_gnss_code_domain_cir'), $pathValidator));
    validation = validate_gnss_code_domain_cir($pathH5, 898);
    metadata = jsondecode(fileread($pathMetadata));
    s0 = readtable($pathStage0);
    s2 = readtable($pathStage2);
    comparison = readtable($pathComparison);
    ids = double(h5read($pathH5, '/pdp_window_id'));
    delay = double(h5read($pathH5, '/delay_samples'));
    pdp = double(h5read($pathH5, '/pdp_power'));
    cirWindowIds = double(h5read($pathH5, '/window_id'));
    cirSnapshotIndices = double(h5read($pathH5, '/snapshot_index_in_window'));
    cirTime = double(h5read($pathH5, '/time_s'));
    cirSampleStart = double(h5read($pathH5, '/sample_start_zero_based'));
    assert(isequal(ids(:), double(s0.window_id(:))), 'HDF5 PDP window IDs do not match Stage0 rows.');
    pdpTimes = double(h5read($pathH5,'/pdp_time_s'));
    pdpStarts = double(h5read($pathH5,'/pdp_start_sample_zero_based'));
    assert(isequal(pdpTimes(:),double(s0.recording_time_s(:))));
    assert(isequal(pdpStarts(:),double(s0.sample_start_zero_based(:))));
    assert(size(pdp,1) == height(s0) && size(pdp,2) == 451);
    assert(numel(cirWindowIds) == 40*height(s0) && numel(cirSnapshotIndices) == numel(cirWindowIds));
    [mapped, stage0Row] = ismember(cirWindowIds(:),double(s0.window_id(:)));
    assert(all(mapped), 'CIR snapshots contain a window absent from Stage0.');
    expectedStart = double(s0.sample_start_zero_based(stage0Row(:))) + ...
        (double(cirSnapshotIndices(:))-1)*10230;
    assert(isequal(cirSampleStart(:),expectedStart(:)), 'CIR sample-start axis does not align to Stage0.');
    expectedTime = expectedStart(:)/10230000;
    assert(max(abs(cirTime(:)-expectedTime(:))) < 1e-12, 'CIR time axis does not align to Stage0 sample starts.');
    primary = s2(double(s2.path_id)==1,:);
    assert(height(primary)==height(comparison), 'Comparison row count differs from Stage2 primary rows.');
    assert(isequal(double(primary.window_id(:)),double(comparison.window_id(:))), 'Comparison identity/order differs from Stage2 primary paths.');
    if ismember('recording_time_s',primary.Properties.VariableNames)
        assert(max(abs(double(primary.recording_time_s(:))-double(comparison.recording_time_s(:))))<1e-12);
    end
    if ismember('delay_samples',primary.Properties.VariableNames)
        assert(max(abs(double(primary.delay_samples(:))-double(comparison.sage_primary_delay_samples(:))))<1e-12);
    end
    rowForWindow = containers.Map('KeyType','double','ValueType','double');
    for k=1:numel(ids), rowForWindow(ids(k))=k; end
    recomputed = zeros(height(primary),1);
    for k=1:height(primary)
        row = rowForWindow(double(primary.window_id(k)));
        [~, peak] = max(pdp(row,:));
        recomputed(k) = delay(peak);
    end
    difference = recomputed - double(primary.delay_samples(:));
    csvDifference = double(comparison.pdp_minus_sage_delay_samples(:));
    assert(max(abs(difference-csvDifference))<1e-12, 'Read-back primary delay differences do not recompute from stored PDP.');
    baselineMetrics = struct('count',height(primary),'min_signed_samples',min(difference), ...
        'max_signed_samples',max(difference),'median_signed_samples',median(difference), ...
        'max_abs_samples',max(abs(difference)),'pdp_max_abs_diff_from_validator',validation.max_pdp_recomputation_difference);
    assert(baselineMetrics.count==54 && abs(baselineMetrics.min_signed_samples-(-4))<1e-12 ...
        && abs(baselineMetrics.max_signed_samples-32.5)<1e-12 ...
        && abs(baselineMetrics.median_signed_samples-0.1)<1e-12 ...
        && abs(baselineMetrics.max_abs_samples-32.5)<1e-12, ...
        'Read-back does not reproduce the documented descriptive G28/ch1 comparison.');
    result = struct('status','PASS','run_id',metadata.run_id,'scene_id',metadata.scene_id, ...
        'metadata',metadata,'validation',validation,'recomputed_comparison_metrics',baselineMetrics, ...
        'baseline_csv_metrics',struct('min_signed_samples',min(csvDifference), ...
        'max_signed_samples',max(csvDifference),'median_signed_samples',median(csvDifference), ...
        'max_abs_samples',max(abs(csvDifference))),'raw_iq_read',false, ...
        'hdf5_payload_read',true,'existing_outputs_modified',false);
    fid=fopen($pathOutput,'w'); assert(fid>=0); cleanup=onCleanup(@()fclose(fid)); fwrite(fid,jsonencode(result),'char');
    fprintf('CIR_EXISTING_PILOT_READBACK=PASS count=%d max_abs=%.12g\\n',height(primary),baselineMetrics.max_abs_samples);
catch ME
    rethrow(ME);
end
"@
    $driverPath = Join-Path (Split-Path -Parent $OutputPath) 'read_existing_g28_pilot.m'
    [IO.File]::WriteAllText($driverPath, $text.TrimStart(), [Text.UTF8Encoding]::new($false))
    $driverPath
}

function Invoke-ReadBackWorker {
    if (-not $ConfirmPilot) { throw 'Read-back worker requires explicit limited-task confirmation.' }
    if ($RunId -ne $script:ExistingPilotRunId) { throw 'ReadBackWorker is restricted to the exact existing G28/ch1 pilot.' }
    $validated = Get-ValidatedSnapshot $RequestManifest $ExpectedRequestSha256 $null $TaskName -SkipLockCheck
    $files = Get-BaselineInputs $validated.request
    $lock = $null
    try {
        $lock = Acquire-GlobalLock
        Assert-NoOtherExecutionProcess -AllowedTaskName $TaskName
        $storageEventsAfterLock = @(Get-StorageEventsSince (ConvertTo-UtcDateTimeOffset $validated.request.created_utc))
        if ($storageEventsAfterLock.Count -gt 0) { throw 'New matching System disk/USB event appeared before existing-pilot read-back.' }
        $outRoot = Join-Path ([string]$validated.request.release_root) 'baseline_readback'
        if (Test-Path -LiteralPath $outRoot) { throw "Baseline read-back attempt already exists; no retry: $outRoot" }
        New-Item -ItemType Directory -Path $outRoot | Out-Null
        $resultPath = Join-Path $outRoot 'g28_ch1_readback.json'
        $driver = New-BaselineReadbackDriver $validated $files $resultPath
        $exit = Invoke-MatlabBatch $driver $outRoot
        Write-JsonNew (Join-Path $outRoot 'matlab_exit_receipt.json') $exit
        if ($exit.exit_code -ne 0 -or -not (Test-Path -LiteralPath $resultPath -PathType Leaf)) {
            throw "Existing pilot read-back failed; no scientific output was modified. MATLAB exit=$($exit.exit_code)."
        }
        $result = Get-JsonDocument $resultPath
        if ($result.status -ne 'PASS' -or $result.run_id -ne $RunId -or $result.raw_iq_read -ne $false -or $result.existing_outputs_modified -ne $false) {
            throw 'Existing pilot read-back receipt identity or read-only assertions failed.'
        }
        Write-JsonNew (Join-Path $outRoot 'readback_receipt.json') ([ordered]@{
            status = 'PASS'
            run_id = $RunId
            request_sha256 = $validated.request_sha256
            completed_utc = [DateTimeOffset]::UtcNow.ToString('o')
            matlab_exit_code = $exit.exit_code
            runtime_seconds = $exit.elapsed_seconds
            raw_iq_read = $false
            existing_outputs_modified = $false
            metrics = $result.recomputed_comparison_metrics
            result_path = Get-RelativeProjectPath $resultPath
        })
        $audit = Get-PilotAudit $validated.request.release_root
        $audit.baseline_readback = [ordered]@{ status = 'PASS'; receipt_path = Get-RelativeProjectPath (Join-Path $outRoot 'readback_receipt.json'); metrics = $result.recomputed_comparison_metrics }
        Write-JsonReplace (Join-Path ([string]$validated.request.release_root) 'pilot_audit.json') $audit
        'CIR_EXISTING_PILOT_READBACK=PASS'
        "CIR_BASELINE_RECEIPT=$(Join-Path $outRoot 'readback_receipt.json')"
    } catch {
        $failure = Join-Path ([string]$validated.request.release_root) 'baseline_readback_failure.json'
        if (-not (Test-Path -LiteralPath $failure)) {
            Write-JsonNew $failure ([ordered]@{ status = 'FAILED_NO_RETRY'; run_id = $RunId; failed_utc = [DateTimeOffset]::UtcNow.ToString('o'); error = $_.Exception.Message; read_only_target_preserved = $true })
        }
        Write-Error "Existing-pilot read-back failed without modifying it: $($_.Exception.Message)"
        exit 1
    } finally {
        if ($lock) { Release-GlobalLock $lock }
    }
}

function Invoke-FinalizePilotAudit {
    if (-not $RequestManifest -or -not $ExpectedRequestSha256) {
        throw '-RequestManifest and -ExpectedRequestSha256 are required with -FinalizePilotAudit.'
    }
    $validated = Get-ValidatedSnapshot $RequestManifest $ExpectedRequestSha256
    Get-LiveExecutionState
    $request = $validated.request
    $root = [string]$request.release_root
    $audit = Get-PilotAudit $root
    if ([string]$audit.release_request_sha256 -ne $validated.request_sha256 -or $audit.baseline_readback.status -ne 'PASS') {
        throw 'Cannot finalize: request-bound pilot audit and existing G28/ch1 read-back must PASS.'
    }
    $baselineFiles = Get-BaselineInputs $request
    $baselineReceipt = Get-JsonDocument (Join-Path $root 'baseline_readback\readback_receipt.json')
    if ($baselineReceipt.status -ne 'PASS' -or $baselineReceipt.run_id -ne $script:ExistingPilotRunId -or
        $baselineReceipt.raw_iq_read -ne $false -or $baselineReceipt.existing_outputs_modified -ne $false) {
        throw 'Existing G28/ch1 read-back receipt failed its identity/read-only contract.'
    }
    if (@($audit.pilots).Count -ne 2 -or
        [string]$audit.pilots[0].run_id -ne $script:ApprovedPilotIds[0] -or
        [string]$audit.pilots[1].run_id -ne $script:ApprovedPilotIds[1] -or
        @($audit.pilots | Where-Object { $_.status -ne 'PASS' }).Count -ne 0) {
        throw 'Both approved new pilots must have one PASS receipt in the approved order before audit finalization.'
    }
    $pilotReceipts = @()
    [long]$pilotWindowTotal = 0
    [double]$pilotElapsedTotal = 0
    [double]$maxSecondsPerWindow = 0
    [double]$maxBytesPerWindow = 0
    [long]$maxPeakWorkingSet = 0
    foreach ($task in $request.tasks) {
        $runRoot = Join-Path (Join-Path $root 'runs') ([string]$task.run_id)
        $receiptPath = Join-Path $runRoot 'pilot_receipt.json'
        if (Test-Path -LiteralPath (Join-Path $runRoot 'pilot_failure_receipt.json')) {
            throw "Failed-pilot receipt exists for $($task.run_id); refusing to mark the release PASS."
        }
        $receipt = Get-JsonDocument $receiptPath
        if ($receipt.status -ne 'PASS' -or $receipt.run_id -ne $task.run_id -or
            $receipt.request_sha256 -ne $validated.request_sha256 -or $receipt.exit_code -ne 0 -or
            $receipt.raw_hash_recomputed -ne $false -or
            $receipt.amplitude_reference_status -ne 'UNKNOWN_RECEIVER_GAIN_OR_AGC' -or
            $receipt.identity.run_id -ne $task.run_id -or $receipt.hdf5_validation.cir_all_finite -ne $true -or
            $receipt.hdf5_validation.pdp_window_count -ne $task.stage0_window_count -or
            $receipt.hdf5_validation.delay_count -ne 451) {
            throw "Pilot receipt identity, MATLAB exit, amplitude, shape, or QA fields do not pass for $($task.run_id)."
        }
        if (@($receipt.outputs).Count -ne 3) { throw "Pilot output receipt count is not 3 for $($task.run_id)." }
        foreach ($output in $receipt.outputs) {
            $path = Resolve-ProjectPath ([string]$output.path)
            $rootPrefix = [IO.Path]::GetFullPath($runRoot).TrimEnd('\') + '\'
            if (-not $path.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                throw "Pilot output escaped its unique release namespace: $path"
            }
            $fi = Get-Item -LiteralPath $path -ErrorAction Stop
            if ([long]$fi.Length -ne [long]$output.size_bytes -or (Get-Sha256 $path) -ne [string]$output.sha256) {
                throw "Pilot output receipt size/SHA mismatch: $path"
            }
        }
        $windowCount = [long]$receipt.identity.stage0_window_count
        if ($windowCount -le 0 -or [double]$receipt.elapsed_seconds -le 0) { throw "Pilot measurement is invalid for $($task.run_id)." }
        $h5Output = @($receipt.outputs | Where-Object { $_.path -match '\.h5$' })
        if ($h5Output.Count -ne 1) { throw "Expected exactly one HDF5 output for $($task.run_id)." }
        $secondsPerWindow = [double]$receipt.elapsed_seconds / $windowCount
        $bytesPerWindow = [double]$h5Output[0].size_bytes / $windowCount
        if ($secondsPerWindow -gt $maxSecondsPerWindow) { $maxSecondsPerWindow = $secondsPerWindow }
        if ($bytesPerWindow -gt $maxBytesPerWindow) { $maxBytesPerWindow = $bytesPerWindow }
        $pilotWindowTotal += $windowCount
        $pilotElapsedTotal += [double]$receipt.elapsed_seconds
        if ([long]$receipt.peak_working_set_bytes_observed -gt $maxPeakWorkingSet) { $maxPeakWorkingSet = [long]$receipt.peak_working_set_bytes_observed }
        $pilotReceipts += [pscustomobject]@{ task = $task; receipt = $receipt; hdf5 = $h5Output[0]; bytes_per_window = $bytesPerWindow; seconds_per_window = $secondsPerWindow }
    }
    if ($pilotWindowTotal -le 0 -or $pilotElapsedTotal -le 0) { throw 'Pilot window/runtime totals are invalid.' }
    $cohort = Get-JsonDocument $script:CohortPath
    $remaining = @($cohort.tasks | Where-Object {
        $_.source_summary_status -eq 'COMPLETE' -and $_.run_id -notin $script:ApprovedPilotIds
    })
    if ($remaining.Count -ne 80) { throw "Expected exactly 80 new-required identities after two pilots; found $($remaining.Count)." }
    [long]$remainingWindows = 0
    foreach ($task in $remaining) { $remainingWindows += [long]$task.stage_counts_from_gate_a.stage0_valid_40ms_windows }
    $throughput = $pilotWindowTotal / $pilotElapsedTotal
    $forecastSeconds = [Math]::Ceiling(($remainingWindows / $throughput) * 1.25)
    $slowestSecondsPerWindowForecast = [Math]::Ceiling($remainingWindows * $maxSecondsPerWindow * 1.25)
    $forecastBytes = [long][Math]::Ceiling($remainingWindows * $maxBytesPerWindow * 1.25)
    $drive = [IO.DriveInfo]::new('E:\')
    $freeBytes = [long]$drive.AvailableFreeSpace
    $requiredWithReserve = $forecastBytes + [long]$script:MinimumFreeReserveBytes
    $snapshot = Get-CurrentCountSnapshot
    $failedIds = @('run_20261003_F1023_V70_D0120_P1_G26_ch3','run_20261003_F1023_V70_D0120_P1_G27_ch8')
    foreach ($failedId in $failedIds) {
        $row = Get-UniqueRow $snapshot.rows 'run_id' $failedId 'Historical failed task'
        if ($row.execution_status -ne 'FAILED') { throw "Historical failed identity changed from FAILED: $failedId" }
    }
    $warningIds = @(
        'run_20261003_F1023_V120_D0121_P2_G06_ch6',
        'run_20261003_F1023_V120_D0121_P2_G12_ch5',
        'run_20261003_F1023_V70_D0120_P9_G23_ch10',
        'run_20261003_F1023_V80_D0117_P8_G29_ch9'
    )
    foreach ($warningId in $warningIds) {
        $row = Get-UniqueRow $snapshot.rows 'run_id' $warningId 'Quarantined mapping-warning task'
        if ($row.execution_status -ne 'PENDING') { throw "Quarantined mapping-warning identity is not PENDING: $warningId" }
    }
    if (-not $snapshot.counts -or $snapshot.counts.ALREADY_COMPLETE -ne 1 -or $snapshot.counts.COMPLETE -ne 82 -or
        $snapshot.counts.PENDING -ne 4 -or $snapshot.counts.FAILED -ne 2 -or $snapshot.counts.IN_PROGRESS -ne 0) {
        throw 'Final mainline Summary counts differ from the frozen 1/82/4/0/2 cohort baseline.'
    }
    $events = @(Get-StorageEventsSince (ConvertTo-UtcDateTimeOffset $request.created_utc))
    if ($events.Count -gt 0) { throw 'New matching System disk/USB events exist; pilot audit cannot be finalized.' }
    $final = [ordered]@{
        finalized_utc = [DateTimeOffset]::UtcNow.ToString('o')
        release_request_sha256 = $validated.request_sha256
        status = 'PILOTS_PASS_BULK_BATCH_NOT_STARTED'
        existing_g28_ch1_readback_status = 'PASS_READ_ONLY'
        new_pilot_status = '2_OF_2_PASS'
        new_pilot_receipts = @($pilotReceipts | ForEach-Object { [ordered]@{ run_id = $_.task.run_id; receipt_path = Get-RelativeProjectPath (Join-Path (Join-Path (Join-Path $root 'runs') $_.task.run_id) 'pilot_receipt.json'); hdf5_bytes = [long]$_.hdf5.size_bytes; windows = [long]$_.receipt.identity.stage0_window_count; bytes_per_window = [double]$_.bytes_per_window; elapsed_seconds = [double]$_.receipt.elapsed_seconds; seconds_per_window = [double]$_.seconds_per_window; peak_working_set_bytes_observed = [long]$_.receipt.peak_working_set_bytes_observed } })
        remaining_new_required_tasks = $remaining.Count
        remaining_stage0_windows = $remainingWindows
        forecast_remaining_cir_bytes_upper_from_worst_pilot = $forecastBytes
        conservative_forecast_bytes_plus_100_gib_reserve = $requiredWithReserve
        current_e_free_bytes = $freeBytes
        capacity_sufficient_for_forecast_and_reserve = ($freeBytes -ge $requiredWithReserve)
        aggregate_pilot_throughput_windows_per_second = $throughput
        forecast_remaining_seconds_with_25pct_margin = $forecastSeconds
        slowest_pilot_forecast_seconds_with_25pct_margin = $slowestSecondsPerWindowForecast
        maximum_observed_peak_working_set_bytes = $maxPeakWorkingSet
        recommended_manual_checkpoint_interval_tasks = 5
        summary_counts = $snapshot.counts
        quarantined_mapping_warning_ids_still_pending = $warningIds
        historical_failed_ids_retained_failed = $failedIds
        new_storage_events_since_release = 0
        all_new_pilots_in_new_only_release_root = $true
        scientific_algorithm_modified = $false
        remaining_80_task_cir_batch_started = $false
        gate_d_scope = 'Pilot acceptance only; independent GitHub review required before any larger CIR production.'
    }
    $audit = Set-PilotAuditFinalAcceptance -Audit $audit `
        -FinalAcceptance $final
    Write-JsonReplace (Join-Path $root 'pilot_audit.json') $audit
    Write-JsonNew (Join-Path $root 'forecast_80_remaining.json') $final
    "PILOT_AUDIT_FINALIZED=$($final.status)"
    "REMAINING_80_FORECAST_BYTES=$forecastBytes RESERVE_BYTES=$($script:MinimumFreeReserveBytes) FREE_BYTES=$freeBytes CAPACITY_SUFFICIENT=$($final.capacity_sufficient_for_forecast_and_reserve)"
    "REMAINING_80_FORECAST_SECONDS=$forecastSeconds SLOWEST_PILOT_SCENARIO_SECONDS=$slowestSecondsPerWindowForecast"
    'BULK_CIR_BATCH_STARTED=false'
}

$modeCount = @($CreateReleaseRequest,$ValidateOnly,$Execute,$ExecuteWorker,$ReadBackExistingPilot,$ReadBackWorker,$FinalizePilotAudit | Where-Object { $_ }).Count
if ($modeCount -ne 1) { throw 'Select exactly one mode: CreateReleaseRequest, ValidateOnly, Execute, ExecuteWorker, ReadBackExistingPilot, ReadBackWorker, or FinalizePilotAudit.' }
if ($CreateReleaseRequest) { New-ReleaseRequest; exit 0 }
if ($ValidateOnly) { Invoke-ValidateOnly; exit 0 }
if ($Execute) { Invoke-ExecuteRequest; exit 0 }
if ($ExecuteWorker) { Invoke-ExecuteWorker; exit 0 }
if ($ReadBackExistingPilot) { Invoke-ReadBackExistingPilot; exit 0 }
if ($ReadBackWorker) { Invoke-ReadBackWorker; exit 0 }
if ($FinalizePilotAudit) { Invoke-FinalizePilotAudit; exit 0 }
