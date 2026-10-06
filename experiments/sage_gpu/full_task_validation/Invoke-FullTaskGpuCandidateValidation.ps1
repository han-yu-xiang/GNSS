[CmdletBinding()]
param(
    [ValidateSet('RunUnitTests', 'Preflight', 'RunAndCompare')]
    [string]$Action,
    [ValidateSet('TaskA', 'TaskB')]
    [string]$Task
)

$ErrorActionPreference = 'Stop'

$script:FrozenProjectRoot = 'E:/GNSS_Multipath_Project'
$script:FrozenAuthorityPath = 'E:/GNSS_Multipath_Project/scripts/sage_pipeline/run_nav_sage_pipeline.m'
$script:FrozenAuthoritySha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
$script:CandidateProjectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$script:QualifiedGpuProbePath = Join-Path $script:CandidateProjectRoot 'experiments/sage_gpu/stage2_window_173_gpu_probe.m'
$script:QualifiedGpuProbeSha256 = 'bfe56ad02c99240257fddd212ba43ee5606a81740b3dda716c5947c433cbfa88'
$script:QualifiedSelectorPath = Join-Path $script:CandidateProjectRoot 'experiments/sage_gpu/selectSeparatedResidualCandidate.m'
$script:QualifiedSelectorSha256 = 'a40c6459e66a384e85053589b270c5d2e112363872153fbf46da5c56fd4bb1f5'
$script:CandidateChangedFunctionCategories = @{
    fitAllOrders = 'GPU_STAGE2_COMPUTATIONAL_DIFFERENCE'
}
$script:QualifiedGpuCandidateFunctions = @(
    'fitAllOrdersGpu', 'initializeResidualPathGpu', 'runSageGpu',
    'evaluateModelGpu', 'gridSearchPathGpu', 'refinePathGpu',
    'scoreReplicaBatchGpu', 'makeReplicaBatchGpu', 'buildReplicasGpu',
    'solveAmplitudesGpu', 'synthesizeGpu', 'residualRssGpu',
    'replicaCoherenceGpu', 'ensureGpuPathState', 'pathAlphaGpu',
    'gatherGpuFit', 'gpuProbeToCpu'
)
$script:CandidatePlumbingFunctionCategories = @{
    run_nav_sage_pipeline_gpu_candidate = 'NON_SCIENTIFIC_PLUMBING_DIFF'
    resolveInputs = 'NON_SCIENTIFIC_PLUMBING_DIFF'
    assertFrozenSageSourceHash = 'NON_SCIENTIFIC_PLUMBING_DIFF'
    getCandidateTaskSpec = 'NON_SCIENTIFIC_PLUMBING_DIFF'
    assertCandidateTaskIdentity = 'NON_SCIENTIFIC_PLUMBING_DIFF'
    readReferenceRunContext = 'NON_SCIENTIFIC_PLUMBING_DIFF'
    assertReferenceContextIdentity = 'NON_SCIENTIFIC_PLUMBING_DIFF'
    resolveCandidateNamespace = 'NON_SCIENTIFIC_PLUMBING_DIFF'
    assertGpuAvailability = 'NON_SCIENTIFIC_PLUMBING_DIFF'
    assertCandidateOutputAbsent = 'NON_SCIENTIFIC_PLUMBING_DIFF'
    normalizeCandidatePath = 'NON_SCIENTIFIC_PLUMBING_DIFF'
    computeFileSha256 = 'PROVENANCE_INSTRUMENTATION'
    writeCandidateProvenance = 'PROVENANCE_INSTRUMENTATION'
}
$script:CandidateTasks = @{
    TaskA = [pscustomobject]@{
        Task = 'TaskA'
        SceneId = 'F1023_V70_D0117_P2'
        Prn = 28
        PrnLabel = 'G28'
        TrackingChannel = 1
        SampleRateHz = 10230000
        CandidateOutputNamespace = 'scenes/F1023_V70_D0117_P2/sage_results/gpu_candidate_fulltask_20261005/G28_ch1'
        ReferenceOutputNamespace = 'scenes/F1023_V70_D0117_P2/sage_results/rerun_20261003_frozen_v3/G28_ch1'
    }
    TaskB = [pscustomobject]@{
        Task = 'TaskB'
        SceneId = 'F1023_V120_D0121_P2'
        Prn = 3
        PrnLabel = 'G03'
        TrackingChannel = 2
        SampleRateHz = 10230000
        CandidateOutputNamespace = 'scenes/F1023_V120_D0121_P2/sage_results/gpu_candidate_fulltask_20261005/G03_ch2'
        ReferenceOutputNamespace = 'scenes/F1023_V120_D0121_P2/sage_results/rerun_20261003_frozen_v3/G03_ch2'
    }
}
$script:StartupMarker = 'MATLAB_STARTUP_OK'
$script:TransportMarker = 'MATLAB_ARGUMENT_TRANSPORT_OK'
$script:FunctionResolutionMarker = 'MATLAB_FUNCTION_RESOLUTION_OK'
$script:GpuPreflightMarker = 'MATLAB_GPU_PREFLIGHT_OK'
$script:FullTaskGpuResultColumns = @(
    'task','scene_id','prn','tracking_channel',
    'stage0_status','stage1_status','stage2_status','stage3_status','stage4_status',
    'stage2_evaluated_windows','stage2_model_rows','stage2_selected_rows',
    'stage2_path_rows','stage2_direct_rows','stage2_mpc_rows',
    'stage3_persistence_rows','stage3_reliable_centers',
    'stage4_joint_results','stage4_joint_path_rows','stage4_confirmation_match',
    'max_delay_abs_diff','max_doppler_abs_diff','max_relative_power_abs_diff',
    'max_alpha_abs_diff','max_path_score_abs_diff','max_rss_abs_diff',
    'max_rss_rel_diff','max_bic_abs_diff','max_bic_rel_diff',
    'frozen_source_sha256','candidate_source_sha256','gpu_identity','task_status',
    'failure_identifier','failure_message','candidate_namespace','failure_timestamp_utc'
)
$script:FullTaskGpuWindowColumns = @(
    'task','scene_id','prn','tracking_channel','window_id','recording_time_s',
    'cpu_selected_L','gpu_selected_L','selected_L_match','path_count',
    'path_identity_match','path_label_match','model_validity_match',
    'max_delay_abs_diff','max_doppler_abs_diff','max_relative_power_abs_diff',
    'max_alpha_abs_diff','max_path_score_abs_diff','max_rss_abs_diff','max_bic_abs_diff'
)
for ($order = 1; $order -le 4; $order++) {
    $script:FullTaskGpuWindowColumns += "L${order}_valid_cpu", "L${order}_valid_gpu"
}
foreach ($transition in 1..3) {
    $prefix = "L${transition}_to_L$($transition + 1)"
    foreach ($suffix in @(
        'checked_cpu','checked_gpu','model_valid_cpu','model_valid_gpu',
        'bic_gain_cpu','bic_gain_gpu','bic_threshold_cpu','bic_threshold_gpu',
        'bic_surplus_cpu','bic_surplus_gpu','rss_gain_percent_cpu',
        'rss_gain_percent_gpu','rss_threshold_cpu','rss_threshold_gpu',
        'rss_surplus_cpu','rss_surplus_gpu','accepted_cpu','accepted_gpu'
    )) {
        $script:FullTaskGpuWindowColumns += "${prefix}_${suffix}"
    }
}
$script:TransportSmokeExpression = "a='F1023_V70_D0117_P2';b='TrackingChannel';c='E:/GNSS_Multipath_Project';assert(strcmp(a,'F1023_V70_D0117_P2'));assert(strcmp(b,'TrackingChannel'));assert(strcmp(c,'E:/GNSS_Multipath_Project'));disp('MATLAB_ARGUMENT_TRANSPORT_OK')"

function Get-FullTaskGpuTaskSpec {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][ValidateSet('TaskA', 'TaskB')][string]$Task)
    return $script:CandidateTasks[$Task]
}

