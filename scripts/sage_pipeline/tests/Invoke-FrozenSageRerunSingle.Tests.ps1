$wrapperPath = Join-Path $PSScriptRoot '..\Invoke-FrozenSageRerunSingle.ps1'
if (Test-Path -LiteralPath $wrapperPath -PathType Leaf) {
    . $wrapperPath
}

function Invoke-ProductionFunctionSafely {
    param(
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][hashtable]$Arguments
    )

    $command = Get-Command -Name $Name -ErrorAction SilentlyContinue
    if ($null -eq $command) {
        return [pscustomobject]@{ Available = $false; Value = $null; Error = 'PRODUCTION_FUNCTION_MISSING' }
    }
    try {
        return [pscustomobject]@{ Available = $true; Value = (& $Name @Arguments); Error = $null }
    } catch {
        return [pscustomobject]@{ Available = $true; Value = $null; Error = $_.Exception.Message }
    }
}

function New-FrozenSageTestManifestRow {
    param(
        [string]$SceneId = 'F1023_V70_D0117_P2',
        [string]$PrnLabel = 'G28',
        [string]$TrackingChannel = '1',
        [string]$MappingWarning = 'NONE',
        [string]$RunId = 'run_20261003_F1023_V70_D0117_P2_G28_ch1',
        [string]$OutputNamespace
    )

    if ([string]::IsNullOrWhiteSpace($OutputNamespace)) {
        $OutputNamespace = "scenes\$SceneId\sage_results\rerun_20261003_frozen_v3\${PrnLabel}_ch${TrackingChannel}"
    }
    [pscustomobject]@{
        run_id = $RunId
        scene_id = $SceneId
        prn = $PrnLabel
        tracking_channel = $TrackingChannel
        mapping_warning = $MappingWarning
        frozen_sage_sha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
        output_namespace = $OutputNamespace
        resume = 'false'
        execution_status = 'NOT_STARTED'
    }
}

