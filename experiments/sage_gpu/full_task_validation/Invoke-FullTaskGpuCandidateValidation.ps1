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
        elseif ($index -eq 0) {
            $renamedCandidate = $candidateBlock.RawText.Replace('run_nav_sage_pipeline_gpu_candidate', 'run_nav_sage_pipeline')
            if ($renamedCandidate -ceq $authorityBlock.RawText) {
                $category = 'NON_SCIENTIFIC_PLUMBING_DIFF'
                $status = 'ALLOWED_DIFF'
                $reason = 'CANDIDATE_ENTRY_FUNCTION_RENAMED_ONLY'
            }
            else {
                $category = 'UNEXPECTED_DIFF'
                $status = 'UNEXPECTED_DIFF'
                $reason = 'CANDIDATE_ENTRY_BODY_CHANGED_BEFORE_PLUMBING_REVIEW'
            }
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
        if ($script:QualifiedGpuCandidateFunctions -contains $candidateBlock.Name -and
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
