$driverPath = Join-Path $PSScriptRoot '..\Invoke-GpuStage2Qualification.ps1'
. $driverPath

function New-TestQualificationItem {
    return [pscustomobject]@{
        qualification_id = 'Q_G03_W1'
        scene_id = 'F1023_V120_D0121_P2'
        prn = 'G03'
        tracking_channel = '2'
        window_id = '1'
        recording_time_s = '596.792752883675'
        production_selected_L = '1'
        production_path_count = '1'
        formal_output_path = 'scenes\F1023_V120_D0121_P2\sage_results\rerun_20261003_frozen_v3\G03_ch2'
    }
}

function New-TestFormalTask {
    return [pscustomobject]@{
        scene_id = 'F1023_V120_D0121_P2'
        prn = 'G03'
        tracking_channel = '2'
        output_namespace = 'scenes\F1023_V120_D0121_P2\sage_results\rerun_20261003_frozen_v3\G03_ch2'
    }
}

function New-TestProductionConfig {
    param([int]$Prn = 3)
    return [pscustomobject]@{
        sceneId = 'F1023_V120_D0121_P2'
        targetPrn = $Prn
        trackingChannel = 2
    }
}

function New-TestFormalWindow {
    return [pscustomobject]@{
        windowId = 1
        recordingTimeS = 596.792752883675
        selectedL = 1
        pathCount = 1
    }
}

Describe 'GPU Stage2 qualification driver gates' {
    It 'accepts a consistent PRN 3 task and full window identity' {
        $result = Assert-GpuQualificationWindowIdentity `
            -ManifestItem (New-TestQualificationItem) `
            -FormalTask (New-TestFormalTask) `
            -ProductionConfig (New-TestProductionConfig -Prn 3) `
            -FormalWindow (New-TestFormalWindow) `
            -HelperRequestedPrn 3

        $result | Should Be $true
    }

    It 'accepts a consistent non-PRN-3 task and full window identity' {
        $item = New-TestQualificationItem
        $item.prn = 'G28'
        $item.scene_id = 'F1023_V70_D0117_P2'
        $item.tracking_channel = '1'
        $item.formal_output_path = 'scenes\F1023_V70_D0117_P2\sage_results\rerun_20261003_frozen_v3\G28_ch1'
        $task = New-TestFormalTask
        $task.prn = 'G28'
        $task.scene_id = $item.scene_id
        $task.tracking_channel = '1'
        $task.output_namespace = $item.formal_output_path
        $cfg = New-TestProductionConfig -Prn 28
        $cfg.sceneId = $item.scene_id
        $cfg.trackingChannel = 1

        $result = Assert-GpuQualificationWindowIdentity `
            -ManifestItem $item `
            -FormalTask $task `
            -ProductionConfig $cfg `
            -FormalWindow (New-TestFormalWindow) `
            -HelperRequestedPrn 28

        $result | Should Be $true
    }

    It 'fails closed on a four-way PRN mismatch' {
        $failureMessage = $null
        try {
            [void](Assert-GpuQualificationWindowIdentity `
                -ManifestItem (New-TestQualificationItem) `
                -FormalTask (New-TestFormalTask) `
                -ProductionConfig (New-TestProductionConfig -Prn 28) `
                -FormalWindow (New-TestFormalWindow) `
                -HelperRequestedPrn 3)
        }
        catch {
            $failureMessage = $_.Exception.Message
        }

        $failureMessage | Should BeLike '*INPUT_IDENTITY_VALIDATION=FAIL*'
    }

    It 'fails closed when recording time differs from the formal window' {
        $formalWindow = New-TestFormalWindow
        $formalWindow.recordingTimeS = 596.792752883676
        $failureMessage = $null
        try {
            [void](Assert-GpuQualificationWindowIdentity `
                -ManifestItem (New-TestQualificationItem) `
                -FormalTask (New-TestFormalTask) `
                -ProductionConfig (New-TestProductionConfig -Prn 3) `
                -FormalWindow $formalWindow `
                -HelperRequestedPrn 3)
        }
        catch {
            $failureMessage = $_.Exception.Message
        }

        $failureMessage | Should BeLike '*INPUT_IDENTITY_VALIDATION=FAIL*'
    }

    It 'never invokes GPU after a failed CPU-to-production reference gate' {
        $script:gpuQualificationCalled = $false
        $cpuResult = [pscustomobject]@{
            cpu_production_selected_L_match = $true
            cpu_production_path_count_match = $true
            cpu_production_path_identity_match = $false
            cpu_production_path_label_match = $true
            cpu_production_model_validity_match = $true
        }
        $failureMessage = $null
        try {
            [void](Invoke-GpuQualificationGpuAfterCpuReference `
                -CpuResult $cpuResult `
                -GpuProbe { $script:gpuQualificationCalled = $true; return 'GPU' })
        }
        catch {
            $failureMessage = $_.Exception.Message
        }

        $failureMessage | Should BeLike '*CPU_PRODUCTION_REFERENCE=FAIL*'
        $script:gpuQualificationCalled | Should Be $false
    }
}
