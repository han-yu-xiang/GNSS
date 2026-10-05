[CmdletBinding()]
param(
    [string]$ProjectRoot = 'E:\GNSS_Multipath_Project',
    [string]$MatlabPath = ''
)

$ErrorActionPreference = 'Stop'
$script:ExpectedFrozenSha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
$script:RunLevelAttestationSourceCommit = 'c7a542daacf66dae4a098d95bad2693505e622c1'
$script:RunLevelAttestationQualificationIds = @(
    'Q_G28_W38', 'Q_G28_W298', 'Q_G28_W725', 'Q_G28_W226',
    'Q_G03_W1', 'Q_G03_W9', 'Q_G03_W11', 'Q_G03_W173'
)
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

function Get-GpuQualificationRequiredProperty {
    param(
        [Parameter(Mandatory)][object]$InputObject,
        [Parameter(Mandatory)][string]$Name,
        [Parameter(Mandatory)][string]$QualificationId
    )
    $property = $InputObject.PSObject.Properties[$Name]
    if ($null -eq $property -or $null -eq $property.Value -or [string]::IsNullOrWhiteSpace([string]$property.Value)) {
        throw "RESUME_PROVENANCE_MISSING qualification_id=$QualificationId field=$Name"
    }
    return $property.Value
}

function ConvertTo-GpuQualificationInvariantDouble {
    param(
        [Parameter(Mandatory)][object]$Value,
        [Parameter(Mandatory)][string]$Field,
        [Parameter(Mandatory)][string]$QualificationId
    )
    try {
        $number = [double]::Parse([string]$Value, [System.Globalization.NumberStyles]::Float, [System.Globalization.CultureInfo]::InvariantCulture)
    }
    catch {
        throw "RESUME_PROVENANCE_INVALID qualification_id=$QualificationId field=$Field value=$Value"
    }
    if ([double]::IsNaN($number) -or [double]::IsInfinity($number)) {
        throw "RESUME_PROVENANCE_INVALID qualification_id=$QualificationId field=$Field value=$Value"
    }
    return $number
}

function Test-GpuQualificationPassFlag {
    param([Parameter(Mandatory)][object]$Value)
    if ($Value -is [bool]) { return $Value }
    return ([string]$Value -match '^(?i:true)$')
}

function Invoke-GpuQualificationGit {
    param(
        [Parameter(Mandatory)][string]$RepositoryRoot,
        [Parameter(Mandatory)][string[]]$GitArguments
    )
    $gitPrefix = @('-c', "safe.directory=$RepositoryRoot", '-C', $RepositoryRoot)
    $output = & git @gitPrefix @GitArguments 2>&1
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "RESUME_GIT_EVIDENCE_COMMAND_FAILED exit_code=$exitCode args=$($GitArguments -join ' ') output=$($output -join ' ')"
    }
    return (($output | ForEach-Object { [string]$_ }) -join "`n").Trim()
}