function Get-FullTaskGpuEvidencePaths {
    [CmdletBinding()]
    param([string]$EvidenceDirectory)
    if ([string]::IsNullOrWhiteSpace($EvidenceDirectory)) {
        $EvidenceDirectory = Join-Path $script:CandidateProjectRoot 'experiments/sage_gpu/full_task_validation'
    }
    $EvidenceDirectory = [IO.Path]::GetFullPath($EvidenceDirectory)
    return [pscustomobject]@{
        Directory = $EvidenceDirectory
        ResultsCsv = Join-Path $EvidenceDirectory 'FULL_TASK_GPU_VALIDATION_RESULTS.csv'
        WindowCsv = Join-Path $EvidenceDirectory 'FULL_TASK_GPU_STAGE2_WINDOW_COMPARISON.csv'
        Summary = Join-Path $EvidenceDirectory 'FULL_TASK_GPU_VALIDATION_SUMMARY.md'
    }
}

function Get-FullTaskGpuEvidenceKey {
    param([Parameter(Mandatory = $true)][object]$Value)
    return '{0}|{1}|{2}|{3}' -f [string]$Value.task, [string]$Value.scene_id, `
        [string]$Value.prn, [string]$Value.tracking_channel
}

function Assert-NoExistingFullTaskGpuEvidence {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$TaskSpec,
        [string]$EvidenceDirectory
    )
    $paths = Get-FullTaskGpuEvidencePaths -EvidenceDirectory $EvidenceDirectory
    $hasResults = Test-Path -LiteralPath $paths.ResultsCsv -PathType Leaf
    $hasWindows = Test-Path -LiteralPath $paths.WindowCsv -PathType Leaf
    if ($hasResults -ne $hasWindows) {
        throw 'FULL_TASK_GPU_EVIDENCE_FILES_INCONSISTENT'
    }
    if (-not $hasResults) { return $true }

    $requiredResultColumns = $script:FullTaskGpuResultColumns
    $resultHeader = @((Get-Content -LiteralPath $paths.ResultsCsv -TotalCount 1) -split ',')
    if ($resultHeader.Count -ne $requiredResultColumns.Count -or
            [string]::Join(',', $resultHeader) -cne [string]::Join(',', $requiredResultColumns)) {
        throw 'FULL_TASK_GPU_RESULTS_SCHEMA_MISMATCH'
    }
    $windowHeader = @((Get-Content -LiteralPath $paths.WindowCsv -TotalCount 1) -split ',')
    if ($windowHeader.Count -ne $script:FullTaskGpuWindowColumns.Count -or
            [string]::Join(',', $windowHeader) -cne [string]::Join(',', $script:FullTaskGpuWindowColumns)) {
        throw 'FULL_TASK_GPU_WINDOW_SCHEMA_MISMATCH'
    }
    $resultRows = @(Import-Csv -LiteralPath $paths.ResultsCsv)
    $windowRows = @(Import-Csv -LiteralPath $paths.WindowCsv)
    $key = '{0}|{1}|{2}|{3}' -f $TaskSpec.Task, $TaskSpec.SceneId, $TaskSpec.Prn, $TaskSpec.TrackingChannel
    foreach ($row in $resultRows) {
        if ((Get-FullTaskGpuEvidenceKey -Value $row) -ceq $key) {
            throw "FULL_TASK_GPU_TASK_EVIDENCE_ALREADY_EXISTS task=$($TaskSpec.Task)"
        }
    }
    foreach ($row in $windowRows) {
        if ((Get-FullTaskGpuEvidenceKey -Value $row) -ceq $key) {
            throw "FULL_TASK_GPU_TASK_EVIDENCE_ALREADY_EXISTS task=$($TaskSpec.Task)"
        }
    }
    return $true
}

function Add-FullTaskGpuFailureReceipt {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$TaskSpec,
        [Parameter(Mandatory = $true)][string]$FailureIdentifier,
        [Parameter(Mandatory = $true)][string]$FailureMessage,
        [string]$GpuIdentity = 'NOT_RECORDED',
        [string]$EvidenceDirectory
    )
    $paths = Get-FullTaskGpuEvidencePaths -EvidenceDirectory $EvidenceDirectory
    if (-not (Test-Path -LiteralPath $paths.Directory -PathType Container)) {
        New-Item -ItemType Directory -Path $paths.Directory -Force | Out-Null
    }
    Assert-NoExistingFullTaskGpuEvidence -TaskSpec $TaskSpec `
        -EvidenceDirectory $paths.Directory | Out-Null

    $failureMessageFlat = [regex]::Replace($FailureMessage, '[\r\n]+', ' ').Trim()
    if ($failureMessageFlat.Length -gt 2000) {
        $failureMessageFlat = $failureMessageFlat.Substring(0, 2000) + '...'
    }
    $candidateHash = if (Test-Path -LiteralPath (Join-Path $script:CandidateProjectRoot 'experiments/sage_gpu/full_task_candidate/run_nav_sage_pipeline_gpu_candidate.m') -PathType Leaf) {
        (Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $script:CandidateProjectRoot 'experiments/sage_gpu/full_task_candidate/run_nav_sage_pipeline_gpu_candidate.m')).Hash.ToLowerInvariant()
    } else { 'NOT_AVAILABLE' }
    $values = [ordered]@{}
    foreach ($column in $script:FullTaskGpuResultColumns) { $values[$column] = '' }
    $values.task = $TaskSpec.Task
    $values.scene_id = $TaskSpec.SceneId
    $values.prn = [string]$TaskSpec.Prn
    $values.tracking_channel = [string]$TaskSpec.TrackingChannel
    foreach ($stage in 0..4) { $values["stage${stage}_status"] = 'NOT_VERIFIED' }
    $values.frozen_source_sha256 = $script:FrozenAuthoritySha256
    $values.candidate_source_sha256 = $candidateHash
    $values.gpu_identity = $GpuIdentity
    $values.task_status = 'FAIL'
    $values.failure_identifier = $FailureIdentifier
    $values.failure_message = $failureMessageFlat
    $values.candidate_namespace = $TaskSpec.CandidateOutputNamespace
    $values.failure_timestamp_utc = [DateTimeOffset]::UtcNow.ToString('o')
    $newRow = [pscustomobject]$values

    $existingRows = @()
    if (Test-Path -LiteralPath $paths.ResultsCsv -PathType Leaf) {
        $existingHeader = @((Get-Content -LiteralPath $paths.ResultsCsv -TotalCount 1) -split ',')
        if ($existingHeader.Count -ne $script:FullTaskGpuResultColumns.Count -or
                [string]::Join(',', $existingHeader) -cne [string]::Join(',', $script:FullTaskGpuResultColumns)) {
            throw 'FULL_TASK_GPU_RESULTS_SCHEMA_MISMATCH'
        }
        $existingRows = @(Import-Csv -LiteralPath $paths.ResultsCsv)
    }
    $temporaryPath = Join-Path $paths.Directory ('.FULL_TASK_GPU_VALIDATION_RESULTS.' + [guid]::NewGuid().ToString('N') + '.tmp')
    try {
        @($existingRows) + @($newRow) | Export-Csv -LiteralPath $temporaryPath -NoTypeInformation -Encoding utf8
        Move-Item -LiteralPath $temporaryPath -Destination $paths.ResultsCsv -Force
    }
    finally {
        if (Test-Path -LiteralPath $temporaryPath -PathType Leaf) {
            Remove-Item -LiteralPath $temporaryPath -Force
        }
    }
    return $newRow
}

