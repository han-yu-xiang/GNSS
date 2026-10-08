$singleRunnerPath = Join-Path $PSScriptRoot '..\Invoke-FrozenSageRerunSingle.ps1'
$batchRunnerPath = Join-Path $PSScriptRoot '..\Invoke-FrozenSageRerunBatch.ps1'
if (Test-Path -LiteralPath $singleRunnerPath -PathType Leaf) {
    . $singleRunnerPath
}
if (Test-Path -LiteralPath $batchRunnerPath -PathType Leaf) {
    . $batchRunnerPath
}

function Invoke-BatchProductionFunctionSafely {
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

function Write-BatchFixtureCsv {
    param(
        [Parameter(Mandatory)][string]$Path,
        [Parameter(Mandatory)][object[]]$Rows
    )
    $Rows | Export-Csv -LiteralPath $Path -NoTypeInformation
}

function New-FrozenSageBatchExecutionPlanFixture {
    param([string[]]$AuthorizedRunIds = @('run_fixture_first', 'run_fixture_second'))
    $root = Join-Path $TestDrive ('batch-gpu-plan-' + [guid]::NewGuid().ToString('N'))
    [void](New-Item -ItemType Directory -Path $root -Force)
    $manifestPath = Join-Path $root 'manifest.csv'
    $repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
    $planPath = Join-Path $root 'plan.json'
    $manifestRows = @(
        [pscustomobject]@{ run_id = 'run_fixture_first'; scene_id = 'FIXTURE_SCENE'; prn = 'G03'; tracking_channel = '2' },
        [pscustomobject]@{ run_id = 'run_fixture_second'; scene_id = 'FIXTURE_SCENE'; prn = 'G04'; tracking_channel = '1' }
    )
    Write-BatchFixtureCsv -Path $manifestPath -Rows $manifestRows
    $authorizedTasks = @(
        foreach ($runId in $AuthorizedRunIds) {
            $row = @($manifestRows | Where-Object { $_.run_id -ceq $runId }) | Select-Object -First 1
            if ($null -eq $row) {
                [pscustomobject]@{ run_id = $runId; task_identity_sha256 = '0' * 64 }
                continue
            }
            $canonical = "run_id=$($row.run_id)`nscene_id=$($row.scene_id)`nprn=$($row.prn)`ntracking_channel=$([int]$row.tracking_channel)`n"
            $digest = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData(
                [Text.UTF8Encoding]::new($false).GetBytes($canonical))).ToLowerInvariant()
            [pscustomobject]@{ run_id = $runId; task_identity_sha256 = $digest }
        }
    )
    $plan = [ordered]@{
        schema_version = 'frozen-sage-gpu-execution-plan-v2'
        execution_mode = 'GPU_STAGE2_QUALIFIED'
        source_manifest_sha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
        resume = $false
        max_parallel_matlab = 1
        authorized_tasks = $authorizedTasks
    }
    [IO.File]::WriteAllText($planPath, ($plan | ConvertTo-Json -Depth 6), [Text.UTF8Encoding]::new($false))
    $script:ApprovedGpuExecutionPlanSha256 = (Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLowerInvariant()
    return [pscustomobject]@{
        Root = $root; ManifestPath = $manifestPath
        SourceContractPath = Join-Path $repoRoot 'experiments\sage_gpu\production_integration\PRODUCTION_GPU_SOURCE_CONTRACT.json'
        ExecutionPlanPath = $planPath
        ManifestRows = $manifestRows
    }
}

function New-BatchFixtureStageOutput {
    param([Parameter(Mandatory)][string]$Path)
    [void](New-Item -ItemType Directory -Path $Path -Force)

    $requiredNames = @(
        'stage0_nav_catalog.mat', 'stage0_valid_symbols.csv', 'stage0_valid_40ms_windows.csv',
        'stage1_nav_fast_scan.mat', 'stage1_nav_fast_scan.csv',
        'stage2_nav_sage_L1_L4.mat', 'stage2_model_orders.csv',
        'stage2_selected_windows.csv', 'stage2_selected_paths.csv',
        'stage3_nav_persistence.mat', 'stage3_persistence.csv', 'stage3_reliable_centers.csv',
        'stage4_nav_joint_100ms.mat', 'stage4_joint_summary.csv', 'stage4_joint_paths.csv'
    )
    foreach ($name in $requiredNames | Where-Object { $_ -match '\.mat$' }) {
        [System.IO.File]::WriteAllText((Join-Path $Path $name), 'fixture')
    }
    Write-BatchFixtureCsv -Path (Join-Path $Path 'stage0_valid_symbols.csv') -Rows @(
        @{ symbol_id = 1 }, @{ symbol_id = 2 }, @{ symbol_id = 3 }
    )
    Write-BatchFixtureCsv -Path (Join-Path $Path 'stage0_valid_40ms_windows.csv') -Rows @(
        @{ window_id = 1 }, @{ window_id = 2 }
    )
    Write-BatchFixtureCsv -Path (Join-Path $Path 'stage1_nav_fast_scan.csv') -Rows @(
        @{ window_id = 1 }, @{ window_id = 2 }, @{ window_id = 3 }, @{ window_id = 4 }
    )
    Write-BatchFixtureCsv -Path (Join-Path $Path 'stage2_model_orders.csv') -Rows @(
        @{ window_id = 1; L = 1 }, @{ window_id = 1; L = 2 },
        @{ window_id = 2; L = 1 }, @{ window_id = 2; L = 2 },
        @{ window_id = 3; L = 1 }, @{ window_id = 3; L = 2 },
        @{ window_id = 4; L = 1 }, @{ window_id = 4; L = 2 }
    )
    Write-BatchFixtureCsv -Path (Join-Path $Path 'stage2_selected_windows.csv') -Rows @(
        @{ window_id = 1 }, @{ window_id = 2 }, @{ window_id = 3 }, @{ window_id = 4 }
    )
    Write-BatchFixtureCsv -Path (Join-Path $Path 'stage2_selected_paths.csv') -Rows @(
        @{ window_id = 1; path_id = 1; is_multipath = 0 },
        @{ window_id = 1; path_id = 2; is_multipath = 1 },
        @{ window_id = 2; path_id = 1; is_multipath = 0 },
        @{ window_id = 2; path_id = 2; is_multipath = 1 },
        @{ window_id = 3; path_id = 1; is_multipath = 1 },
        @{ window_id = 4; path_id = 1; is_multipath = 1 }
    )
    Write-BatchFixtureCsv -Path (Join-Path $Path 'stage3_persistence.csv') -Rows @(
        @{ center_window_id = 1; multipath_id = 1; persistence_pass = 1 },
        @{ center_window_id = 2; multipath_id = 1; persistence_pass = 1 },
        @{ center_window_id = 3; multipath_id = 0; persistence_pass = 1 }
    )
    Write-BatchFixtureCsv -Path (Join-Path $Path 'stage3_reliable_centers.csv') -Rows @(
        @{ center_window_id = 1; reliable_multipath = 1 }
    )
    Write-BatchFixtureCsv -Path (Join-Path $Path 'stage4_joint_summary.csv') -Rows @(
        @{ center_window_id = 1; joint_valid = 1; joint_multipath_count = 1; joint_selected_L = 2 },
        @{ center_window_id = 2; joint_valid = 1; joint_multipath_count = 0; joint_selected_L = 2 },
        @{ center_window_id = 3; joint_valid = 0; joint_multipath_count = 1; joint_selected_L = 2 }
    )
    Write-BatchFixtureCsv -Path (Join-Path $Path 'stage4_joint_paths.csv') -Rows @(
        @{ center_window_id = 1; path_id = 2; is_multipath = 1 },
        @{ center_window_id = 2; path_id = 2; is_multipath = 1 },
        @{ center_window_id = 3; path_id = 1; is_multipath = 1 }
    )
}

function New-BatchFixturePostRunRecoveryCase {
    param([Parameter(Mandatory)][string]$Root)
    $frozenHash = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
    $repoRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
    $sourcePath = Join-Path $Root 'scripts\sage_pipeline\run_nav_sage_pipeline.m'
    [void](New-Item -ItemType Directory -Path (Split-Path -Parent $sourcePath) -Force)
    Copy-Item -LiteralPath (Join-Path $repoRoot 'scripts\sage_pipeline\run_nav_sage_pipeline.m') -Destination $sourcePath

    $manifestDirectory = Join-Path $Root 'reports\data_consolidation_20261003'
    [void](New-Item -ItemType Directory -Path $manifestDirectory -Force)
    [System.IO.File]::WriteAllText((Join-Path $manifestDirectory 'mainline_iq_gnss_sdr_dataset_audit.csv'), 'fixture audit')

    $baseline = New-BatchFixtureManifestRow
    $baselineRows = [System.Collections.Generic.List[object]]::new()
    $baselineRows.Add($baseline)
    $target = New-BatchFixtureManifestRow
    $target.run_id = 'run_20261003_F1023_V120_D0121_P2_G03_ch2'
    $target.dataset_id = 'F1023_V120_D0121_P2'
    $target.scene_id = 'F1023_V120_D0121_P2'
    $target.prn = 'G03'
    $target.tracking_channel = '2'
    $target.mapping_warning = 'NONE'
    $target.output_namespace = 'scenes\F1023_V120_D0121_P2\sage_results\rerun_20261003_frozen_v3\G03_ch2'
    $targetRows = [System.Collections.Generic.List[object]]::new()
    $targetRows.Add($target)
    $manifestRows = [System.Collections.Generic.List[object]]::new()
    $manifestRows.Add($baseline)
    $manifestRows.Add($target)
    for ($index = 1; $index -le 87; $index++) {
        $scene = 'FIXTURE_SCENE_{0:D2}' -f $index
        $prn = 'G{0:D2}' -f $index
        $channel = [string]($index % 33)
        $row = New-BatchFixtureManifestRow
        $row.run_id = 'run_fixture_{0:D2}' -f $index
        $row.dataset_id = $scene
        $row.scene_id = $scene
        $row.prn = $prn
        $row.tracking_channel = $channel
        $row.mapping_warning = if ($index -le 4) { 'NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING' } else { 'NONE' }
        $row.output_namespace = 'scenes\{0}\sage_results\rerun_20261003_frozen_v3\{1}_ch{2}' -f $scene, $prn, $channel
        $manifestRows.Add($row)
    }
    $manifestRows | Export-Csv -LiteralPath (Join-Path $manifestDirectory 'MAINLINE_SAGE_1023_RERUN_MANIFEST.csv') -NoTypeInformation

    $summaryRows = [System.Collections.Generic.List[object]]::new()
    $summaryRows.Add((New-FrozenSageBatchSummaryRow -ManifestRow $baseline -Status 'ALREADY_COMPLETE'))
    $summaryRows.Add((New-FrozenSageBatchSummaryRow -ManifestRow $target -Status 'FAILED' -FailureReason 'POST_RUN_VALIDATION_FAILURE'))
    foreach ($manifestRow in $manifestRows | Select-Object -Skip 2) {
        $summaryRows.Add((New-FrozenSageBatchSummaryRow -ManifestRow $manifestRow -Status 'PENDING'))
    }
    $summaryPath = Join-Path $manifestDirectory 'MAINLINE_SAGE_1023_BATCH_RERUN_SUMMARY.csv'
    [void](Write-FrozenSageBatchSummary -SummaryPath $summaryPath -Rows @($summaryRows) -ExpectedCurrentHash '')

    $finalPath = Join-Path $Root $target.output_namespace
    New-BatchFixtureStageOutput -Path $finalPath
    Write-BatchFixtureCsv -Path (Join-Path $finalPath 'stage0_valid_symbols.csv') -Rows @((1..232) | ForEach-Object { @{ symbol_id = $_ } })
    Write-BatchFixtureCsv -Path (Join-Path $finalPath 'stage0_valid_40ms_windows.csv') -Rows @((1..230) | ForEach-Object { @{ window_id = $_ } })
    Write-BatchFixtureCsv -Path (Join-Path $finalPath 'stage1_nav_fast_scan.csv') -Rows @((1..230) | ForEach-Object { @{ window_id = $_ } })
    Write-BatchFixtureCsv -Path (Join-Path $finalPath 'stage2_model_orders.csv') -Rows @((1..96) | ForEach-Object { @{ window_id = $_; selected_L = 1 } })
    Write-BatchFixtureCsv -Path (Join-Path $finalPath 'stage2_selected_windows.csv') -Rows @((1..96) | ForEach-Object { @{ window_id = $_ } })
    $paths = [System.Collections.Generic.List[object]]::new()
    for ($window = 1; $window -le 96; $window++) { $paths.Add(@{ window_id = $window; path_id = 1; is_multipath = 0 }) }
    for ($window = 1; $window -le 46; $window++) { $paths.Add(@{ window_id = $window; path_id = 2; is_multipath = 1 }) }
    Write-BatchFixtureCsv -Path (Join-Path $finalPath 'stage2_selected_paths.csv') -Rows @($paths)
    Write-BatchFixtureCsv -Path (Join-Path $finalPath 'stage3_persistence.csv') -Rows @((1..46) | ForEach-Object {
        @{ center_window_id = $_; multipath_id = 1; persistence_pass = if ($_ -le 9) { 1 } else { 0 } }
    })
    Write-BatchFixtureCsv -Path (Join-Path $finalPath 'stage3_reliable_centers.csv') -Rows @((1..9) | ForEach-Object { @{ center_window_id = $_ } })
    Write-BatchFixtureCsv -Path (Join-Path $finalPath 'stage4_joint_summary.csv') -Rows @((1..8) | ForEach-Object {
        @{ center_window_id = $_; joint_valid = 1; joint_multipath_count = 0; joint_selected_L = 4 }
    })
    [System.IO.File]::WriteAllText((Join-Path $finalPath 'stage4_joint_paths.csv'), "center_window_id,path_id,is_multipath`n")

    $stagingPath = Join-Path $Root ('scenes\{0}\sage_results\nav_sage_v2\{1}' -f $target.scene_id, $target.prn)
    $runContext = [ordered]@{
        sceneId = $target.scene_id; prn = 3; prnLabel = 'G03'; trackingChannel = 2; samplingRateHz = 10230000
        outputDir = $stagingPath
    }
    [System.IO.File]::WriteAllText((Join-Path $finalPath 'run_context.json'), ($runContext | ConvertTo-Json -Depth 4))
    $relocation = [ordered]@{
        scene_id = $target.scene_id; prn = '3'; tracking_channel = 2; frozen_sage_sha256 = $frozenHash
        final_relocated_path = $finalPath; resume = $false; matlab_exit_code = 0; relocation_status = 'VERIFIED_SAME_VOLUME_MOVE'
        source_file_count_before_move = 21; destination_file_count_after_move = 21
        source_bytes_before_move = 753870; destination_bytes_after_move = 753870
    }
    [System.IO.File]::WriteAllText((Join-Path $finalPath 'relocation_receipt.json'), ($relocation | ConvertTo-Json -Depth 4))
    $runner = [ordered]@{
        run_id = $target.run_id; scene_id = $target.scene_id; prn = 3; tracking_channel = 2
        mapping_warning = 'NONE'; resume = $false; process_id = 4242
    }
    [System.IO.File]::WriteAllText((Join-Path $finalPath 'windows_runner_lock_receipt.json'), ($runner | ConvertTo-Json -Depth 4))

    $oldReceiptDirectory = Join-Path $Root 'dataset_generation_logs\batch_sage_execution\frozen_sage_batch_receipts\frozen_sage_batch_stopped_20261004T130609973Z'
    [void](New-Item -ItemType Directory -Path $oldReceiptDirectory -Force)
    $oldReceiptPath = Join-Path $oldReceiptDirectory 'batch_receipt.json'
    $oldStopReason = "POST_RUN_VALIDATION_STOP:FROZEN_SAGE_SOURCE_HASH_MISMATCH expected=[string]@{manifest row}.frozen_sage_sha256 actual=$frozenHash frozen_sage_sha256=$frozenHash"
    [System.IO.File]::WriteAllText($oldReceiptPath, (([ordered]@{ final_status = 'STOPPED'; stop_reason = $oldStopReason } | ConvertTo-Json -Compress)))
    return [pscustomobject]@{
        ProjectRoot = $Root; RunId = $target.run_id; Target = $target; SummaryPath = $summaryPath
        FinalPath = $finalPath; OldReceiptPath = $oldReceiptPath; StagingPath = $stagingPath
    }
}

function New-BatchFixtureManifestRow {
    [pscustomobject]@{
        run_id = 'run_20261003_F1023_V70_D0117_P2_G28_ch1'
        dataset_id = 'F1023_V70_D0117_P2'
        scene_id = 'F1023_V70_D0117_P2'
        prn = 'G28'
        tracking_channel = '1'
        mapping_warning = 'NONE'
        frozen_sage_sha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
        output_namespace = 'scenes\F1023_V70_D0117_P2\sage_results\rerun_20261003_frozen_v3\G28_ch1'
        resume = 'false'
        execution_status = 'NOT_STARTED'
    }
}

function New-BatchFixtureExistingSummaryState {
    param(
        [string]$PilotStatus = 'PENDING',
        [string]$MismatchField = '',
        [switch]$ReverseSummaryOrder,
        [switch]$WriteSummary = $true
    )

    $root = Join-Path $TestDrive ('existing-summary-' + [guid]::NewGuid().ToString('N'))
    $summaryDirectory = Join-Path $root 'reports\data_consolidation_20261003'
    [void](New-Item -ItemType Directory -Path $summaryDirectory -Force)
    $baseline = New-BatchFixtureManifestRow
    $manifestRows = [System.Collections.Generic.List[object]]::new()
    $manifestRows.Add($baseline)

    $pilot = New-BatchFixtureManifestRow
    $pilot.run_id = 'run_20261003_F1023_V120_D0121_P2_G12_ch11'
    $pilot.dataset_id = 'F1023_V120_D0121_P2'
    $pilot.scene_id = 'F1023_V120_D0121_P2'
    $pilot.prn = 'G12'
    $pilot.tracking_channel = '11'
    $pilot.mapping_warning = 'NONE'
    $pilot.output_namespace = 'scenes\F1023_V120_D0121_P2\sage_results\rerun_20261003_frozen_v3\G12_ch11'
    $manifestRows.Add($pilot)

    for ($index = 3; $index -le 89; $index++) {
        $scene = 'FIXTURE_SCENE_{0:D2}' -f $index
        $prn = 'G{0:D2}' -f $index
        $channel = [string]($index % 33)
        $row = New-BatchFixtureManifestRow
        $row.run_id = 'run_fixture_{0:D2}' -f $index
        $row.dataset_id = $scene
        $row.scene_id = $scene
        $row.prn = $prn
        $row.tracking_channel = $channel
        $row.mapping_warning = 'NONE'
        $row.output_namespace = 'scenes\{0}\sage_results\rerun_20261003_frozen_v3\{1}_ch{2}' -f $scene, $prn, $channel
        $manifestRows.Add($row)
    }

    $summaryRows = [System.Collections.Generic.List[object]]::new()
    $summaryRows.Add((New-FrozenSageBatchSummaryRow -ManifestRow $baseline -Status 'ALREADY_COMPLETE'))
    $summaryRows.Add((New-FrozenSageBatchSummaryRow -ManifestRow $pilot -Status $PilotStatus -FailureReason $(if ($PilotStatus -eq 'FAILED') { 'FIXTURE_FAILURE' } else { '' })))
    for ($index = 2; $index -lt $manifestRows.Count; $index++) {
        $status = if ($index -le 4) { 'COMPLETE' } else { 'PENDING' }
        $summaryRows.Add((New-FrozenSageBatchSummaryRow -ManifestRow $manifestRows[$index] -Status $status))
    }

    if (-not [string]::IsNullOrWhiteSpace($MismatchField)) {
        $summaryRows[1].PSObject.Properties[$MismatchField].Value = 'FIXTURE_IDENTITY_MISMATCH'
    }
    if ($ReverseSummaryOrder) {
        $first = $summaryRows[0]
        $summaryRows[0] = $summaryRows[1]
        $summaryRows[1] = $first
    }

    $summaryPath = Join-Path $summaryDirectory 'MAINLINE_SAGE_1023_BATCH_RERUN_SUMMARY.csv'
    if ($WriteSummary) {
        $summaryRows | Export-Csv -LiteralPath $summaryPath -NoTypeInformation -Encoding utf8NoBOM
    }
    return [pscustomobject]@{
        Root = $root
        SummaryPath = $summaryPath
        ManifestRows = @($manifestRows)
        SummaryRows = @($summaryRows)
        BaselineSummaryRow = New-FrozenSageBatchSummaryRow -ManifestRow $baseline -Status 'ALREADY_COMPLETE'
        PilotRunId = [string]$pilot.run_id
        AuthorizedRunIds = @([string]$pilot.run_id)
    }
}

Describe 'Invoke-FrozenSageRerunBatch safety contract' {
    It 'resolves exactly one explicit execution mode' {
        $validate = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchMode' -Arguments @{
            ValidateOnly = $true
            Execute = $false
        }
        $validate.Available | Should Be $true
        $validate.Error | Should Be $null
        $validate.Value | Should Be 'VALIDATE_ONLY'

        $execute = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchMode' -Arguments @{
            ValidateOnly = $false
            Execute = $true
        }
        $execute.Error | Should Be $null
        $execute.Value | Should Be 'EXECUTE'

        $neither = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchMode' -Arguments @{
            ValidateOnly = $false
            Execute = $false
        }
        [string]::IsNullOrWhiteSpace($neither.Error) | Should Be $false

        $both = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchMode' -Arguments @{
            ValidateOnly = $true
            Execute = $true
        }
        [string]::IsNullOrWhiteSpace($both.Error) | Should Be $false
    }

    It 'defines the exact one-row batch summary schema' {
        $result = Invoke-BatchProductionFunctionSafely -Name 'Get-FrozenSageBatchSummaryColumns' -Arguments @{}
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        ($result.Value -join ',') | Should Be 'run_id,scene_id,prn,tracking_channel,mapping_warning,execution_status,matlab_exit_code,stage0_valid_nav_symbols,stage0_valid_40ms_windows,stage1_scanned_windows,stage2_evaluated_windows,stage2_selected_path_count,direct_path_count,stage2_mpc_count,stage3_persistence_row_count,stage3_persistent_mpc_count,stage4_joint_result_count,stage4_confirmed_mpc_count,output_namespace,frozen_sage_sha256,failure_reason'
    }

    It 'resumes a valid plan from the existing 89-row summary without rebuilding other rows' {
        $fixture = New-BatchFixtureExistingSummaryState
        $beforeHash = (Get-FileHash -LiteralPath $fixture.SummaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $result = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchSummaryState' -Arguments @{
            SummaryPath = $fixture.SummaryPath
            ManifestRows = $fixture.ManifestRows
            BaselineSummaryRow = $fixture.BaselineSummaryRow
            PlanProvided = $true
            AuthorizedRunIds = $fixture.AuthorizedRunIds
        }

        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $state = $result.Value
        $state.IsExistingSummary | Should Be $true
        $state.SummaryRows.Count | Should Be 89
        $state.ExpectedCurrentHash | Should Be $beforeHash
        @($state.SummaryRows | Where-Object { $_.execution_status -eq 'ALREADY_COMPLETE' }).Count | Should Be 1
        @($state.SummaryRows | Where-Object { $_.execution_status -eq 'COMPLETE' }).Count | Should Be 3
        @($state.SummaryRows | Where-Object { $_.execution_status -eq 'PENDING' }).Count | Should Be 85
        $state.ExecutionRows.Count | Should Be 1
        $state.ExecutionRows[0].run_id | Should Be $fixture.PilotRunId
        (Get-FileHash -LiteralPath $fixture.SummaryPath -Algorithm SHA256).Hash.ToLowerInvariant() | Should Be $beforeHash
    }

    It 'keeps an existing summary fail-closed when no execution plan is supplied' {
        $fixture = New-BatchFixtureExistingSummaryState
        $result = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchSummaryState' -Arguments @{
            SummaryPath = $fixture.SummaryPath
            ManifestRows = $fixture.ManifestRows
            BaselineSummaryRow = $fixture.BaselineSummaryRow
            PlanProvided = $false
            AuthorizedRunIds = @()
        }
        $result.Error | Should Match 'BATCH_SUMMARY_ALREADY_EXISTS'
    }

    It 'rejects an authorized task that is already complete' {
        $fixture = New-BatchFixtureExistingSummaryState -PilotStatus 'COMPLETE'
        $result = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchSummaryState' -Arguments @{
            SummaryPath = $fixture.SummaryPath
            ManifestRows = $fixture.ManifestRows
            BaselineSummaryRow = $fixture.BaselineSummaryRow
            PlanProvided = $true
            AuthorizedRunIds = $fixture.AuthorizedRunIds
        }
        $result.Error | Should Match 'GPU_EXECUTION_PLAN_TASK_NOT_PENDING'
    }

    It 'rejects resumable summaries containing IN_PROGRESS or FAILED rows' {
        foreach ($status in @('IN_PROGRESS', 'FAILED')) {
            $fixture = New-BatchFixtureExistingSummaryState -PilotStatus $status
            $result = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchSummaryState' -Arguments @{
                SummaryPath = $fixture.SummaryPath
                ManifestRows = $fixture.ManifestRows
                BaselineSummaryRow = $fixture.BaselineSummaryRow
                PlanProvided = $true
                AuthorizedRunIds = $fixture.AuthorizedRunIds
            }
            $result.Error | Should Match 'BATCH_SUMMARY_STATUS_NOT_RESUMABLE'
            $result.Error | Should Match $status
        }
    }

    It 'rejects a summary whose immutable identity differs from the manifest' {
        $fixture = New-BatchFixtureExistingSummaryState -MismatchField 'scene_id'
        $result = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchSummaryState' -Arguments @{
            SummaryPath = $fixture.SummaryPath
            ManifestRows = $fixture.ManifestRows
            BaselineSummaryRow = $fixture.BaselineSummaryRow
            PlanProvided = $true
            AuthorizedRunIds = $fixture.AuthorizedRunIds
        }
        $result.Error | Should Match 'BATCH_SUMMARY_MANIFEST_IDENTITY_MISMATCH'
        $result.Error | Should Match 'scene_id'
    }

    It 'rejects summary rows that are not in manifest order' {
        $fixture = New-BatchFixtureExistingSummaryState -ReverseSummaryOrder
        $result = Invoke-BatchProductionFunctionSafely -Name 'Read-And-ValidateExistingFrozenSageBatchSummary' -Arguments @{
            SummaryPath = $fixture.SummaryPath
            ManifestRows = $fixture.ManifestRows
            AuthorizedRunIds = $fixture.AuthorizedRunIds
        }
        $result.Error | Should Match 'BATCH_SUMMARY_RUN_ID_ORDER_MISMATCH'
    }

    It 'preserves the existing-summary SHA compare-and-swap ownership guard' {
        $fixture = New-BatchFixtureExistingSummaryState
        $stateResult = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchSummaryState' -Arguments @{
            SummaryPath = $fixture.SummaryPath
            ManifestRows = $fixture.ManifestRows
            BaselineSummaryRow = $fixture.BaselineSummaryRow
            PlanProvided = $true
            AuthorizedRunIds = $fixture.AuthorizedRunIds
        }
        $stateResult.Error | Should Be $null
        [System.IO.File]::AppendAllText($fixture.SummaryPath, "external-change`n")
        $writeResult = Invoke-BatchProductionFunctionSafely -Name 'Write-FrozenSageBatchSummary' -Arguments @{
            SummaryPath = $fixture.SummaryPath
            Rows = $stateResult.Value.SummaryRows
            ExpectedCurrentHash = $stateResult.Value.ExpectedCurrentHash
        }
        $writeResult.Error | Should Match 'BATCH_SUMMARY_OWNERSHIP_HASH_MISMATCH'
        (Get-Content -Raw -LiteralPath $fixture.SummaryPath).EndsWith("external-change`n") | Should Be $true
    }

    It 'preserves fresh-batch baseline and pending-row initialization when no summary exists' {
        $fixture = New-BatchFixtureExistingSummaryState -WriteSummary:$false
        $stateResult = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchSummaryState' -Arguments @{
            SummaryPath = $fixture.SummaryPath
            ManifestRows = $fixture.ManifestRows
            BaselineSummaryRow = $fixture.BaselineSummaryRow
            PlanProvided = $false
            AuthorizedRunIds = @()
        }
        $stateResult.Error | Should Be $null
        $stateResult.Value.IsExistingSummary | Should Be $false
        $stateResult.Value.SummaryRows.Count | Should Be 89
        $stateResult.Value.ExpectedCurrentHash | Should Be ''
        @($stateResult.Value.SummaryRows | Where-Object { $_.execution_status -eq 'ALREADY_COMPLETE' }).Count | Should Be 1
        @($stateResult.Value.SummaryRows | Where-Object { $_.execution_status -eq 'PENDING' }).Count | Should Be 88
    }

    It 'marks plan scope complete independently from unrelated global pending tasks' {
        $fixture = New-BatchFixtureExistingSummaryState
        $fixture.SummaryRows[1].execution_status = 'COMPLETE'
        $result = Invoke-BatchProductionFunctionSafely -Name 'Get-FrozenSagePlanScopeCompletion' -Arguments @{
            Rows = $fixture.SummaryRows
            AuthorizedRunIds = $fixture.AuthorizedRunIds
            StopReason = ''
        }
        $result.Error | Should Be $null
        $result.Value.FinalStatus | Should Be 'PLAN_SCOPE_COMPLETED'
        $result.Value.AuthorizedTaskCount | Should Be 1
        $result.Value.AuthorizedCompleteCount | Should Be 1
        $result.Value.GlobalCompleteCount | Should Be 5
        $result.Value.GlobalPendingCount | Should Be 84
    }

    It 'refuses to start when any runner or batch lock is already present' {
        $root = Join-Path $TestDrive 'lock-root'
        [void](New-Item -ItemType Directory -Path (Join-Path $root 'scripts\sage_pipeline') -Force)
        $clear = Invoke-BatchProductionFunctionSafely -Name 'Assert-FrozenSageNoActiveRunnerLocks' -Arguments @{
            ProjectRoot = $root
        }
        $clear.Available | Should Be $true
        $clear.Error | Should Be $null
        $clear.Value | Should Be $true

        $lockPath = Join-Path $root 'scripts\sage_pipeline\.windows_runner_active.lock'
        [System.IO.File]::WriteAllText($lockPath, '{"process_id":123}')
        $blocked = Invoke-BatchProductionFunctionSafely -Name 'Assert-FrozenSageNoActiveRunnerLocks' -Arguments @{
            ProjectRoot = $root
        }
        $blocked.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($blocked.Error) | Should Be $false
        (Test-Path -LiteralPath $lockPath) | Should Be $true

        $taskRoot = Join-Path $TestDrive 'task-lock-root'
        $taskLock = Join-Path $taskRoot 'dataset_generation_logs\batch_sage_execution\.windows_runner_active_run_fixture.lock'
        [void](New-Item -ItemType Directory -Path (Split-Path -Parent $taskLock) -Force)
        [System.IO.File]::WriteAllText($taskLock, '{"run_id":"run_fixture"}')
        $taskBlocked = Invoke-BatchProductionFunctionSafely -Name 'Assert-FrozenSageNoActiveRunnerLocks' -Arguments @{
            ProjectRoot = $taskRoot
        }
        [string]::IsNullOrWhiteSpace($taskBlocked.Error) | Should Be $false
        $taskBlocked.Error | Should Match 'ACTIVE_RUNNER_LOCK_PRESENT'
    }

    It 'counts Stage2 direct paths, all Stage2 MPCs, exact Stage3 persistence, and strict Stage4 confirmation' {
        $output = Join-Path $TestDrive 'stage-output'
        New-BatchFixtureStageOutput -Path $output
        $result = Invoke-BatchProductionFunctionSafely -Name 'Get-FrozenSageTaskMetrics' -Arguments @{ OutputPath = $output }

        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $metrics = $result.Value
        $metrics.stage0_valid_nav_symbols | Should Be 3
        $metrics.stage0_valid_40ms_windows | Should Be 2
        $metrics.stage1_scanned_windows | Should Be 4
        $metrics.stage2_evaluated_windows | Should Be 4
        $metrics.stage2_selected_path_count | Should Be 6
        $metrics.direct_path_count | Should Be 2
        $metrics.stage2_mpc_count | Should Be 4
        $metrics.stage3_persistence_row_count | Should Be 3
        $metrics.stage3_persistent_mpc_count | Should Be 3
        $metrics.stage4_joint_result_count | Should Be 3
        $metrics.stage4_confirmed_mpc_count | Should Be 1
        ($metrics.direct_path_count + $metrics.stage2_mpc_count) | Should Be $metrics.stage2_selected_path_count
    }

    It 'passes only the manifest frozen SHA scalar to post-run hash validation' {
        $root = Join-Path $TestDrive 'post-run-hash-root'
        $sourcePath = Join-Path $root 'scripts\sage_pipeline\run_nav_sage_pipeline.m'
        [void](New-Item -ItemType Directory -Path (Split-Path -Parent $sourcePath) -Force)
        [System.IO.File]::WriteAllText($sourcePath, 'frozen source fixture')
        $expectedHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()

        $row = New-BatchFixtureManifestRow
        $row.run_id = 'run_20261003_F1023_V120_D0121_P2_G03_ch2'
        $row.scene_id = 'F1023_V120_D0121_P2'
        $row.prn = 'G03'
        $row.tracking_channel = '2'
        $row.output_namespace = 'scenes\F1023_V120_D0121_P2\sage_results\rerun_20261003_frozen_v3\G03_ch2'
        $row.frozen_sage_sha256 = $expectedHash

        $finalPath = Join-Path $root $row.output_namespace
        New-BatchFixtureStageOutput -Path $finalPath
        $relocation = [ordered]@{
            final_relocated_path = $finalPath
            relocation_status = 'VERIFIED_SAME_VOLUME_MOVE'
            matlab_exit_code = 0
            matlab_process_id = 8420
            matlab_start_utc = '2026-10-04T00:00:00Z'
            matlab_end_utc = '2026-10-04T00:01:00Z'
            resume = $false
            frozen_sage_sha256 = $expectedHash
            scene_id = $row.scene_id
            prn = 3
            tracking_channel = 2
        }
        [System.IO.File]::WriteAllText((Join-Path $finalPath 'relocation_receipt.json'), ($relocation | ConvertTo-Json -Depth 4))
        $lockReceipt = [ordered]@{
            run_id = $row.run_id
            scene_id = $row.scene_id
            prn = 3
            tracking_channel = 2
            process_id = 4242
            mapping_warning = 'NONE'
            resume = $false
        }
        [System.IO.File]::WriteAllText((Join-Path $finalPath 'windows_runner_lock_receipt.json'), ($lockReceipt | ConvertTo-Json -Depth 4))
        $peerLockDirectory = Join-Path $root 'dataset_generation_logs\batch_sage_execution'
        [void](New-Item -ItemType Directory -Path $peerLockDirectory -Force)
        [System.IO.File]::WriteAllText((Join-Path $peerLockDirectory '.windows_runner_active_peer_task.lock'), '{"run_id":"peer_task"}')

        $child = [pscustomobject]@{
            ProcessEnded = $true
            ExitCode = 0
            ProcessId = 4242
            CombinedOutput = "PREFLIGHT_PASS MATLAB_STARTUP_SMOKE_PASS MATLAB_ARGUMENT_TRANSPORT_SMOKE_PASS EXECUTION_GATES_REVERIFIED SAGE_EXECUTION_BEGIN RELOCATION_VERIFIED mapping_warning=NONE resume=false FROZEN_SAGE_SHA_AFTER=$expectedHash"
        }
        $result = Invoke-BatchProductionFunctionSafely -Name 'Assert-FrozenSageSuccessfulTask' -Arguments @{
            ManifestRow = $row
            ChildResult = $child
            ProjectRoot = $root
        }

        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value.OutputPath | Should Be $finalPath
        $result.Value.Metrics.stage0_valid_nav_symbols | Should Be 3
    }

    It 'recovers only the proven G03 post-run false failure through the coordinator' {
        $case = New-BatchFixturePostRunRecoveryCase -Root (Join-Path $TestDrive 'g03-recovery')
        $summaryHashBefore = (Get-FileHash -LiteralPath $case.SummaryPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $readOnly = Invoke-BatchProductionFunctionSafely -Name 'Invoke-FrozenSageBatchPostRunRecovery' -Arguments @{
            ProjectRoot = $case.ProjectRoot
            RunId = $case.RunId
            ValidateOnly = $true
        }
        $readOnly.Error | Should Be $null
        $readOnly.Value.G03RecoveryValidation | Should Be 'PASS'
        $readOnly.Value.SummaryRecovery | Should Be 'NOT_STARTED_READ_ONLY_VALIDATION'
        (Get-FileHash -LiteralPath $case.SummaryPath -Algorithm SHA256).Hash.ToLowerInvariant() | Should Be $summaryHashBefore
        (Test-Path -LiteralPath (Join-Path $case.ProjectRoot 'dataset_generation_logs\batch_sage_execution\.frozen_sage_batch_active.lock')) | Should Be $false

        $result = Invoke-BatchProductionFunctionSafely -Name 'Invoke-FrozenSageBatchPostRunRecovery' -Arguments @{
            ProjectRoot = $case.ProjectRoot
            RunId = $case.RunId
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value.G03RecoveryValidation | Should Be 'PASS'
        $result.Value.SummaryRecovery | Should Be 'PASS'
        (Test-Path -LiteralPath $case.StagingPath) | Should Be $false
        $rows = @(Import-Csv -LiteralPath $case.SummaryPath)
        $rows.Count | Should Be 89
        @($rows | Where-Object execution_status -eq 'ALREADY_COMPLETE').Count | Should Be 1
        @($rows | Where-Object execution_status -eq 'COMPLETE').Count | Should Be 1
        @($rows | Where-Object execution_status -eq 'PENDING').Count | Should Be 87
        @($rows | Where-Object execution_status -eq 'FAILED').Count | Should Be 0
        $recovered = @($rows | Where-Object run_id -eq $case.RunId)[0]
        $recovered.matlab_exit_code | Should Be '0'
        $recovered.stage2_mpc_count | Should Be '46'
        $recovered.failure_reason | Should Be ''
        Test-Path -LiteralPath $result.Value.RecoveryReceipt | Should Be $true
        Test-Path -LiteralPath $case.OldReceiptPath | Should Be $true
        (Get-Content -Raw -LiteralPath $case.OldReceiptPath) | Should Match 'FROZEN_SAGE_SOURCE_HASH_MISMATCH'
        $receipt = Get-Content -Raw -LiteralPath $result.Value.RecoveryReceipt | ConvertFrom-Json
        $receipt.previous_summary_status | Should Be 'FAILED'
        $receipt.recovered_summary_status | Should Be 'COMPLETE'
        $receipt.recovery_reason | Should Be 'POSTRUN_SHA_VALIDATOR_PARAMETER_BINDING_FALSE_FAILURE'
        $receipt.scientific_execution_status | Should Be 'SUCCESS'
        $receipt.sage_rerun_performed | Should Be $false
    }

    It 'selects exactly two pending warning-free tasks with distinct scene-PRN staging keys' {
        $first = New-BatchFixtureManifestRow
        $first.run_id = 'run_fixture_first'
        $first.scene_id = 'FIXTURE_SAME_SCENE'
        $first.prn = 'G06'
        $first.tracking_channel = '1'
        $first.output_namespace = 'scenes\FIXTURE_SAME_SCENE\sage_results\rerun_20261003_frozen_v3\G06_ch1'
        $secondSameKey = New-BatchFixtureManifestRow
        $secondSameKey.run_id = 'run_fixture_second_same_key'
        $secondSameKey.scene_id = 'FIXTURE_SAME_SCENE'
        $secondSameKey.prn = 'G06'
        $secondSameKey.tracking_channel = '2'
        $secondSameKey.output_namespace = 'scenes\FIXTURE_SAME_SCENE\sage_results\rerun_20261003_frozen_v3\G06_ch2'
        $third = New-BatchFixtureManifestRow
        $third.run_id = 'run_fixture_third'
        $third.scene_id = 'FIXTURE_OTHER_SCENE'
        $third.prn = 'G07'
        $third.tracking_channel = '1'
        $third.output_namespace = 'scenes\FIXTURE_OTHER_SCENE\sage_results\rerun_20261003_frozen_v3\G07_ch1'
        $warning = New-BatchFixtureManifestRow
        $warning.run_id = 'run_fixture_warning'
        $warning.scene_id = 'FIXTURE_WARNING_SCENE'
        $warning.prn = 'G08'
        $warning.tracking_channel = '1'
        $warning.output_namespace = 'scenes\FIXTURE_WARNING_SCENE\sage_results\rerun_20261003_frozen_v3\G08_ch1'
        $warning.mapping_warning = 'NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING'
        $rows = @($first, $secondSameKey, $third, $warning)
        $summary = @($rows | ForEach-Object { New-FrozenSageBatchSummaryRow -ManifestRow $_ -Status 'PENDING' })

        $result = Invoke-BatchProductionFunctionSafely -Name 'Select-FrozenSageParallelPilotTasks' -Arguments @{
            ManifestRows = $rows
            SummaryRows = $summary
            MaxParallel = 2
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value.Count | Should Be 2
        (@($result.Value | ForEach-Object run_id) -join ',') | Should Be 'run_fixture_first,run_fixture_third'
        (@($result.Value | ForEach-Object { '{0}|{1}' -f $_.scene_id, $_.prn } | Sort-Object -Unique).Count) | Should Be 2
    }

    It 'builds each worker command with a single explicit run id and native arguments' {
        $root = Join-Path $TestDrive 'worker-start-info'
        $runner = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\Invoke-FrozenSageRerunSingle.ps1'))
        $result = Invoke-BatchProductionFunctionSafely -Name 'New-FrozenSageSingleTaskProcessStartInfo' -Arguments @{
            ProjectRoot = $root
            RunId = 'run_fixture_exact_task'
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value.UseShellExecute | Should Be $false
        $result.Value.ArgumentList.Count | Should Be 6
        $result.Value.ArgumentList[0] | Should Be '-NoProfile'
        $result.Value.ArgumentList[1] | Should Be '-File'
        $result.Value.ArgumentList[2] | Should Be $runner
        $result.Value.ArgumentList[3] | Should Be '-RunId'
        $result.Value.ArgumentList[4] | Should Be 'run_fixture_exact_task'
        $result.Value.ArgumentList[5] | Should Be '-Execute'
    }

    It 'propagates a validated GPU plan path to the review-checkout single runner' {
        $fixture = New-FrozenSageBatchExecutionPlanFixture
        $expectedRunner = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\Invoke-FrozenSageRerunSingle.ps1'))
        $result = Invoke-BatchProductionFunctionSafely -Name 'New-FrozenSageSingleTaskProcessStartInfo' -Arguments @{
            ProjectRoot = 'E:\GNSS_Multipath_Project'
            RunId = 'run_fixture_first'
            ExecutionPlanPath = $fixture.ExecutionPlanPath
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value.ArgumentList[2] | Should Be $expectedRunner
        $result.Value.ArgumentList[5] | Should Be '-ExecutionPlanPath'
        $result.Value.ArgumentList[6] | Should Be ([IO.Path]::GetFullPath($fixture.ExecutionPlanPath))
        $result.Value.ArgumentList[7] | Should Be '-Execute'
    }

    It 'resolves batch GPU plan scope only to existing manifest run ids' {
        $fixture = New-FrozenSageBatchExecutionPlanFixture
        $result = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath
            ManifestPath = $fixture.ManifestPath
            SourceContractPath = $fixture.SourceContractPath
            ManifestRows = $fixture.ManifestRows
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value.ExecutionPlan.ExecutionMode | Should Be 'GPU_STAGE2_QUALIFIED'
        ($result.Value.AuthorizedRunIds -join ',') | Should Be 'run_fixture_first,run_fixture_second'
    }

    It 'uses plan v2 task identities without embedding source-contract or entry hashes' {
        $fixture = New-FrozenSageBatchExecutionPlanFixture
        $plan = Get-Content -Raw -LiteralPath $fixture.ExecutionPlanPath | ConvertFrom-Json
        $plan.schema_version | Should Be 'frozen-sage-gpu-execution-plan-v2'
        ($plan.PSObject.Properties.Name -contains 'gpu_source_contract_sha256') | Should Be $false
        ($plan.PSObject.Properties.Name -contains 'production_gpu_entry_sha256') | Should Be $false
        @($plan.authorized_tasks | ForEach-Object { $_.task_identity_sha256 -match '^[0-9a-f]{64}$' }).Count | Should Be 2
    }

    It 'reuses the single-runner plan pin and rejects a plan before batch authorization parsing' {
        $fixture = New-FrozenSageBatchExecutionPlanFixture
        $script:ApprovedGpuExecutionPlanSha256 = ''
        $result = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath; ManifestPath = $fixture.ManifestPath
            SourceContractPath = $fixture.SourceContractPath; ManifestRows = $fixture.ManifestRows
        }
        $result.Error | Should Match 'GPU_EXECUTION_PLAN_NOT_RELEASED'
        $batchSource = Get-Content -Raw -LiteralPath $batchRunnerPath
        $batchSource | Should Not Match '\$script:ApprovedGpu(?:ProductionEntry|SourceContract|ExecutionPlan)Sha256\s*='
    }

    It 'rejects a GPU plan whose authorized run id is absent from the manifest' {
        $fixture = New-FrozenSageBatchExecutionPlanFixture -AuthorizedRunIds @('run_not_in_manifest')
        $result = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath
            ManifestPath = $fixture.ManifestPath
            SourceContractPath = $fixture.SourceContractPath
            ManifestRows = $fixture.ManifestRows
        }
        $result.Error | Should Match 'RUN_ID_NOT_UNIQUE'
    }

    It 'rejects GPU execution plans with duplicate authorized run ids' {
        $fixture = New-FrozenSageBatchExecutionPlanFixture -AuthorizedRunIds @('run_fixture_first', 'run_fixture_first')
        $result = Invoke-BatchProductionFunctionSafely -Name 'Resolve-FrozenSageBatchExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath
            ManifestPath = $fixture.ManifestPath
            SourceContractPath = $fixture.SourceContractPath
            ManifestRows = $fixture.ManifestRows
        }
        $result.Error | Should Match 'DUPLICATE.*RUN_ID'
    }

    It 'blocks GPU execution plans from the two-worker parallel pilot' {
        $fixture = New-FrozenSageBatchExecutionPlanFixture
        $result = Invoke-BatchProductionFunctionSafely -Name 'Assert-FrozenSageGpuParallelPilotNotAllowed' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath
        }
        $result.Error | Should Match 'GPU_PARALLEL_PILOT_NOT_ALLOWED'
    }

    It 'classifies a held cross-run GPU lock as systemic and stops the batch' {
        $result = Invoke-BatchProductionFunctionSafely -Name 'Get-FrozenSageFailureDisposition' -Arguments @{
            FailureReason = 'GPU_GLOBAL_LOCK_PRESENT'; RunnerProcessEnded = $true
            MatlabStarted = $false; MatlabProcessEnded = $false
        }
        $result.Error | Should Be $null
        $result.Value | Should Be 'STOP_BATCH'
    }

    It 'returns NA for zero retention denominators and a numeric ratio otherwise' {
        $zero = Invoke-BatchProductionFunctionSafely -Name 'Get-FrozenSageRetentionRatio' -Arguments @{
            Numerator = 0
            Denominator = 0
        }
        $zero.Available | Should Be $true
        $zero.Error | Should Be $null
        $zero.Value | Should Be 'NA'

        $ratio = Invoke-BatchProductionFunctionSafely -Name 'Get-FrozenSageRetentionRatio' -Arguments @{
            Numerator = 3
            Denominator = 4
        }
        $ratio.Error | Should Be $null
        $ratio.Value | Should Be '0.75'
    }

    It 'creates and atomically checkpoints only its own batch summary' {
        $summaryPath = Join-Path $TestDrive 'summary.csv'
        $row = [pscustomobject]@{
            run_id = 'run_fixture'
            scene_id = 'F1023_V120_D0121_P2'
            prn = 'G06'
            tracking_channel = '6'
            mapping_warning = 'NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING'
            execution_status = 'PENDING'
            frozen_sage_sha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
        }
        $created = Invoke-BatchProductionFunctionSafely -Name 'Write-FrozenSageBatchSummary' -Arguments @{
            SummaryPath = $summaryPath
            Rows = @($row)
            ExpectedCurrentHash = ''
        }
        $created.Available | Should Be $true
        $created.Error | Should Be $null
        (Get-FileHash -Algorithm SHA256 -LiteralPath $summaryPath).Hash.ToLowerInvariant() | Should Be $created.Value.Sha256

        $row.execution_status = 'IN_PROGRESS'
        $updated = Invoke-BatchProductionFunctionSafely -Name 'Write-FrozenSageBatchSummary' -Arguments @{
            SummaryPath = $summaryPath
            Rows = @($row)
            ExpectedCurrentHash = $created.Value.Sha256
        }
        $updated.Error | Should Be $null
        (Import-Csv -LiteralPath $summaryPath)[0].execution_status | Should Be 'IN_PROGRESS'

        $priorText = Get-Content -Raw -LiteralPath $summaryPath
        [System.IO.File]::AppendAllText($summaryPath, "external-change`n")
        $tampered = Invoke-BatchProductionFunctionSafely -Name 'Write-FrozenSageBatchSummary' -Arguments @{
            SummaryPath = $summaryPath
            Rows = @($row)
            ExpectedCurrentHash = $updated.Value.Sha256
        }
        [string]::IsNullOrWhiteSpace($tampered.Error) | Should Be $false
        (Get-Content -Raw -LiteralPath $summaryPath).EndsWith("external-change`n") | Should Be $true
        $priorText | Should Not Be ''
    }

    It 'seeds the frozen G28 baseline only from exact regression, relocation receipt, and complete stages' {
        $output = Join-Path $TestDrive 'baseline-output'
        New-BatchFixtureStageOutput -Path $output
        $row = New-BatchFixtureManifestRow
        $receipt = [ordered]@{
            scene_id = $row.scene_id
            prn = '28'
            tracking_channel = 1
            frozen_sage_sha256 = $row.frozen_sage_sha256
            final_relocated_path = $row.output_namespace
            resume = $false
            matlab_exit_code = 0
            relocation_status = 'VERIFIED_SAME_VOLUME_MOVE'
        }
        [System.IO.File]::WriteAllText((Join-Path $output 'relocation_receipt.json'), ($receipt | ConvertTo-Json -Depth 4))
        $report = Join-Path $TestDrive 'baseline-report.md'
        [System.IO.File]::WriteAllText($report, 'BASELINE_REGRESSION=PASS_EXACT')

        $result = Invoke-BatchProductionFunctionSafely -Name 'Get-FrozenSageBaselineSummaryRow' -Arguments @{
            ManifestRow = $row
            OutputPath = $output
            RegressionReportPath = $report
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value.execution_status | Should Be 'ALREADY_COMPLETE'
        $result.Value.matlab_exit_code | Should Be 0
        $result.Value.stage2_mpc_count | Should Be 4
        $result.Value.stage3_persistent_mpc_count | Should Be 3
        $result.Value.stage4_confirmed_mpc_count | Should Be 1
    }

    It 'continues only for classified task-specific input or ended Stage0 failures' {
        $input = Invoke-BatchProductionFunctionSafely -Name 'Get-FrozenSageFailureDisposition' -Arguments @{
            FailureReason = 'REQUIRED_INPUT_MISSING'
            RunnerProcessEnded = $true
            MatlabStarted = $false
            MatlabProcessEnded = $false
        }
        $input.Error | Should Be $null
        $input.Value | Should Be 'CONTINUE_TASK'

        $stage0 = Invoke-BatchProductionFunctionSafely -Name 'Get-FrozenSageFailureDisposition' -Arguments @{
            FailureReason = 'STAGE0_NO_VALID_NAV_SYMBOLS'
            RunnerProcessEnded = $true
            MatlabStarted = $true
            MatlabProcessEnded = $true
        }
        $stage0.Error | Should Be $null
        $stage0.Value | Should Be 'CONTINUE_TASK'
    }

    It 'stops for unknown failure or any unconfirmed runner or MATLAB termination' {
        foreach ($case in @(
            @{ FailureReason = 'UNCLASSIFIED_WRAPPER_FAILURE'; RunnerProcessEnded = $true; MatlabStarted = $false; MatlabProcessEnded = $false },
            @{ FailureReason = 'STAGE0_NO_VALID_NAV_SYMBOLS'; RunnerProcessEnded = $true; MatlabStarted = $true; MatlabProcessEnded = $false },
            @{ FailureReason = 'STAGE0_NO_VALID_NAV_SYMBOLS'; RunnerProcessEnded = $false; MatlabStarted = $true; MatlabProcessEnded = $true },
            @{ FailureReason = 'REQUIRED_INPUT_MISSING'; RunnerProcessEnded = $true; MatlabStarted = $true; MatlabProcessEnded = $true }
        )) {
            $result = Invoke-BatchProductionFunctionSafely -Name 'Get-FrozenSageFailureDisposition' -Arguments $case
            $result.Error | Should Be $null
            $result.Value | Should Be 'STOP_BATCH'
        }
    }

    It 'stops the batch for every GPU system failure classification' {
        foreach ($reason in @('GPU_SOURCE_IDENTITY_MISMATCH', 'GPU_NOT_AVAILABLE', 'GPU_INITIALIZATION_FAILED', 'GPU_STAGE2_MATLAB_FAILURE')) {
            $result = Invoke-BatchProductionFunctionSafely -Name 'Get-FrozenSageFailureDisposition' -Arguments @{
                FailureReason = $reason
                RunnerProcessEnded = $true
                MatlabStarted = $true
                MatlabProcessEnded = $true
            }
            $result.Error | Should Be $null
            $result.Value | Should Be 'STOP_BATCH'
        }
    }

    It 'moves a classified failed staging tree and records every required receipt field' {
        $staging = Join-Path $TestDrive 'scene\sage_results\nav_sage_v2\G06'
        $final = Join-Path $TestDrive 'scene\sage_results\rerun_20261003_frozen_v3\G06_ch6'
        $diagnostic = Join-Path $TestDrive 'scene\sage_results\rerun_20261003_frozen_v3_failed\G06_ch6\run_fixture_20261004T000000000Z'
        [void](New-Item -ItemType Directory -Path $staging -Force)
        [System.IO.File]::WriteAllText((Join-Path $staging 'stage0_valid_symbols.csv'), "symbol_id`n")

        $result = Invoke-BatchProductionFunctionSafely -Name 'Move-FrozenSageFailedStaging' -Arguments @{
            StagingPath = $staging
            FinalDestinationPath = $final
            DiagnosticDestinationPath = $diagnostic
            SceneId = 'F1023_V120_D0121_P2'
            PrnLabel = 'G06'
            TrackingChannel = 6
            RunId = 'run_fixture'
            FailureReason = 'STAGE0_NO_VALID_NAV_SYMBOLS'
            RunnerProcessEnded = $true
            MatlabStarted = $true
            MatlabProcessId = 8765
            MatlabProcessEnded = $true
            MatlabExitCode = 1
        }

        $result.Available | Should Be $true
        $result.Error | Should Be $null
        (Test-Path -LiteralPath $staging) | Should Be $false
        (Test-Path -LiteralPath $final) | Should Be $false
        (Test-Path -LiteralPath (Join-Path $diagnostic 'stage0_valid_symbols.csv')) | Should Be $true
        $receipt = Get-Content -Raw -LiteralPath $result.Value.ReceiptPath | ConvertFrom-Json
        $receipt.scene_id | Should Be 'F1023_V120_D0121_P2'
        $receipt.prn | Should Be 'G06'
        $receipt.tracking_channel | Should Be 6
        $receipt.run_id | Should Be 'run_fixture'
        $receipt.failure_reason | Should Be 'STAGE0_NO_VALID_NAV_SYMBOLS'
        $receipt.source_staging_path | Should Be $staging
        $receipt.diagnostic_destination | Should Be $diagnostic
        $receipt.file_count | Should Be 1
        ([long]$receipt.byte_count -gt 0) | Should Be $true
        $receipt.move_method | Should Be 'Move-Item'
        $receipt.matlab_process_ended | Should Be $true
    }

    It 'refuses unsafe failed-staging moves without changing the source' {
        $staging = Join-Path $TestDrive 'unsafe-scene\sage_results\nav_sage_v2\G06'
        $final = Join-Path $TestDrive 'unsafe-scene\sage_results\rerun_20261003_frozen_v3\G06_ch6'
        $diagnostic = Join-Path $TestDrive 'unsafe-scene\sage_results\rerun_20261003_frozen_v3_failed\G06_ch6\run_fixture'
        [void](New-Item -ItemType Directory -Path $staging -Force)
        [System.IO.File]::WriteAllText((Join-Path $staging 'partial.bin'), 'keep')
        $args = @{
            StagingPath = $staging
            FinalDestinationPath = $final
            DiagnosticDestinationPath = $diagnostic
            SceneId = 'F1023_V120_D0121_P2'
            PrnLabel = 'G06'
            TrackingChannel = 6
            RunId = 'run_fixture'
            FailureReason = 'STAGE0_NO_VALID_NAV_SYMBOLS'
            RunnerProcessEnded = $true
            MatlabStarted = $true
            MatlabProcessId = 8765
            MatlabProcessEnded = $true
            MatlabExitCode = 1
        }

        $args.RunnerProcessEnded = $false
        $liveRunner = Invoke-BatchProductionFunctionSafely -Name 'Move-FrozenSageFailedStaging' -Arguments $args
        $liveRunner.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($liveRunner.Error) | Should Be $false
        (Test-Path -LiteralPath (Join-Path $staging 'partial.bin')) | Should Be $true
        (Test-Path -LiteralPath $diagnostic) | Should Be $false

        $args.RunnerProcessEnded = $true
        $args.MatlabProcessEnded = $false
        $liveMatlab = Invoke-BatchProductionFunctionSafely -Name 'Move-FrozenSageFailedStaging' -Arguments $args
        $liveMatlab.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($liveMatlab.Error) | Should Be $false
        (Test-Path -LiteralPath (Join-Path $staging 'partial.bin')) | Should Be $true

        $args.MatlabProcessEnded = $true
        $args.FailureReason = 'SYSTEMIC_RUNNER_FAILURE'
        $unknown = Invoke-BatchProductionFunctionSafely -Name 'Move-FrozenSageFailedStaging' -Arguments $args
        $unknown.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($unknown.Error) | Should Be $false
        (Test-Path -LiteralPath (Join-Path $staging 'partial.bin')) | Should Be $true
    }

    It 'refuses a pre-existing final or diagnostic destination rather than overwriting it' {
        $staging = Join-Path $TestDrive 'collision-scene\sage_results\nav_sage_v2\G06'
        $final = Join-Path $TestDrive 'collision-scene\sage_results\rerun_20261003_frozen_v3\G06_ch6'
        $diagnostic = Join-Path $TestDrive 'collision-scene\sage_results\rerun_20261003_frozen_v3_failed\G06_ch6\run_fixture'
        [void](New-Item -ItemType Directory -Path $staging -Force)
        [System.IO.File]::WriteAllText((Join-Path $staging 'partial.bin'), 'keep')
        [void](New-Item -ItemType Directory -Path $final -Force)

        $args = @{
            StagingPath = $staging
            FinalDestinationPath = $final
            DiagnosticDestinationPath = $diagnostic
            SceneId = 'F1023_V120_D0121_P2'
            PrnLabel = 'G06'
            TrackingChannel = 6
            RunId = 'run_fixture'
            FailureReason = 'STAGE0_NO_VALID_NAV_SYMBOLS'
            RunnerProcessEnded = $true
            MatlabStarted = $true
            MatlabProcessId = 8765
            MatlabProcessEnded = $true
            MatlabExitCode = 1
        }
        $finalCollision = Invoke-BatchProductionFunctionSafely -Name 'Move-FrozenSageFailedStaging' -Arguments $args
        $finalCollision.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($finalCollision.Error) | Should Be $false
        (Test-Path -LiteralPath (Join-Path $staging 'partial.bin')) | Should Be $true

        $staging2 = Join-Path $TestDrive 'collision-scene-2\sage_results\nav_sage_v2\G06'
        $final2 = Join-Path $TestDrive 'collision-scene-2\sage_results\rerun_20261003_frozen_v3\G06_ch6'
        $diagnostic2 = Join-Path $TestDrive 'collision-scene-2\sage_results\rerun_20261003_frozen_v3_failed\G06_ch6\run_fixture'
        [void](New-Item -ItemType Directory -Path $staging2 -Force)
        [System.IO.File]::WriteAllText((Join-Path $staging2 'partial.bin'), 'keep')
        [void](New-Item -ItemType Directory -Path $diagnostic2 -Force)
        $args.StagingPath = $staging2
        $args.FinalDestinationPath = $final2
        $args.DiagnosticDestinationPath = $diagnostic2
        $diagnosticCollision = Invoke-BatchProductionFunctionSafely -Name 'Move-FrozenSageFailedStaging' -Arguments $args
        $diagnosticCollision.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($diagnosticCollision.Error) | Should Be $false
        (Test-Path -LiteralPath (Join-Path $staging2 'partial.bin')) | Should Be $true
    }
}