Describe 'Invoke-FrozenSageRerunSingle safety contract' {
    It 'accepts only the frozen source hash' {
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageHash' -Arguments @{
            ActualHash = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
            ExpectedHash = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value | Should Be $true
    }

    It 'rejects a changed source hash' {
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageHash' -Arguments @{
            ActualHash = '0000000000000000000000000000000000000000000000000000000000000000'
            ExpectedHash = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
        }
        $result.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($result.Error) | Should Be $false
    }

    It 'accepts the exact manifest row and rejects a different channel' {
        $row = New-FrozenSageTestManifestRow
        $accepted = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageManifestRow' -Arguments @{
            Row = $row
            ExpectedRunId = $row.run_id
        }
        $accepted.Available | Should Be $true
        $accepted.Error | Should Be $null
        $accepted.Value | Should Be $true

        $row.tracking_channel = '2'
        $rejected = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageManifestRow' -Arguments @{
            Row = $row
            ExpectedRunId = $row.run_id
        }
        $rejected.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($rejected.Error) | Should Be $false
    }

    It 'preserves a manifest tracking channel zero when frozen MATLAB accepts it' {
        $row = New-FrozenSageTestManifestRow `
            -SceneId 'F1023_V120_D0121_P2' `
            -PrnLabel 'G11' `
            -TrackingChannel '0' `
            -RunId 'run_20261003_F1023_V120_D0121_P2_G11_ch0'
        $accepted = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageManifestRow' -Arguments @{
            Row = $row
            ExpectedRunId = $row.run_id
        }
        $accepted.Available | Should Be $true
        $accepted.Error | Should Be $null
        $accepted.Value | Should Be $true
        $row.output_namespace | Should Be 'scenes\F1023_V120_D0121_P2\sage_results\rerun_20261003_frozen_v3\G11_ch0'

        $expression = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageMatlabExpression' -Arguments @{
            SceneId = $row.scene_id
            Prn = 11
            TrackingChannel = 0
            ProjectRoot = 'E:\GNSS_Multipath_Project'
        }
        $expression.Error | Should Be $null
        $expression.Value | Should Be "run_nav_sage_pipeline('F1023_V120_D0121_P2',11,'TrackingChannel',0,'ProjectRoot','E:/GNSS_Multipath_Project','Resume',false)"
    }

    It 'accepts the approved missing tracking-start warning without changing the channel namespace' {
        $warningRow = New-FrozenSageTestManifestRow `
            -SceneId 'F1023_V120_D0121_P2' `
            -PrnLabel 'G06' `
            -TrackingChannel '6' `
            -MappingWarning 'NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING' `
            -RunId 'run_20261003_F1023_V120_D0121_P2_G06_ch6'
        $accepted = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageManifestRow' -Arguments @{
            Row = $warningRow
            ExpectedRunId = $warningRow.run_id
        }

        $accepted.Available | Should Be $true
        $accepted.Error | Should Be $null
        $accepted.Value | Should Be $true
        $warningRow.mapping_warning | Should Be 'NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING'
        $warningRow.output_namespace | Should Be 'scenes\F1023_V120_D0121_P2\sage_results\rerun_20261003_frozen_v3\G06_ch6'
    }

    It 'rejects an unsupported warning and a namespace that omits the channel' {
        $row = New-FrozenSageTestManifestRow -MappingWarning 'UNEXPECTED_WARNING'
        $warningRejected = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageManifestRow' -Arguments @{
            Row = $row
            ExpectedRunId = $row.run_id
        }
        $warningRejected.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($warningRejected.Error) | Should Be $false

        $badNamespace = New-FrozenSageTestManifestRow -OutputNamespace 'scenes\F1023_V70_D0117_P2\sage_results\rerun_20261003_frozen_v3\G28'
        $namespaceRejected = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageManifestRow' -Arguments @{
            Row = $badNamespace
            ExpectedRunId = $badNamespace.run_id
        }
        [string]::IsNullOrWhiteSpace($namespaceRejected.Error) | Should Be $false
    }

    It 'rejects any missing required input file' {
        $existingInput = Join-Path $TestDrive 'tracking.mat'
        [System.IO.File]::WriteAllText($existingInput, 'fixture')
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-RequiredInputFiles' -Arguments @{
            Paths = @($existingInput, (Join-Path $TestDrive 'missing.dat'))
        }
        $result.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($result.Error) | Should Be $false
    }

    It 'allocates a distinct active runner lock per manifest run id' {
        $root = Join-Path $TestDrive 'task-locks'
        $first = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageTaskRunnerLockPath' -Arguments @{
            ExecutionLogParent = $root
            RunId = 'run_fixture_scene_G03_ch1'
        }
        $second = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageTaskRunnerLockPath' -Arguments @{
            ExecutionLogParent = $root
            RunId = 'run_fixture_scene_G04_ch2'
        }
        $first.Available | Should Be $true
        $second.Available | Should Be $true
        $first.Error | Should Be $null
        $second.Error | Should Be $null
        $first.Value | Should Not Be $second.Value
        [System.IO.Path]::GetFileName($first.Value) | Should Match '^\.windows_runner_active_[A-Za-z0-9_-]+\.lock$'
    }

    It 'rejects execution outside a non-admin PowerShell 7 user session' {
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-ApprovedExecutionEnvironment' -Arguments @{
            Identity = 'TJ-CHANNEL\codexsandboxoffline'
            PowerShellVersion = '7.6.5'
            IsAdministrator = $false
        }
        $result.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($result.Error) | Should Be $false
    }

    It 'rejects an existing staging or final namespace' {
        $existing = Join-Path $TestDrive 'stage'
        [void](New-Item -ItemType Directory -Path $existing)
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-OutputNamespacesAbsent' -Arguments @{
            StagingPath = $existing
            FinalPath = (Join-Path $TestDrive 'final')
        }
        $result.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($result.Error) | Should Be $false
    }

    It 'requires the complete Stage0 through Stage4 artifact set' {
        $output = Join-Path $TestDrive 'sage-output'
        [void](New-Item -ItemType Directory -Path $output)
        $requiredFiles = @(
            'stage0_nav_catalog.mat', 'stage0_valid_symbols.csv', 'stage0_valid_40ms_windows.csv',
            'stage1_nav_fast_scan.mat', 'stage1_nav_fast_scan.csv',
            'stage2_nav_sage_L1_L4.mat', 'stage2_model_orders.csv',
            'stage2_selected_windows.csv', 'stage2_selected_paths.csv',
            'stage3_nav_persistence.mat', 'stage3_persistence.csv', 'stage3_reliable_centers.csv',
            'stage4_nav_joint_100ms.mat', 'stage4_joint_summary.csv', 'stage4_joint_paths.csv'
        )
        foreach ($name in $requiredFiles) {
            [System.IO.File]::WriteAllText((Join-Path $output $name), 'fixture')
        }
        $complete = Invoke-ProductionFunctionSafely -Name 'Assert-StageOutputsComplete' -Arguments @{ OutputPath = $output }
        $complete.Available | Should Be $true
        $complete.Error | Should Be $null
        $complete.Value | Should Be $true

        $incompleteOutput = Join-Path $TestDrive 'incomplete-sage-output'
        [void](New-Item -ItemType Directory -Path $incompleteOutput)
        foreach ($name in ($requiredFiles | Where-Object { $_ -ne 'stage4_joint_paths.csv' })) {
            [System.IO.File]::WriteAllText((Join-Path $incompleteOutput $name), 'fixture')
        }
        $incomplete = Invoke-ProductionFunctionSafely -Name 'Assert-StageOutputsComplete' -Arguments @{ OutputPath = $incompleteOutput }
        $incomplete.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($incomplete.Error) | Should Be $false
    }

    It 'builds the selected scene, PRN, and channel invocation with Resume=false' {
        $result = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageMatlabExpression' -Arguments @{
            SceneId = 'F1023_V120_D0121_P2'
            Prn = 6
            TrackingChannel = 6
            ProjectRoot = 'E:\GNSS_Multipath_Project'
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value | Should Be "run_nav_sage_pipeline('F1023_V120_D0121_P2',6,'TrackingChannel',6,'ProjectRoot','E:/GNSS_Multipath_Project','Resume',false)"
    }

    It 'passes -batch and the single-quoted MATLAB expression as separate native arguments' {
        $expression = "a='F1023_V70_D0117_P2';b='TrackingChannel';c='E:/GNSS_Multipath_Project';assert(strcmp(a,'F1023_V70_D0117_P2'));assert(strcmp(b,'TrackingChannel'));assert(strcmp(c,'E:/GNSS_Multipath_Project'));disp('MATLAB_ARGUMENT_TRANSPORT_OK')"
        $result = Invoke-ProductionFunctionSafely -Name 'New-FrozenMatlabProcessStartInfo' -Arguments @{
            MatlabPath = 'C:\MATLAB\bin\matlab.exe'
            Expression = $expression
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value.ArgumentList.Count | Should Be 2
        $result.Value.ArgumentList[0] | Should Be '-batch'
        $result.Value.ArgumentList[1] | Should Be $expression
        $result.Value.UseShellExecute | Should Be $false
        $result.Value.RedirectStandardOutput | Should Be $true
        $result.Value.RedirectStandardError | Should Be $true
        $result.Value.CreateNoWindow | Should Be $true
    }

    It 'checks raw IQ size against the audit without computing a raw SHA-256' {
        $rawFixture = Join-Path $TestDrive 'raw-size-fixture.bin'
        $stream = [System.IO.File]::Open($rawFixture, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        $stream.WriteByte(1)
        $stream.Flush()
        try {
            $result = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageRawIqMetadata' -Arguments @{
                Path = $rawFixture
                ExpectedSizeBytes = 1
            }
            $result.Available | Should Be $true
            $result.Error | Should Be $null
            $result.Value.RawIqSizeBytes | Should Be 1
            $result.Value.RawIqSha256 | Should Be ''
            $result.Value.RawIqSha256Status | Should Be 'NOT_RECOMPUTED'
        } finally {
            $stream.Dispose()
        }
    }

    It 'moves a controlled failure lock and records the failure reason' {
        $receiptRoot = Join-Path $TestDrive 'runner-receipts'
        [void](New-Item -ItemType Directory -Path $receiptRoot)
        $lockPath = Join-Path $TestDrive '.windows_runner_active.lock'
        $lockText = '{"run_id":"run_fixture","scene_id":"F1023_V70_D0117_P2","prn":28,"tracking_channel":1,"process_id":999999,"started_utc":"2026-10-04T00:00:00Z"}'
        [System.IO.File]::WriteAllText($lockPath, $lockText)
        $lockPayload = $lockText | ConvertFrom-Json

        $result = Invoke-ProductionFunctionSafely -Name 'Move-FrozenRunnerLockToFailureReceipt' -Arguments @{
            GlobalLockPath = $lockPath
            ReceiptRoot = $receiptRoot
            LockPayload = $lockPayload
            FailureReason = 'MATLAB_ARGUMENT_TRANSPORT_FAILURE'
            ErrorMessage = 'MATLAB_ARGUMENT_TRANSPORT_FAILED'
        }

        $result.Available | Should Be $true
        $result.Error | Should Be $null
        (Test-Path -LiteralPath $lockPath) | Should Be $false
        (Test-Path -LiteralPath $result.Value.LockPath -PathType Leaf) | Should Be $true
        (Get-Content -LiteralPath $result.Value.LockPath -Raw) | Should Be $lockText
        $receiptText = Get-Content -LiteralPath $result.Value.ReceiptPath -Raw
        $receipt = $receiptText | ConvertFrom-Json
        $receipt.failure_reason | Should Be 'MATLAB_ARGUMENT_TRANSPORT_FAILURE'
        $receipt.run_id | Should Be 'run_fixture'
        $receipt.scene_id | Should Be 'F1023_V70_D0117_P2'
        $receipt.prn | Should Be 28
        $receipt.tracking_channel | Should Be 1
        $receipt.old_pid | Should Be 999999
        $receiptDocument = [System.Text.Json.JsonDocument]::Parse($receiptText)
        try {
            $receiptDocument.RootElement.GetProperty('lock_started_utc').GetString() | Should Be '2026-10-04T00:00:00Z'
        } finally {
            $receiptDocument.Dispose()
        }
    }

    It 'records the SAGE MATLAB process identity and confirmed end state in failure receipts' {
        $receiptRoot = Join-Path $TestDrive 'runner-process-receipts'
        [void](New-Item -ItemType Directory -Path $receiptRoot)
        $lockPath = Join-Path $TestDrive '.windows_runner_process_active.lock'
        $lockText = '{"run_id":"run_fixture","scene_id":"F1023_V120_D0121_P2","prn":6,"tracking_channel":6,"mapping_warning":"NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING","process_id":4321,"started_utc":"2026-10-04T00:00:00Z"}'
        [System.IO.File]::WriteAllText($lockPath, $lockText)

        $result = Invoke-ProductionFunctionSafely -Name 'Move-FrozenRunnerLockToFailureReceipt' -Arguments @{
            GlobalLockPath = $lockPath
            ReceiptRoot = $receiptRoot
            LockPayload = ($lockText | ConvertFrom-Json)
            FailureReason = 'STAGE0_NO_VALID_NAV_SYMBOLS'
            ErrorMessage = 'Stage0 produced no valid NAV symbols.'
            MatlabProcessState = [pscustomobject]@{
                Started = $true
                ProcessId = 8765
                ExitCode = 1
                ProcessEnded = $true
                StartedUtc = '2026-10-04T00:01:00Z'
                EndedUtc = '2026-10-04T00:02:00Z'
            }
        }

        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $receiptText = Get-Content -Raw -LiteralPath $result.Value.ReceiptPath
        $receipt = $receiptText | ConvertFrom-Json
        $receipt.failure_reason | Should Be 'STAGE0_NO_VALID_NAV_SYMBOLS'
        $receipt.run_id | Should Be 'run_fixture'
        $receipt.mapping_warning | Should Be 'NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING'
        $receipt.matlab_started | Should Be $true
        $receipt.matlab_process_id | Should Be 8765
        $receipt.matlab_exit_code | Should Be 1
        $receipt.matlab_process_ended | Should Be $true
        $receiptDocument = [System.Text.Json.JsonDocument]::Parse($receiptText)
        try {
            $receiptDocument.RootElement.GetProperty('matlab_start_utc').GetString() | Should Be '2026-10-04T00:01:00Z'
            $receiptDocument.RootElement.GetProperty('matlab_end_utc').GetString() | Should Be '2026-10-04T00:02:00Z'
        } finally {
            $receiptDocument.Dispose()
        }
    }

    It 'classifies only explicit zero-row Stage0 catalogs as task-specific failures' {
        $output = Join-Path $TestDrive 'stage0-failure'
        [void](New-Item -ItemType Directory -Path $output)
        [System.IO.File]::WriteAllText((Join-Path $output 'stage0_valid_symbols.csv'), "symbol_id`n")
        [System.IO.File]::WriteAllText((Join-Path $output 'stage0_valid_40ms_windows.csv'), "window_id`n")
        $noSymbols = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageStage0FailureReason' -Arguments @{
            StagingPath = $output
        }
        $noSymbols.Available | Should Be $true
        $noSymbols.Error | Should Be $null
        $noSymbols.Value | Should Be 'STAGE0_NO_VALID_NAV_SYMBOLS'

        [System.IO.File]::WriteAllText((Join-Path $output 'stage0_valid_symbols.csv'), "symbol_id`n1`n")
        $noWindows = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageStage0FailureReason' -Arguments @{
            StagingPath = $output
        }
        $noWindows.Available | Should Be $true
        $noWindows.Error | Should Be $null
        $noWindows.Value | Should Be 'STAGE0_NO_VALID_40MS_WINDOWS'
    }

    It 'rejects empty Stage0 catalogs before any staging relocation' {
        $output = Join-Path $TestDrive 'stage0-empty-gate'
        [void](New-Item -ItemType Directory -Path $output)
        [System.IO.File]::WriteAllText((Join-Path $output 'stage0_valid_symbols.csv'), "symbol_id`n")
        [System.IO.File]::WriteAllText((Join-Path $output 'stage0_valid_40ms_windows.csv'), "window_id`n1`n")
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageStage0Ready' -Arguments @{ StagingPath = $output }
        $result.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($result.Error) | Should Be $false
        $result.Error | Should Match 'STAGE0_NO_VALID_NAV_SYMBOLS'
    }

    It 'requires a successful MATLAB startup marker and zero exit code' {
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-MatlabStartupSmoke' -Arguments @{
            ExitCode = 0
            Output = 'MATLAB_STARTUP_OK'
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value | Should Be $true
    }

    It 'requires zero exit code and the MATLAB argument marker in stdout' {
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-MatlabArgumentTransportSmoke' -Arguments @{
            ExitCode = 0
            Stdout = 'MATLAB_ARGUMENT_TRANSPORT_OK'
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value | Should Be $true

        $rejected = Invoke-ProductionFunctionSafely -Name 'Assert-MatlabArgumentTransportSmoke' -Arguments @{
            ExitCode = 1
            Stdout = 'MATLAB_ARGUMENT_TRANSPORT_OK'
        }
        [string]::IsNullOrWhiteSpace($rejected.Error) | Should Be $false

        $missingMarker = Invoke-ProductionFunctionSafely -Name 'Assert-MatlabArgumentTransportSmoke' -Arguments @{
            ExitCode = 0
            Stdout = 'MATLAB_ARGUMENT_TRANSPORT_DIAGNOSTIC_ONLY'
        }
        [string]::IsNullOrWhiteSpace($missingMarker.Error) | Should Be $false
    }

    It 'moves a validated staging directory without overwriting and writes a receipt' {
        $stage = Join-Path $TestDrive 'sage_results\nav_sage_v2\G28'
        $final = Join-Path $TestDrive 'sage_results\rerun_20261003_frozen_v3\G28_ch1'
        [void](New-Item -ItemType Directory -Path $stage -Force)
        [System.IO.File]::WriteAllText((Join-Path $stage 'stage0_valid_symbols.csv'), 'a,b')
        [System.IO.File]::WriteAllText((Join-Path $stage 'stage4_joint_paths.csv'), 'c,d')
        $context = [pscustomobject]@{
            SceneId = 'F1023_V70_D0117_P2'
            Prn = 28
            TrackingChannel = 1
            FrozenSageSha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
            RawIqSizeBytes = 1234
            RawIqSha256 = ''
            RawIqSha256Status = 'NOT_RECOMPUTED'
            Resume = $false
            MatlabStartUtc = '2026-10-04T00:00:00Z'
            MatlabEndUtc = '2026-10-04T00:01:00Z'
            MatlabProcessId = 31415
            MatlabExitCode = 0
        }
        $result = Invoke-ProductionFunctionSafely -Name 'Move-ValidatedStageOutput' -Arguments @{
            StagingPath = $stage
            FinalPath = $final
            Context = $context
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        (Test-Path -LiteralPath $stage) | Should Be $false
        (Test-Path -LiteralPath $final -PathType Container) | Should Be $true
        (Test-Path -LiteralPath (Join-Path $final 'relocation_receipt.json') -PathType Leaf) | Should Be $true
        $receipt = Get-Content -Raw -LiteralPath (Join-Path $final 'relocation_receipt.json') | ConvertFrom-Json
        $receipt.source_file_count_before_move | Should Be 2
        $receipt.destination_file_count_after_move | Should Be 2
        $receipt.source_bytes_before_move | Should Be $receipt.destination_bytes_after_move
        $receipt.resume | Should Be $false
        $receipt.raw_iq_sha256 | Should Be ''
        $receipt.raw_iq_sha256_status | Should Be 'NOT_RECOMPUTED'
        $receipt.matlab_process_id | Should Be 31415
        ([datetime]$receipt.matlab_start_utc).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') | Should Be '2026-10-04T00:00:00Z'
        ([datetime]$receipt.matlab_end_utc).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') | Should Be '2026-10-04T00:01:00Z'
    }
}