function Assert-GpuQualificationRunLevelAttestation {
    param(
        [Parameter(Mandatory)][object]$Result,
        [Parameter(Mandatory)][object]$ManifestItem,
        [Parameter(Mandatory)][string]$ResultPath,
        [Parameter(Mandatory)][object]$Attestation,
        [Parameter(Mandatory)][string]$ExpectedFrozenSha256,
        [Parameter(Mandatory)][string]$RepositoryRoot
    )
    $id = [string]$ManifestItem.qualification_id
    if ($id -cnotin $script:RunLevelAttestationQualificationIds) {
        throw "RESUME_PROVENANCE_MISSING qualification_id=$id run-level fallback is not authorized for this ID."
    }
    if ([string]$Attestation.attestation_scope -cne 'historical_first_8_gpu_stage2_qualification_windows' -or
        [string]$Attestation.source_review_commit -cne $script:RunLevelAttestationSourceCommit) {
        throw "RESUME_ATTESTATION_COMMIT_MISMATCH qualification_id=$id expected_commit=$script:RunLevelAttestationSourceCommit actual=$($Attestation.source_review_commit)"
    }
    if ([string]$Attestation.expected_frozen_sage_sha256 -cne $ExpectedFrozenSha256 -or
        [int]$Attestation.qualification_windows -ne 8 -or
        [string]$Attestation.per_window_embedded_frozen_sha -cne 'MISSING' -or
        [string]$Attestation.frozen_sha_provenance_source -cne 'RUN_LEVEL_PREEXECUTION_GUARD_PLUS_CONTEMPORANEOUS_COMMITTED_SNAPSHOT' -or
        [string]$Attestation.this_attestation_does_not_modify_historical_result_json -cne 'YES') {
        throw "RESUME_ATTESTATION_CONTENT_MISMATCH qualification_id=$id"
    }
    $expectedDriverPath = 'experiments/sage_gpu/qualification/Invoke-GpuStage2Qualification.ps1'
    $expectedSnapshotPath = 'reports/project_stage_review_20261005/GNSS_PROJECT_STAGE_SNAPSHOT.md'
    if ([string]$Attestation.evidence_driver_path -cne $expectedDriverPath -or
        [string]$Attestation.evidence_snapshot_path -cne $expectedSnapshotPath) {
        throw "RESUME_ATTESTATION_EVIDENCE_PATH_MISMATCH qualification_id=$id"
    }

    $expectedResultPath = "experiments/sage_gpu/qualification/results/$id.json"
    $attestationRows = @($Attestation.results | Where-Object { [string]$_.qualification_id -ceq $id })
    if ($attestationRows.Count -ne 1 -or [string]$attestationRows[0].result_path -cne $expectedResultPath -or
        -not (Test-GpuQualificationPassFlag $attestationRows[0].byte_identity_verified) -or
        [string]$attestationRows[0].historical_status -cne 'COMPLETE' -or
        [string]$attestationRows[0].cpu_production_reference -cne 'PASS' -or
        [string]$attestationRows[0].gpu_structural_equivalence -cne 'PASS') {
        throw "RESUME_ATTESTATION_RESULT_ENTRY_MISMATCH qualification_id=$id"
    }
    $allAttestedIds = @($Attestation.results | ForEach-Object { [string]$_.qualification_id })
    if ($allAttestedIds.Count -ne 8 -or (@($allAttestedIds | Select-Object -Unique).Count -ne 8) -or
        @($allAttestedIds | Where-Object { $_ -cnotin $script:RunLevelAttestationQualificationIds }).Count -gt 0) {
        throw 'RESUME_ATTESTATION_ALLOWLIST_MISMATCH'
    }

    $sourceCommit = [string]$Attestation.source_review_commit
    $driverBlob = Invoke-GpuQualificationGit -RepositoryRoot $RepositoryRoot -GitArguments @('rev-parse', "${sourceCommit}:$expectedDriverPath")
    $snapshotBlob = Invoke-GpuQualificationGit -RepositoryRoot $RepositoryRoot -GitArguments @('rev-parse', "${sourceCommit}:$expectedSnapshotPath")
    if ($driverBlob -cne [string]$Attestation.evidence_driver_blob_sha1 -or
        $snapshotBlob -cne [string]$Attestation.evidence_snapshot_blob_sha1) {
        throw 'RESUME_ATTESTATION_EVIDENCE_BLOB_MISMATCH'
    }
    $historicalDriver = Invoke-GpuQualificationGit -RepositoryRoot $RepositoryRoot -GitArguments @('show', "${sourceCommit}:$expectedDriverPath")
    $historicalSnapshot = Invoke-GpuQualificationGit -RepositoryRoot $RepositoryRoot -GitArguments @('show', "${sourceCommit}:$expectedSnapshotPath")
    $hashGuardIndex = $historicalDriver.IndexOf('$actualHash = (Get-FileHash')
    $mismatchGuardIndex = $historicalDriver.IndexOf('SAGE_SOURCE_HASH_MISMATCH')
    $manifestReadIndex = $historicalDriver.IndexOf('$manifestPath =')
    if (-not $historicalDriver.Contains($ExpectedFrozenSha256) -or
        -not $historicalDriver.Contains('Get-FileHash') -or
        -not $historicalDriver.Contains('SAGE_SOURCE_HASH_MISMATCH') -or
        $hashGuardIndex -lt 0 -or $mismatchGuardIndex -le $hashGuardIndex -or $manifestReadIndex -le $mismatchGuardIndex -or
        -not $historicalSnapshot.Contains('EXECUTED_WINDOWS=8') -or
        -not $historicalSnapshot.Contains('CPU_PRODUCTION_REFERENCE_PASS=8') -or
        -not $historicalSnapshot.Contains('GPU_STRUCTURAL_PASS=8') -or
        -not $historicalSnapshot.Contains('FROZEN_PRODUCTION_MODIFIED=NO') -or
        -not $historicalSnapshot.Contains('Q_G06_W6850') -or
        -not $historicalSnapshot.Contains('STATUS=STOPPED_ON_IDENTITY_MISMATCH')) {
        throw 'RESUME_ATTESTATION_RUN_EVIDENCE_MISMATCH'
    }

    $commitResultBlob = Invoke-GpuQualificationGit -RepositoryRoot $RepositoryRoot -GitArguments @('rev-parse', "${sourceCommit}:$expectedResultPath")
    $localResultBlob = Invoke-GpuQualificationGit -RepositoryRoot $RepositoryRoot -GitArguments @('hash-object', '--', $ResultPath)
    if ([string]$Result.status -cne [string]$attestationRows[0].historical_status -or
        [string]$Result.cpu_production_reference -cne [string]$attestationRows[0].cpu_production_reference -or
        [string]$Result.gpu_structural_equivalence -cne [string]$attestationRows[0].gpu_structural_equivalence -or
        $commitResultBlob -cne [string]$attestationRows[0].git_blob_sha1 -or $localResultBlob -cne $commitResultBlob) {
        throw "RESUME_ATTESTATION_BLOB_MISMATCH qualification_id=$id expected=$commitResultBlob attested=$($attestationRows[0].git_blob_sha1) local=$localResultBlob"
    }
    return [pscustomobject]@{
        provenance_mode = 'RUN_LEVEL_ATTESTED'
        result_blob_sha1 = $localResultBlob
        source_review_commit = $sourceCommit
    }
}

