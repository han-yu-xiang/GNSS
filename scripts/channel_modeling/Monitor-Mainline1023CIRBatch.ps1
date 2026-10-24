[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$RequestPath,
    [Parameter(Mandatory)][string]$ExpectedRequestSha256,
    [string]$ReportRoot = 'E:\GNSS_Multipath_Project\dataset_generation_logs\batch_sage_execution\codex_monitor_83task'
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = 'E:\GNSS_Multipath_Project'
$batchLogRoot = Join-Path $projectRoot 'dataset_generation_logs\batch_sage_execution'
$checkUtc = [DateTimeOffset]::UtcNow
$errors = [System.Collections.Generic.List[string]]::new()
$snapshot = [ordered]@{
    schema_version = 1
    check_time_utc = $checkUtc.ToString('o')
    production_state = 'UNKNOWN'
    request_path = [IO.Path]::GetFullPath($RequestPath)
    request_sha256 = ''
    current_run_id = ''
    current_task_elapsed_seconds = $null
    latest_progress_utc = $null
    completed_count = 0
    expected_count = 80
    newly_completed_last_30m = $null
    last_pass_receipt_path = $null
    coordinator_state = 'UNKNOWN'
    worker_states = @()
    matlab_processes = @()
    runner_processes = @()
    e_free_bytes = $null
    new_storage_events = @()
    exceptions = @()
}

function Get-ResolvedProjectPath {
    param([Parameter(Mandatory)][string]$Path)
    if ([IO.Path]::IsPathRooted($Path)) { return [IO.Path]::GetFullPath($Path) }
    $candidate = [IO.Path]::GetFullPath((Join-Path $projectRoot ($Path.Replace('/', '\'))))
    $prefix = $projectRoot.TrimEnd('\') + '\'
    if (-not $candidate.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Receipt path escapes project root: $Path"
    }
    $candidate
}

function Get-StorageEventsSince {
    param([Parameter(Mandatory)][DateTime]$Since)
    $badIds = @(7, 11, 15, 51, 55, 98, 129, 153, 157)
    $events = @()
    try {
        $events = @(Get-WinEvent -FilterHashtable @{ LogName = 'System'; StartTime = $Since } -ErrorAction Stop)
    } catch {
        if ($_.FullyQualifiedErrorId -match 'NoMatchingEventsFound') { return @() }
        throw
    }
    @($events | Where-Object {
        $provider = [string]$_.ProviderName
        $message = [string]$_.Message
        $isStorage = $provider -match '(?i)disk|ntfs|stor|usb|kernel-pnp|volmgr|partmgr'
        $mentionsTarget = $message -match '(?i)(E:|Kingston XS1000|VID_174C|PID_55AA)'
        $failure = $message -match '(?i)(error|failed|failure|disconnect|surprise.?remov|device was not ready|bad block|I/O device error|reset to device|controller error|corrupt)'
        (($isStorage -and $_.Id -in $badIds -and $_.Level -le 3) -or ($mentionsTarget -and $failure))
    } | Select-Object TimeCreated, Id, ProviderName, RecordId, Message)
}

try {
    if ($ExpectedRequestSha256 -notmatch '^[a-fA-F0-9]{64}$' -or -not (Test-Path -LiteralPath $RequestPath -PathType Leaf)) {
        throw 'The pinned immutable batch request is missing or has an invalid SHA pin.'
    }
    $actualRequestHash = (Get-FileHash -LiteralPath $RequestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualRequestHash -cne $ExpectedRequestSha256.ToLowerInvariant()) { throw 'The immutable batch request SHA no longer matches the monitor pin.' }
    $snapshot.request_sha256 = $actualRequestHash
    $request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$request.execution_mode -cne 'SERIAL_BATCH' -or @($request.tasks).Count -ne 80 -or
        [int]$request.max_parallel_matlab -ne 1 -or $request.resume -ne $false) {
        throw 'Pinned request does not describe the authorized 80-task serial, non-resuming batch.'
    }
    $releaseRoot = [IO.Path]::GetFullPath([string]$request.release_root)
    if (-not $releaseRoot.StartsWith(([IO.Path]::GetFullPath((Join-Path $projectRoot 'dataset_generation_logs\channel_modeling')).TrimEnd('\') + '\'), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Pinned release root is outside the approved CIR release directory.'
    }
    $auditPath = Join-Path $releaseRoot 'cir_batch_audit.json'
    $audit = Get-Content -LiteralPath $auditPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$audit.release_request_sha256 -cne $actualRequestHash) { throw 'CIR audit does not bind the pinned batch request.' }
    $completed = @($audit.completed_tasks)
    if ($completed.Count -gt 80) { throw 'CIR audit reports more than 80 completed tasks.' }
    foreach ($task in $completed) {
        $receiptPath = Get-ResolvedProjectPath ([string]$task.receipt_path)
        if (-not (Test-Path -LiteralPath $receiptPath -PathType Leaf)) { throw "A completed audit entry lacks its PASS receipt: $receiptPath" }
        $receiptHash = (Get-FileHash -LiteralPath $receiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $receipt = Get-Content -LiteralPath $receiptPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ([string]$task.status -cne 'PASS' -or [string]$receipt.status -cne 'PASS' -or
            [string]$receipt.run_id -cne [string]$task.run_id -or
            [string]$receipt.request_sha256 -cne $actualRequestHash -or
            [string]$task.receipt_sha256 -cne $receiptHash -or
            [long]$task.windows_task_last_result -ne 0 -or [int]$receipt.exit_code -ne 0) {
            throw "Audit/Summary receipt evidence is inconsistent for $($task.run_id)."
        }
    }
    $snapshot.completed_count = $completed.Count
    if ($completed.Count -gt 0) { $snapshot.last_pass_receipt_path = [string]$completed[-1].receipt_path }
    $snapshot.current_run_id = [string]$audit.current_run_id
    if (-not [string]::IsNullOrWhiteSpace([string]$audit.current_task_started_utc)) {
        $started = [DateTimeOffset]::Parse([string]$audit.current_task_started_utc).ToUniversalTime()
        $snapshot.current_task_elapsed_seconds = [Math]::Max(0, [Math]::Floor(($checkUtc - $started).TotalSeconds))
    }

    $launchRoot = Join-Path $releaseRoot 'batch_launch_records'
    $coordinatorNames = @()
    foreach ($file in @(Get-ChildItem -LiteralPath $launchRoot -Filter '*.json' -File -ErrorAction SilentlyContinue)) {
        $launch = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8 | ConvertFrom-Json
        if ([string]$launch.request_sha256 -cne $actualRequestHash) { throw "A coordinator launch record has a conflicting request pin: $($file.FullName)" }
        $coordinatorNames += [string]$launch.task_name
    }
    $scheduled = @(Get-ScheduledTask -ErrorAction Stop)
    $coordinatorTasks = @($scheduled | Where-Object { $_.TaskName -in $coordinatorNames })
    $snapshot.coordinator_state = if ($coordinatorTasks.Count -eq 0) { 'NOT_REGISTERED' } else { [string]$coordinatorTasks[-1].State }
    $workerTasks = @($scheduled | Where-Object {
        @($_.Actions | Where-Object {
            $argumentProperty = $_.PSObject.Properties['Arguments']
            $null -ne $argumentProperty -and
            [string]$argumentProperty.Value -like "*$actualRequestHash*" -and
            [string]$argumentProperty.Value -match '(?i)-ExecuteBatchWorker(?:\s|$)'
        }).Count -gt 0
    })
    $snapshot.worker_states = @($workerTasks | ForEach-Object { [pscustomobject]@{ task_name = $_.TaskName; state = [string]$_.State } })
    $processes = @(Get-CimInstance -ClassName Win32_Process -ErrorAction Stop)
    $snapshot.matlab_processes = @($processes | Where-Object { $_.Name -match '(?i)^matlab' } | ForEach-Object { [pscustomobject]@{ pid = [int]$_.ProcessId; name = [string]$_.Name; created = [string]$_.CreationDate } })
    $snapshot.runner_processes = @($processes | Where-Object {
        [string]$_.CommandLine -match [regex]::Escape($actualRequestHash) -and
        [string]$_.CommandLine -match '(?i)(RunBatchCoordinator|ExecuteBatchWorker)'
    } | ForEach-Object { [pscustomobject]@{ pid = [int]$_.ProcessId; name = [string]$_.Name; command_line = [string]$_.CommandLine } })

    if (-not [string]::IsNullOrWhiteSpace($snapshot.current_run_id)) {
        $runRoot = Join-Path (Join-Path $releaseRoot 'runs') $snapshot.current_run_id
        if (Test-Path -LiteralPath $runRoot -PathType Container) {
            $progressFiles = @(Get-ChildItem -LiteralPath $runRoot -File -Recurse -ErrorAction Stop | Where-Object { $_.Extension -notmatch '(?i)^\.(mat|h5|hdf5)$' })
            if ($progressFiles.Count -gt 0) { $snapshot.latest_progress_utc = ($progressFiles | Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1).LastWriteTimeUtc.ToString('o') }
        }
    }

    $drive = [IO.DriveInfo]::new('E:\')
    $snapshot.e_free_bytes = [long]$drive.AvailableFreeSpace
    $reportFiles = @(Get-ChildItem -LiteralPath $ReportRoot -Filter '*_CIR_Task5_30m.json' -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending)
    $sinceUtc = $checkUtc.AddMinutes(-30)
    if ($reportFiles.Count -gt 0) {
        try {
            $previous = Get-Content -LiteralPath $reportFiles[0].FullName -Raw -Encoding UTF8 | ConvertFrom-Json
            $snapshot.newly_completed_last_30m = [Math]::Max(0, [int]$snapshot.completed_count - [int]$previous.completed_count)
            $sinceUtc = [DateTimeOffset]::Parse([string]$previous.check_time_utc).UtcDateTime
        } catch { $errors.Add("Unable to compare with prior monitor report $($reportFiles[0].FullName): $($_.Exception.Message)") }
    }
    $snapshot.new_storage_events = @(Get-StorageEventsSince $sinceUtc)
    if (@($snapshot.new_storage_events).Count -gt 0) { $errors.Add('New matching System disk/USB I/O event(s) were recorded.') }
    if (Test-Path -LiteralPath (Join-Path $releaseRoot 'cir_batch_stop_receipt.json') -PathType Leaf) {
        $snapshot.production_state = 'NEEDS_ATTENTION'
        $stop = Get-Content -LiteralPath (Join-Path $releaseRoot 'cir_batch_stop_receipt.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        $errors.Add("Batch has FAILED_NO_RETRY stop receipt: $($stop.error)")
    } elseif (Test-Path -LiteralPath (Join-Path $releaseRoot 'cir_batch_completion_receipt.json') -PathType Leaf) {
        $completion = Get-Content -LiteralPath (Join-Path $releaseRoot 'cir_batch_completion_receipt.json') -Raw -Encoding UTF8 | ConvertFrom-Json
        if ([string]$completion.status -cne 'PASS' -or [string]$completion.request_sha256 -cne $actualRequestHash -or
            [int]$completion.completed_task_count -ne 80 -or $snapshot.completed_count -ne 80) {
            $snapshot.production_state = 'NEEDS_ATTENTION'
            $errors.Add('Batch completion receipt, audit count, or request pin is inconsistent.')
        } else { $snapshot.production_state = 'COMPLETE' }
    } elseif ([string]$audit.status -ceq 'FAILED_NO_RETRY') {
        $snapshot.production_state = 'NEEDS_ATTENTION'
        $errors.Add('Audit is FAILED_NO_RETRY but the stop receipt is missing.')
    } elseif (@($snapshot.matlab_processes).Count -gt 0 -or
        @($coordinatorTasks | Where-Object { $_.State -in @('Running','Queued') }).Count -gt 0 -or
        @($workerTasks | Where-Object { $_.State -in @('Running','Queued') }).Count -gt 0) {
        $snapshot.production_state = 'RUNNING'
    } elseif ([string]$audit.status -ceq 'CREATED_NOT_STARTED' -and $coordinatorNames.Count -eq 0) {
        $snapshot.production_state = 'NOT_STARTED'
    } else {
        $snapshot.production_state = 'NEEDS_ATTENTION'
        $errors.Add('Batch audit is nonterminal but no Coordinator, worker, or MATLAB process is active.')
    }
    if ($errors.Count -gt 0 -and $snapshot.production_state -ne 'COMPLETE') { $snapshot.production_state = 'NEEDS_ATTENTION' }
} catch {
    $snapshot.production_state = 'NEEDS_ATTENTION'
    $errors.Add($_.Exception.Message)
}

$snapshot.exceptions = @($errors.ToArray())
[IO.Directory]::CreateDirectory($ReportRoot) | Out-Null
$stamp = [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$reportPath = Join-Path $ReportRoot "${stamp}_CIR_Task5_30m.json"
$stream = $null
try {
    $stream = [IO.File]::Open($reportPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    $json = ConvertTo-Json -InputObject $snapshot -Depth 12
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($json + [Environment]::NewLine)
    $stream.Write($bytes, 0, $bytes.Length)
    $stream.Flush($true)
} finally {
    if ($null -ne $stream) { $stream.Dispose() }
}
"CIR_TASK5_MONITOR_STATE=$($snapshot.production_state) REPORT=$reportPath"
