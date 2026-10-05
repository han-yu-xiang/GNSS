[CmdletBinding()]
param(
    [string]$ProjectRoot = 'E:\GNSS_Multipath_Project',
    [string]$MatlabPath = ''
)

$ErrorActionPreference = 'Stop'
$script:ExpectedFrozenSha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
$script:QualificationMarker = 'GPU_STAGE2_QUALIFICATION_JSON='
$script:ConfigMarker = 'GPU_STAGE2_CFG_IDENTITY='

$prnGuardPath = Join-Path $PSScriptRoot 'Assert-GpuQualificationPrnIdentity.ps1'
. $prnGuardPath

function ConvertTo-GpuQualificationNumericPrn {
    param([Parameter(Mandatory)][object]$Value)

    $text = ([string]$Value).Trim()
    if ($text -notmatch '^(?i:G)?(?<digits>\d{1,2})$') {
        throw 'INPUT_IDENTITY_VALIDATION=FAIL: invalid PRN in qualification metadata.'
    }
    return [int]::Parse($Matches['digits'], [System.Globalization.CultureInfo]::InvariantCulture)
}

function Normalize-GpuQualificationPath {
    param([Parameter(Mandatory)][string]$Path)
    return $Path.Replace('/', '\').TrimEnd('\')
}

function Assert-GpuQualificationWindowIdentity {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object]$ManifestItem,
        [Parameter(Mandatory)][object]$FormalTask,
        [Parameter(Mandatory)][object]$ProductionConfig,
        [Parameter(Mandatory)][object]$FormalWindow,
        [Parameter(Mandatory)][object]$HelperRequestedPrn
    )

    [void](Assert-GpuQualificationPrnIdentity `
        -ManifestPrn $ManifestItem.prn `
        -FormalTaskPrn $FormalTask.prn `
        -ProductionCfgPrn $ProductionConfig.targetPrn `
        -HelperRequestedPrn $HelperRequestedPrn)

    $checks = @(
        @('scene_id', [string]$ManifestItem.scene_id, [string]$FormalTask.scene_id),
        @('scene_id_cfg', [string]$ManifestItem.scene_id, [string]$ProductionConfig.sceneId),
        @('tracking_channel', [string]$ManifestItem.tracking_channel, [string]$FormalTask.tracking_channel),
        @('tracking_channel_cfg', [string]$ManifestItem.tracking_channel, [string]$ProductionConfig.trackingChannel),
        @('formal_output_path', (Normalize-GpuQualificationPath ([string]$ManifestItem.formal_output_path)), (Normalize-GpuQualificationPath ([string]$FormalTask.output_namespace))),
        @('window_id', [int]$ManifestItem.window_id, [int]$FormalWindow.windowId),
        @('recording_time_s', [double]$ManifestItem.recording_time_s, [double]$FormalWindow.recordingTimeS),
        @('production_selected_L', [int]$ManifestItem.production_selected_L, [int]$FormalWindow.selectedL),
        @('production_path_count', [int]$ManifestItem.production_path_count, [int]$FormalWindow.pathCount)
    )

    foreach ($check in $checks) {
        if ($check[1] -ne $check[2]) {
            throw "INPUT_IDENTITY_VALIDATION=FAIL: $($check[0]) manifest=$($check[1]) formal=$($check[2])."
        }
    }
    if ($null -ne $FormalWindow.PSObject.Properties['formalTimeValues']) {
        foreach ($timeValue in @($FormalWindow.formalTimeValues)) {
            if ([double]$ManifestItem.recording_time_s -ne [double]$timeValue) {
                throw "INPUT_IDENTITY_VALIDATION=FAIL: recording_time_s manifest=$($ManifestItem.recording_time_s) formal=$timeValue."
            }
        }
    }
    return $true
}

function Assert-GpuQualificationCpuReference {
    [CmdletBinding()]
    param([Parameter(Mandatory)][object]$CpuResult)

    $required = @(
        'cpu_production_selected_L_match',
        'cpu_production_path_count_match',
        'cpu_production_path_identity_match',
        'cpu_production_path_label_match',
        'cpu_production_model_validity_match'
    )
    foreach ($field in $required) {
        if ($CpuResult.$field -ne $true) {
            throw "CPU_PRODUCTION_REFERENCE=FAIL: $field is not true."
        }
    }
    return $true
}