function Assert-GpuQualificationReusablePass {
    param(
        [Parameter(Mandatory)][object]$Result,
        [Parameter(Mandatory)][object]$ManifestItem,
        [Parameter(Mandatory)][string]$ExpectedFrozenSha256,
        [Parameter(Mandatory)][string]$ResultPath,
        [Parameter(Mandatory)][ValidateSet('LEGACY', 'CURRENT')][string]$ResultLocation,
        [string]$AttestationPath = '',
        [string]$RepositoryRoot = ''
    )
    $id = [string]$ManifestItem.qualification_id
    $identityFields = @('qualification_id', 'scene_id', 'prn', 'tracking_channel', 'window_id', 'recording_time_s', 'production_selected_L', 'production_path_count')
    foreach ($field in $identityFields) {
        [void](Get-GpuQualificationRequiredProperty -InputObject $Result -Name $field -QualificationId $id)
    }

    if ([string]$Result.qualification_id -cne [string]$ManifestItem.qualification_id -or
        [string]$Result.scene_id -cne [string]$ManifestItem.scene_id -or
        (ConvertTo-GpuQualificationNumericPrn $Result.prn) -ne (ConvertTo-GpuQualificationNumericPrn $ManifestItem.prn) -or
        [int]$Result.tracking_channel -ne [int]$ManifestItem.tracking_channel -or
        [int]$Result.window_id -ne [int]$ManifestItem.window_id -or
        (ConvertTo-GpuQualificationInvariantDouble -Value $Result.recording_time_s -Field 'recording_time_s' -QualificationId $id) -ne (ConvertTo-GpuQualificationInvariantDouble -Value $ManifestItem.recording_time_s -Field 'manifest.recording_time_s' -QualificationId $id) -or
        [int]$Result.production_selected_L -ne [int]$ManifestItem.production_selected_L -or
        [int]$Result.production_path_count -ne [int]$ManifestItem.production_path_count) {
        throw "RESUME_IDENTITY_MISMATCH qualification_id=$id"
    }

    $shaProperty = $Result.PSObject.Properties['frozen_sage_sha256']
    $runProvenance = $null
    if ($null -eq $shaProperty -or [string]::IsNullOrWhiteSpace([string]$shaProperty.Value)) {
        if ($ResultLocation -cne 'LEGACY' -or $id -cnotin $script:RunLevelAttestationQualificationIds) {
            throw "RESUME_PROVENANCE_MISSING qualification_id=$id field=frozen_sage_sha256"
        }
        if ([string]::IsNullOrWhiteSpace($AttestationPath) -or -not (Test-Path -LiteralPath $AttestationPath -PathType Leaf) -or [string]::IsNullOrWhiteSpace($RepositoryRoot)) {
            throw "RESUME_PROVENANCE_MISSING qualification_id=$id external run-level attestation unavailable."
        }
        try { $attestation = Get-Content -LiteralPath $AttestationPath -Raw | ConvertFrom-Json }
        catch { throw "RESUME_ATTESTATION_INVALID_JSON qualification_id=$id path=$AttestationPath" }
        $runProvenance = Assert-GpuQualificationRunLevelAttestation -Result $Result -ManifestItem $ManifestItem -ResultPath $ResultPath -Attestation $attestation -ExpectedFrozenSha256 $ExpectedFrozenSha256 -RepositoryRoot $RepositoryRoot
    } else {
        $frozenSha = [string]$shaProperty.Value
        if ($frozenSha.ToLowerInvariant() -cne $ExpectedFrozenSha256.ToLowerInvariant()) {
            throw "RESUME_PROVENANCE_MISMATCH qualification_id=$id field=frozen_sage_sha256 expected=$ExpectedFrozenSha256 actual=$frozenSha"
        }
    }
    if ([string]$Result.status -cne 'COMPLETE' -or
        [string]$Result.cpu_production_reference -cne 'PASS' -or
        [string]$Result.gpu_structural_equivalence -cne 'PASS') {
        throw "RESUME_STATUS_NOT_PASS qualification_id=$id status=$($Result.status) cpu=$($Result.cpu_production_reference) gpu=$($Result.gpu_structural_equivalence)"
    }

    if ($ResultLocation -ceq 'CURRENT') {
        foreach ($field in @('result_source', 'provenance_mode', 'qualification_driver_sha256', 'execution_timestamp_utc')) {
            [void](Get-GpuQualificationRequiredProperty -InputObject $Result -Name $field -QualificationId $id)
        }
        if ([string]$Result.result_source -cne 'NEW_EXECUTION' -or
            [string]$Result.provenance_mode -cne 'PER_WINDOW_EMBEDDED_SHA' -or
            [string]$Result.qualification_driver_sha256 -notmatch '^(?i:[0-9a-f]{64})$') {
            throw "RESUME_PROVENANCE_INVALID qualification_id=$id current result is missing valid execution provenance."
        }
        $executionTimestamp = [DateTimeOffset]::MinValue
        if (-not [DateTimeOffset]::TryParse([string]$Result.execution_timestamp_utc, [ref]$executionTimestamp)) {
            throw "RESUME_PROVENANCE_INVALID qualification_id=$id field=execution_timestamp_utc"
        }
    }

    $requiredPassFlags = @(
        'selected_L_match',
        'path_count_match',
        'path_identity_match',
        'path_label_match',
        'model_validity_match'
    )
    if ($ResultLocation -ceq 'LEGACY') {
        $requiredPassFlags = @(
            'cpu_production_selected_L_match',
            'cpu_production_path_count_match',
            'cpu_production_path_identity_match',
            'cpu_production_path_label_match',
            'cpu_production_model_validity_match'
        ) + $requiredPassFlags
    }
    foreach ($field in $requiredPassFlags) {
        $value = Get-GpuQualificationRequiredProperty -InputObject $Result -Name $field -QualificationId $id
        if (-not (Test-GpuQualificationPassFlag $value)) {
            throw "RESUME_STATUS_NOT_PASS qualification_id=$id field=$field value=$value"
        }
    }
    if ($null -ne $runProvenance) { return $runProvenance }
    return [pscustomobject]@{ provenance_mode = 'PER_WINDOW_EMBEDDED_SHA'; result_blob_sha1 = ''; source_review_commit = '' }
}