function Update-FullTaskGpuValidationSummary {
    [CmdletBinding()]
    param(
        [string]$EvidenceDirectory,
        [string]$GpuIdentity = 'NOT_RECORDED'
    )
    $paths = Get-FullTaskGpuEvidencePaths -EvidenceDirectory $EvidenceDirectory
    $results = @()
    $windows = @()
    if (Test-Path -LiteralPath $paths.ResultsCsv -PathType Leaf) {
        $results = @(Import-Csv -LiteralPath $paths.ResultsCsv)
    }
    if (Test-Path -LiteralPath $paths.WindowCsv -PathType Leaf) {
        $windows = @(Import-Csv -LiteralPath $paths.WindowCsv)
    }

    $lines = New-Object 'System.Collections.Generic.List[string]'
    $lines.Add('# Full-Task GPU Candidate Validation')
    $lines.Add('')
    $lines.Add('This is a lightweight run-level validation record, not a project handoff or a production result.')
    $lines.Add('')
    $statusByTask = @{}
    foreach ($taskName in @('TaskA', 'TaskB')) {
        $row = @($results | Where-Object { $_.task -ceq $taskName } | Select-Object -First 1)
        if ($row.Count -eq 0) { $statusByTask[$taskName] = 'NOT_RUN' }
        else { $statusByTask[$taskName] = [string]$row[0].task_status }
    }
    $lines.Add('```ini')
    $lines.Add("TASK_A=$($statusByTask.TaskA)")
    $lines.Add("TASK_B=$($statusByTask.TaskB)")
    $lines.Add("FROZEN_SHA=$script:FrozenAuthoritySha256")
    $candidatePath = Join-Path $script:CandidateProjectRoot 'experiments/sage_gpu/full_task_candidate/run_nav_sage_pipeline_gpu_candidate.m'
    $candidateSha = if (Test-Path -LiteralPath $candidatePath -PathType Leaf) {
        (Get-FileHash -Algorithm SHA256 -LiteralPath $candidatePath).Hash.ToLowerInvariant()
    } else { 'NOT_AVAILABLE' }
    $lines.Add("CANDIDATE_SHA=$candidateSha")
    $gpuRows = @($results | Where-Object { -not [string]::IsNullOrWhiteSpace($_.gpu_identity) } | Select-Object -First 1)
    if ($gpuRows.Count -gt 0) { $GpuIdentity = [string]$gpuRows[0].gpu_identity }
    $lines.Add("GPU_IDENTITY=$GpuIdentity")
    $lines.Add('```')
    $lines.Add('')

    foreach ($taskName in @('TaskA', 'TaskB')) {
        $row = @($results | Where-Object { $_.task -ceq $taskName } | Select-Object -First 1)
        $lines.Add("## $taskName")
        $lines.Add('')
        if ($row.Count -eq 0) {
            $lines.Add('Status: `NOT_RUN`.')
            $lines.Add('')
            continue
        }
        $value = $row[0]
        $prnLabel = 'G{0:D2}' -f [int]$value.prn
        $lines.Add("Task status: ``$($value.task_status)``")
        $lines.Add("Scene/PRN/channel: ``$($value.scene_id) / $prnLabel / ch$($value.tracking_channel)``")
        $lines.Add("Stage0–Stage4: ``$($value.stage0_status) / $($value.stage1_status) / $($value.stage2_status) / $($value.stage3_status) / $($value.stage4_status)``")
        $lines.Add("Stage2 evaluated/model/selected/path rows: ``$($value.stage2_evaluated_windows) / $($value.stage2_model_rows) / $($value.stage2_selected_rows) / $($value.stage2_path_rows)``; direct/MPC ``$($value.stage2_direct_rows) / $($value.stage2_mpc_rows)``.")
        $lines.Add("Stage3 persistence/reliable centers: ``$($value.stage3_persistence_rows) / $($value.stage3_reliable_centers)``; Stage4 joint results/paths/confirmation match: ``$($value.stage4_joint_results) / $($value.stage4_joint_path_rows) / $($value.stage4_confirmation_match)``.")
        $lines.Add('')
        $lines.Add('Numeric maxima (unthresholded):')
        $lines.Add('')
        $lines.Add(('- Delay / Doppler / relative power: ``{0} / {1} / {2}``' -f $value.max_delay_abs_diff, $value.max_doppler_abs_diff, $value.max_relative_power_abs_diff))
        $lines.Add(('- Alpha / path score: ``{0} / {1}``' -f $value.max_alpha_abs_diff, $value.max_path_score_abs_diff))
        $lines.Add(('- RSS absolute/relative: ``{0} / {1}``; BIC absolute/relative: ``{2} / {3}``' -f $value.max_rss_abs_diff, $value.max_rss_rel_diff, $value.max_bic_abs_diff, $value.max_bic_rel_diff))
        if ($value.task_status -ceq 'FAIL') {
            $lines.Add('')
            $lines.Add("Failure: ``$($value.failure_identifier)`` — $($value.failure_message)")
            $lines.Add("Candidate namespace: ``$($value.candidate_namespace)``; timestamp UTC: ``$($value.failure_timestamp_utc)``.")
        }
        $lines.Add('')
    }

    $lines.Add('## Sequential decision diagnostics')
    $lines.Add('')
    foreach ($kind in @('bic', 'rss')) {
        foreach ($side in @('cpu', 'gpu')) {
            $best = $null
            foreach ($window in $windows) {
                foreach ($fromOrder in 1..3) {
                    $prefix = "L${fromOrder}_to_L$($fromOrder + 1)"
                    $checkedField = "${prefix}_checked_${side}"
                    if ([string]$window.$checkedField -notmatch '^(?i:true|1)$') { continue }
                    $surplusField = "${prefix}_${kind}_surplus_${side}"
                    $value = 0.0
                    if (-not [double]::TryParse([string]$window.$surplusField, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$value) -or [double]::IsNaN($value) -or [double]::IsInfinity($value)) { continue }
                    if ($null -eq $best -or $value -lt $best.Value) {
                        $acceptedField = "${prefix}_accepted_${side}"
                        $best = [pscustomobject]@{
                            Value = $value
                            Task = [string]$window.task
                            Window = [string]$window.window_id
                            Transition = $prefix
                            Accepted = [string]$window.$acceptedField
                        }
                    }
                }
            }
            $diagnosticName = "minimum_checked_${kind}_surplus_${side}"
            if ($null -eq $best) {
                $lines.Add("$diagnosticName=NOT_AVAILABLE")
            }
            else {
                $formattedValue = $best.Value.ToString('R', [Globalization.CultureInfo]::InvariantCulture)
                $lines.Add("$diagnosticName=$formattedValue task=$($best.Task) window=$($best.Window) transition=$($best.Transition) accepted=$($best.Accepted)")
            }
        }
    }
    $lines.Add('')
    $lines.Add('## Runtime provenance note')
    $lines.Add('')
    $lines.Add('One MATLAB startup smoke printed its marker but exited with code 3. No workaround was applied. Subsequent full startup, ArgumentList, function-resolution, and synthetic test validation passed. A Task A preflight must repeat startup smoke; any nonzero exit blocks before Task A execution or raw-IQ access.')
    $lines.Add('')
    $content = [string]::Join("`n", $lines) + "`n"
    [IO.File]::WriteAllText($paths.Summary, $content, [Text.UTF8Encoding]::new($false))
    return $paths.Summary
}

