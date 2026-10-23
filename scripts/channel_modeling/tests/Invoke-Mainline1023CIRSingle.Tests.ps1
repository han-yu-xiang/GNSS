[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = 'E:\GNSS_Multipath_Project'
$originalProjectRoot = $projectRoot
$scriptPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..\Invoke-Mainline1023CIRSingle.ps1'
$scriptPath = [System.IO.Path]::GetFullPath($scriptPath)
$runnerText = Get-Content -LiteralPath $scriptPath -Raw -Encoding UTF8
$releaseBase = Join-Path $projectRoot 'dataset_generation_logs\channel_modeling'
$stamp = [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$fixtureRoot = Join-Path $releaseBase ("mainline_1023_cir_v1_${stamp}_TEST_" + [Guid]::NewGuid().ToString('N'))
$batchFixtureRoot = Join-Path $releaseBase ("mainline_1023_cir_v1_${stamp}_BATCH")
$temporaryRequest = Join-Path ([System.IO.Path]::GetTempPath()) ("cir-request-" + [Guid]::NewGuid().ToString('N') + '.json')
$pilotRunIds = @(
    'run_20261003_F1023_V70_D0120_P1_G18_ch2',
    'run_20261003_F1023_V70_D0120_P5_G23_ch0'
)
$failures = [System.Collections.Generic.List[string]]::new()
$passes = 0

function Assert-True {
    param([Parameter(Mandatory)][bool]$Condition, [Parameter(Mandatory)][string]$Message)
    if (-not $Condition) {
        $failures.Add($Message)
        throw $Message
    }
    $script:passes++
}

function Invoke-Captured {
    param([Parameter(Mandatory)][scriptblock]$Command)
    try {
        $output = @(& $Command 2>&1 | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
        return [pscustomobject]@{ Succeeded = $true; Output = $output; Error = '' }
    } catch {
        return [pscustomobject]@{ Succeeded = $false; Output = ''; Error = $_.Exception.Message }
    }
}

try {
    Assert-True ($runnerText -notmatch '(?m)^\s*\$trigger\s*=\s*New-ScheduledTaskTrigger|Register-ScheduledTask[^\r\n]*-Trigger') 'Manual-only worker registration must not retain a future time trigger that can rerun a failed one-shot attempt.'
    Assert-True ($runnerText -match 'Register-ScheduledTask -TaskName \$name -Action \$action -Principal \$principal -Settings \$settings') 'Manual-only worker registration must be explicitly started on demand.'
    $launchRecordAssignment = @($runnerText -split "`r?`n" | Where-Object { $_ -match '^\s*\$startedPath\s*=' })
    Assert-True ($launchRecordAssignment.Count -eq 1 -and
        $launchRecordAssignment[0] -match 'release_root.*launch_records' -and
        $launchRecordAssignment[0] -notmatch 'runs') 'The launcher receipt must stay outside the run namespace so worker preflight can require that namespace to be absent.'
    $settingsLine = @($runnerText -split "`r?`n" | Where-Object { $_ -match 'New-ScheduledTaskSettingsSet.*-ExecutionTimeLimit \$executionTimeLimit' })
    $limitSelectionLine = @($runnerText -split "`r?`n" | Where-Object { $_ -match '^\s*\$executionTimeLimit = if \(\$WorkerMode -eq ''ExecuteBatchWorker''\)' })
    Assert-True ($settingsLine.Count -eq 1 -and $limitSelectionLine.Count -eq 1 -and
        $settingsLine[0] -match '\s-DontStopIfGoingOnBatteries(?:\s|$)' -and
        $settingsLine[0] -notmatch '\s-AllowStartIfOnBatteries(?:\s|$)') 'A batch CIR worker must have no scheduler time limit, require AC at start and continue if AC briefly drops.'
    $powerSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Hours 12) -StartWhenAvailable:$false `
        -DontStopIfGoingOnBatteries
    $unlimitedSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -StartWhenAvailable:$false `
        -DontStopIfGoingOnBatteries
    Assert-True ($powerSettings.DisallowStartIfOnBatteries -and
        -not $powerSettings.StopIfGoingOnBatteries) 'PowerShell task settings must deny battery start while allowing a running worker to continue through a brief battery switch.'
    Assert-True ($unlimitedSettings.ExecutionTimeLimit -eq 'PT0S') 'Task Scheduler zero duration must represent no imposed execution timeout for long batch workers.'
    $coordinatorSettingsLine = @($runnerText -split "`r?`n" | Where-Object { $_ -match 'New-ScheduledTaskSettingsSet.*-Seconds 0' })
    Assert-True ($coordinatorSettingsLine.Count -eq 1 -and
        $coordinatorSettingsLine[0] -match '\s-DontStopIfGoingOnBatteries(?:\s|$)' -and
        $runnerText -match 'Set-CirBatchSystemRequired -Enable \$true' -and
        $runnerText -match 'Set-CirBatchSystemRequired -Enable \$false') 'The batch coordinator must run without a timeout, continue through AC switching, hold a scoped idle-sleep request, then release it.'

    $prepare = Invoke-Captured { & $scriptPath -CreateReleaseRequest -ReleaseRoot $fixtureRoot -PilotRunIds $pilotRunIds }
    Assert-True $prepare.Succeeded "CreateReleaseRequest must create a pinned two-pilot request: $($prepare.Error)"

    $requestPath = Join-Path $fixtureRoot 'release_request.json'
    Assert-True (Test-Path -LiteralPath $requestPath -PathType Leaf) 'CreateReleaseRequest must write release_request.json.'
    $requestHash = (Get-FileHash -LiteralPath $requestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $firstRunRoot = Join-Path (Join-Path $fixtureRoot 'runs') $pilotRunIds[0]

    $validation = Invoke-Captured {
        & $scriptPath -ValidateOnly -RequestManifest $requestPath `
            -ExpectedRequestSha256 $requestHash -RunId $pilotRunIds[0]
    }
    Assert-True $validation.Succeeded 'ValidateOnly must accept the exact frozen inputs and selected run.'
    Assert-True ($validation.Output -match 'VALIDATION_ONLY_OK') 'ValidateOnly must report its successful gate result.'
    Assert-True ($validation.Output -match 'MATLAB_INVOKED=false') 'ValidateOnly must not invoke MATLAB.'
    Assert-True (-not (Test-Path -LiteralPath $firstRunRoot)) 'ValidateOnly must not create a run/output directory.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'dataset_generation_logs\batch_sage_execution\.windows_runner_active.lock'))) 'ValidateOnly must not create or modify the global execution lock.'

    $windowsPowerShell = Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
    $legacyOutput = @(& $windowsPowerShell -NoProfile -ExecutionPolicy Bypass -File $scriptPath `
        -ValidateOnly -RequestManifest $requestPath -ExpectedRequestSha256 $requestHash `
        -RunId $pilotRunIds[0] 2>&1 | ForEach-Object { [string]$_ }) -join [Environment]::NewLine
    $legacyExitCode = $LASTEXITCODE
    Assert-True ($legacyExitCode -eq 0) 'Windows PowerShell 5.1 ValidateOnly must accept numeric provenance serialized by PowerShell 7.'
    Assert-True ($legacyOutput -match 'VALIDATION_ONLY_OK' -and $legacyOutput -match 'MATLAB_INVOKED=false') 'Windows PowerShell 5.1 compatibility validation must remain non-computational.'

    $request = Get-Content -LiteralPath $requestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-True (@($request.tasks).Count -eq 2) 'Release request must contain exactly two pilot identities.'
    Assert-True ($request.tasks[0].run_id -eq $pilotRunIds[0] -and $request.tasks[1].run_id -eq $pilotRunIds[1]) 'Release request must preserve the selected task order and exact run IDs.'
    Assert-True ($request.tasks[0].scene_id -ne $request.tasks[1].scene_id -and $request.tasks[0].environment_class -eq 'Urban' -and $request.tasks[1].environment_class -eq 'Urban') 'The new pilots must be distinct Urban scenes.'
    Assert-True ($request.tasks[0].elevation_group -ne $request.tasks[1].elevation_group) 'The two new Urban pilots must cover distinct supported elevation groups.'
    Assert-True ($request.resume -eq $false -and $request.max_parallel_matlab -eq 1) 'Release policy must be fresh, serial, and non-resuming.'
    Assert-True ($request.baseline_existing_pilot.run_id -eq 'run_20261003_F1023_V70_D0117_P2_G28_ch1') 'The frozen G28/ch1 pilot must be bound as read-only baseline evidence.'
    Assert-True ($request.baseline_existing_pilot.psobject.Properties.Name -notcontains 'raw_iq_sha256') 'The existing baseline must not introduce a raw-IQ content hash.'

    $passReceiptPaths = @(
        (Join-Path $projectRoot 'dataset_generation_logs\channel_modeling\mainline_1023_cir_v1_20261022T164829696Z\baseline_readback\readback_receipt.json'),
        (Join-Path $projectRoot 'dataset_generation_logs\channel_modeling\mainline_1023_cir_v1_20261023T060236191Z\runs\run_20261003_F1023_V70_D0120_P1_G18_ch2\pilot_receipt.json'),
        (Join-Path $projectRoot 'dataset_generation_logs\channel_modeling\mainline_1023_cir_v1_20261023T060236191Z\runs\run_20261003_F1023_V70_D0120_P5_G23_ch0\pilot_receipt.json')
    )
    $priorFailedBatchRequest = Join-Path $projectRoot 'dataset_generation_logs\channel_modeling\mainline_1023_cir_v1_20261023T102159053Z_task5batch\release_request.json'
    $batchPrepare = Invoke-Captured {
        & $scriptPath -CreateBatchReleaseRequest -ReleaseRoot $batchFixtureRoot -PassReceiptPaths $passReceiptPaths `
            -SupersedePriorBatchRequestPath $priorFailedBatchRequest
    }
    Assert-True $batchPrepare.Succeeded "Batch release creation must accept the frozen cohort and three PASS skips: $($batchPrepare.Error)"
    $batchRequestPath = Join-Path $batchFixtureRoot 'release_request.json'
    Assert-True (Test-Path -LiteralPath $batchRequestPath -PathType Leaf) 'Batch release creation must write an immutable request.'
    $batchRequest = Get-Content -LiteralPath $batchRequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $frozenTaskPath = Join-Path $projectRoot 'dataset_generation_logs\channel_modeling\mainline_1023_cohort_v1_20261022T082520Z\cir_tasks.json'
    $frozenTasks = @((Get-Content -LiteralPath $frozenTaskPath -Raw -Encoding UTF8 | ConvertFrom-Json).tasks)
    $frozenIds = @($frozenTasks | ForEach-Object { [string]$_.run_id })
    $expectedSkipIds = @(
        'run_20261003_F1023_V70_D0117_P2_G28_ch1',
        'run_20261003_F1023_V70_D0120_P1_G18_ch2',
        'run_20261003_F1023_V70_D0120_P5_G23_ch0'
    )
    $expectedBatchIds = @($frozenIds | Where-Object { $_ -notin $expectedSkipIds })
    Assert-True ($frozenIds.Count -eq 83 -and $batchRequest.frozen_cohort_run_ids.Count -eq 83) 'Batch request must bind all 83 Gate-B identities.'
    Assert-True ((@($batchRequest.frozen_cohort_run_ids) -join "`n") -ceq ($frozenIds -join "`n")) 'Batch request must preserve exact frozen Gate-B order.'
    Assert-True ($batchRequest.tasks.Count -eq 80 -and $batchRequest.skipped_existing_pass.Count -eq 3) 'Batch request must contain exactly 80 remaining tasks and three PASS skips.'
    Assert-True ((@($batchRequest.skipped_existing_pass | ForEach-Object { [string]$_.run_id }) -join ',') -ceq ($expectedSkipIds -join ',')) 'G28/G18/G23 PASS identities must be skipped exactly once.'
    Assert-True ((@($batchRequest.tasks | ForEach-Object { [string]$_.run_id }) -join "`n") -ceq ($expectedBatchIds -join "`n")) 'The executable queue must retain Gate-B order after removing only PASS identities.'
    Assert-True (@($batchRequest.tasks | Where-Object { $_.task_status -ne 'NEW_REQUIRED' }).Count -eq 0) 'Only NEW_REQUIRED identities may enter the executable queue.'
    Assert-True ($batchRequest.excluded_run_ids.Count -eq 6 -and
        @($batchRequest.tasks | Where-Object { $_.run_id -in @($batchRequest.excluded_run_ids) }).Count -eq 0) 'All six frozen exclusions must remain out of the queue.'
    Assert-True ($batchRequest.execution_mode -eq 'SERIAL_BATCH' -and $batchRequest.resume -eq $false -and
        $batchRequest.max_parallel_matlab -eq 1 -and
        $batchRequest.batch_reservation_supersession.authorization -eq 'COMMANDER_APPROVED_EMPTY_SCIENCE_TAKEOVER' -and
        $batchRequest.source_sha256.'scripts/channel_modeling/Invoke-Mainline1023CIRSingle.ps1' -eq
        (Get-FileHash -LiteralPath $scriptPath -Algorithm SHA256).Hash.ToLowerInvariant()) 'Batch release must bind the current source SHA and fresh serial policy.'
    foreach ($sourcePath in @(
        'scripts/channel_modeling/Invoke-Mainline1023CIRSingle.ps1',
        'scripts/channel_modeling/export_gnss_code_domain_cir.m',
        'scripts/channel_modeling/validate_gnss_code_domain_cir.m'
    )) {
        $runnerRepoRoot = [IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $scriptPath) '..\..'))
        $sourceFullPath = Join-Path $runnerRepoRoot ($sourcePath.Replace('/', '\'))
        $actualSourceHash = (Get-FileHash -LiteralPath $sourceFullPath -Algorithm SHA256).Hash.ToLowerInvariant()
        Assert-True ($batchRequest.source_sha256.$sourcePath -eq $actualSourceHash) "Batch release must bind the current SHA of $sourcePath."
    }
    $batchHash = (Get-FileHash -LiteralPath $batchRequestPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $batchValidation = Invoke-Captured {
        & $scriptPath -ValidateBatchOnly -RequestManifest $batchRequestPath -ExpectedRequestSha256 $batchHash
    }
    Assert-True $batchValidation.Succeeded "Batch ValidateOnly must not require a MATLAB worker: $($batchValidation.Error)"
    Assert-True ($batchValidation.Output -match 'BATCH_VALIDATION_ONLY_OK' -and
        $batchValidation.Output -match 'MATLAB_INVOKED=false') 'Batch ValidateOnly must explicitly confirm no MATLAB invocation.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $batchFixtureRoot 'runs'))) 'Batch ValidateOnly must not create output namespaces.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'dataset_generation_logs\batch_sage_execution\.windows_runner_active.lock'))) 'Batch ValidateOnly must not create or change the execution lock.'
    $windowsPowerShellBatchOutput = @(& $windowsPowerShell -NoProfile -ExecutionPolicy Bypass -File $scriptPath `
        -ValidateBatchOnly -RequestManifest $batchRequestPath -ExpectedRequestSha256 $batchHash 2>&1 |
        ForEach-Object { [string]$_ }) -join [Environment]::NewLine
    $windowsPowerShellBatchExitCode = $LASTEXITCODE
    Assert-True ($windowsPowerShellBatchExitCode -eq 0) 'Windows PowerShell 5.1 must accept the immutable SERIAL_BATCH request without invoking MATLAB.'
    Assert-True ($windowsPowerShellBatchOutput -match 'BATCH_VALIDATION_ONLY_OK' -and
        $windowsPowerShellBatchOutput -match 'MATLAB_INVOKED=false') 'Windows PowerShell 5.1 Batch ValidateOnly must explicitly remain no-compute.'

    $wrongChannelRequest = $batchRequest | ConvertTo-Json -Depth 24 | ConvertFrom-Json
    $wrongChannelRequest.tasks[0].tracking_channel = [int]$wrongChannelRequest.tasks[0].tracking_channel + 1
    [System.IO.File]::WriteAllText($temporaryRequest, ($wrongChannelRequest | ConvertTo-Json -Depth 24) + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false))
    $wrongChannelHash = (Get-FileHash -LiteralPath $temporaryRequest -Algorithm SHA256).Hash.ToLowerInvariant()
    $wrongChannel = Invoke-Captured {
        & $scriptPath -ValidateBatchOnly -RequestManifest $temporaryRequest -ExpectedRequestSha256 $wrongChannelHash
    }
    Assert-True (-not $wrongChannel.Succeeded -and $wrongChannel.Error -match 'identity|tracking_channel') 'Batch validation must reject an altered PRN/channel identity.'

    $crossTaskRequest = $batchRequest | ConvertTo-Json -Depth 24 | ConvertFrom-Json
    $crossTaskRequest.tasks[0].run_id = [string]$crossTaskRequest.tasks[1].run_id
    [System.IO.File]::WriteAllText($temporaryRequest, ($crossTaskRequest | ConvertTo-Json -Depth 24) + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false))
    $crossTaskHash = (Get-FileHash -LiteralPath $temporaryRequest -Algorithm SHA256).Hash.ToLowerInvariant()
    $crossTask = Invoke-Captured {
        & $scriptPath -ValidateBatchOnly -RequestManifest $temporaryRequest -ExpectedRequestSha256 $crossTaskHash
    }
    Assert-True (-not $crossTask.Succeeded -and $crossTask.Error -match 'identity|run_id') 'Batch validation must reject cross-task pin substitution.'

    $testTokens = $null
    $testParseErrors = $null
    $testAst = [System.Management.Automation.Language.Parser]::ParseInput($runnerText, [ref]$testTokens, [ref]$testParseErrors)
    Assert-True ($testParseErrors.Count -eq 0) 'Runner AST must parse before extracting batch safety helpers.'
    foreach ($functionName in @(
        'Resolve-ProjectPath', 'Get-RelativeProjectPath', 'Get-Sha256', 'Get-JsonDocument', 'ConvertTo-UtcDateTimeOffset', 'Test-TaskPinPropertyMatch',
        'Assert-NewCIROutputNamespace', 'Assert-BatchRequestIdentities', 'Assert-MatlabExitReceiptMatches', 'Invoke-SerialCirBatchTasks',
        'Assert-WorkerTaskReceiptPass', 'Assert-NoNewStorageFailures', 'New-CirBatchAuditDocument',
        'Get-CirBatchExistingRunNamespaces', 'Assert-CirBatchReservationSupersessionEvidence', 'New-CirBatchReservationRecord',
        'Acquire-CirBatchCoordinatorLock', 'Release-CirBatchCoordinatorLock'
    )) {
        $functionAst = @($testAst.FindAll({
            param($node)
            $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq $functionName
        }, $true))
        Assert-True ($functionAst.Count -eq 1) "Expected one testable safety helper: $functionName"
        . ([scriptblock]::Create($functionAst[0].Extent.Text))
    }
    $script:ProjectRoot = $projectRoot
    $script:ExistingPilotRunId = [string]$expectedSkipIds[0]

    $batchAudit = New-CirBatchAuditDocument -RequestSha256 $batchHash
    $batchAudit.status = 'RUNNING'
    $batchAudit.current_run_id = [string]$batchRequest.tasks[0].run_id
    $batchAudit.current_task_started_utc = [DateTimeOffset]::UtcNow.ToString('o')
    $batchAudit.completed_tasks = @()
    $batchAudit.last_completed_utc = [DateTimeOffset]::UtcNow.ToString('o')
    $batchAudit.completion_receipt_path = 'cir_batch_completion_receipt.json'
    $batchAudit.completed_utc = [DateTimeOffset]::UtcNow.ToString('o')
    $batchAudit.stop_receipt_path = 'cir_batch_stop_receipt.json'
    $batchAudit.stopped_utc = [DateTimeOffset]::UtcNow.ToString('o')
    Assert-True ($batchAudit.release_request_sha256 -eq $batchHash -and
        @('current_task_started_utc','last_completed_utc','completion_receipt_path','completed_utc','stop_receipt_path','stopped_utc' |
            Where-Object { $null -eq $batchAudit.PSObject.Properties[$_] }).Count -eq 0) 'A newly created batch audit must declare every strict-mode field the coordinator may later update.'
    $roundTripAudit = ($batchAudit | ConvertTo-Json -Depth 12) | ConvertFrom-Json
    $roundTripAudit.current_task_started_utc = '2026-10-23T00:00:00.0000000+00:00'
    $roundTripAudit.last_completed_utc = '2026-10-23T00:01:00.0000000+00:00'
    $roundTripAudit.completion_receipt_path = 'cir_batch_completion_receipt.json'
    $roundTripAudit.completed_utc = '2026-10-23T00:02:00.0000000+00:00'
    $roundTripAudit.stop_receipt_path = 'cir_batch_stop_receipt.json'
    $roundTripAudit.stopped_utc = '2026-10-23T00:03:00.0000000+00:00'
    Assert-True ($roundTripAudit.current_task_started_utc -eq '2026-10-23T00:00:00.0000000+00:00' -and
        $roundTripAudit.last_completed_utc -eq '2026-10-23T00:01:00.0000000+00:00' -and
        $roundTripAudit.completion_receipt_path -eq 'cir_batch_completion_receipt.json' -and
        $roundTripAudit.completed_utc -eq '2026-10-23T00:02:00.0000000+00:00' -and
        $roundTripAudit.stop_receipt_path -eq 'cir_batch_stop_receipt.json' -and
        $roundTripAudit.stopped_utc -eq '2026-10-23T00:03:00.0000000+00:00') 'JSON-round-tripped batch audit must accept every real coordinator update field under StrictMode.'

    $cohortFixtureSha = 'c' * 64
    $oldRequestFixtureSha = 'd' * 64
    $oldReservationFixtureSha = 'e' * 64
    $oldStopFixtureSha = 'f' * 64
    $oldAuditFixtureSha = '1' * 64
    $oldStartedFixtureSha = '2' * 64
    $oldLaunchFixtureSha = '3' * 64
    $oldReleaseFixture = Join-Path $batchFixtureRoot 'prior_failed_release'
    $oldCoordinatorFixtureTask = 'GNSS-CIR-BatchFixture-Old'
    $takeoverRequest = [pscustomobject]@{
        execution_mode = 'SERIAL_BATCH'
        release_root = Join-Path $batchFixtureRoot 'new_takeover_release'
        inputs = [pscustomobject]@{ cohort_sha256 = $cohortFixtureSha }
        batch_reservation_supersession = [pscustomobject]@{
            authorization = 'COMMANDER_APPROVED_EMPTY_SCIENCE_TAKEOVER'
            prior_reservation_path = 'dataset_generation_logs/batch_sage_execution/cir_batch_reservations/fixture.json'
            prior_reservation_sha256 = $oldReservationFixtureSha
            prior_release_request_path = 'dataset_generation_logs/channel_modeling/prior_failed_release/release_request.json'
            prior_request_sha256 = $oldRequestFixtureSha
            prior_stop_receipt_path = 'dataset_generation_logs/channel_modeling/prior_failed_release/cir_batch_stop_receipt.json'
            prior_stop_receipt_sha256 = $oldStopFixtureSha
            prior_audit_path = 'dataset_generation_logs/channel_modeling/prior_failed_release/cir_batch_audit.json'
            prior_audit_sha256 = $oldAuditFixtureSha
            prior_execution_started_path = 'dataset_generation_logs/channel_modeling/prior_failed_release/batch_execution_started.json'
            prior_execution_started_sha256 = $oldStartedFixtureSha
            prior_launch_record_path = 'dataset_generation_logs/channel_modeling/prior_failed_release/batch_launch_records/GNSS-CIR-BatchFixture-Old.json'
            prior_launch_record_sha256 = $oldLaunchFixtureSha
            prior_coordinator_task_name = $oldCoordinatorFixtureTask
        }
    }
    $takeoverEvidence = [pscustomobject]@{
        reservation_sha256 = $oldReservationFixtureSha
        reservation = [pscustomobject]@{ schema_version = 1; cohort_sha256 = $cohortFixtureSha; release_root = $oldReleaseFixture; request_sha256 = $oldRequestFixtureSha }
        request_sha256 = $oldRequestFixtureSha
        prior_request = [pscustomobject]@{ execution_mode = 'SERIAL_BATCH'; release_root = $oldReleaseFixture; inputs = [pscustomobject]@{ cohort_sha256 = $cohortFixtureSha }; tasks = @([pscustomobject]@{ run_id = 'run_fixture_g03_ch2' },[pscustomobject]@{ run_id = 'run_fixture_second' }) }
        stop_receipt_sha256 = $oldStopFixtureSha
        stop_receipt = [pscustomobject]@{ status = 'FAILED_NO_RETRY'; request_sha256 = $oldRequestFixtureSha; coordinator_task_name = $oldCoordinatorFixtureTask; coordinator_pid = 12345; current_run_id = 'run_fixture_g03_ch2'; current_worker_task_name = ''; completed_count = 0; completed_run_ids = @(); automatic_retry = $false }
        audit_sha256 = $oldAuditFixtureSha
        audit = [pscustomobject]@{ release_request_sha256 = $oldRequestFixtureSha; status = 'CREATED_NOT_STARTED'; completed_tasks = @(); current_run_id = '' }
        execution_started_sha256 = $oldStartedFixtureSha
        execution_started = [pscustomobject]@{ status = 'RUNNING'; request_sha256 = $oldRequestFixtureSha; coordinator_task_name = $oldCoordinatorFixtureTask; coordinator_pid = 12345; started_utc = '2026-10-23T00:00:00.0000000+00:00' }
        launch_record_sha256 = $oldLaunchFixtureSha
        launch_record = [pscustomobject]@{ request_sha256 = $oldRequestFixtureSha; task_name = $oldCoordinatorFixtureTask }
        coordinator_task_state = 'Ready'
        coordinator_last_task_result = 1
        coordinator_process_identity_alive = $false
        worker_launch_record_count = 0
        worker_scheduled_task_count = 0
        coordinator_lock_unowned = $true
        run_namespace_exists = $false
        completion_receipt_exists = $false
        matlab_process_count = 0
    }
    Assert-True (Assert-CirBatchReservationSupersessionEvidence -Request $takeoverRequest -Evidence $takeoverEvidence) 'An independently evidenced terminal batch with zero worker/science artifacts may be superseded once.'
    $runningEvidence = $takeoverEvidence | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $runningEvidence.coordinator_task_state = 'Running'
    $runningEvidence.coordinator_last_task_result = 0
    $runningEvidenceError = Invoke-Captured { Assert-CirBatchReservationSupersessionEvidence -Request $takeoverRequest -Evidence $runningEvidence }
    Assert-True (-not $runningEvidenceError.Succeeded -and $runningEvidenceError.Error -match 'still active|terminal') 'A running old coordinator must block reservation takeover.'
    $mismatchedPidEvidence = $takeoverEvidence | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $mismatchedPidEvidence.stop_receipt.coordinator_pid = 54321
    $mismatchedPidError = Invoke-Captured { Assert-CirBatchReservationSupersessionEvidence -Request $takeoverRequest -Evidence $mismatchedPidEvidence }
    Assert-True (-not $mismatchedPidError.Succeeded -and $mismatchedPidError.Error -match 'zero-completion|terminal|coordinator') 'The stopped process identity must match the process identity recorded at launch.'
    $scienceEvidence = $takeoverEvidence | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $scienceEvidence.worker_launch_record_count = 1
    $scienceError = Invoke-Captured { Assert-CirBatchReservationSupersessionEvidence -Request $takeoverRequest -Evidence $scienceEvidence }
    Assert-True (-not $scienceError.Succeeded -and $scienceError.Error -match 'science|worker') 'Any old worker launch/scientific attempt must block reservation takeover.'
    $scheduledWorkerEvidence = $takeoverEvidence | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $scheduledWorkerEvidence.worker_scheduled_task_count = 1
    $scheduledWorkerError = Invoke-Captured { Assert-CirBatchReservationSupersessionEvidence -Request $takeoverRequest -Evidence $scheduledWorkerEvidence }
    Assert-True (-not $scheduledWorkerError.Succeeded -and $scheduledWorkerError.Error -match 'science|worker') 'Any old worker task still registered with the request pin must block reservation takeover.'
    $namespaceEvidence = $takeoverEvidence | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $namespaceEvidence.run_namespace_exists = $true
    $namespaceError = Invoke-Captured { Assert-CirBatchReservationSupersessionEvidence -Request $takeoverRequest -Evidence $namespaceEvidence }
    Assert-True (-not $namespaceError.Succeeded -and $namespaceError.Error -match 'science|namespace') 'An old run namespace must block reservation takeover even if the stop receipt reports zero completions.'
    $matlabEvidence = $takeoverEvidence | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $matlabEvidence.matlab_process_count = 1
    $matlabError = Invoke-Captured { Assert-CirBatchReservationSupersessionEvidence -Request $takeoverRequest -Evidence $matlabEvidence }
    Assert-True (-not $matlabError.Succeeded -and $matlabError.Error -match 'MATLAB|active') 'A live MATLAB process must block reservation takeover.'

    $priorRunsFixtureRoot = Join-Path $oldReleaseFixture 'runs'
    New-Item -ItemType Directory -Path $priorRunsFixtureRoot -Force | Out-Null
    $noPriorRunNamespaces = @(Get-CirBatchExistingRunNamespaces -PriorRequest $takeoverEvidence.prior_request -PriorReleaseRoot $oldReleaseFixture)
    Assert-True ($noPriorRunNamespaces.Count -eq 0) 'A zero-science release must have no run namespace for any task in its immutable request.'
    $unexpectedPriorRun = Join-Path $priorRunsFixtureRoot 'run_fixture_second'
    New-Item -ItemType Directory -Path $unexpectedPriorRun -Force | Out-Null
    $priorRunNamespaces = @(Get-CirBatchExistingRunNamespaces -PriorRequest $takeoverEvidence.prior_request -PriorReleaseRoot $oldReleaseFixture)
    Assert-True ($priorRunNamespaces.Count -eq 1 -and $priorRunNamespaces[0] -eq $unexpectedPriorRun) 'Any previous task output namespace, not only the first failed task, must block takeover.'

    $reservationRootFixture = Join-Path $batchFixtureRoot 'cir_batch_reservations'
    New-Item -ItemType Directory -Path $reservationRootFixture -Force | Out-Null
    $script:BatchLogRoot = Join-Path $batchFixtureRoot 'batch_log_root'
    New-Item -ItemType Directory -Path $script:BatchLogRoot -Force | Out-Null
    $script:ProjectRoot = $batchFixtureRoot
    $cohortReservationRoot = Join-Path $script:BatchLogRoot 'cir_batch_reservations'
    New-Item -ItemType Directory -Path $cohortReservationRoot -Force | Out-Null
    $priorReservationPathFixture = Join-Path $cohortReservationRoot "$cohortFixtureSha.json"
    [IO.File]::WriteAllText($priorReservationPathFixture, '{"schema_version":1,"cohort_sha256":"' + $cohortFixtureSha + '","release_root":"' + $oldReleaseFixture.Replace('\','\\') + '","request_sha256":"' + $oldRequestFixtureSha + '"}', [Text.UTF8Encoding]::new($false))
    $priorReservationHashBefore = (Get-FileHash -LiteralPath $priorReservationPathFixture -Algorithm SHA256).Hash.ToLowerInvariant()
    $takeoverEvidence.reservation_sha256 = $priorReservationHashBefore
    $takeoverRequest.batch_reservation_supersession.prior_reservation_path = Get-RelativeProjectPath $priorReservationPathFixture
    $takeoverRequest.batch_reservation_supersession.prior_reservation_sha256 = $priorReservationHashBefore
    $takeoverRequestSha = '4' * 64
    $script:takeoverEvidence = $takeoverEvidence
    function Get-CirBatchReservationSupersessionEvidence { param($Request) return $script:takeoverEvidence }
    $batchReservationAst = @($testAst.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'New-CirBatchLaunchReservation' }, $true))
    Assert-True ($batchReservationAst.Count -eq 1) 'The batch coordinator must use one testable atomic cohort reservation helper.'
    . ([scriptblock]::Create($batchReservationAst[0].Extent.Text))
    $newReservationPath = New-CirBatchLaunchReservation -Request $takeoverRequest -RequestSha256 $takeoverRequestSha
    Assert-True ((Test-Path -LiteralPath $newReservationPath -PathType Leaf) -and
        ([IO.Path]::GetFullPath($newReservationPath) -ne [IO.Path]::GetFullPath($priorReservationPathFixture))) 'An authorized takeover must create independent reservation evidence without replacing the prior file.'
    $newReservation = Get-Content -LiteralPath $newReservationPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-True ($newReservation.request_sha256 -eq $takeoverRequestSha -and
        $newReservation.supersedes_reservation_path -eq $takeoverRequest.batch_reservation_supersession.prior_reservation_path -and
        $newReservation.supersedes_reservation_sha256 -eq $priorReservationHashBefore) 'The new reservation must pin and point to the exact preserved prior reservation.'
    $priorReservationHashAfter = (Get-FileHash -LiteralPath $priorReservationPathFixture -Algorithm SHA256).Hash.ToLowerInvariant()
    Assert-True ($priorReservationHashAfter -eq $priorReservationHashBefore) 'Reservation takeover must leave the historical reservation bytes unchanged.'
    $sameReleaseReservationError = Invoke-Captured { New-CirBatchLaunchReservation -Request $takeoverRequest -RequestSha256 $takeoverRequestSha }
    Assert-True (-not $sameReleaseReservationError.Succeeded -and $sameReleaseReservationError.Error -match 'already|successor|reserved') 'The same immutable release may not reserve twice.'
    $competingReleaseRequest = $takeoverRequest | ConvertTo-Json -Depth 12 | ConvertFrom-Json
    $competingReleaseRequestSha = '5' * 64
    $competingReleaseError = Invoke-Captured { New-CirBatchLaunchReservation -Request $competingReleaseRequest -RequestSha256 $competingReleaseRequestSha }
    Assert-True (-not $competingReleaseError.Succeeded -and $competingReleaseError.Error -match 'already|successor|reserved') 'Two distinct releases attempting to supersede the same failed batch must not both reserve successfully.'

    $coordinatorLock = Acquire-CirBatchCoordinatorLock -CohortSha256 $cohortFixtureSha -RequestSha256 $takeoverRequestSha -TaskName 'GNSS-CIR-BatchFixture-New'
    $secondCoordinatorLock = Invoke-Captured { Acquire-CirBatchCoordinatorLock -CohortSha256 $cohortFixtureSha -RequestSha256 $competingReleaseRequestSha -TaskName 'GNSS-CIR-BatchFixture-Competing' }
    Assert-True (-not $secondCoordinatorLock.Succeeded -and $secondCoordinatorLock.Error -match 'active|owned|lock') 'A second coordinator for the same cohort must not acquire the live OS lock.'
    Release-CirBatchCoordinatorLock -Lock $coordinatorLock
    $afterReleaseLock = Acquire-CirBatchCoordinatorLock -CohortSha256 $cohortFixtureSha -RequestSha256 $competingReleaseRequestSha -TaskName 'GNSS-CIR-BatchFixture-AfterRelease'
    Assert-True ($afterReleaseLock -and (Test-Path -LiteralPath $afterReleaseLock.path -PathType Leaf)) 'Disposing a completed coordinator must release the OS lock without deleting its file.'
    Release-CirBatchCoordinatorLock -Lock $afterReleaseLock
    $script:ProjectRoot = $originalProjectRoot
    $script:BatchLogRoot = Join-Path $originalProjectRoot 'dataset_generation_logs\batch_sage_execution'

    $wrongSkipIds = @([string]$expectedSkipIds[0], [string]$batchRequest.tasks[0].run_id, [string]$expectedSkipIds[2])
    $wrongSkipRequest = [pscustomobject]@{
        frozen_cohort_run_ids = @($batchRequest.frozen_cohort_run_ids)
        excluded_run_ids = @($batchRequest.excluded_run_ids)
        skipped_existing_pass = @(
            [pscustomobject]@{ run_id = [string]$expectedSkipIds[0]; receipt_type = 'EXISTING_BASELINE_READBACK' },
            [pscustomobject]@{ run_id = [string]$batchRequest.tasks[0].run_id; receipt_type = 'CIR_PILOT' },
            [pscustomobject]@{ run_id = [string]$expectedSkipIds[2]; receipt_type = 'CIR_PILOT' }
        )
        tasks = @($frozenTasks | Where-Object { $_.task_status -eq 'NEW_REQUIRED' -and $_.run_id -notin $wrongSkipIds } |
            ForEach-Object { [pscustomobject]@{ run_id = [string]$_.run_id; task_status = 'NEW_REQUIRED' } })
    }
    $cohortPath = Join-Path $originalProjectRoot 'dataset_generation_logs\channel_modeling\mainline_1023_cohort_v1_20261022T082520Z\cohort.json'
    $cirTasksForSkipTest = Get-Content -LiteralPath $frozenTaskPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $cohortForSkipTest = Get-Content -LiteralPath $cohortPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $wrongPilotSkip = Invoke-Captured {
        Assert-BatchRequestIdentities $wrongSkipRequest $cohortForSkipTest $cirTasksForSkipTest
    }
    Assert-True (-not $wrongPilotSkip.Succeeded -and $wrongPilotSkip.Error -match 'exactly the three approved') "Batch identity validation must reject skipping a different valid NEW_REQUIRED run instead of the exact approved G18/G23 pilots. Actual error: $($wrongPilotSkip.Error)"

    $batchRunRoot = Join-Path (Join-Path $batchFixtureRoot 'runs') ([string]$batchRequest.tasks[0].run_id)
    $preservedFile = Join-Path $batchRunRoot 'attempt_01\preserved_fixture.txt'
    New-Item -ItemType Directory -Path (Split-Path -Parent $preservedFile) -Force | Out-Null
    [System.IO.File]::WriteAllText($preservedFile, 'preserve-existing-test-fixture')
    $existingOutput = Invoke-Captured {
        Assert-NewCIROutputNamespace -Request $batchRequest -TaskPin $batchRequest.tasks[0]
    }
    Assert-True (-not $existingOutput.Succeeded -and $existingOutput.Error -match 'already exists|overwrite') 'An existing batch run namespace must fail closed without overwrite.'
    Assert-True ((Get-Content -LiteralPath $preservedFile -Raw) -ceq 'preserve-existing-test-fixture') 'A rejected existing namespace must remain byte-for-byte untouched.'

    $seenSerialIds = [System.Collections.Generic.List[string]]::new()
    $serialPins = @(
        [pscustomobject]@{ run_id = 'run_fixture_first' },
        [pscustomobject]@{ run_id = 'run_fixture_second' },
        [pscustomobject]@{ run_id = 'run_fixture_third' }
    )
    $serialResult = Invoke-SerialCirBatchTasks -TaskPins $serialPins -DispatchAndVerify {
        param($pin)
        $seenSerialIds.Add([string]$pin.run_id)
        [pscustomobject]@{ status = 'PASS'; run_id = [string]$pin.run_id }
    }
    Assert-True (($seenSerialIds -join ',') -ceq 'run_fixture_first,run_fixture_second,run_fixture_third' -and $serialResult.Count -eq 3) 'The batch coordinator helper must preserve strict frozen order after each callback returns PASS.'
    $seenSerialIds.Clear()
    $failStop = Invoke-Captured {
        Invoke-SerialCirBatchTasks -TaskPins $serialPins -DispatchAndVerify {
            param($pin)
            $seenSerialIds.Add([string]$pin.run_id)
            [pscustomobject]@{ status = 'FAILED_NO_RETRY'; run_id = [string]$pin.run_id }
        }
    }
    Assert-True (-not $failStop.Succeeded -and $seenSerialIds.Count -eq 1 -and
        $seenSerialIds[0] -eq 'run_fixture_first') 'A failed task must stop the coordinator before the next task is dispatched.'

    $taskPin = $batchRequest.tasks[0]
    $attemptRoot = Join-Path $batchRunRoot 'attempt_01'
    New-Item -ItemType Directory -Path $attemptRoot -Force | Out-Null
    $stem = "$($taskPin.prn)_ch$($taskPin.tracking_channel)_code_domain_cir"
    $outputPaths = @(
        (Join-Path $attemptRoot "$stem.h5"),
        (Join-Path $attemptRoot "${stem}_metadata.json"),
        (Join-Path $attemptRoot "$($taskPin.prn)_ch$($taskPin.tracking_channel)_primary_delay_comparison.csv")
    )
    foreach ($outputPath in $outputPaths) { [System.IO.File]::WriteAllText($outputPath, 'metadata-only-test-fixture') }
    $outputRecords = @($outputPaths | ForEach-Object {
        [pscustomobject]@{
            path = (Get-RelativeProjectPath $_)
            size_bytes = [long](Get-Item -LiteralPath $_).Length
            sha256 = 'a' * 64
        }
    })
    $expectedSnapshotCount = [long]$taskPin.stage0_window_count * 40
    $matlabStarted = [DateTimeOffset]::UtcNow.AddMinutes(-1)
    $matlabEnded = $matlabStarted.AddSeconds(1)
    $matlabExitReceiptPath = Join-Path $batchRunRoot 'matlab_exit_receipt.json'
    $matlabExitReceipt = [pscustomobject]@{
        exit_code = 0; pid = 43210; started_utc = $matlabStarted.ToString('o')
        ended_utc = $matlabEnded.ToString('o'); elapsed_seconds = 1.0
        peak_working_set_bytes_observed = 1048576
    }
    [System.IO.File]::WriteAllText($matlabExitReceiptPath,
        ($matlabExitReceipt | ConvertTo-Json -Depth 5) + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false))
    $workerReceipt = [pscustomobject]@{
        status = 'PASS'; run_id = [string]$taskPin.run_id; request_sha256 = $batchHash
        attempt = 1; resume = $false; exit_code = 0; scientific_algorithm_modified = $false
        matlab_pid = 43210; started_utc = $matlabStarted.ToString('o'); elapsed_seconds = 1.0
        peak_working_set_bytes_observed = 1048576
        matlab_exit_receipt_path = (Get-RelativeProjectPath $matlabExitReceiptPath)
        matlab_exit_receipt_sha256 = (Get-FileHash -LiteralPath $matlabExitReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        identity = $taskPin
        hdf5_validation = [pscustomobject]@{
            hdf5_path = $outputPaths[0]; snapshot_count = $expectedSnapshotCount; delay_count = 451
            time_monotonic_nondecreasing = $true; raw_iq_rms_all_positive = $true; cir_all_finite = $true
            pdp_window_count = [long]$taskPin.stage0_window_count; snapshots_per_pdp_window = 40
            pdp_mean_exactly_recomputed = $true; max_pdp_recomputation_difference = 0
        }
        metadata_summary = [pscustomobject]@{
            stage0_window_count = [long]$taskPin.stage0_window_count; cir_snapshot_count = $expectedSnapshotCount
            delay_grid_count = 451; amplitude_reference_status = 'UNKNOWN_RECEIVER_GAIN_OR_AGC'
        }
        export_summary = [pscustomobject]@{
            stage0_window_count = [long]$taskPin.stage0_window_count; cir_snapshot_count = $expectedSnapshotCount
            delay_grid_count = 451
        }
        outputs = $outputRecords
    }
    $matchingMatlabExit = Invoke-Captured { Assert-MatlabExitReceiptMatches $workerReceipt $matlabExitReceipt }
    Assert-True $matchingMatlabExit.Succeeded "The CIR receipt must bind the actual MATLAB exit record: $($matchingMatlabExit.Error)"
    $wrongMatlabExit = $matlabExitReceipt | ConvertTo-Json -Depth 5 | ConvertFrom-Json
    $wrongMatlabExit.pid++
    $matlabMismatch = Invoke-Captured { Assert-MatlabExitReceiptMatches $workerReceipt $wrongMatlabExit }
    Assert-True (-not $matlabMismatch.Succeeded -and $matlabMismatch.Error -match 'MATLAB exit receipt') 'A CIR PASS receipt must not disagree with MATLAB PID/exit evidence.'
    $workerReceiptCheck = Invoke-Captured {
        Assert-WorkerTaskReceiptPass ([pscustomobject]@{ LastTaskResult = 0 }) $workerReceipt `
            ([string]$taskPin.run_id) $batchHash $taskPin $batchFixtureRoot
    }
    Assert-True $workerReceiptCheck.Succeeded "A matching zero-exit Windows task and complete CIR/PDP receipt should pass: $($workerReceiptCheck.Error)"
    $badWindowsExit = Invoke-Captured {
        Assert-WorkerTaskReceiptPass ([pscustomobject]@{ LastTaskResult = 1 }) $workerReceipt `
            ([string]$taskPin.run_id) $batchHash $taskPin $batchFixtureRoot
    }
    Assert-True (-not $badWindowsExit.Succeeded -and $badWindowsExit.Error -match 'LastTaskResult') 'A PASS receipt cannot override a failing Windows scheduled-task result.'
    $badQaReceipt = $workerReceipt | ConvertTo-Json -Depth 20 | ConvertFrom-Json
    $badQaReceipt.hdf5_validation.max_pdp_recomputation_difference = 0.0001
    $badQa = Invoke-Captured {
        Assert-WorkerTaskReceiptPass ([pscustomobject]@{ LastTaskResult = 0 }) $badQaReceipt `
            ([string]$taskPin.run_id) $batchHash $taskPin $batchFixtureRoot
    }
    Assert-True (-not $badQa.Succeeded -and $badQa.Error -match 'QA') 'A Windows exit 0 cannot pass a receipt with contradictory HDF5/PDP QA.'

    Assert-True (Assert-NoNewStorageFailures -Events @() -Context 'synthetic baseline Warning test') 'An unchanged accepted storage warning with no new events must not be treated as a new I/O failure.'
    $syntheticIoEvent = [pscustomobject]@{
        TimeCreated = [DateTimeOffset]::UtcNow; Id = 157; ProviderName = 'Disk'; RecordId = 999999
    }
    $newIo = Invoke-Captured { Assert-NoNewStorageFailures -Events @($syntheticIoEvent) -Context 'synthetic new I/O test' }
    Assert-True (-not $newIo.Succeeded -and $newIo.Error -match 'New matching System') 'A new matching storage I/O event must fail closed despite the accepted historical Warning baseline.'

    $missingSourcePinRequest = $request | ConvertTo-Json -Depth 16 | ConvertFrom-Json
    $missingSourcePinRequest.source_sha256.PSObject.Properties.Remove('scripts/channel_modeling/validate_gnss_code_domain_cir.m')
    [System.IO.File]::WriteAllText($temporaryRequest,
        ($missingSourcePinRequest | ConvertTo-Json -Depth 16) + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false))
    $missingSourcePinHash = (Get-FileHash -LiteralPath $temporaryRequest -Algorithm SHA256).Hash.ToLowerInvariant()
    $missingSourcePin = Invoke-Captured {
        & $scriptPath -ValidateOnly -RequestManifest $temporaryRequest `
            -ExpectedRequestSha256 $missingSourcePinHash -RunId $pilotRunIds[0]
    }
    Assert-True (-not $missingSourcePin.Succeeded) 'ValidateOnly must reject a request that omits one required source SHA pin even when its request hash is recomputed.'
    Assert-True ($missingSourcePin.Error -match 'source.*pin|pin.*set') 'An incomplete source-pin set must report the provenance-contract failure.'

    $arraySourcePinRequest = $request | ConvertTo-Json -Depth 16 | ConvertFrom-Json
    $sourcePinKey = 'scripts/channel_modeling/validate_gnss_code_domain_cir.m'
    $arraySourcePinRequest.source_sha256.$sourcePinKey = @([string]$arraySourcePinRequest.source_sha256.$sourcePinKey)
    [System.IO.File]::WriteAllText($temporaryRequest,
        ($arraySourcePinRequest | ConvertTo-Json -Depth 16) + [Environment]::NewLine,
        [System.Text.UTF8Encoding]::new($false))
    $arraySourcePinHash = (Get-FileHash -LiteralPath $temporaryRequest -Algorithm SHA256).Hash.ToLowerInvariant()
    $arraySourcePin = Invoke-Captured {
        & $scriptPath -ValidateOnly -RequestManifest $temporaryRequest `
            -ExpectedRequestSha256 $arraySourcePinHash -RunId $pilotRunIds[0]
    }
    Assert-True (-not $arraySourcePin.Succeeded) 'ValidateOnly must reject a one-element array where a scalar source SHA is required.'
    Assert-True ($arraySourcePin.Error -match 'source.*pin|SHA') 'A malformed source-pin value must report its provenance failure.'

    foreach ($policyMutation in @(
        [pscustomobject]@{ Name = 'execution_policy'; Value = 'AUTOMATIC_RETRY_ALLOWED'; ErrorPattern = 'execution policy' },
        [pscustomobject]@{ Name = 'execution_policy'; Value = @('MANUAL_ONLY_SERIAL_ONE_TASK_PER_INVOCATION_NO_RETRY'); ErrorPattern = 'execution policy' },
        [pscustomobject]@{ Name = 'resume'; Value = $true; ErrorPattern = 'resume' },
        [pscustomobject]@{ Name = 'max_parallel_matlab'; Value = 2; ErrorPattern = 'parallel' },
        [pscustomobject]@{ Name = 'max_parallel_matlab'; Value = $true; ErrorPattern = 'parallel' }
    )) {
        $mutatedPolicyRequest = $request | ConvertTo-Json -Depth 16 | ConvertFrom-Json
        $mutatedPolicyRequest.($policyMutation.Name) = $policyMutation.Value
        [System.IO.File]::WriteAllText($temporaryRequest,
            ($mutatedPolicyRequest | ConvertTo-Json -Depth 16) + [Environment]::NewLine,
            [System.Text.UTF8Encoding]::new($false))
        $mutatedPolicyHash = (Get-FileHash -LiteralPath $temporaryRequest -Algorithm SHA256).Hash.ToLowerInvariant()
        $mutatedPolicy = Invoke-Captured {
            & $scriptPath -ValidateOnly -RequestManifest $temporaryRequest `
                -ExpectedRequestSha256 $mutatedPolicyHash -RunId $pilotRunIds[0]
        }
        Assert-True (-not $mutatedPolicy.Succeeded) "ValidateOnly must reject altered immutable release policy '$($policyMutation.Name)'."
        Assert-True ($mutatedPolicy.Error -match $policyMutation.ErrorPattern) "The '$($policyMutation.Name)' policy rejection must identify the violated contract."
    }

    $request.tasks[0].raw_iq_size_bytes = [long]$request.tasks[0].raw_iq_size_bytes + 4
    $tamperedJson = $request | ConvertTo-Json -Depth 16
    [System.IO.File]::WriteAllText($temporaryRequest, $tamperedJson, [System.Text.UTF8Encoding]::new($false))
    $tamperedHash = (Get-FileHash -LiteralPath $temporaryRequest -Algorithm SHA256).Hash.ToLowerInvariant()
    $tampered = Invoke-Captured {
        & $scriptPath -ValidateOnly -RequestManifest $temporaryRequest `
            -ExpectedRequestSha256 $tamperedHash -RunId $pilotRunIds[0]
    }
    Assert-True (-not $tampered.Succeeded) 'ValidateOnly must reject a raw-size pin that differs from Gate A and scene metadata.'
    Assert-True ($tampered.Error -match 'raw.*size|size.*raw|Gate A') 'The raw-size rejection must identify the provenance check.'

    $wrongHash = Invoke-Captured {
        & $scriptPath -ValidateOnly -RequestManifest $requestPath `
            -ExpectedRequestSha256 ('0' * 64) -RunId $pilotRunIds[0]
    }
    Assert-True (-not $wrongHash.Succeeded) 'ValidateOnly must reject a mismatched immutable request hash.'

    $unconfirmed = Invoke-Captured {
        & $scriptPath -Execute -RequestManifest $requestPath `
            -ExpectedRequestSha256 $requestHash -RunId $pilotRunIds[0]
    }
    Assert-True (-not $unconfirmed.Succeeded) 'Execute must require the separate ConfirmPilot acknowledgement.'
    Assert-True (-not (Test-Path -LiteralPath $firstRunRoot)) 'An unconfirmed Execute must not create an attempt or output.'

    $beforeBaselineReadback = Invoke-Captured {
        & $scriptPath -Execute -ConfirmPilot -RequestManifest $requestPath `
            -ExpectedRequestSha256 $requestHash -RunId $pilotRunIds[0]
    }
    Assert-True (-not $beforeBaselineReadback.Succeeded) 'A new pilot must not launch before the existing G28/ch1 read-back PASS receipt.'
    Assert-True ($beforeBaselineReadback.Error -match 'G28/ch1 baseline read-back') 'Pre-sequence refusal must name the unmet baseline evidence.'
    Assert-True (-not (Test-Path -LiteralPath $firstRunRoot)) 'A pilot blocked by missing baseline evidence must create no run output.'

    $prematureFinalize = Invoke-Captured {
        & $scriptPath -FinalizePilotAudit -RequestManifest $requestPath `
            -ExpectedRequestSha256 $requestHash
    }
    Assert-True (-not $prematureFinalize.Succeeded) 'Final audit must reject a release without baseline and both pilot receipts.'
    Assert-True ($prematureFinalize.Error -match 'G28/ch1 read-back') 'Premature finalization must identify the missing prerequisite.'
    Assert-True (-not (Test-Path -LiteralPath (Join-Path $fixtureRoot 'forecast_80_remaining.json'))) 'Premature finalization must not emit a false capacity forecast.'

    $tokens = $null
    $parseErrors = $null
    $runnerAst = [System.Management.Automation.Language.Parser]::ParseInput(
        $runnerText, [ref]$tokens, [ref]$parseErrors)
    Assert-True ($parseErrors.Count -eq 0) 'Runner source must parse before audit helper extraction.'
    $auditHelperAsts = @($runnerAst.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
            $node.Name -eq 'Set-PilotAuditFinalAcceptance'
    }, $true))
    Assert-True ($auditHelperAsts.Count -eq 1) 'Final audit update must use one testable helper for absent optional PSCustomObject properties.'
    . ([scriptblock]::Create($auditHelperAsts[0].Extent.Text))
    $auditShape = [pscustomobject]@{
        schema_version = 1
        release_request_sha256 = 'a' * 64
        pilots = @()
        baseline_readback = [pscustomobject]@{ status = 'PASS' }
    }
    $finalAcceptance = [ordered]@{
        status = 'PILOTS_PASS_BULK_BATCH_NOT_STARTED'
        remaining_new_required_tasks = 80
    }
    $updatedAudit = Set-PilotAuditFinalAcceptance -Audit $auditShape `
        -FinalAcceptance $finalAcceptance
    Assert-True ($updatedAudit.status -eq 'PILOTS_PASS_BULK_BATCH_NOT_STARTED' -and
        $updatedAudit.final_acceptance.remaining_new_required_tasks -eq 80) 'Final acceptance fields must be added to the existing baseline/pilots-only audit schema.'
    Assert-True ($updatedAudit.schema_version -eq 1 -and
        $updatedAudit.release_request_sha256 -eq ('a' * 64) -and
        $updatedAudit.baseline_readback.status -eq 'PASS') 'Adding final acceptance must preserve preexisting audit fields.'

    $reservationAsts = @($runnerAst.FindAll({
        param($node)
        $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and
            $node.Name -eq 'New-CirLaunchReservation'
    }, $true))
    Assert-True ($reservationAsts.Count -eq 1) 'Each exact run_id must have one atomic durable launch reservation helper.'
    . ([scriptblock]::Create($reservationAsts[0].Extent.Text))
    $sharedReservationRoot = Join-Path $fixtureRoot 'global_launch_reservations'
    $reservationPath = New-CirLaunchReservation -ReleaseRoot $fixtureRoot `
        -ReservationRoot $sharedReservationRoot -RunId $pilotRunIds[0] -RequestSha256 $requestHash
    Assert-True (Test-Path -LiteralPath $reservationPath -PathType Leaf) 'The first launch reservation must create a durable one-shot marker.'
    $reservation = Get-Content -LiteralPath $reservationPath -Raw -Encoding UTF8 | ConvertFrom-Json
    Assert-True ($reservation.run_id -eq $pilotRunIds[0] -and
        $reservation.request_sha256 -eq $requestHash -and
        $reservation.release_root -eq [IO.Path]::GetFullPath($fixtureRoot)) 'A global launch reservation must bind exact run identity, request hash, and originating release.'
    $duplicateReservation = Invoke-Captured {
        New-CirLaunchReservation -ReleaseRoot $fixtureRoot `
            -ReservationRoot $sharedReservationRoot -RunId $pilotRunIds[0] -RequestSha256 $requestHash
    }
    Assert-True (-not $duplicateReservation.Succeeded -and
        $duplicateReservation.Error -match 'reserved|duplicate') 'A duplicate or concurrent same-run launch must fail closed without replacing the reservation.'
    $secondReleaseRoot = Join-Path $fixtureRoot 'second_release_root'
    New-Item -ItemType Directory -Path $secondReleaseRoot -Force | Out-Null
    $crossReleaseReservation = Invoke-Captured {
        New-CirLaunchReservation -ReleaseRoot $secondReleaseRoot `
            -ReservationRoot $sharedReservationRoot -RunId $pilotRunIds[0] -RequestSha256 $requestHash
    }
    Assert-True (-not $crossReleaseReservation.Succeeded -and
        $crossReleaseReservation.Error -match 'reserved|duplicate') 'The same run_id must not be launched concurrently from a second immutable release root.'

    "CIR_SINGLE_RUNNER_TESTS=$passes/$passes`nTASK4_RUNNER_TESTS=PASS"
} catch {
    Write-Error ("{0}`n{1}" -f $_.Exception.Message, $_.ScriptStackTrace)
    if ($failures.Count -eq 0) {
        Write-Output 'CIR_SINGLE_RUNNER_TESTS=0/1'
    } else {
        Write-Output "CIR_SINGLE_RUNNER_TESTS=$($passes)/$($passes + $failures.Count)"
    }
    exit 1
} finally {
    if (Test-Path -LiteralPath $temporaryRequest) {
        Remove-Item -LiteralPath $temporaryRequest -Force
    }
    foreach ($fixture in @($fixtureRoot,$batchFixtureRoot)) {
      if (Test-Path -LiteralPath $fixture) {
        $expectedParent = [System.IO.Path]::GetFullPath($releaseBase).TrimEnd('\') + '\'
        $resolvedFixture = [System.IO.Path]::GetFullPath($fixture)
        if ($resolvedFixture.StartsWith($expectedParent, [System.StringComparison]::OrdinalIgnoreCase) -and
            (Split-Path -Leaf $resolvedFixture) -match '^mainline_1023_cir_v1_[A-Za-z0-9_]+$') {
            Remove-Item -LiteralPath $resolvedFixture -Recurse -Force
        } else {
            throw "Refusing to clean unexpected test fixture path: $resolvedFixture"
        }
      }
    }
}
