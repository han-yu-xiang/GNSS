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
    [pscustomobject]@{
        run_id = 'run_20261003_F1023_V70_D0117_P2_G28_ch1'
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
        $accepted = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageManifestRow' -Arguments @{ Row = $row }
        $accepted.Available | Should Be $true
        $accepted.Error | Should Be $null
        $accepted.Value | Should Be $true

        $row.tracking_channel = '2'
        $rejected = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageManifestRow' -Arguments @{ Row = $row }
        $rejected.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($rejected.Error) | Should Be $false
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

    It 'builds one explicit Resume=false invocation for G28 channel 1' {
        $result = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageMatlabExpression' -Arguments @{}
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value | Should Be 'run_nav_sage_pipeline("F1023_V70_D0117_P2",28,"TrackingChannel",1,"ProjectRoot","E:/GNSS_Multipath_Project","Resume",false)'
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
            RawIqSha256 = '48c3378d3dae18ef0064abc8c238c4b1e3bf1762bf663077dd593ab445a99dac'
            Resume = $false
            MatlabStartUtc = '2026-10-04T00:00:00Z'
            MatlabEndUtc = '2026-10-04T00:01:00Z'
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
    }
}
