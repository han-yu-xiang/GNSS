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

function New-TestResumeManifestItem {
    param(
        [string]$Id = 'Q_RESUME_1',
        [int]$Window = 10,
        [double]$Time = 100.25
    )
    return [pscustomobject]@{
        qualification_id = $Id
        scene_id = 'F1023_V120_D0121_P2'
        prn = 'G03'
        tracking_channel = '2'
        window_id = $Window
        recording_time_s = $Time
        production_selected_L = 2
        production_path_count = 2
    }
}

function New-TestValidatedPassResult {
    param([Parameter(Mandatory)][object]$Item)
    return [pscustomobject]@{
        qualification_id = $Item.qualification_id
        scene_id = $Item.scene_id
        prn = $Item.prn
        tracking_channel = $Item.tracking_channel
        window_id = [int]$Item.window_id
        recording_time_s = [double]$Item.recording_time_s
        production_selected_L = [int]$Item.production_selected_L
        production_path_count = [int]$Item.production_path_count
        cpu_production_reference = 'PASS'
        cpu_production_selected_L_match = $true
        cpu_production_path_count_match = $true
        cpu_production_path_identity_match = $true
        cpu_production_path_label_match = $true
        cpu_production_model_validity_match = $true
        gpu_structural_equivalence = 'PASS'
        selected_L_match = 'True'
        path_count_match = 'True'
        path_identity_match = 'True'
        path_label_match = 'True'
        model_validity_match = 'True'
        frozen_sage_sha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
        status = 'COMPLETE'
        cpu_stage2_seconds = 1.25
        gpu_warm_stage2_seconds = 0.5
    }
}

function Get-TestQualificationRepositoryRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')).Path
}