function Assert-FullTaskGpuTaskIdentity {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$CandidateRequest,
        [Parameter(Mandatory = $true)][object]$FormalContext,
        [Parameter(Mandatory = $true)][object]$CandidateCfg,
        [Parameter(Mandatory = $true)][double]$HelperRequestedPrn
    )

    if ($FormalContext -isnot [System.Collections.IDictionary]) {
        throw 'INPUT_IDENTITY_VALIDATION_FAIL formal_context_not_hashtable'
    }
    foreach ($requiredKey in @('sceneId', 'prn', 'trackingChannel', 'samplingRateHz', 'rawFile', 'trackingFile', 'telemetryFile')) {
        if (-not $FormalContext.Contains($requiredKey)) {
            throw "INPUT_IDENTITY_VALIDATION_FAIL formal_context_field_missing field=$requiredKey"
        }
    }

    $sceneValues = @([string]$CandidateRequest.SceneId, [string]$FormalContext['sceneId'], [string]$CandidateCfg.SceneId)
    $prnValues = @([double]$CandidateRequest.Prn, [double]$FormalContext['prn'], [double]$CandidateCfg.TargetPrn, $HelperRequestedPrn)
    $channelValues = @([double]$CandidateRequest.TrackingChannel, [double]$FormalContext['trackingChannel'], [double]$CandidateCfg.TrackingChannel)
    $rateValues = @([double]$FormalContext['samplingRateHz'], [double]$CandidateCfg.FsHz)

    if (@($sceneValues | Select-Object -Unique).Count -ne 1 -or
            @($prnValues | Select-Object -Unique).Count -ne 1 -or
            @($channelValues | Select-Object -Unique).Count -ne 1 -or
            @($rateValues | Select-Object -Unique).Count -ne 1) {
        throw 'INPUT_IDENTITY_VALIDATION_FAIL scene_prn_channel_or_sample_rate_mismatch'
    }

    if ((Normalize-CandidateIdentityPath ([string]$FormalContext['rawFile'])) -cne
            (Normalize-CandidateIdentityPath ([string]$CandidateCfg.RawFile))) {
        throw 'INPUT_IDENTITY_VALIDATION_FAIL input_path_mismatch field=RawFile'
    }
    if ((Normalize-CandidateIdentityPath ([string]$FormalContext['trackingFile'])) -cne
            (Normalize-CandidateIdentityPath ([string]$CandidateCfg.TrackingFile))) {
        throw 'INPUT_IDENTITY_VALIDATION_FAIL input_path_mismatch field=TrackingFile'
    }
    if ((Normalize-CandidateIdentityPath ([string]$FormalContext['telemetryFile'])) -cne
            (Normalize-CandidateIdentityPath ([string]$CandidateCfg.TelemetryFile))) {
        throw 'INPUT_IDENTITY_VALIDATION_FAIL input_path_mismatch field=TelemetryFile'
    }
    return $true
}

function Normalize-CandidateIdentityPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return ([IO.Path]::GetFullPath($Path).Replace('\', '/')).TrimEnd('/')
}

function Assert-CandidateOutputAbsent {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$Path)
    if (Test-Path -LiteralPath $Path) {
        throw "OUTPUT_NAMESPACE_ALREADY_EXISTS path=$Path"
    }
    return $true
}

function Assert-MatlabFunctionResolution {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$CandidateResolvedPath,
        [Parameter(Mandatory = $true)][string]$SelectorResolvedPath,
        [Parameter(Mandatory = $true)][string]$CandidateExpectedPath,
        [Parameter(Mandatory = $true)][string]$SelectorExpectedPath
    )
    $candidateMatch = [string]::Equals(
        (Normalize-CandidateIdentityPath $CandidateResolvedPath),
        (Normalize-CandidateIdentityPath $CandidateExpectedPath),
        [StringComparison]::OrdinalIgnoreCase)
    $selectorMatch = [string]::Equals(
        (Normalize-CandidateIdentityPath $SelectorResolvedPath),
        (Normalize-CandidateIdentityPath $SelectorExpectedPath),
        [StringComparison]::OrdinalIgnoreCase)
    if (-not $candidateMatch -or -not $selectorMatch) {
        throw 'MATLAB_FUNCTION_RESOLUTION_MISMATCH'
    }
    return $true
}

function ConvertTo-MatlabCharLiteral {
    param([Parameter(Mandatory = $true)][string]$Value)
    return "'" + $Value.Replace("'", "''") + "'"
}

function Get-CandidateMatlabPaths {
    [CmdletBinding()]
    param([string]$ReviewProjectRoot = $script:CandidateProjectRoot)
    [pscustomobject]@{
        ReviewProjectRoot = [IO.Path]::GetFullPath($ReviewProjectRoot)
        CandidateDirectory = Join-Path ([IO.Path]::GetFullPath($ReviewProjectRoot)) 'experiments/sage_gpu/full_task_candidate'
        SageGpuDirectory = Join-Path ([IO.Path]::GetFullPath($ReviewProjectRoot)) 'experiments/sage_gpu'
        CandidateFile = Join-Path ([IO.Path]::GetFullPath($ReviewProjectRoot)) 'experiments/sage_gpu/full_task_candidate/run_nav_sage_pipeline_gpu_candidate.m'
        SelectorFile = Join-Path ([IO.Path]::GetFullPath($ReviewProjectRoot)) 'experiments/sage_gpu/selectSeparatedResidualCandidate.m'
    }
}

function New-CandidateUnitTestExpression {
    [CmdletBinding()]
    param([string]$ReviewProjectRoot = $script:CandidateProjectRoot)
    $paths = Get-CandidateMatlabPaths -ReviewProjectRoot $ReviewProjectRoot
    $rootLiteral = ConvertTo-MatlabCharLiteral $paths.ReviewProjectRoot
    $candidateLiteral = ConvertTo-MatlabCharLiteral $paths.CandidateDirectory
    $gpuLiteral = ConvertTo-MatlabCharLiteral $paths.SageGpuDirectory
    $validationLiteral = ConvertTo-MatlabCharLiteral (Join-Path $paths.ReviewProjectRoot 'experiments/sage_gpu/full_task_validation')
    return "cd($rootLiteral); candidateDir=$candidateLiteral; sageGpuDir=$gpuLiteral; validationDir=$validationLiteral; addpath(candidateDir); addpath(sageGpuDir); addpath(validationDir); candidateFile=which('run_nav_sage_pipeline_gpu_candidate'); helperFile=which('selectSeparatedResidualCandidate'); assert(strcmpi(candidateFile,fullfile(candidateDir,'run_nav_sage_pipeline_gpu_candidate.m')) && strcmpi(helperFile,fullfile(sageGpuDir,'selectSeparatedResidualCandidate.m')),'MATLAB_FUNCTION_RESOLUTION_MISMATCH'); disp('MATLAB_FUNCTION_RESOLUTION_OK'); results = runtests('experiments/sage_gpu/full_task_validation/tests'); assert(~isempty(results) && all([results.Passed]), 'FULL_TASK_GPU_TESTS_FAILED')"
}

function New-CandidateMatlabProcessStartInfo {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$MatlabPath,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Expression
    )
    $startInfo = [Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $MatlabPath
    $startInfo.WorkingDirectory = $WorkingDirectory
    $startInfo.UseShellExecute = $false
    $startInfo.RedirectStandardOutput = $true
    $startInfo.RedirectStandardError = $true
    $startInfo.CreateNoWindow = $true
    [void]$startInfo.ArgumentList.Add('-batch')
    [void]$startInfo.ArgumentList.Add($Expression)
    return $startInfo
}

function Invoke-CandidateMatlabBatch {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][string]$MatlabPath,
        [Parameter(Mandatory = $true)][string]$WorkingDirectory,
        [Parameter(Mandatory = $true)][string]$Expression
    )
    $startInfo = New-CandidateMatlabProcessStartInfo -MatlabPath $MatlabPath `
        -WorkingDirectory $WorkingDirectory -Expression $Expression
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    $startedUtc = [DateTimeOffset]::UtcNow.ToString('o')
    try {
        if (-not $process.Start()) {
            throw 'MATLAB_PROCESS_START_FAILED'
        }
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        return [pscustomobject]@{
            ExitCode = $process.ExitCode
            Stdout = $stdout
            Stderr = $stderr
            Output = $stdout + "`n" + $stderr
            ProcessId = $process.Id
            ProcessEnded = $true
            StartedUtc = $startedUtc
            EndedUtc = [DateTimeOffset]::UtcNow.ToString('o')
            Expression = $Expression
        }
    }
    finally {
        $process.Dispose()
    }
}

function Assert-CandidateMatlabSmoke {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)][object]$Result,
        [Parameter(Mandatory = $true)][string]$Marker
    )
    if ($Result.ExitCode -ne 0 -or $Result.Output -notmatch [regex]::Escape($Marker)) {
        throw "MATLAB_SMOKE_FAILED marker=$Marker exit_code=$($Result.ExitCode) stdout=$($Result.Stdout) stderr=$($Result.Stderr)"
    }
    return $true
}

function Get-CandidateMatlabApplication {
    $application = Get-Command -Name 'matlab' -CommandType Application -ErrorAction Stop
    return $application.Source
}