function Test-GpuQualificationHistoricalIdentityFailure {
    param(
        [Parameter(Mandatory)][object]$Result,
        [Parameter(Mandatory)][object]$ManifestItem
    )
    $id = [string]$ManifestItem.qualification_id
    if ([string]$Result.status -cne 'FAIL_IDENTITY' -or [string]$Result.qualification_id -cne $id) { return $false }
    foreach ($field in @('scene_id', 'prn', 'tracking_channel', 'window_id', 'production_selected_L', 'production_path_count', 'recording_time_s', 'notes')) {
        if ($null -eq $Result.PSObject.Properties[$field]) { return $false }
    }
    if ([string]$Result.scene_id -cne [string]$ManifestItem.scene_id -or
        (ConvertTo-GpuQualificationNumericPrn $Result.prn) -ne (ConvertTo-GpuQualificationNumericPrn $ManifestItem.prn) -or
        [int]$Result.tracking_channel -ne [int]$ManifestItem.tracking_channel -or
        [int]$Result.window_id -ne [int]$ManifestItem.window_id -or
        [int]$Result.production_selected_L -ne [int]$ManifestItem.production_selected_L -or
        [int]$Result.production_path_count -ne [int]$ManifestItem.production_path_count) { return $false }

    $notes = [string]$Result.notes
    $numberPattern = '[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?'
    $timeMatch = [regex]::Match($notes, "recording_time_s manifest=(?<old>$numberPattern) formal=(?<formal>$numberPattern)")
    $stage0Match = [regex]::Match($notes, "formal_stage0_time=(?<formal>$numberPattern)")
    if (-not $notes.Contains('INPUT_IDENTITY_VALIDATION=FAIL') -or -not $timeMatch.Success -or -not $stage0Match.Success) { return $false }
    $oldTime = ConvertTo-GpuQualificationInvariantDouble -Value $timeMatch.Groups['old'].Value -Field 'historical.manifest_time' -QualificationId $id
    $formalTime = ConvertTo-GpuQualificationInvariantDouble -Value $timeMatch.Groups['formal'].Value -Field 'historical.formal_time' -QualificationId $id
    $stage0Time = ConvertTo-GpuQualificationInvariantDouble -Value $stage0Match.Groups['formal'].Value -Field 'historical.formal_stage0_time' -QualificationId $id
    $resultTime = ConvertTo-GpuQualificationInvariantDouble -Value $Result.recording_time_s -Field 'historical.recording_time_s' -QualificationId $id
    $currentTime = ConvertTo-GpuQualificationInvariantDouble -Value $ManifestItem.recording_time_s -Field 'manifest.recording_time_s' -QualificationId $id
    return ($oldTime -ne $currentTime -and $resultTime -eq $oldTime -and $formalTime -eq $currentTime -and $stage0Time -eq $currentTime)
}

