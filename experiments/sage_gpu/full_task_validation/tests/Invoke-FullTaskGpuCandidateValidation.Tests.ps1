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

    It 'pins the qualified GPU helper and shared selector source identities' {
        $identity = Get-QualifiedGpuSourceIdentity
        $identity.ProbeSha256 | Should Be 'bfe56ad02c99240257fddd212ba43ee5606a81740b3dda716c5947c433cbfa88'
        $identity.SelectorSha256 | Should Be 'a40c6459e66a384e85053589b270c5d2e112363872153fbf46da5c56fd4bb1f5'
        $identity.Match | Should Be $true
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

    It 'limits the Stage2 replacement to GPU fit computation, CPU gather, and the pre-return contract check' {
        $audit = Get-FullTaskGpuSourceBoundaryAudit -AuthorityPath $script:AuthorityPath -CandidatePath $script:CandidatePath
        $fitRow = @($audit.Rows | Where-Object { $_.Function -eq 'fitAllOrders' })[0]
        $fitRow.Category | Should Be 'GPU_STAGE2_COMPUTATIONAL_DIFFERENCE'
        $fitRow.Status | Should Be 'ALLOWED_DIFF'
        $audit.UnexpectedDiffCount | Should Be 0

        $candidate = Get-MatlabFunctionBlocks -LiteralPath $script:CandidatePath
        $fit = @($candidate | Where-Object { $_.Name -eq 'fitAllOrders' })[0]
        $fit.Normalized | Should Match '(?s)function\s+fit\s*=\s*fitAllOrders\s*\(\s*\.\.\.\s*row,\s*scanRow,\s*rawFile,\s*dopplerSign,\s*cfg\s*\)'
        $sequence = @('loadNavWipedFortyMs', 'makeSignalContext', 'fitAllOrdersGpu', 'gatherGpuFit', 'assertCpuResidentFrozenFit')
        $position = -1
        foreach ($name in $sequence) {
            $nextPosition = $fit.Normalized.IndexOf($name, $position + 1)
            ($nextPosition -gt $position) | Should Be $true
            $position = $nextPosition
        }
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

    It 'escapes MATLAB char literals by doubling embedded apostrophes' {
        (ConvertTo-MatlabCharLiteral "E:/reviewer's project") | Should Be "'E:/reviewer''s project'"
    }

    It 'maps only the two approved tasks to their exact namespaces' {
        $taskA = Get-FullTaskGpuTaskSpec -Task 'TaskA'
        $taskA.SceneId | Should Be 'F1023_V70_D0117_P2'
        $taskA.Prn | Should Be 28
        $taskA.TrackingChannel | Should Be 1
        $taskA.CandidateOutputNamespace | Should Be 'scenes/F1023_V70_D0117_P2/sage_results/gpu_candidate_fulltask_20261005/G28_ch1'
        $taskA.ReferenceOutputNamespace | Should Be 'scenes/F1023_V70_D0117_P2/sage_results/rerun_20261003_frozen_v3/G28_ch1'

        $taskB = Get-FullTaskGpuTaskSpec -Task 'TaskB'
        $taskB.SceneId | Should Be 'F1023_V120_D0121_P2'
        $taskB.Prn | Should Be 3
        $taskB.TrackingChannel | Should Be 2
        $taskB.CandidateOutputNamespace | Should Be 'scenes/F1023_V120_D0121_P2/sage_results/gpu_candidate_fulltask_20261005/G03_ch2'
        $taskB.ReferenceOutputNamespace | Should Be 'scenes/F1023_V120_D0121_P2/sage_results/rerun_20261003_frozen_v3/G03_ch2'
    }

    It 'requires candidate request, formal context, cfg/input, and helper identity to agree' {
        $request = [pscustomobject]@{ SceneId='F1023_V70_D0117_P2'; Prn=28; TrackingChannel=1 }
        $formal = [pscustomobject]@{
            sceneId='F1023_V70_D0117_P2'; prn=28; trackingChannel=1; samplingRateHz=10230000
            rawFile='E:/data/task-a.iq'; trackingFile='E:/data/task-a-track.mat'; telemetryFile='E:/data/task-a-telemetry.dat'
        }
        $cfg = [pscustomobject]@{
            sceneId='F1023_V70_D0117_P2'; targetPrn=28; trackingChannel=1; fsHz=10230000
            rawFile='E:\data\task-a.iq'; trackingFile='E:\data\task-a-track.mat'; telemetryFile='E:\data\task-a-telemetry.dat'
        }
        (Assert-FullTaskGpuTaskIdentity -CandidateRequest $request -FormalContext $formal -CandidateCfg $cfg -HelperRequestedPrn 28) | Should Be $true

        $cfg.targetPrn = 3
        $rejected = $false
        try {
            Assert-FullTaskGpuTaskIdentity -CandidateRequest $request -FormalContext $formal -CandidateCfg $cfg -HelperRequestedPrn 28 | Out-Null
        }
        catch {
            $rejected = $true
        }
        $rejected | Should Be $true
    }

    It 'blocks an existing candidate namespace without touching it' {
        $root = Join-Path ([IO.Path]::GetTempPath()) ('gpu-candidate-' + [guid]::NewGuid().ToString('N'))
        $existing = Join-Path $root 'existing'
        New-Item -ItemType Directory -Path $existing -Force | Out-Null
        try {
            (Assert-CandidateOutputAbsent -Path (Join-Path $root 'absent')) | Should Be $true
            $rejected = $false
            try {
                Assert-CandidateOutputAbsent -Path $existing | Out-Null
            }
            catch {
                $rejected = $true
            }
            $rejected | Should Be $true
            (Test-Path -LiteralPath $existing -PathType Container) | Should Be $true
        }
        finally {
            Remove-Item -LiteralPath $root -Recurse -Force
        }
    }

    It 'validates exact MATLAB function resolution after path normalization' {
        $candidate = Join-Path $script:ProjectRoot 'experiments/sage_gpu/full_task_candidate/run_nav_sage_pipeline_gpu_candidate.m'
        $selector = Join-Path $script:ProjectRoot 'experiments/sage_gpu/selectSeparatedResidualCandidate.m'
        (Assert-MatlabFunctionResolution -CandidateResolvedPath $candidate.Replace('\','/') -SelectorResolvedPath $selector -CandidateExpectedPath $candidate -SelectorExpectedPath $selector) | Should Be $true

        $rejected = $false
        try {
            Assert-MatlabFunctionResolution -CandidateResolvedPath (Join-Path $script:ProjectRoot 'wrong.m') -SelectorResolvedPath $selector -CandidateExpectedPath $candidate -SelectorExpectedPath $selector | Out-Null
        }
        catch {
            $rejected = $true
        }
        $rejected | Should Be $true
    }

    It 'builds RunUnitTests with only the two approved addpath directories' {
        $expression = New-CandidateUnitTestExpression -ReviewProjectRoot $script:ProjectRoot
        ([regex]::Matches($expression, 'addpath\(').Count) | Should Be 2
        $expression | Should Match 'MATLAB_FUNCTION_RESOLUTION_MISMATCH'
        $expression | Should Match 'MATLAB_FUNCTION_RESOLUTION_OK'
        $expression | Should Match 'runtests\('
        $expression | Should Not Match 'genpath'
        $expression.Contains((ConvertTo-MatlabCharLiteral (Join-Path $script:ProjectRoot 'experiments/sage_gpu/full_task_candidate'))) | Should Be $true
        $expression.Contains((ConvertTo-MatlabCharLiteral (Join-Path $script:ProjectRoot 'experiments/sage_gpu'))) | Should Be $true
    }

    It 'passes -batch and the whole expression as separate native arguments' {
        $expression = "disp('ARGUMENT_LIST_SMOKE')"
        $startInfo = New-CandidateMatlabProcessStartInfo -MatlabPath 'C:/MATLAB/bin/matlab.exe' -WorkingDirectory $script:ProjectRoot -Expression $expression
        $startInfo.UseShellExecute | Should Be $false
        $startInfo.RedirectStandardOutput | Should Be $true
        $startInfo.RedirectStandardError | Should Be $true
        $startInfo.ArgumentList.Count | Should Be 2
        $startInfo.ArgumentList[0] | Should Be '-batch'
        $startInfo.ArgumentList[1] | Should Be $expression
    }

    It 'initializes one GPU device after all candidate preflights and before Stage0, with no fallback' {
        $candidateSource = [IO.File]::ReadAllText($script:CandidatePath)
        ([regex]::Matches($candidateSource, '\bgpuDevice\s*\(').Count) | Should Be 1
        $entry = @(Get-MatlabFunctionBlocks -LiteralPath $script:CandidatePath | Where-Object { $_.Name -eq 'run_nav_sage_pipeline_gpu_candidate' })[0]
        $sequence = @('assertFrozenSageSourceHash', 'assertCandidateTaskIdentity', 'assertReferenceContextIdentity', 'assertGpuAvailability', 'assertCandidateOutputAbsent', 'gpuDevice(', '%% Stage 0')
        $position = -1
        foreach ($token in $sequence) {
            $nextPosition = $entry.Normalized.IndexOf($token, $position + 1)
            ($nextPosition -gt $position) | Should Be $true
            $position = $nextPosition
        }
        $candidateSource | Should Not Match 'gpuDeviceReset'
        $candidateSource | Should Not Match 'fitAllOrdersCpu'

        foreach ($functionName in @('fitAllOrders', 'fitAllOrdersGpu', 'initializeResidualPathGpu', 'runSageGpu', 'evaluateModelGpu')) {
            $block = @(Get-MatlabFunctionBlocks -LiteralPath $script:CandidatePath | Where-Object { $_.Name -eq $functionName })[0]
            $block.Normalized | Should Not Match '\bgpuDevice\s*\('
        }
    }

    It 'keeps candidate provenance outside the Frozen cfg' {
        $candidateSource = [IO.File]::ReadAllText($script:CandidatePath)
        $candidateSource | Should Match 'candidate_provenance\.json'
        $candidateSource | Should Match 'frozen_source_sha256'
        $candidateSource | Should Match 'gpu_candidate_source_sha256'
        $candidateSource | Should Not Match 'cfg\s*\.\s*(frozen_source_sha256|gpu_candidate_source_sha256|qualified_gpu_stage2_source_identity|candidate_output_namespace|gpu_identity)'
        $candidateSource | Should Not Match 'cfg\s*\.\s*(sceneId|prnLabel|trackingChannel)\s*='
    }

    It 'invokes exactly one named task and does not queue a follow-up task' {
        $driverSource = [IO.File]::ReadAllText($script:DriverPath)
        $driverSource | Should Not Match 'foreach\s*\(\s*\$task\s+in\s+\$script:CandidateTasks'
        $driverSource | Should Not Match 'Start-Job|Start-ThreadJob'
        $runAndCompare = [regex]::Match($driverSource, '(?s)function Invoke-RunAndCompare\b.*?(?=\r?\nfunction |\z)').Value
        $runAndCompare | Should Match '\$TaskSpec'
        ([regex]::Matches($runAndCompare, 'Invoke-CandidateMatlabBatch')).Count | Should Be 1
    }
}