function New-CandidateFunctionResolutionExpression {
    [CmdletBinding()]
    param([string]$ReviewProjectRoot = $script:CandidateProjectRoot)
    $paths = Get-CandidateMatlabPaths -ReviewProjectRoot $ReviewProjectRoot
    $rootLiteral = ConvertTo-MatlabCharLiteral $paths.ReviewProjectRoot
    $candidateLiteral = ConvertTo-MatlabCharLiteral $paths.CandidateDirectory
    $gpuLiteral = ConvertTo-MatlabCharLiteral $paths.SageGpuDirectory
    return "cd($rootLiteral); candidateDir=$candidateLiteral; sageGpuDir=$gpuLiteral; addpath(candidateDir); addpath(sageGpuDir); candidateFile=which('run_nav_sage_pipeline_gpu_candidate'); helperFile=which('selectSeparatedResidualCandidate'); assert(strcmpi(candidateFile,fullfile(candidateDir,'run_nav_sage_pipeline_gpu_candidate.m')) && strcmpi(helperFile,fullfile(sageGpuDir,'selectSeparatedResidualCandidate.m')),'MATLAB_FUNCTION_RESOLUTION_MISMATCH'); disp('MATLAB_FUNCTION_RESOLUTION_OK')"
}

function New-CandidateGpuPreflightExpression {
    [CmdletBinding()]
    param([string]$ReviewProjectRoot = $script:CandidateProjectRoot)
    $resolution = New-CandidateFunctionResolutionExpression -ReviewProjectRoot $ReviewProjectRoot
    return "$resolution; assert(exist('canUseGPU','file') == 2 || exist('canUseGPU','builtin') == 5,'GPU_NOT_AVAILABLE'); assert(canUseGPU && gpuDeviceCount('available') > 0,'GPU_NOT_AVAILABLE'); device=gpuDevice; fprintf('GPU_PREFLIGHT_NAME=%s\n',device.Name); disp('$script:GpuPreflightMarker')"
}

function Assert-CandidateImplementationSource {
    [CmdletBinding()]
    param()
    $paths = Get-CandidateMatlabPaths
    [void](Assert-FrozenSourceIdentity -Path $script:FrozenAuthorityPath)
    [void](Assert-QualifiedGpuSourceIdentity)
    [void](Assert-FullTaskGpuSourceBoundary -AuthorityPath $script:FrozenAuthorityPath `
        -CandidatePath $paths.CandidateFile)
}

function Read-CandidateJsonFile {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$LiteralPath)
    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
        throw "CANDIDATE_IDENTITY_FILE_MISSING path=$LiteralPath"
    }
    $jsonText = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $LiteralPath).Path)
    if ($jsonText.Length -gt 0 -and $jsonText[0] -eq [char]0xFEFF) {
        $jsonText = $jsonText.Substring(1)
    }
    try {
        return ConvertFrom-Json -InputObject $jsonText -AsHashtable -ErrorAction Stop
    }
    catch {
        throw "CANDIDATE_IDENTITY_JSON_INVALID path=$LiteralPath error=$($_.Exception.Message)"
    }
}

function Assert-CandidateInputsAndReference {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object]$TaskSpec)

    $sceneDir = Join-Path $script:FrozenProjectRoot (Join-Path 'scenes' $TaskSpec.SceneId)
    $metadataPath = Join-Path $sceneDir 'metadata.json'
    $metadata = Read-CandidateJsonFile -LiteralPath $metadataPath
    if ([string]$metadata.scene_id -cne $TaskSpec.SceneId -or
            [double]$metadata.signal.sample_rate_hz -ne [double]$TaskSpec.SampleRateHz) {
        throw "INPUT_IDENTITY_VALIDATION_FAIL metadata_scene_or_sample_rate scene=$($TaskSpec.SceneId)"
    }
    $rawPath = [string]$metadata.raw_iq.path
    if ([string]::IsNullOrWhiteSpace($rawPath) -or -not [IO.Path]::IsPathRooted($rawPath) -or
            -not (Test-Path -LiteralPath $rawPath -PathType Leaf)) {
        throw "INPUT_IDENTITY_VALIDATION_FAIL raw_iq_path_missing_or_not_absolute path=$rawPath"
    }

    $gnssSdrDir = Join-Path $sceneDir 'gnss_sdr'
    $trackingPath = Join-Path $gnssSdrDir (Join-Path 'tracking' ("{0}_track_ch_{1}.mat" -f $TaskSpec.SceneId, $TaskSpec.TrackingChannel))
    $telemetryPath = Join-Path $gnssSdrDir (Join-Path 'telemetry' ("{0}_telemetry_ch_{1}.dat" -f $TaskSpec.SceneId, $TaskSpec.TrackingChannel))
    $nmeaFiles = @(Get-ChildItem -LiteralPath (Join-Path $sceneDir 'trajectory') -Filter '*.nmea' -File -ErrorAction Stop)
    $navFiles = @(Get-ChildItem -LiteralPath (Join-Path $sceneDir 'navigation/rinex_nav') -Filter '*.26N' -File -ErrorAction Stop)
    foreach ($inputPath in @($trackingPath, $telemetryPath)) {
        if (-not (Test-Path -LiteralPath $inputPath -PathType Leaf)) {
            throw "CANDIDATE_INPUT_MISSING path=$inputPath"
        }
    }
    if ($nmeaFiles.Count -ne 1 -or $navFiles.Count -ne 1) {
        throw "CANDIDATE_INPUT_CARDINALITY_FAIL nmea=$($nmeaFiles.Count) rinex_nav=$($navFiles.Count)"
    }

    $referencePath = Join-Path $script:FrozenProjectRoot ($TaskSpec.ReferenceOutputNamespace.Replace('/', '\'))
    $referenceContextPath = Join-Path $referencePath 'run_context.json'
    $formal = Read-CandidateJsonFile -LiteralPath $referenceContextPath
    $candidateRequest = [pscustomobject]@{
        SceneId = $TaskSpec.SceneId
        Prn = $TaskSpec.Prn
        TrackingChannel = $TaskSpec.TrackingChannel
    }
    $candidateCfgIdentity = [pscustomobject]@{
        SceneId = $TaskSpec.SceneId
        TargetPrn = $TaskSpec.Prn
        TrackingChannel = $TaskSpec.TrackingChannel
        FsHz = $TaskSpec.SampleRateHz
        RawFile = $rawPath
        TrackingFile = $trackingPath
        TelemetryFile = $telemetryPath
    }
    $identityPassed = Assert-FullTaskGpuTaskIdentity -CandidateRequest $candidateRequest `
        -FormalContext $formal -CandidateCfg $candidateCfgIdentity -HelperRequestedPrn $TaskSpec.Prn
    if (-not $identityPassed -or
            (Normalize-CandidateIdentityPath ([string]$formal['rawFile'])) -cne (Normalize-CandidateIdentityPath $rawPath) -or
            (Normalize-CandidateIdentityPath ([string]$formal['trackingFile'])) -cne (Normalize-CandidateIdentityPath $trackingPath) -or
            (Normalize-CandidateIdentityPath ([string]$formal['telemetryFile'])) -cne (Normalize-CandidateIdentityPath $telemetryPath)) {
        throw "INPUT_IDENTITY_VALIDATION_FAIL task=$($TaskSpec.Task)"
    }

    return [pscustomobject]@{
        MetadataPath = $metadataPath
        RawPath = $rawPath
        TrackingPath = $trackingPath
        TelemetryPath = $telemetryPath
        NmeaPath = $nmeaFiles[0].FullName
        RinexNavPath = $navFiles[0].FullName
        ReferenceOutputPath = $referencePath
        CandidateOutputPath = Join-Path $script:FrozenProjectRoot ($TaskSpec.CandidateOutputNamespace.Replace('/', '\'))
        FormalContext = $formal
        SampleRateHz = [double]$TaskSpec.SampleRateHz
    }
}

function Invoke-CandidateStartupAndTransportSmokes {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][string]$MatlabPath)
    $startup = Invoke-CandidateMatlabBatch -MatlabPath $MatlabPath `
        -WorkingDirectory $script:CandidateProjectRoot -Expression "disp('$script:StartupMarker')"
    [void](Assert-CandidateMatlabSmoke -Result $startup -Marker $script:StartupMarker)
    $transport = Invoke-CandidateMatlabBatch -MatlabPath $MatlabPath `
        -WorkingDirectory $script:CandidateProjectRoot -Expression $script:TransportSmokeExpression
    [void](Assert-CandidateMatlabSmoke -Result $transport -Marker $script:TransportMarker)
    return [pscustomobject]@{ Startup = $startup; Transport = $transport }
}

function Invoke-CandidatePreflight {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object]$TaskSpec)

    Assert-NoExistingFullTaskGpuEvidence -TaskSpec $TaskSpec | Out-Null
    Assert-CandidateImplementationSource
    $inputIdentity = Assert-CandidateInputsAndReference -TaskSpec $TaskSpec
    $matlabPath = Get-CandidateMatlabApplication
    [void](Invoke-CandidateStartupAndTransportSmokes -MatlabPath $matlabPath)
    $resolution = Invoke-CandidateMatlabBatch -MatlabPath $matlabPath `
        -WorkingDirectory $script:CandidateProjectRoot `
        -Expression (New-CandidateFunctionResolutionExpression)
    [void](Assert-CandidateMatlabSmoke -Result $resolution -Marker $script:FunctionResolutionMarker)
    $gpuCheck = Invoke-CandidateMatlabBatch -MatlabPath $matlabPath `
        -WorkingDirectory $script:CandidateProjectRoot `
        -Expression (New-CandidateGpuPreflightExpression)
    [void](Assert-CandidateMatlabSmoke -Result $gpuCheck -Marker $script:GpuPreflightMarker)
    Assert-CandidateOutputAbsent -Path $inputIdentity.CandidateOutputPath | Out-Null

    return [pscustomobject]@{
        TaskSpec = $TaskSpec
        Inputs = $inputIdentity
        MatlabPath = $matlabPath
        GpuName = [regex]::Match($gpuCheck.Output, 'GPU_PREFLIGHT_NAME=(?<name>[^\r\n]+)').Groups['name'].Value
    }
}