function Get-TestHistoricalManifestItem {
    param([Parameter(Mandatory)][string]$QualificationId)
    $repo = Get-TestQualificationRepositoryRoot
    $manifestPath = Join-Path $repo 'experiments\sage_gpu\qualification\GPU_STAGE2_QUALIFICATION_MANIFEST.csv'
    $matches = @(Import-Csv -LiteralPath $manifestPath | Where-Object { $_.qualification_id -eq $QualificationId })
    if ($matches.Count -ne 1) { throw "Test fixture manifest row missing or ambiguous: $QualificationId" }
    return $matches[0]
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

Describe 'GPU Stage2 qualification fail-closed resume' {
    It 'reuses eight validated PASS records without scheduling execution' {
        $root = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-qualification-resume-test-' + [guid]::NewGuid().ToString('N'))
        $resultsDirectory = Join-Path $root 'results'
        $null = New-Item -ItemType Directory -Path $resultsDirectory -Force
        try {
            $manifest = @()
            for ($index = 1; $index -le 8; $index++) {
                $item = New-TestResumeManifestItem -Id "Q_RESUME_$index" -Window $index -Time (100 + $index)
                $manifest += $item
                (New-TestValidatedPassResult -Item $item) | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $resultsDirectory ($item.qualification_id + '.json')) -Encoding UTF8
            }

            $plan = Get-GpuQualificationResumePlan -Manifest $manifest -ResultsDirectory $resultsDirectory -ExpectedFrozenSha256 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'

            $plan.CanonicalResults.Count | Should Be 8
            $plan.PendingItems.Count | Should Be 0
            @($plan.CanonicalResults | Where-Object { $_.result_source -ne 'REUSED' -or $_.provenance_mode -ne 'PER_WINDOW_EMBEDDED_SHA' }).Count | Should Be 0
        }
        finally {
            Remove-Item -LiteralPath $root -Recurse -Force
        }
    }

    It 'stops when an existing PASS identity differs from the current manifest' {
        $root = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-qualification-resume-test-' + [guid]::NewGuid().ToString('N'))
        $resultsDirectory = Join-Path $root 'results'
        $null = New-Item -ItemType Directory -Path $resultsDirectory -Force
        try {
            $item = New-TestResumeManifestItem
            $result = New-TestValidatedPassResult -Item $item
            $result.scene_id = 'WRONG_SCENE'
            $result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $resultsDirectory ($item.qualification_id + '.json')) -Encoding UTF8

            $failureMessage = $null
            try {
                [void](Get-GpuQualificationResumePlan -Manifest @($item) -ResultsDirectory $resultsDirectory -ExpectedFrozenSha256 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c')
            }
            catch { $failureMessage = $_.Exception.Message }

            $failureMessage | Should BeLike '*RESUME_IDENTITY_MISMATCH*'
        }
        finally {
            Remove-Item -LiteralPath $root -Recurse -Force
        }
    }

    It 'preserves a known old identity-fail as history and leaves the corrected item pending' {
        $root = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-qualification-resume-test-' + [guid]::NewGuid().ToString('N'))
        $resultsDirectory = Join-Path $root 'results'
        $null = New-Item -ItemType Directory -Path $resultsDirectory -Force
        try {
            $item = New-TestResumeManifestItem -Id 'Q_G06_W6850' -Window 6850 -Time 163.771145552297
            $oldFailure = [pscustomobject]@{
                qualification_id = $item.qualification_id
                scene_id = $item.scene_id
                prn = $item.prn
                tracking_channel = $item.tracking_channel
                window_id = $item.window_id
                recording_time_s = 163.771145454545
                production_selected_L = $item.production_selected_L
                production_path_count = $item.production_path_count
                cpu_production_reference = 'NOT_RUN'
                gpu_structural_equivalence = 'NOT_RUN'
                status = 'FAIL_IDENTITY'
                notes = 'INPUT_IDENTITY_VALIDATION=FAIL: recording_time_s manifest=163.771145454545 formal=163.771145552297. manifest_time=163.771145454545 formal_stage0_time=163.771145552297'
            }
            $oldPath = Join-Path $resultsDirectory ($item.qualification_id + '.json')
            $oldFailure | ConvertTo-Json | Set-Content -LiteralPath $oldPath -Encoding UTF8
            $originalJson = Get-Content -LiteralPath $oldPath -Raw

            $plan = Get-GpuQualificationResumePlan -Manifest @($item) -ResultsDirectory $resultsDirectory -ExpectedFrozenSha256 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'

            $plan.PendingItems.Count | Should Be 1
            $plan.HistoricalResults.Count | Should Be 1
            (Get-Content -LiteralPath $oldPath -Raw) | Should Be $originalJson
        }
        finally {
            Remove-Item -LiteralPath $root -Recurse -Force
        }
    }

    It 'rebuilds an existing aggregate from canonical results without duplicate rows' {
        $root = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-qualification-resume-test-' + [guid]::NewGuid().ToString('N'))
        $aggregatePath = Join-Path $root 'aggregate.csv'
        $null = New-Item -ItemType Directory -Path $root -Force
        try {
            @(
                [pscustomobject]@{ qualification_id = 'Q_STALE'; status = 'FAIL_IDENTITY' },
                [pscustomobject]@{ qualification_id = 'Q_CANONICAL'; status = 'OLD' },
                [pscustomobject]@{ qualification_id = 'Q_CANONICAL'; status = 'DUPLICATE' }
            ) | Export-Csv -LiteralPath $aggregatePath -NoTypeInformation
            $item = New-TestResumeManifestItem -Id 'Q_CANONICAL'
            $result = New-TestValidatedPassResult -Item $item
            $result | Add-Member -NotePropertyName result_source -NotePropertyValue 'REUSED_VALIDATED_PASS'

            Write-GpuQualificationAggregate -Results @($result) -CsvPath $aggregatePath

            $rows = @(Import-Csv -LiteralPath $aggregatePath)
            $rows.Count | Should Be 1
            $rows[0].qualification_id | Should Be 'Q_CANONICAL'
            $rows[0].result_source | Should Be 'REUSED_VALIDATED_PASS'
        }
        finally {
            Remove-Item -LiteralPath $root -Recurse -Force
        }
    }

    It 'preserves fields that exist only on new rows when aggregating legacy and new results' {
        $root = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-qualification-resume-test-' + [guid]::NewGuid().ToString('N'))
        $aggregatePath = Join-Path $root 'aggregate.csv'
        $null = New-Item -ItemType Directory -Path $root -Force
        try {
            $legacy = [pscustomobject]@{ qualification_id = 'Q_LEGACY'; status = 'COMPLETE' }
            $new = [pscustomobject]@{
                qualification_id = 'Q_NEW'
                status = 'COMPLETE'
                cpu_stage2_seconds = 12.5
                gpu_warm_stage2_seconds = 4.25
                frozen_sage_sha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
            }

            Write-GpuQualificationAggregate -Results @($legacy, $new) -CsvPath $aggregatePath

            $rows = @(Import-Csv -LiteralPath $aggregatePath)
            $rows.Count | Should Be 2
            (@($rows[0].PSObject.Properties.Name) -contains 'cpu_stage2_seconds') | Should Be $true
            [string]$rows[0].cpu_stage2_seconds | Should Be ''
            $rows[1].cpu_stage2_seconds | Should Be '12.5'
            $rows[1].gpu_warm_stage2_seconds | Should Be '4.25'
            $rows[1].frozen_sage_sha256 | Should Be 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
        }
        finally {
            Remove-Item -LiteralPath $root -Recurse -Force
        }
    }

    It 'replaces a stale aggregate with a header-only canonical aggregate when there are no reusable results' {
        $root = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-qualification-resume-test-' + [guid]::NewGuid().ToString('N'))
        $aggregatePath = Join-Path $root 'aggregate.csv'
        $null = New-Item -ItemType Directory -Path $root -Force
        try {
            [pscustomobject]@{ qualification_id = 'Q_STALE'; status = 'FAIL_IDENTITY' } | Export-Csv -LiteralPath $aggregatePath -NoTypeInformation

            Write-GpuQualificationAggregate -Results @() -CsvPath $aggregatePath

            @(Import-Csv -LiteralPath $aggregatePath).Count | Should Be 0
            (Get-Content -LiteralPath $aggregatePath -TotalCount 1) | Should BeLike '*qualification_id*'
        }
        finally {
            Remove-Item -LiteralPath $root -Recurse -Force
        }
    }

    It 'refuses to overwrite a current per-window result artifact' {
        $root = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-qualification-resume-test-' + [guid]::NewGuid().ToString('N'))
        $path = Join-Path $root 'current.json'
        $null = New-Item -ItemType Directory -Path $root -Force
        try {
            Set-Content -LiteralPath $path -Value '{"status":"OLD"}' -Encoding UTF8
            $originalJson = Get-Content -LiteralPath $path -Raw
            $result = [pscustomobject]@{ status = 'COMPLETE' }
            $failureMessage = $null
            try { Write-GpuQualificationResult -Result $result -Path $path }
            catch { $failureMessage = $_.Exception.Message }

            $failureMessage | Should BeLike '*QUALIFICATION_RESULT_COLLISION*'
            (Get-Content -LiteralPath $path -Raw) | Should Be $originalJson
        }
        finally {
            Remove-Item -LiteralPath $root -Recurse -Force
        }
    }

    It 'stops when two current result artifacts make canonical selection ambiguous' {
        $root = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-qualification-resume-test-' + [guid]::NewGuid().ToString('N'))
        $resultsDirectory = Join-Path $root 'results'
        $currentDirectory = Join-Path $resultsDirectory 'current'
        $null = New-Item -ItemType Directory -Path $currentDirectory -Force
        try {
            $item = New-TestResumeManifestItem
            $result = New-TestValidatedPassResult -Item $item
            $result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $resultsDirectory ($item.qualification_id + '.json')) -Encoding UTF8
            $result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $currentDirectory ($item.qualification_id + '.json')) -Encoding UTF8

            $failureMessage = $null
            try {
                [void](Get-GpuQualificationResumePlan -Manifest @($item) -ResultsDirectory $resultsDirectory -ExpectedFrozenSha256 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c')
            }
            catch { $failureMessage = $_.Exception.Message }

            $failureMessage | Should BeLike '*RESUME_AMBIGUOUS_CURRENT_RESULT*'
        }
        finally {
            Remove-Item -LiteralPath $root -Recurse -Force
        }
    }

    It 'reuses current run records with embedded SHA and runner provenance without legacy-only CPU flags' {
        $root = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-qualification-current-result-test-' + [guid]::NewGuid().ToString('N'))
        $resultsDirectory = Join-Path $root 'results'
        $currentDirectory = Join-Path $resultsDirectory 'current'
        $null = New-Item -ItemType Directory -Path $currentDirectory -Force
        try {
            $item = New-TestResumeManifestItem
            $result = New-TestValidatedPassResult -Item $item
            foreach ($field in @(
                'cpu_production_selected_L_match', 'cpu_production_path_count_match',
                'cpu_production_path_identity_match', 'cpu_production_path_label_match',
                'cpu_production_model_validity_match'
            )) { $result.PSObject.Properties.Remove($field) }
            $result | Add-Member -NotePropertyName result_source -NotePropertyValue 'NEW_EXECUTION'
            $result | Add-Member -NotePropertyName provenance_mode -NotePropertyValue 'PER_WINDOW_EMBEDDED_SHA'
            $result | Add-Member -NotePropertyName qualification_driver_sha256 -NotePropertyValue ('a' * 64)
            $result | Add-Member -NotePropertyName execution_timestamp_utc -NotePropertyValue '2026-10-05T00:00:00Z'
            $result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $currentDirectory ($item.qualification_id + '.json')) -Encoding UTF8

            $plan = Get-GpuQualificationResumePlan -Manifest @($item) -ResultsDirectory $resultsDirectory -ExpectedFrozenSha256 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'

            $plan.CanonicalResults.Count | Should Be 1
            $plan.CanonicalResults[0].result_source | Should Be 'NEW_EXECUTION'
            $plan.CanonicalResults[0].provenance_mode | Should Be 'PER_WINDOW_EMBEDDED_SHA'
            $plan.CanonicalResults[0].resume_disposition | Should Be 'REUSED_VALIDATED_PASS'
            $plan.PendingItems.Count | Should Be 0
        }
        finally {
            Remove-Item -LiteralPath $root -Recurse -Force
        }
    }

    It 'fails closed when a PASS result lacks frozen-source provenance' {
        $root = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-qualification-resume-test-' + [guid]::NewGuid().ToString('N'))
        $resultsDirectory = Join-Path $root 'results'
        $null = New-Item -ItemType Directory -Path $resultsDirectory -Force
        try {
            $item = New-TestResumeManifestItem
            $result = New-TestValidatedPassResult -Item $item
            $result.PSObject.Properties.Remove('frozen_sage_sha256')
            $result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $resultsDirectory ($item.qualification_id + '.json')) -Encoding UTF8

            $failureMessage = $null
            try {
                [void](Get-GpuQualificationResumePlan -Manifest @($item) -ResultsDirectory $resultsDirectory -ExpectedFrozenSha256 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c')
            }
            catch { $failureMessage = $_.Exception.Message }

            $failureMessage | Should BeLike '*RESUME_PROVENANCE_MISSING*'
        }
        finally {
            Remove-Item -LiteralPath $root -Recurse -Force
        }
    }

    It 'fails closed when a PASS result names a different frozen-source SHA' {
        $root = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-qualification-resume-test-' + [guid]::NewGuid().ToString('N'))
        $resultsDirectory = Join-Path $root 'results'
        $null = New-Item -ItemType Directory -Path $resultsDirectory -Force
        try {
            $item = New-TestResumeManifestItem
            $result = New-TestValidatedPassResult -Item $item
            $result.frozen_sage_sha256 = '9a263f0000000000000000000000000000000000000000000000000000000000'
            $result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $resultsDirectory ($item.qualification_id + '.json')) -Encoding UTF8

            $failureMessage = $null
            try {
                [void](Get-GpuQualificationResumePlan -Manifest @($item) -ResultsDirectory $resultsDirectory -ExpectedFrozenSha256 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c')
            }
            catch { $failureMessage = $_.Exception.Message }

            $failureMessage | Should BeLike '*RESUME_PROVENANCE_MISMATCH*'
        }
        finally {
            Remove-Item -LiteralPath $root -Recurse -Force
        }
    }

    It 'reuses an unchanged historical PASS through the committed run-level attestation only' {
        $repo = Get-TestQualificationRepositoryRoot
        $qualificationId = 'Q_G28_W38'
        $item = Get-TestHistoricalManifestItem -QualificationId $qualificationId
        $qualificationRoot = Join-Path $repo 'experiments\sage_gpu\qualification'
        $resultsDirectory = Join-Path $qualificationRoot 'results'
        $attestationPath = Join-Path $qualificationRoot 'HISTORICAL_8_WINDOW_RUN_PROVENANCE_ATTESTATION.json'
        $beforeBlob = (& git -c "safe.directory=$repo" -C $repo hash-object -- (Join-Path $resultsDirectory ($qualificationId + '.json')) | Out-String).Trim()

        $plan = Get-GpuQualificationResumePlan -Manifest @($item) -ResultsDirectory $resultsDirectory -ExpectedFrozenSha256 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c' -AttestationPath $attestationPath -RepositoryRoot $repo

        $plan.CanonicalResults.Count | Should Be 1
        $plan.CanonicalResults[0].result_source | Should Be 'REUSED'
        $plan.CanonicalResults[0].provenance_mode | Should Be 'RUN_LEVEL_ATTESTED'
        $plan.CanonicalResults[0].resume_disposition | Should Be 'REUSED_RUN_LEVEL_ATTESTED'
        $plan.PendingItems.Count | Should Be 0
        $afterBlob = (& git -c "safe.directory=$repo" -C $repo hash-object -- (Join-Path $resultsDirectory ($qualificationId + '.json')) | Out-String).Trim()
        $afterBlob | Should Be $beforeBlob
    }

    It 'stops when a historical result differs by one byte from its committed blob' {
        $repo = Get-TestQualificationRepositoryRoot
        $qualificationId = 'Q_G28_W38'
        $item = Get-TestHistoricalManifestItem -QualificationId $qualificationId
        $qualificationRoot = Join-Path $repo 'experiments\sage_gpu\qualification'
        $sourceResult = Join-Path $qualificationRoot "results\$qualificationId.json"
        $attestationPath = Join-Path $qualificationRoot 'HISTORICAL_8_WINDOW_RUN_PROVENANCE_ATTESTATION.json'
        $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-attestation-byte-mismatch-' + [guid]::NewGuid().ToString('N'))
        $resultsDirectory = Join-Path $tempRoot 'results'
        $null = New-Item -ItemType Directory -Path $resultsDirectory -Force
        try {
            $tamperedResult = Join-Path $resultsDirectory ($qualificationId + '.json')
            [System.IO.File]::Copy($sourceResult, $tamperedResult)
            [System.IO.File]::AppendAllText($tamperedResult, ' ')

            $failureMessage = $null
            try {
                [void](Get-GpuQualificationResumePlan -Manifest @($item) -ResultsDirectory $resultsDirectory -ExpectedFrozenSha256 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c' -AttestationPath $attestationPath -RepositoryRoot $repo)
            }
            catch { $failureMessage = $_.Exception.Message }

            $failureMessage | Should BeLike '*RESUME_ATTESTATION_BLOB_MISMATCH*'
        }
        finally {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force
        }
    }

    It 'does not use run-level fallback for a qualification ID outside the historical allowlist' {
        $root = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-attestation-unknown-id-' + [guid]::NewGuid().ToString('N'))
        $resultsDirectory = Join-Path $root 'results'
        $null = New-Item -ItemType Directory -Path $resultsDirectory -Force
        try {
            $item = New-TestResumeManifestItem -Id 'Q_FUTURE_99'
            $result = New-TestValidatedPassResult -Item $item
            $result.PSObject.Properties.Remove('frozen_sage_sha256')
            $result | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $resultsDirectory ($item.qualification_id + '.json')) -Encoding UTF8

            $failureMessage = $null
            try {
                [void](Get-GpuQualificationResumePlan -Manifest @($item) -ResultsDirectory $resultsDirectory -ExpectedFrozenSha256 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c' -AttestationPath (Join-Path (Get-TestQualificationRepositoryRoot) 'experiments\sage_gpu\qualification\HISTORICAL_8_WINDOW_RUN_PROVENANCE_ATTESTATION.json') -RepositoryRoot (Get-TestQualificationRepositoryRoot))
            }
            catch { $failureMessage = $_.Exception.Message }

            $failureMessage | Should BeLike '*RESUME_PROVENANCE_MISSING*'
        }
        finally {
            Remove-Item -LiteralPath $root -Recurse -Force
        }
    }

    It 'stops when the external attestation names a different source commit' {
        $repo = Get-TestQualificationRepositoryRoot
        $qualificationId = 'Q_G28_W38'
        $item = Get-TestHistoricalManifestItem -QualificationId $qualificationId
        $qualificationRoot = Join-Path $repo 'experiments\sage_gpu\qualification'
        $resultsDirectory = Join-Path $qualificationRoot 'results'
        $attestationPath = Join-Path $qualificationRoot 'HISTORICAL_8_WINDOW_RUN_PROVENANCE_ATTESTATION.json'
        $tempAttestation = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-attestation-wrong-commit-' + [guid]::NewGuid().ToString('N') + '.json')
        try {
            $attestation = Get-Content -LiteralPath $attestationPath -Raw | ConvertFrom-Json
            $attestation.source_review_commit = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
            $attestation | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $tempAttestation -Encoding UTF8

            $failureMessage = $null
            try {
                [void](Get-GpuQualificationResumePlan -Manifest @($item) -ResultsDirectory $resultsDirectory -ExpectedFrozenSha256 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c' -AttestationPath $tempAttestation -RepositoryRoot $repo)
            }
            catch { $failureMessage = $_.Exception.Message }

            $failureMessage | Should BeLike '*RESUME_ATTESTATION_COMMIT_MISMATCH*'
        }
        finally {
            Remove-Item -LiteralPath $tempAttestation -Force -ErrorAction SilentlyContinue
        }
    }

    It 'requires an embedded Frozen SHA for current-layout future results' {
        $root = Join-Path ([System.IO.Path]::GetTempPath()) ('gpu-attestation-current-layout-' + [guid]::NewGuid().ToString('N'))
        $resultsDirectory = Join-Path $root 'results'
        $currentDirectory = Join-Path $resultsDirectory 'current'
        $null = New-Item -ItemType Directory -Path $currentDirectory -Force
        try {
            $item = Get-TestHistoricalManifestItem -QualificationId 'Q_G28_W38'
            $repo = Get-TestQualificationRepositoryRoot
            $source = Join-Path $repo 'experiments\sage_gpu\qualification\results\Q_G28_W38.json'
            $result = Get-Content -LiteralPath $source -Raw | ConvertFrom-Json
            $currentPath = Join-Path $currentDirectory ($item.qualification_id + '.json')
            $result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $currentPath -Encoding UTF8

            $failureMessage = $null
            try {
                [void](Get-GpuQualificationResumePlan -Manifest @($item) -ResultsDirectory $resultsDirectory -ExpectedFrozenSha256 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c' -AttestationPath (Join-Path $repo 'experiments\sage_gpu\qualification\HISTORICAL_8_WINDOW_RUN_PROVENANCE_ATTESTATION.json') -RepositoryRoot $repo)
            }
            catch { $failureMessage = $_.Exception.Message }

            $failureMessage | Should BeLike '*RESUME_PROVENANCE_MISSING*'
        }
        finally {
            Remove-Item -LiteralPath $root -Recurse -Force
        }
    }
}