function Get-GpuQualificationResumePlan {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)][object[]]$Manifest,
        [Parameter(Mandatory)][string]$ResultsDirectory,
        [Parameter(Mandatory)][string]$ExpectedFrozenSha256,
        [string]$AttestationPath = '',
        [string]$RepositoryRoot = ''
    )
    $canonical = [System.Collections.Generic.List[object]]::new()
    $pending = [System.Collections.Generic.List[object]]::new()
    $historical = [System.Collections.Generic.List[object]]::new()
    $seenIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    $currentDirectory = Join-Path $ResultsDirectory 'current'

    foreach ($item in $Manifest) {
        $id = [string]$item.qualification_id
        if ([string]::IsNullOrWhiteSpace($id) -or -not $seenIds.Add($id)) {
            throw "QUALIFICATION_MANIFEST_DUPLICATE_ID qualification_id=$id"
        }
        $legacyPath = Join-Path $ResultsDirectory ($id + '.json')
        $currentPath = Join-Path $currentDirectory ($id + '.json')
        $hasLegacy = Test-Path -LiteralPath $legacyPath -PathType Leaf
        $hasCurrent = Test-Path -LiteralPath $currentPath -PathType Leaf
        $legacyIsHistorical = $false
        $legacyResult = $null

        if ($hasLegacy) {
            try { $legacyResult = Get-Content -LiteralPath $legacyPath -Raw | ConvertFrom-Json }
            catch { throw "RESUME_RESULT_INVALID_JSON qualification_id=$id path=$legacyPath" }
            $legacyIsHistorical = Test-GpuQualificationHistoricalIdentityFailure -Result $legacyResult -ManifestItem $item
        }

        if ($hasLegacy -and $hasCurrent -and -not $legacyIsHistorical) {
            throw "RESUME_AMBIGUOUS_CURRENT_RESULT qualification_id=$id legacy=$legacyPath current=$currentPath"
        }
        if ($legacyIsHistorical) {
            $historical.Add([pscustomobject]@{
                qualification_id = $id
                path = $legacyPath
                status = [string]$legacyResult.status
                reason = 'PREVIOUS_IDENTITY_FAIL_MANIFEST_TIME_CORRECTION'
            })
        } elseif ($hasLegacy) {
            $provenance = Assert-GpuQualificationReusablePass -Result $legacyResult -ManifestItem $item -ExpectedFrozenSha256 $ExpectedFrozenSha256 -ResultPath $legacyPath -ResultLocation 'LEGACY' -AttestationPath $AttestationPath -RepositoryRoot $RepositoryRoot
            $legacyResult | Add-Member -NotePropertyName result_source -NotePropertyValue 'REUSED' -Force
            $legacyResult | Add-Member -NotePropertyName provenance_mode -NotePropertyValue $provenance.provenance_mode -Force
            $legacyResult | Add-Member -NotePropertyName resume_disposition -NotePropertyValue $(if ($provenance.provenance_mode -eq 'RUN_LEVEL_ATTESTED') { 'REUSED_RUN_LEVEL_ATTESTED' } else { 'REUSED_VALIDATED_PASS' }) -Force
            if ($provenance.result_blob_sha1) { $legacyResult | Add-Member -NotePropertyName result_blob_sha1 -NotePropertyValue $provenance.result_blob_sha1 -Force }
            $canonical.Add($legacyResult)
        }

        if ($hasCurrent) {
            try { $currentResult = Get-Content -LiteralPath $currentPath -Raw | ConvertFrom-Json }
            catch { throw "RESUME_RESULT_INVALID_JSON qualification_id=$id path=$currentPath" }
            $provenance = Assert-GpuQualificationReusablePass -Result $currentResult -ManifestItem $item -ExpectedFrozenSha256 $ExpectedFrozenSha256 -ResultPath $currentPath -ResultLocation 'CURRENT' -AttestationPath $AttestationPath -RepositoryRoot $RepositoryRoot
            if ($legacyIsHistorical) {
                $currentResult | Add-Member -NotePropertyName resume_disposition -NotePropertyValue 'REUSED_VALIDATED_PASS' -Force
                $canonical.Add($currentResult)
            } elseif (-not $hasLegacy) {
                $currentResult | Add-Member -NotePropertyName resume_disposition -NotePropertyValue 'REUSED_VALIDATED_PASS' -Force
                $canonical.Add($currentResult)
            }
        }

        if (-not $hasCurrent -and (-not $hasLegacy -or $legacyIsHistorical)) {
            $pending.Add($item)
        }
    }

    $canonicalIds = @($canonical | ForEach-Object { [string]$_.qualification_id })
    if (($canonicalIds | Select-Object -Unique).Count -ne $canonicalIds.Count) {
        throw 'RESUME_AGGREGATE_DUPLICATE_QUALIFICATION_ID'
    }
    return [pscustomobject]@{
        CanonicalResults = $canonical.ToArray()
        PendingItems = $pending.ToArray()
        HistoricalResults = $historical.ToArray()
    }
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
        [Parameter(Mandatory)][AllowEmptyCollection()][object[]]$Results,
        [Parameter(Mandatory)][string]$CsvPath
    )
    $ids = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($result in $Results) {
        if (-not $ids.Add([string]$result.qualification_id)) {
            throw "RESUME_AGGREGATE_DUPLICATE_QUALIFICATION_ID qualification_id=$($result.qualification_id)"
        }
    }
    if ($Results.Count -gt 0) {
        $columns = [System.Collections.Generic.List[string]]::new()
        foreach ($result in $Results) {
            foreach ($property in $result.PSObject.Properties) {
                if (-not $columns.Contains([string]$property.Name)) {
                    $columns.Add([string]$property.Name)
                }
            }
        }
        $normalizedResults = foreach ($result in $Results) {
            $row = [ordered]@{}
            foreach ($column in $columns) {
                $property = $result.PSObject.Properties[$column]
                $row[$column] = if ($null -eq $property) { $null } else { $property.Value }
            }
            [pscustomobject]$row
        }
        $normalizedResults | Export-Csv -LiteralPath $CsvPath -NoTypeInformation -Encoding UTF8
    } else {
        $columns = @(
            'qualification_id', 'scene_id', 'prn', 'tracking_channel', 'window_id', 'recording_time_s',
            'production_selected_L', 'cpu_selected_L', 'gpu_selected_L', 'production_path_count', 'cpu_path_count', 'gpu_path_count',
            'cpu_production_reference', 'gpu_structural_equivalence', 'selected_L_match', 'path_count_match', 'path_identity_match',
            'path_label_match', 'model_validity_match', 'max_delay_abs_diff', 'max_doppler_abs_diff', 'max_relative_power_abs_diff',
            'max_alpha_abs_diff', 'max_path_score_abs_diff', 'max_rss_abs_diff', 'max_rss_rel_diff', 'max_bic_abs_diff', 'max_bic_rel_diff',
            'cpu_best_l', 'cpu_second_best_l', 'cpu_bic_margin', 'gpu_best_l', 'gpu_second_best_l', 'gpu_bic_margin',
            'cpu_stage2_seconds', 'gpu_first_stage2_seconds', 'gpu_warm_stage2_seconds', 'gpu_transfer_in_seconds',
            'gpu_transfer_out_seconds', 'compute_speedup', 'end_to_end_warm_speedup', 'cpu_production_max_delay_abs_diff',
            'cpu_production_max_doppler_abs_diff', 'cpu_production_max_relative_power_abs_diff', 'cpu_production_max_alpha_abs_diff',
            'cpu_production_max_path_score_abs_diff', 'cpu_production_max_rss_abs_diff', 'cpu_production_max_rss_rel_diff',
            'cpu_production_max_bic_abs_diff', 'cpu_production_max_bic_rel_diff', 'separation_retry_status', 'raw_iq_read',
            'raw_iq_samples', 'status', 'notes', 'frozen_sage_sha256', 'result_source', 'provenance_mode',
            'resume_disposition', 'result_blob_sha1', 'qualification_driver_sha256', 'execution_timestamp_utc'
        )
        $headerObject = [ordered]@{}
        foreach ($column in $columns) { $headerObject[$column] = '' }
        $header = @([pscustomobject]$headerObject | ConvertTo-Csv -NoTypeInformation)[0]
        Set-Content -LiteralPath $CsvPath -Value $header -Encoding UTF8
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
    $reused = @($Results | Where-Object { $_.result_source -eq 'REUSED' }).Count
    $newExecution = @($Results | Where-Object { $_.result_source -eq 'NEW_EXECUTION' }).Count
    $runLevelAttested = @($Results | Where-Object { $_.provenance_mode -eq 'RUN_LEVEL_ATTESTED' }).Count
    $embeddedSha = @($Results | Where-Object { $_.provenance_mode -eq 'PER_WINDOW_EMBEDDED_SHA' }).Count
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
        "PREVIOUS_PASS_RESULTS_REUSED=$reused",
        "QUALIFICATION_WINDOWS_NEWLY_EXECUTED=$newExecution",
        "RESULTS_RUN_LEVEL_ATTESTED=$runLevelAttested",
        "RESULTS_WITH_PER_WINDOW_EMBEDDED_SHA=$embeddedSha",
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
        'New per-window records are in `results/current/`; unchanged legacy records remain in `results/`; aggregate rows are in `GPU_STAGE2_QUALIFICATION_RESULTS.csv`.',
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

function Write-GpuQualificationResult {
    param(
        [Parameter(Mandatory)][object]$Result,
        [Parameter(Mandatory)][string]$Path
    )
    if (Test-Path -LiteralPath $Path) {
        throw "QUALIFICATION_RESULT_COLLISION path=$Path; refusing overwrite."
    }
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        $null = New-Item -ItemType Directory -Path $parent -Force
    }
    $Result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $Path -Encoding UTF8
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
    $attestationPath = Join-Path $PSScriptRoot 'HISTORICAL_8_WINDOW_RUN_PROVENANCE_ATTESTATION.json'
    $repositoryRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
    $resumePlan = Get-GpuQualificationResumePlan -Manifest $manifest -ResultsDirectory $resultsDirectory -ExpectedFrozenSha256 $actualHash -AttestationPath $attestationPath -RepositoryRoot $repositoryRoot
    if (-not (Test-Path -LiteralPath $resultsDirectory -PathType Container)) {
        $null = New-Item -ItemType Directory -Path $resultsDirectory -Force
    }
    $csvCache = @{}
    $results = [System.Collections.Generic.List[object]]::new()
    foreach ($result in $resumePlan.CanonicalResults) { $results.Add($result) }
    $canonicalIds = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::Ordinal)
    foreach ($result in $results) { [void]$canonicalIds.Add([string]$result.qualification_id) }
    Write-GpuQualificationAggregate -Results $results.ToArray() -CsvPath $aggregatePath
    [void](Write-GpuQualificationSummary -Results $results.ToArray() -Path $summaryMarkdownPath)
    if ($resumePlan.PendingItems.Count -eq 0) {
        $verifiedHash = (Get-FileHash -LiteralPath $expectedSource -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($verifiedHash -cne $script:ExpectedFrozenSha256) {
            throw "SAGE_SOURCE_HASH_CHANGED during qualification expected=$script:ExpectedFrozenSha256 actual=$verifiedHash"
        }
        return
    }
    if ([string]::IsNullOrWhiteSpace($MatlabPath)) {
        $MatlabPath = (Get-Command matlab -CommandType Application -ErrorAction Stop).Source
    }
    if (-not (Test-Path -LiteralPath $MatlabPath -PathType Leaf)) {
        throw "MATLAB_EXECUTABLE_MISSING path=$MatlabPath"
    }
    $currentResultsDirectory = Join-Path $resultsDirectory 'current'
    $null = New-Item -ItemType Directory -Path $currentResultsDirectory -Force
    $qualificationDriverPath = Join-Path $PSScriptRoot 'Invoke-GpuStage2Qualification.ps1'
    $qualificationDriverSha256 = (Get-FileHash -LiteralPath $qualificationDriverPath -Algorithm SHA256).Hash.ToLowerInvariant()
    $stopReason = $null
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('gnss_gpu_qualification_' + [guid]::NewGuid().ToString('N'))
    $null = New-Item -ItemType Directory -Path $tempRoot

    try {
        foreach ($item in $manifest) {
            if ($canonicalIds.Contains([string]$item.qualification_id)) { continue }
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
                frozen_sage_sha256 = $actualHash
                result_source = 'NEW_EXECUTION'
                provenance_mode = 'PER_WINDOW_EMBEDDED_SHA'
                resume_disposition = 'NEW_EXECUTION'
                qualification_driver_sha256 = $qualificationDriverSha256
                execution_timestamp_utc = [DateTime]::UtcNow.ToString('o')
                status = 'NOT_STARTED'
                notes = ''
            }

            if ($null -ne $stopReason) {
                $record.status = if ($stopReason -like '*INPUT_IDENTITY_VALIDATION=FAIL*') { 'FAIL_IDENTITY' } else { 'FAIL_PREFLIGHT' }
                $record.notes = $stopReason
                if ($null -ne $formalWindow) {
                    $record.notes += " manifest_time=$($item.recording_time_s) formal_stage0_time=$($formalWindow.recordingTimeS)"
                }
                $recordJsonPath = Join-Path $currentResultsDirectory ($item.qualification_id + '.json')
                Write-GpuQualificationResult -Result ([pscustomobject]$record) -Path $recordJsonPath
                $results.Add([pscustomobject]$record)
                [void]$canonicalIds.Add([string]$item.qualification_id)
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

            $recordPath = Join-Path $currentResultsDirectory ($item.qualification_id + '.json')
            Write-GpuQualificationResult -Result ([pscustomobject]$record) -Path $recordPath
            $results.Add([pscustomobject]$record)
            [void]$canonicalIds.Add([string]$item.qualification_id)
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