function New-CandidateRunAndCompareExpression {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object]$TaskSpec)
    $paths = Get-CandidateMatlabPaths
    $rootLiteral = ConvertTo-MatlabCharLiteral $script:FrozenProjectRoot
    $candidateLiteral = ConvertTo-MatlabCharLiteral $paths.CandidateDirectory
    $gpuLiteral = ConvertTo-MatlabCharLiteral $paths.SageGpuDirectory
    $sceneLiteral = ConvertTo-MatlabCharLiteral $TaskSpec.SceneId
    $referenceLiteral = ConvertTo-MatlabCharLiteral (Join-Path $script:FrozenProjectRoot ($TaskSpec.ReferenceOutputNamespace.Replace('/', '\')))
    $candidateOutputLiteral = ConvertTo-MatlabCharLiteral (Join-Path $script:FrozenProjectRoot ($TaskSpec.CandidateOutputNamespace.Replace('/', '\')))
    $validationLiteral = ConvertTo-MatlabCharLiteral (Join-Path $script:CandidateProjectRoot 'experiments/sage_gpu/full_task_validation')
    return "try; cd($rootLiteral); candidateDir=$candidateLiteral; sageGpuDir=$gpuLiteral; validationDir=$validationLiteral; comparisonEvidenceDirectory=validationDir; addpath(candidateDir); addpath(sageGpuDir); addpath(validationDir); candidateFile=which('run_nav_sage_pipeline_gpu_candidate'); helperFile=which('selectSeparatedResidualCandidate'); assert(strcmpi(candidateFile,fullfile(candidateDir,'run_nav_sage_pipeline_gpu_candidate.m')) && strcmpi(helperFile,fullfile(sageGpuDir,'selectSeparatedResidualCandidate.m')),'MATLAB_FUNCTION_RESOLUTION_MISMATCH'); disp('MATLAB_FUNCTION_RESOLUTION_OK'); candidateResult=run_nav_sage_pipeline_gpu_candidate($sceneLiteral,$($TaskSpec.Prn),'TrackingChannel',$($TaskSpec.TrackingChannel),'ProjectRoot',$rootLiteral,'Resume',false); formalOutputDir=$referenceLiteral; candidateOutputDir=$candidateOutputLiteral; taskSceneId=$sceneLiteral; taskPrn=$($TaskSpec.Prn); taskChannel=$($TaskSpec.TrackingChannel); cd(validationDir); eval(fileread('Compare-FullTaskGpuCandidateOutputs.m')); assert(isstruct(candidateComparison) && isfield(candidateComparison,'Passed') && candidateComparison.Passed,'FULL_TASK_GPU_COMPARISON_FAILED'); catch exception; failureIdentifier=exception.identifier; if isempty(failureIdentifier), failureIdentifier='UNIDENTIFIED_MATLAB_FAILURE'; end; failureMessage=regexprep(exception.message,'[\r\n]+',' '); fprintf(2,'FULL_TASK_GPU_FAILURE_IDENTIFIER=%s\n',failureIdentifier); fprintf(2,'FULL_TASK_GPU_FAILURE_MESSAGE=%s\n',failureMessage); rethrow(exception); end"
}

function Get-FullTaskGpuMatlabFailureDetails {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object]$Result)
    $output = "$(($Result.Stdout))`n$(($Result.Stderr))"
    $identifierMatch = [regex]::Match($output, '(?m)^FULL_TASK_GPU_FAILURE_IDENTIFIER=(?<value>[^\r\n]+)')
    $messageMatch = [regex]::Match($output, '(?m)^FULL_TASK_GPU_FAILURE_MESSAGE=(?<value>[^\r\n]*)')
    $identifier = if ($identifierMatch.Success) { $identifierMatch.Groups['value'].Value.Trim() } else { "CANDIDATE_RUN_OR_COMPARISON_FAILED_EXIT_$($Result.ExitCode)" }
    $message = if ($messageMatch.Success) { $messageMatch.Groups['value'].Value.Trim() } else { "MATLAB exited with code $($Result.ExitCode). $($Result.Stderr) $($Result.Stdout)" }
    return [pscustomobject]@{ Identifier = $identifier; Message = $message }
}

function Invoke-RunAndCompare {
    [CmdletBinding()]
    param([Parameter(Mandatory = $true)][object]$TaskSpec)
    $preflight = Invoke-CandidatePreflight -TaskSpec $TaskSpec
    $expression = New-CandidateRunAndCompareExpression -TaskSpec $TaskSpec
    try {
        $result = Invoke-CandidateMatlabBatch -MatlabPath $preflight.MatlabPath `
            -WorkingDirectory $script:CandidateProjectRoot -Expression $expression
    }
    catch {
        Add-FullTaskGpuFailureReceipt -TaskSpec $TaskSpec `
            -FailureIdentifier 'CANDIDATE_RUNNER_EXCEPTION' `
            -FailureMessage $_.Exception.Message -GpuIdentity $preflight.GpuName | Out-Null
        Update-FullTaskGpuValidationSummary -GpuIdentity $preflight.GpuName | Out-Null
        throw
    }
    if ($result.ExitCode -ne 0) {
        $failure = Get-FullTaskGpuMatlabFailureDetails -Result $result
        Add-FullTaskGpuFailureReceipt -TaskSpec $TaskSpec `
            -FailureIdentifier $failure.Identifier -FailureMessage $failure.Message `
            -GpuIdentity $preflight.GpuName | Out-Null
        Update-FullTaskGpuValidationSummary -GpuIdentity $preflight.GpuName | Out-Null
        throw "CANDIDATE_RUN_OR_COMPARISON_FAILED task=$($TaskSpec.Task) exit_code=$($result.ExitCode) identifier=$($failure.Identifier) message=$($failure.Message)"
    }
    Update-FullTaskGpuValidationSummary -GpuIdentity $preflight.GpuName | Out-Null
    return [pscustomobject]@{ Task = $TaskSpec.Task; Result = $result; GpuName = $preflight.GpuName }
}

function Invoke-CandidateUnitTests {
    [CmdletBinding()]
    param()
    Assert-CandidateImplementationSource
    $matlabPath = Get-CandidateMatlabApplication
    [void](Invoke-CandidateStartupAndTransportSmokes -MatlabPath $matlabPath)
    $result = Invoke-CandidateMatlabBatch -MatlabPath $matlabPath `
        -WorkingDirectory $script:CandidateProjectRoot `
        -Expression (New-CandidateUnitTestExpression)
    if ($result.ExitCode -ne 0 -or $result.Output -notmatch [regex]::Escape($script:FunctionResolutionMarker)) {
        throw "CANDIDATE_UNIT_TESTS_FAILED exit_code=$($result.ExitCode) stdout=$($result.Stdout) stderr=$($result.Stderr)"
    }
    Write-Output $result.Stdout
    return $result
}

$script:FrozenImmutableFunctionSha256 = @{
    runStage2 = '96dc162a17cf87dde5300ccd902a8a08fa6c0c10643c0d7b446a214ff1eb8f8e'
    flattenStage2 = '22c15b598ff84df379710b2ec9ce4d054855fb5a2fc4786c4b7d734da4b16d2c'
    evaluatePersistence = '221746eb016bdc94aacd9d95a5a89b4315c266a9418fd897f9962b3934940152'
    runJointStage = 'cc0ab1a13007aeceb805bde92f74b806de5136ed45a5e9f645544fc40707a52f'
}

function Get-FrozenSourceIdentity {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "FROZEN_SOURCE_NOT_FOUND path=$Path"
    }

    $sha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant()
    [pscustomobject]@{
        Path         = $Path
        ExpectedPath = $script:FrozenAuthorityPath
        Sha256       = $sha256
        ExpectedSha  = $script:FrozenAuthoritySha256
        Match        = ($sha256 -ceq $script:FrozenAuthoritySha256)
    }
}

function Assert-FrozenSourceIdentity {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $identity = Get-FrozenSourceIdentity -Path $Path
    if (-not $identity.Match) {
        throw "FROZEN_SOURCE_HASH_MISMATCH actual=$($identity.Sha256) expected=$($identity.ExpectedSha) path=$Path"
    }

    $resolvedPath = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $Path).Path).TrimEnd('\', '/')
    $resolvedAuthority = [IO.Path]::GetFullPath((Resolve-Path -LiteralPath $script:FrozenAuthorityPath).Path).TrimEnd('\', '/')
    if (-not [string]::Equals($resolvedPath, $resolvedAuthority, [StringComparison]::OrdinalIgnoreCase)) {
        throw "FROZEN_SOURCE_PATH_MISMATCH actual=$resolvedPath expected=$resolvedAuthority"
    }

    return $identity
}

function Get-QualifiedGpuSourceIdentity {
    [CmdletBinding()]
    param()

    foreach ($path in @($script:QualifiedGpuProbePath, $script:QualifiedSelectorPath)) {
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            throw "QUALIFIED_GPU_SOURCE_NOT_FOUND path=$path"
        }
    }

    $probeHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $script:QualifiedGpuProbePath).Hash.ToLowerInvariant()
    $selectorHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $script:QualifiedSelectorPath).Hash.ToLowerInvariant()
    [pscustomobject]@{
        ProbePath     = $script:QualifiedGpuProbePath
        ProbeSha256   = $probeHash
        SelectorPath  = $script:QualifiedSelectorPath
        SelectorSha256 = $selectorHash
        Match         = ($probeHash -ceq $script:QualifiedGpuProbeSha256 -and
            $selectorHash -ceq $script:QualifiedSelectorSha256)
    }
}

function Assert-QualifiedGpuSourceIdentity {
    [CmdletBinding()]
    param()

    $identity = Get-QualifiedGpuSourceIdentity
    if (-not $identity.Match) {
        throw "QUALIFIED_GPU_SOURCE_IDENTITY_MISMATCH probe=$($identity.ProbeSha256) selector=$($identity.SelectorSha256)"
    }
    return $identity
}

function Get-MatlabFunctionBlocks {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$LiteralPath
    )

    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
        throw "MATLAB_SOURCE_NOT_FOUND path=$LiteralPath"
    }

    $source = [IO.File]::ReadAllText((Resolve-Path -LiteralPath $LiteralPath).Path)
    $matches = [regex]::Matches($source, '(?m)^[\t ]*function\b')
    if ($matches.Count -eq 0) {
        throw "MATLAB_FUNCTIONS_NOT_FOUND path=$LiteralPath"
    }

    $blocks = New-Object 'System.Collections.Generic.List[object]'
    for ($index = 0; $index -lt $matches.Count; $index++) {
        $start = $matches[$index].Index
        $end = if ($index + 1 -lt $matches.Count) { $matches[$index + 1].Index } else { $source.Length }
        $blockText = $source.Substring($start, $end - $start).TrimEnd([char[]]@("`r", "`n"))
        $openParen = $blockText.IndexOf('(')
        if ($openParen -lt 0) {
            throw "MATLAB_FUNCTION_SIGNATURE_UNPARSEABLE path=$LiteralPath offset=$start"
        }

        $signaturePrefix = $blockText.Substring(0, $openParen)
        $nameMatch = [regex]::Match($signaturePrefix, '(?<name>[A-Za-z][A-Za-z0-9_]*)[\t ]*$')
        if (-not $nameMatch.Success) {
            throw "MATLAB_FUNCTION_NAME_UNPARSEABLE path=$LiteralPath offset=$start"
        }

        $normalized = ($blockText -replace "`r`n?", "`n").TrimEnd([char[]]@("`n"))
        $digest = Get-Utf8Sha256 -Text $normalized
        $lineNumber = ([regex]::Matches($source.Substring(0, $start), "`n")).Count + 1
        $blocks.Add([pscustomobject]@{
            Name       = $nameMatch.Groups['name'].Value
            RawText    = $blockText
            Normalized = $normalized
            Sha256     = $digest
            StartLine  = $lineNumber
        })
    }

    return $blocks.ToArray()
}

function Get-Utf8Sha256 {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text
    )

    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $bytes = (New-Object Text.UTF8Encoding($false)).GetBytes($Text)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    }
    finally {
        $sha.Dispose()
    }
}

function Get-FullTaskGpuSourceBoundaryAudit {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$AuthorityPath,
        [Parameter(Mandatory = $true)]
        [string]$CandidatePath
    )

    $authorityIdentity = Assert-FrozenSourceIdentity -Path $AuthorityPath
    $qualifiedIdentity = Assert-QualifiedGpuSourceIdentity
    $candidateFullPath = (Resolve-Path -LiteralPath $CandidatePath).Path
    $candidateHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $candidateFullPath).Hash.ToLowerInvariant()
    $authorityBlocks = @(Get-MatlabFunctionBlocks -LiteralPath $AuthorityPath)
    $candidateBlocks = @(Get-MatlabFunctionBlocks -LiteralPath $candidateFullPath)
    $qualifiedBlocks = @(Get-MatlabFunctionBlocks -LiteralPath $qualifiedIdentity.ProbePath)
    $rows = New-Object 'System.Collections.Generic.List[object]'

    for ($index = 0; $index -lt $authorityBlocks.Count; $index++) {
        $authorityBlock = $authorityBlocks[$index]
        if ($index -ge $candidateBlocks.Count) {
            $rows.Add([pscustomobject]@{
                Function = $authorityBlock.Name; AuthoritySha256 = $authorityBlock.Sha256; CandidateSha256 = ''
                Category = 'UNEXPECTED_DIFF'; Status = 'UNEXPECTED_DIFF'; ByteIdentical = $false
                NormalizedExact = $false; AuthorityStartLine = $authorityBlock.StartLine; CandidateStartLine = $null
                Reason = 'FROZEN_FUNCTION_MISSING_FROM_CANDIDATE'
            })
            continue
        }

        $candidateBlock = $candidateBlocks[$index]
        $expectedCandidateName = if ($index -eq 0) { 'run_nav_sage_pipeline_gpu_candidate' } else { $authorityBlock.Name }
        $nameMatches = $candidateBlock.Name -ceq $expectedCandidateName
        $textMatches = $authorityBlock.RawText -ceq $candidateBlock.RawText
        $normalizedMatches = $authorityBlock.Normalized -ceq $candidateBlock.Normalized
        $isImmutable = $script:FrozenImmutableFunctionSha256.ContainsKey($authorityBlock.Name)
        $pinnedHashMatches = $true
        if ($isImmutable) {
            $pinnedHashMatches = $authorityBlock.Sha256 -ceq $script:FrozenImmutableFunctionSha256[$authorityBlock.Name]
        }

        if (-not $pinnedHashMatches) {
            $category = 'UNEXPECTED_DIFF'
            $status = 'UNEXPECTED_DIFF'
            $reason = 'AUTHORITY_FUNCTION_FINGERPRINT_MISMATCH'
        }
        elseif (-not $nameMatches) {
            $category = 'UNEXPECTED_DIFF'
            $status = 'UNEXPECTED_DIFF'
            $reason = "FUNCTION_IDENTITY_MISMATCH candidate=$($candidateBlock.Name) expected=$expectedCandidateName"
        }
        elseif ($textMatches) {
            $category = 'UNCHANGED'
            $status = 'UNCHANGED'
            $reason = 'EXACT_FUNCTION_TEXT_MATCH'
        }
        elseif ($isImmutable) {
            $category = 'UNEXPECTED_DIFF'
            $status = 'UNEXPECTED_DIFF'
            $reason = 'PINNED_FROZEN_FUNCTION_CHANGED'
        }
        elseif ($script:CandidateChangedFunctionCategories.ContainsKey($authorityBlock.Name)) {
            $category = $script:CandidateChangedFunctionCategories[$authorityBlock.Name]
            $status = 'ALLOWED_DIFF'
            $reason = 'EXPLICITLY_SCOPED_CANDIDATE_STAGE2_SUBSTITUTION'
        }
        elseif ($script:CandidatePlumbingFunctionCategories.ContainsKey($expectedCandidateName)) {
            $category = $script:CandidatePlumbingFunctionCategories[$expectedCandidateName]
            $status = 'ALLOWED_DIFF'
            $reason = 'EXPLICITLY_SCOPED_CANDIDATE_ENTRY_OR_IDENTITY_PLUMBING'
        }
        else {
            $category = 'UNEXPECTED_DIFF'
            $status = 'UNEXPECTED_DIFF'
            $reason = 'UNAPPROVED_FROZEN_FUNCTION_CHANGE'
        }

        $rows.Add([pscustomobject]@{
            Function = $authorityBlock.Name; AuthoritySha256 = $authorityBlock.Sha256; CandidateSha256 = $candidateBlock.Sha256
            Category = $category; Status = $status; ByteIdentical = $textMatches; NormalizedExact = $normalizedMatches
            AuthorityStartLine = $authorityBlock.StartLine; CandidateStartLine = $candidateBlock.StartLine; Reason = $reason
        })
    }

    for ($index = $authorityBlocks.Count; $index -lt $candidateBlocks.Count; $index++) {
        $candidateBlock = $candidateBlocks[$index]
        $qualifiedBlock = @($qualifiedBlocks | Where-Object { $_.Name -eq $candidateBlock.Name }) | Select-Object -First 1
        if ($script:CandidatePlumbingFunctionCategories.ContainsKey($candidateBlock.Name)) {
            $rows.Add([pscustomobject]@{
                Function = $candidateBlock.Name; AuthoritySha256 = ''; CandidateSha256 = $candidateBlock.Sha256
                Category = $script:CandidatePlumbingFunctionCategories[$candidateBlock.Name]; Status = 'ALLOWED_DIFF'; ByteIdentical = $false
                NormalizedExact = $false; AuthorityStartLine = $null; CandidateStartLine = $candidateBlock.StartLine
                Reason = 'EXPLICITLY_SCOPED_CANDIDATE_ONLY_PLUMBING_OR_PROVENANCE'
            })
        }
        elseif ($script:QualifiedGpuCandidateFunctions -contains $candidateBlock.Name -and
                $null -ne $qualifiedBlock -and
                $candidateBlock.Normalized -ceq $qualifiedBlock.Normalized) {
            $rows.Add([pscustomobject]@{
                Function = $candidateBlock.Name; AuthoritySha256 = ''; CandidateSha256 = $candidateBlock.Sha256
                Category = 'GPU_STAGE2_COMPUTATIONAL_DIFFERENCE'; Status = 'ALLOWED_DIFF'; ByteIdentical = $false
                NormalizedExact = $true; AuthorityStartLine = $null; CandidateStartLine = $candidateBlock.StartLine
                Reason = 'EXACT_PINNED_QUALIFIED_GPU_FUNCTION_REUSED'
            })
        }
        else {
            $rows.Add([pscustomobject]@{
                Function = $candidateBlock.Name; AuthoritySha256 = ''; CandidateSha256 = $candidateBlock.Sha256
                Category = 'UNEXPECTED_DIFF'; Status = 'UNEXPECTED_DIFF'; ByteIdentical = $false
                NormalizedExact = $false; AuthorityStartLine = $null; CandidateStartLine = $candidateBlock.StartLine
                Reason = 'UNAPPROVED_OR_MODIFIED_CANDIDATE_ONLY_FUNCTION'
            })
        }
    }

    $rowArray = $rows.ToArray()
    $unexpectedCount = @($rowArray | Where-Object { $_.Status -eq 'UNEXPECTED_DIFF' }).Count
    [pscustomobject]@{
        Status               = if ($unexpectedCount -eq 0) { 'PASS' } else { 'BLOCKED' }
        AuthorityPath        = $AuthorityPath
        AuthoritySha256      = $authorityIdentity.Sha256
        CandidatePath        = $candidateFullPath
        CandidateSha256      = $candidateHash
        UnexpectedDiffCount  = $unexpectedCount
        Rows                 = $rowArray
    }
}

