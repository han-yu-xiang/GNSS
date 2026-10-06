$script:ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
$script:DriverPath = Join-Path $script:ProjectRoot 'experiments/sage_gpu/full_task_validation/Invoke-FullTaskGpuCandidateValidation.ps1'
$script:AuthorityPath = 'E:/GNSS_Multipath_Project/scripts/sage_pipeline/run_nav_sage_pipeline.m'
$script:CandidatePath = Join-Path $script:ProjectRoot 'experiments/sage_gpu/full_task_candidate/run_nav_sage_pipeline_gpu_candidate.m'
$script:ExpectedFrozenSha = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'

if (Test-Path -LiteralPath $script:DriverPath) {
    . $script:DriverPath
}

Describe 'Full-task candidate Frozen source boundary' {
    It 'pins the absolute local authority and verifies its SHA-256' {
        $identity = Get-FrozenSourceIdentity -Path $script:AuthorityPath
        $identity.Path | Should Be $script:AuthorityPath
        $identity.Sha256 | Should Be $script:ExpectedFrozenSha
        $identity.Match | Should Be $true
    }

    It 'rejects the stale Frozen copy in the review worktree' {
        $staleSource = Join-Path $script:ProjectRoot 'scripts/sage_pipeline/run_nav_sage_pipeline.m'
        $identity = Get-FrozenSourceIdentity -Path $staleSource
        $identity.Match | Should Be $false
        $rejected = $false
        try {
            Assert-FrozenSourceIdentity -Path $staleSource | Out-Null
        }
        catch {
            $rejected = $true
        }
        $rejected | Should Be $true
    }

    It 'keeps the immutable Frozen function bodies and runStage2 byte-identical' {
        $audit = Get-FullTaskGpuSourceBoundaryAudit -AuthorityPath $script:AuthorityPath -CandidatePath $script:CandidatePath
        $audit.Status | Should Be 'PASS'
        $audit.UnexpectedDiffCount | Should Be 0

        foreach ($functionName in @('runStage2', 'flattenStage2', 'evaluatePersistence', 'runJointStage')) {
            $row = @($audit.Rows | Where-Object { $_.Function -eq $functionName })[0]
            $row.Status | Should Be 'UNCHANGED'
            $row.NormalizedExact | Should Be $true
        }

        $runStage2 = @($audit.Rows | Where-Object { $_.Function -eq 'runStage2' })[0]
        $runStage2.ByteIdentical | Should Be $true
    }

    It 'fails closed on an injected unclassified function change' {
        $temporaryCandidate = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString('N') + '.m')
        try {
            Copy-Item -LiteralPath $script:CandidatePath -Destination $temporaryCandidate
            $source = [IO.File]::ReadAllText($temporaryCandidate)
            $mutated = $source.Replace('function model = evaluateModel(', 'function model = evaluateModelInjected(')
            ($mutated -ne $source) | Should Be $true
            [IO.File]::WriteAllText($temporaryCandidate, $mutated, (New-Object Text.UTF8Encoding($false)))

            $audit = Get-FullTaskGpuSourceBoundaryAudit -AuthorityPath $script:AuthorityPath -CandidatePath $temporaryCandidate
            $audit.Status | Should Be 'BLOCKED'
            $audit.UnexpectedDiffCount | Should BeGreaterThan 0
            $rejected = $false
            try {
                Assert-FullTaskGpuSourceBoundary -AuthorityPath $script:AuthorityPath -CandidatePath $temporaryCandidate | Out-Null
            }
            catch {
                $rejected = $true
            }
            $rejected | Should Be $true
        }
        finally {
            if (Test-Path -LiteralPath $temporaryCandidate) {
                Remove-Item -LiteralPath $temporaryCandidate -Force
            }
        }
    }
}