function Invoke-GpuQualificationGpuAfterCpuReference {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object]$CpuResult,
        [Parameter(Mandatory)][scriptblock]$GpuProbe
    )
    [void](Assert-GpuQualificationCpuReference -CpuResult $CpuResult)
    return & $GpuProbe
}

function Invoke-GpuQualificationMatlab {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$Executable,
        [Parameter(Mandatory)][string]$Expression,
        [Parameter(Mandatory)][string]$WorkingDirectory
    )

    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $Executable
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    [void]$startInfo.ArgumentList.Add('-batch')
    [void]$startInfo.ArgumentList.Add($Expression)

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $started = $process.Start()
    if (-not $started) {
        throw 'MATLAB_PROCESS_START_FAILED'
    }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    return [pscustomobject]@{
        ExitCode = [int]$process.ExitCode
        Stdout = [string]$stdoutTask.Result
        Stderr = [string]$stderrTask.Result
    }
}

function ConvertTo-MatlabCharLiteral {
    param([Parameter(Mandatory)][string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function Get-GpuQualificationFormalWindow {
    param(
        [Parameter(Mandatory)][object]$ManifestItem,
        [Parameter(Mandatory)][object]$FormalTask,
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][hashtable]$CsvCache
    )

    $outputPath = Join-Path $ProjectRoot $FormalTask.output_namespace
    if (-not (Test-Path -LiteralPath $outputPath -PathType Container)) {
        throw "INPUT_IDENTITY_VALIDATION=FAIL: formal output path missing: $outputPath"
    }
    $stage0Path = Join-Path $outputPath 'stage0_valid_40ms_windows.csv'
    $stage1Path = Join-Path $outputPath 'stage1_nav_fast_scan.csv'
    $modelsPath = Join-Path $outputPath 'stage2_model_orders.csv'
    $pathsPath = Join-Path $outputPath 'stage2_selected_paths.csv'
    $selectedPath = Join-Path $outputPath 'stage2_selected_windows.csv'
    foreach ($path in @($stage0Path, $stage1Path, $modelsPath, $pathsPath, $selectedPath)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "INPUT_IDENTITY_VALIDATION=FAIL: formal Stage2/Stage0 file missing: $path"
        }
    }

    foreach ($path in @($stage0Path, $stage1Path, $modelsPath, $pathsPath, $selectedPath)) {
        if (-not $CsvCache.ContainsKey($path)) {
            $CsvCache[$path] = @(Import-Csv -LiteralPath $path)
        }
    }
    $windowId = [int]$ManifestItem.window_id
    $stage0Rows = @($CsvCache[$stage0Path] | Where-Object { [int]$_.window_id -eq $windowId })
    $stage1Rows = @($CsvCache[$stage1Path] | Where-Object { [int]$_.window_id -eq $windowId })
    $modelRows = @($CsvCache[$modelsPath] | Where-Object { [int]$_.window_id -eq $windowId } | Sort-Object { [int]$_.model_order })
    $selectedRows = @($CsvCache[$selectedPath] | Where-Object { [int]$_.window_id -eq $windowId })
    $pathRows = @($CsvCache[$pathsPath] | Where-Object { [int]$_.window_id -eq $windowId } | Sort-Object { [int]$_.path_id })

    if ($stage0Rows.Count -ne 1 -or $stage1Rows.Count -ne 1 -or $modelRows.Count -ne 4 -or $selectedRows.Count -ne 1) {
        throw "INPUT_IDENTITY_VALIDATION=FAIL: formal window $windowId does not have unique Stage0/Stage1/selected rows and four model rows."
    }
    $stage0 = $stage0Rows[0]
    $stage1 = $stage1Rows[0]
    $selectedModelRows = @($modelRows | Where-Object { $_.selected -eq '1' })
    if ($selectedModelRows.Count -ne 1 -or $pathRows.Count -ne [int]$selectedRows[0].selected_L) {
        throw "INPUT_IDENTITY_VALIDATION=FAIL: formal path/model row count mismatch for window $windowId."
    }
    $selectedL = [int]$selectedModelRows[0].model_order
    if ($selectedL -ne [int]$selectedRows[0].selected_L) {
        throw "INPUT_IDENTITY_VALIDATION=FAIL: formal selected L disagreement for window $windowId."
    }
    $allTimes = @(
        [double]$stage0.recording_time_s,
        [double]$stage1.recording_time_s,
        [double]$selectedRows[0].recording_time_s
    )
    foreach ($time in $modelRows) {
        $allTimes += [double]$time.recording_time_s
    }
    foreach ($pathRow in $pathRows) {
        $allTimes += [double]$pathRow.recording_time_s
    }

    return [pscustomobject]@{
        outputPath = $outputPath
        windowId = $windowId
        recordingTimeS = [double]$stage0.recording_time_s
        stage0RecordingTimeS = [double]$stage0.recording_time_s
        stage1RecordingTimeS = [double]$stage1.recording_time_s
        selectedL = $selectedL
        pathCount = $pathRows.Count
        modelRows = $modelRows
        pathRows = $pathRows
        stage0Row = $stage0
        stage1Row = $stage1
        formalTimeValues = $allTimes
    }
}

function Write-GpuQualificationAggregate {
    param(
        [Parameter(Mandatory)][object[]]$Results,
        [Parameter(Mandatory)][string]$CsvPath
    )
    if ($Results.Count -gt 0) {
        $Results | Export-Csv -LiteralPath $CsvPath -NoTypeInformation -Encoding UTF8
    }
}

function Write-GpuQualificationSummary {
    param(
        [Parameter(Mandatory)][object[]]$Results,
        [Parameter(Mandatory)][string]$Path
    )
    $completed = @($Results | Where-Object { $_.gpu_structural_equivalence -eq 'PASS' }).Count
    $cpuFailures = @($Results | Where-Object { $_.cpu_production_reference -eq 'FAIL' }).Count
    $gpuFailures = @($Results | Where-Object { $_.gpu_structural_equivalence -eq 'FAIL' }).Count
    $identityFailures = @($Results | Where-Object { $_.status -eq 'FAIL_IDENTITY' }).Count
    $cpuPasses = @($Results | Where-Object { $_.cpu_production_reference -eq 'PASS' }).Count
    $rawReads = @($Results | Where-Object { $_.raw_iq_read -eq 'YES' }).Count
    $retryTriggered = @($Results | Where-Object { $_.separation_retry_status -eq 'TRIGGERED' }).Count
    $retryNotTriggered = @($Results | Where-Object { $_.separation_retry_status -eq 'NOT_TRIGGERED' }).Count
    $retryUnknown = @($Results | Where-Object { $_.separation_retry_status -eq 'UNKNOWN' }).Count
    $status = if ($gpuFailures -gt 0) {
        'FAIL_GPU_STRUCTURE'
    } elseif ($cpuFailures -gt 0) {
        'FAIL_CPU_PRODUCTION_REFERENCE'
    } elseif ($identityFailures -gt 0) {
        'INCOMPLETE_STOPPED_ON_IDENTITY_MISMATCH'
    } elseif ($completed -eq 14 -and $retryNotTriggered -gt 0 -and $retryTriggered -gt 0) {
        'STRUCTURAL_PASS'
    } elseif ($completed -eq 14) {
        'STRUCTURAL_PASS_COVERAGE_INCOMPLETE'
    } else {
        'INCOMPLETE'
    }
    $lines = @(
        '# GPU Stage2 qualification summary',
        '',
        'Scope: the frozen 14-window qualification manifest only. This is experimental evidence, not production qualification.',
        '',
        'QUALIFICATION_WINDOWS_PLANNED=14',
        "QUALIFICATION_WINDOWS_EXECUTED=$completed",
        "CPU_PRODUCTION_REFERENCE_FAIL=$cpuFailures",
        "CPU_PRODUCTION_REFERENCE_PASS=$cpuPasses",
        "GPU_STRUCTURAL_FAIL=$gpuFailures",
        "IDENTITY_GATE_FAIL=$identityFailures",
        "WINDOWS_WITH_AUTHORIZED_RAW_IQ_READ=$rawReads",
        "RETRY_TRIGGERED_WINDOWS=$retryTriggered",
        "RETRY_NOT_TRIGGERED_WINDOWS=$retryNotTriggered",
        "RETRY_UNKNOWN_WINDOWS=$retryUnknown",
        "GPU_STAGE2_QUALIFICATION=$status",
        '',
        'Per-window machine-readable records are in `results/`; aggregate rows are in `GPU_STAGE2_QUALIFICATION_RESULTS.csv`.',
        '',
        $(if ($completed -eq 14) { 'All 14 completed; performance summaries may be computed from the preselected representative L1/L3/L4 windows.' } else { 'Performance median is not reported because the 14-window structural comparison did not complete.' }),
        '',
        'No raw IQ, MAT, HDF5, or large Stage output is part of the review bundle.',
        '',
        'Production GPU remains disabled; frozen CPU source remains unchanged; the remaining 85-task CPU batch remains paused.'
    )
    Set-Content -LiteralPath $Path -Value $lines -Encoding UTF8
    return $status
}

function Get-GpuQualificationMatlabJson {
    param(
        [Parameter(Mandatory)][object]$Invocation,
        [Parameter(Mandatory)][string]$Marker
    )
    if ($Invocation.ExitCode -ne 0) {
        throw "MATLAB_EXIT_NONZERO exit_code=$($Invocation.ExitCode) stdout=$($Invocation.Stdout) stderr=$($Invocation.Stderr)"
    }
    $line = @($Invocation.Stdout -split "`r?`n" | Where-Object { $_.Contains($Marker) } | Select-Object -Last 1)
    if ($line.Count -ne 1) {
        throw "MATLAB_MARKER_MISSING marker=$Marker stdout=$($Invocation.Stdout) stderr=$($Invocation.Stderr)"
    }
    $json = $line[0].Substring($line[0].IndexOf($Marker) + $Marker.Length).Trim()
    return ConvertFrom-Json -InputObject $json
}

function Invoke-GpuStage2Qualification {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][string]$ProjectRoot,
        [string]$MatlabPath = ''
    )

    $expectedSource = Join-Path $ProjectRoot 'scripts\sage_pipeline\run_nav_sage_pipeline.m'
    $actualHash = (Get-FileHash -LiteralPath $expectedSource -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -cne $script:ExpectedFrozenSha256) {
        throw "SAGE_SOURCE_HASH_MISMATCH expected=$script:ExpectedFrozenSha256 actual=$actualHash"
    }

    if ([string]::IsNullOrWhiteSpace($MatlabPath)) {
        $MatlabPath = (Get-Command matlab -CommandType Application -ErrorAction Stop).Source
    }
    if (-not (Test-Path -LiteralPath $MatlabPath -PathType Leaf)) {
        throw "MATLAB_EXECUTABLE_MISSING path=$MatlabPath"
    }

    $manifestPath = Join-Path $PSScriptRoot 'GPU_STAGE2_QUALIFICATION_MANIFEST.csv'
    $taskManifestPath = Join-Path $ProjectRoot 'reports\data_consolidation_20261003\MAINLINE_SAGE_1023_RERUN_MANIFEST.csv'
    $summaryPath = Join-Path $ProjectRoot 'reports\data_consolidation_20261003\MAINLINE_SAGE_1023_BATCH_RERUN_SUMMARY.csv'
    $manifest = @(Import-Csv -LiteralPath $manifestPath)
    $tasks = @(Import-Csv -LiteralPath $taskManifestPath)
    $batchRows = @(Import-Csv -LiteralPath $summaryPath)
    if ($manifest.Count -ne 14) {
        throw "QUALIFICATION_MANIFEST_COUNT_MISMATCH expected=14 actual=$($manifest.Count)"
    }

    $resultsDirectory = Join-Path $PSScriptRoot 'results'
    $aggregatePath = Join-Path $PSScriptRoot 'GPU_STAGE2_QUALIFICATION_RESULTS.csv'
    $summaryMarkdownPath = Join-Path $PSScriptRoot 'GPU_STAGE2_QUALIFICATION_SUMMARY.md'
    foreach ($path in @($resultsDirectory, $aggregatePath, $summaryMarkdownPath)) {
        if (Test-Path -LiteralPath $path) {
            throw "QUALIFICATION_OUTPUT_ALREADY_EXISTS path=$path; refusing resume or overwrite."
        }
    }
    $null = New-Item -ItemType Directory -Path $resultsDirectory
    $csvCache = @{}
    $results = [System.Collections.Generic.List[object]]::new()
    $stopReason = $null
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('gnss_gpu_qualification_' + [guid]::NewGuid().ToString('N'))
    $null = New-Item -ItemType Directory -Path $tempRoot

    try {
        foreach ($item in $manifest) {
            $taskMatches = @($tasks | Where-Object {
                $_.scene_id -eq $item.scene_id -and $_.prn -eq $item.prn -and $_.tracking_channel -eq $item.tracking_channel
            })
            if ($taskMatches.Count -ne 1) {
                $stopReason = "INPUT_IDENTITY_VALIDATION=FAIL: expected one formal task row; found $($taskMatches.Count)."
                $formalTask = $null
                $formalWindow = $null
                $productionConfig = $null
            } else {
                $formalTask = $taskMatches[0]
                $summaryMatches = @($batchRows | Where-Object { $_.run_id -eq $formalTask.run_id })
                if ($summaryMatches.Count -ne 1 -or $summaryMatches[0].execution_status -notin @('COMPLETE', 'ALREADY_COMPLETE')) {
                    $stopReason = "FORMAL_TASK_NOT_COMPLETE run_id=$($formalTask.run_id)"
                    $formalWindow = $null
                    $productionConfig = $null
                } else {
                    try {
                        $formalWindow = Get-GpuQualificationFormalWindow -ManifestItem $item -FormalTask $formalTask -ProjectRoot $ProjectRoot -CsvCache $csvCache
                        $outputUnix = $formalWindow.outputPath.Replace('\', '/')
                        $matlabPathLiteral = ConvertTo-MatlabCharLiteral $outputUnix
                        $cfgExpression = "s=load(fullfile($matlabPathLiteral,'stage2_nav_progress.mat'),'cfg'); c=s.cfg; q=struct('sceneId',string(c.sceneId),'targetPrn',double(c.targetPrn),'trackingChannel',double(c.trackingChannel)); disp(['$script:ConfigMarker',char(jsonencode(q))]);"
                        $cfgInvocation = Invoke-GpuQualificationMatlab -Executable $MatlabPath -Expression $cfgExpression -WorkingDirectory $ProjectRoot
                        $productionConfig = Get-GpuQualificationMatlabJson -Invocation $cfgInvocation -Marker $script:ConfigMarker
                        [void](Assert-GpuQualificationWindowIdentity -ManifestItem $item -FormalTask $formalTask -ProductionConfig $productionConfig -FormalWindow $formalWindow -HelperRequestedPrn (ConvertTo-GpuQualificationNumericPrn $item.prn))
                    }
                    catch {
                        $stopReason = $_.Exception.Message
                    }
                }
            }

            $record = [ordered]@{
                qualification_id = [string]$item.qualification_id
                scene_id = [string]$item.scene_id
                prn = [string]$item.prn
                tracking_channel = [string]$item.tracking_channel
                window_id = [int]$item.window_id
                recording_time_s = [double]$item.recording_time_s
                production_selected_L = [int]$item.production_selected_L
                cpu_selected_L = $null
                gpu_selected_L = $null
                production_path_count = [int]$item.production_path_count
                cpu_path_count = $null
                gpu_path_count = $null
                cpu_production_reference = 'NOT_RUN'
                gpu_structural_equivalence = 'NOT_RUN'
                selected_L_match = 'NA'
                path_count_match = 'NA'
                path_identity_match = 'NA'
                path_label_match = 'NA'
                model_validity_match = 'NA'
                max_delay_abs_diff = $null
                max_doppler_abs_diff = $null
                max_relative_power_abs_diff = $null
                max_alpha_abs_diff = $null
                max_path_score_abs_diff = $null
                max_rss_abs_diff = $null
                max_rss_rel_diff = $null
                max_bic_abs_diff = $null
                max_bic_rel_diff = $null
                cpu_best_l = $null
                cpu_second_best_l = $null
                cpu_bic_margin = $null
                gpu_best_l = $null
                gpu_second_best_l = $null
                gpu_bic_margin = $null
                cpu_stage2_seconds = $null
                gpu_first_stage2_seconds = $null
                gpu_warm_stage2_seconds = $null
                gpu_transfer_in_seconds = $null
                gpu_transfer_out_seconds = $null
                compute_speedup = $null
                end_to_end_warm_speedup = $null
                cpu_production_max_delay_abs_diff = $null
                cpu_production_max_doppler_abs_diff = $null
                cpu_production_max_relative_power_abs_diff = $null
                cpu_production_max_alpha_abs_diff = $null
                cpu_production_max_path_score_abs_diff = $null
                cpu_production_max_rss_abs_diff = $null
                cpu_production_max_rss_rel_diff = $null
                cpu_production_max_bic_abs_diff = $null
                cpu_production_max_bic_rel_diff = $null
                separation_retry_status = 'UNKNOWN'
                raw_iq_read = 'NO'
                raw_iq_samples = 0
                status = 'NOT_STARTED'
                notes = ''
            }

            if ($null -ne $stopReason) {
                $record.status = if ($stopReason -like '*INPUT_IDENTITY_VALIDATION=FAIL*') { 'FAIL_IDENTITY' } else { 'FAIL_PREFLIGHT' }
                $record.notes = $stopReason
                if ($null -ne $formalWindow) {
                    $record.notes += " manifest_time=$($item.recording_time_s) formal_stage0_time=$($formalWindow.recordingTimeS)"
                }
                $recordJsonPath = Join-Path $resultsDirectory ($item.qualification_id + '.json')
                [pscustomobject]$record | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $recordJsonPath -Encoding UTF8
                $results.Add([pscustomobject]$record)
                Write-GpuQualificationAggregate -Results $results.ToArray() -CsvPath $aggregatePath
                break
            }

            $taskRoot = Join-Path $ProjectRoot $formalTask.output_namespace
            $rawRow = $formalTask
            if (-not (Test-Path -LiteralPath $rawRow.raw_path -PathType Leaf)) {
                $record.status = 'FAIL_IDENTITY'
                $record.notes = 'INPUT_IDENTITY_VALIDATION=FAIL: raw path does not exist.'
            } else {
                $helperRequestedPrn = ConvertTo-GpuQualificationNumericPrn $item.prn
                $qPayload = [ordered]@{
                    qualificationId = [string]$item.qualification_id
                    manifestPrn = [string]$item.prn
                    formalTaskPrn = [string]$formalTask.prn
                    helperRequestedPrn = $helperRequestedPrn
                    sceneId = [string]$item.scene_id
                    trackingChannel = [int]$item.tracking_channel
                    formalOutputPath = [string]$formalWindow.outputPath
                    windowId = [int]$item.window_id
                    recordingTimeS = [double]$item.recording_time_s
                    productionSelectedL = [int]$item.production_selected_L
                    productionPathCount = [int]$item.production_path_count
                }
                $qJsonPath = Join-Path $tempRoot ($item.qualification_id + '.json')
                $scratchPath = Join-Path $tempRoot ($item.qualification_id + '_cpu.mat')
                $gpuMatPath = Join-Path $tempRoot ($item.qualification_id + '_gpu.mat')
                $gpuJsonPath = Join-Path $tempRoot ($item.qualification_id + '_gpu.json')
                $qJsonText = $qPayload | ConvertTo-Json -Depth 8
                [System.IO.File]::WriteAllText($qJsonPath, $qJsonText, [System.Text.UTF8Encoding]::new($false))
                $helperPath = (Join-Path $PSScriptRoot '..\stage2_window_173_probe.m').Replace('\', '/')
                $qPathLiteral = ConvertTo-MatlabCharLiteral $qJsonPath.Replace('\', '/')
                $outPathLiteral = ConvertTo-MatlabCharLiteral $formalWindow.outputPath.Replace('\', '/')
                $rawPathLiteral = ConvertTo-MatlabCharLiteral ([string]$formalTask.raw_path).Replace('\', '/')
                $scratchLiteral = ConvertTo-MatlabCharLiteral $scratchPath.Replace('\', '/')
                $helperDirectory = Split-Path -Parent $helperPath
                $cpuExpression = "addpath('$helperDirectory'); q=jsondecode(fileread($qPathLiteral)); r=stage2_window_173_probe($outPathLiteral,$rawPathLiteral,$scratchLiteral,$helperRequestedPrn,q); disp(['$script:QualificationMarker',char(jsonencode(r))]);"
                try {
                    $record.raw_iq_read = 'UNKNOWN'
                    $cpuInvocation = Invoke-GpuQualificationMatlab -Executable $MatlabPath -Expression $cpuExpression -WorkingDirectory $ProjectRoot
                    $cpuResult = Get-GpuQualificationMatlabJson -Invocation $cpuInvocation -Marker $script:QualificationMarker
                    $record.raw_iq_read = 'YES'
                    $record.raw_iq_samples = [int]$cpuResult.raw_samples_requested
                    $record.cpu_stage2_seconds = [double]$cpuResult.cpu_compute_seconds
                    $record.cpu_selected_L = [int]$cpuResult.cpu_selected_L
                    $record.cpu_path_count = [int]$cpuResult.cpu_path_count
                    $record.cpu_production_reference = [string]$cpuResult.cpu_production_reference
                    $record.cpu_production_max_delay_abs_diff = $cpuResult.max_delay_abs_diff
                    $record.cpu_production_max_doppler_abs_diff = $cpuResult.max_doppler_abs_diff
                    $record.cpu_production_max_relative_power_abs_diff = $cpuResult.max_relative_power_abs_diff
                    $record.cpu_production_max_alpha_abs_diff = $cpuResult.max_alpha_abs_diff
                    $record.cpu_production_max_path_score_abs_diff = $cpuResult.max_path_score_abs_diff
                    $record.cpu_production_max_rss_abs_diff = $cpuResult.max_rss_abs_diff
                    $record.cpu_production_max_rss_rel_diff = $cpuResult.max_rss_rel_diff
                    $record.cpu_production_max_bic_abs_diff = $cpuResult.max_bic_abs_diff
                    $record.cpu_production_max_bic_rel_diff = $cpuResult.max_bic_rel_diff
                    $record.cpu_best_l = $cpuResult.cpu_best_l
                    $record.cpu_second_best_l = $cpuResult.cpu_second_best_l
                    $record.cpu_bic_margin = $cpuResult.cpu_bic_margin

                    if ([string]$cpuResult.cpu_production_reference -ne 'PASS') {
                        $record.status = 'CPU_PRODUCTION_REFERENCE_FAIL'
                        $record.notes = 'Experimental CPU helper did not reproduce the formal Frozen CPU Stage2 structure; GPU was not invoked.'
                        throw 'CPU_PRODUCTION_REFERENCE=FAIL'
                    }
                    [void](Assert-GpuQualificationCpuReference -CpuResult $cpuResult)

                    $gpuHelperPath = (Join-Path $PSScriptRoot '..\stage2_window_173_gpu_probe.m').Replace('\', '/')
                    $gpuMatLiteral = ConvertTo-MatlabCharLiteral $gpuMatPath.Replace('\', '/')
                    $gpuJsonLiteral = ConvertTo-MatlabCharLiteral $gpuJsonPath.Replace('\', '/')
                    $scratchMatLiteral = ConvertTo-MatlabCharLiteral $scratchPath.Replace('\', '/')
                    $gpuHelperDirectory = Split-Path -Parent $gpuHelperPath
                    $gpuExpression = "addpath('$gpuHelperDirectory'); g=stage2_window_173_gpu_probe($scratchMatLiteral,$gpuMatLiteral,$helperRequestedPrn); q=stage2_qualification_compare($scratchMatLiteral,$gpuMatLiteral,$gpuJsonLiteral); disp(['$script:QualificationMarker',char(jsonencode(q))]);"
                    $gpuInvocation = Invoke-GpuQualificationGpuAfterCpuReference -CpuResult $cpuResult -GpuProbe {
                        Invoke-GpuQualificationMatlab -Executable $MatlabPath -Expression $gpuExpression -WorkingDirectory $ProjectRoot
                    }
                    $gpuResult = Get-GpuQualificationMatlabJson -Invocation $gpuInvocation -Marker $script:QualificationMarker
                    $record.gpu_selected_L = [int]$gpuResult.gpu_selected_L
                    $record.gpu_path_count = [int]$gpuResult.gpu_path_count
                    $record.gpu_structural_equivalence = [string]$gpuResult.gpu_structural_equivalence
                    $record.selected_L_match = [string]$gpuResult.selected_L_match
                    $record.path_count_match = [string]$gpuResult.path_count_match
                    $record.path_identity_match = [string]$gpuResult.path_identity_match
                    $record.path_label_match = [string]$gpuResult.path_label_match
                    $record.model_validity_match = [string]$gpuResult.model_validity_match
                    $record.max_delay_abs_diff = $gpuResult.max_delay_abs_diff
                    $record.max_doppler_abs_diff = $gpuResult.max_doppler_abs_diff
                    $record.max_relative_power_abs_diff = $gpuResult.max_relative_power_abs_diff
                    $record.max_alpha_abs_diff = $gpuResult.max_alpha_abs_diff
                    $record.max_path_score_abs_diff = $gpuResult.max_path_score_abs_diff
                    $record.max_rss_abs_diff = $gpuResult.max_rss_abs_diff
                    $record.max_rss_rel_diff = $gpuResult.max_rss_rel_diff
                    $record.max_bic_abs_diff = $gpuResult.max_bic_abs_diff
                    $record.max_bic_rel_diff = $gpuResult.max_bic_rel_diff
                    $record.gpu_best_l = $gpuResult.gpu_best_l
                    $record.gpu_second_best_l = $gpuResult.gpu_second_best_l
                    $record.gpu_bic_margin = $gpuResult.gpu_bic_margin
                    $record.gpu_first_stage2_seconds = [double]$gpuResult.gpu_first_stage2_time
                    $record.gpu_warm_stage2_seconds = [double]$gpuResult.gpu_warm_stage2_time
                    $record.gpu_transfer_in_seconds = [double]$gpuResult.gpu_transfer_in_time
                    $record.gpu_transfer_out_seconds = [double]$gpuResult.gpu_transfer_out_time
                    $record.compute_speedup = [double]$gpuResult.compute_speedup
                    $record.end_to_end_warm_speedup = [double]$gpuResult.gpu_end_to_end_warm_speedup
                    $record.separation_retry_status = [string]$gpuResult.separation_retry_status
                    $record.status = if ($record.gpu_structural_equivalence -eq 'PASS') { 'COMPLETE' } else { 'GPU_STRUCTURAL_FAIL' }
                    if ($record.status -eq 'GPU_STRUCTURAL_FAIL') {
                        $record.notes = 'GPU structural mismatch; qualification stopped immediately.'
                    }
                }
                catch {
                    if ($record.status -eq 'NOT_STARTED') {
                        $message = $_.Exception.Message
                        if ($message -like '*CPU_PRODUCTION_REFERENCE=FAIL*') {
                            $record.status = 'CPU_PRODUCTION_REFERENCE_FAIL'
                            $record.cpu_production_reference = 'FAIL'
                        } elseif ($message -like '*GPU_STRUCTURAL_EQUIVALENCE=FAIL*') {
                            $record.status = 'GPU_STRUCTURAL_FAIL'
                            $record.gpu_structural_equivalence = 'FAIL'
                        } else {
                            $record.status = 'HELPER_FAILURE'
                        }
                        $record.notes = $message
                    }
                }
            }

            $recordPath = Join-Path $resultsDirectory ($item.qualification_id + '.json')
            [pscustomobject]$record | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $recordPath -Encoding UTF8
            $results.Add([pscustomobject]$record)
            Write-GpuQualificationAggregate -Results $results.ToArray() -CsvPath $aggregatePath
            if ($record.status -ne 'COMPLETE') {
                break
            }
        }
    }
    finally {
        $afterHash = (Get-FileHash -LiteralPath $expectedSource -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($afterHash -cne $script:ExpectedFrozenSha256) {
            throw "SAGE_SOURCE_HASH_CHANGED during qualification expected=$script:ExpectedFrozenSha256 actual=$afterHash"
        }
        if ($results.Count -gt 0) {
            [void](Write-GpuQualificationSummary -Results $results.ToArray() -Path $summaryMarkdownPath)
        }
    }
}

if ($MyInvocation.InvocationName -ne '.') {
    Invoke-GpuStage2Qualification -ProjectRoot $ProjectRoot -MatlabPath $MatlabPath
}