function Assert-FullTaskGpuSourceBoundary {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [string]$AuthorityPath,
        [Parameter(Mandatory = $true)]
        [string]$CandidatePath
    )

    $audit = Get-FullTaskGpuSourceBoundaryAudit -AuthorityPath $AuthorityPath -CandidatePath $CandidatePath
    if ($audit.UnexpectedDiffCount -gt 0) {
        $unexpectedFunctions = @($audit.Rows | Where-Object { $_.Status -eq 'UNEXPECTED_DIFF' } | ForEach-Object { $_.Function }) -join ','
        throw "UNEXPECTED_DIFF source boundary rejected functions=$unexpectedFunctions"
    }

    return $audit
}

if ($MyInvocation.InvocationName -ne '.') {
    if ([string]::IsNullOrWhiteSpace($Action)) {
        throw 'ACTION_REQUIRED RunUnitTests|Preflight|RunAndCompare'
    }
    switch ($Action) {
        'RunUnitTests' {
            Invoke-CandidateUnitTests
        }
        'Preflight' {
            if ([string]::IsNullOrWhiteSpace($Task)) { throw 'TASK_REQUIRED TaskA|TaskB' }
            $taskSpec = Get-FullTaskGpuTaskSpec -Task $Task
            $preflight = Invoke-CandidatePreflight -TaskSpec $taskSpec
            Write-Output "PREFLIGHT_PASS task=$Task scene=$($taskSpec.SceneId) prn=$($taskSpec.PrnLabel) channel=$($taskSpec.TrackingChannel) sample_rate_hz=$($taskSpec.SampleRateHz) resume=false gpu=$($preflight.GpuName) candidate_output=$($preflight.Inputs.CandidateOutputPath)"
            Write-Output 'PREFLIGHT_ONLY candidate_namespace_created=false raw_iq_content_read=false'
        }
        'RunAndCompare' {
            if ([string]::IsNullOrWhiteSpace($Task)) { throw 'TASK_REQUIRED TaskA|TaskB' }
            $taskSpec = Get-FullTaskGpuTaskSpec -Task $Task
            Invoke-RunAndCompare -TaskSpec $taskSpec
        }
    }
}
