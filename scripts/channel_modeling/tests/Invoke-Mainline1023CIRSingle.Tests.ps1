[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$projectRoot = 'E:\GNSS_Multipath_Project'
$scriptPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) '..\Invoke-Mainline1023CIRSingle.ps1'
$scriptPath = [System.IO.Path]::GetFullPath($scriptPath)
$runnerText = Get-Content -LiteralPath $scriptPath -Raw -Encoding UTF8
$releaseBase = Join-Path $projectRoot 'dataset_generation_logs\channel_modeling'
$stamp = [DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$fixtureRoot = Join-Path $releaseBase ("mainline_1023_cir_v1_${stamp}_TEST_" + [Guid]::NewGuid().ToString('N'))
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
    $settingsLine = @($runnerText -split "`r?`n" | Where-Object { $_ -match 'New-ScheduledTaskSettingsSet' })
    Assert-True ($settingsLine.Count -eq 1 -and
        $settingsLine[0] -match '\s-DontStopIfGoingOnBatteries(?:\s|$)' -and
        $settingsLine[0] -notmatch '\s-AllowStartIfOnBatteries(?:\s|$)') 'A worker must require AC when it starts but must not be killed if AC briefly drops after launch.'
    $powerSettings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
        -ExecutionTimeLimit (New-TimeSpan -Hours 12) -StartWhenAvailable:$false `
        -DontStopIfGoingOnBatteries
    Assert-True ($powerSettings.DisallowStartIfOnBatteries -and
        -not $powerSettings.StopIfGoingOnBatteries) 'PowerShell task settings must deny battery start while allowing a running worker to continue through a brief battery switch.'

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
    Write-Error $_.Exception.Message
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
    if (Test-Path -LiteralPath $fixtureRoot) {
        $expectedParent = [System.IO.Path]::GetFullPath($releaseBase).TrimEnd('\') + '\'
        $resolvedFixture = [System.IO.Path]::GetFullPath($fixtureRoot)
        if ($resolvedFixture.StartsWith($expectedParent, [System.StringComparison]::OrdinalIgnoreCase) -and
            (Split-Path -Leaf $resolvedFixture) -match '^mainline_1023_cir_v1_[A-Za-z0-9_]+$') {
            Remove-Item -LiteralPath $resolvedFixture -Recurse -Force
        } else {
            throw "Refusing to clean unexpected test fixture path: $resolvedFixture"
        }
    }
}
