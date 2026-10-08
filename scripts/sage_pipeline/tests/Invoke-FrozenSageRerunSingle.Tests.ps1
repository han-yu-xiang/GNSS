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

function New-GpuExecutionProvenanceTestFiles {
    param(
        [Parameter(Mandatory)][string]$Directory,
        [Parameter(Mandatory)][object]$Context
    )

    $timestamp = [DateTimeOffset]::UtcNow.ToString('o')
    $attempt = [ordered]@{
        run_id = [string]$Context.RunId
        scene_id = [string]$Context.SceneId
        prn = 'G{0:D2}' -f [int]$Context.Prn
        tracking_channel = [int]$Context.TrackingChannel
        execution_mode = 'GPU_STAGE2_QUALIFIED'
        execution_plan_sha256 = [string]$Context.ExecutionPlanSha256
        gpu_source_contract_sha256 = $script:ApprovedGpuSourceContractSha256
        frozen_authority_sha256 = $script:FrozenSourceSha256
        qualified_candidate_sha256 = $script:QualifiedCandidateSha256
        qualified_probe_sha256 = $script:QualifiedProbeSha256
        qualified_selector_sha256 = $script:QualifiedSelectorSha256
        resume = $false
        attempt_timestamp = $timestamp
        attempt_status = 'AUTHORIZED'
    }
    $runtime = [ordered]@{
        run_id = [string]$Context.RunId
        execution_mode = 'GPU_STAGE2_QUALIFIED'
        execution_plan_sha256 = [string]$Context.ExecutionPlanSha256
        gpu_source_contract_sha256 = $script:ApprovedGpuSourceContractSha256
        production_gpu_entry_sha256 = $script:ApprovedGpuProductionEntrySha256
        frozen_authority_sha256 = $script:FrozenSourceSha256
        qualified_candidate_sha256 = $script:QualifiedCandidateSha256
        qualified_probe_sha256 = $script:QualifiedProbeSha256
        qualified_selector_sha256 = $script:QualifiedSelectorSha256
        gpu_identity = 'Fixture GPU'
        matlab_version = 'R2025a fixture'
        resume = $false
        execution_timestamp = $timestamp
    }
    [IO.File]::WriteAllText((Join-Path $Directory 'gpu_execution_attempt.json'),
        ($attempt | ConvertTo-Json -Depth 5 -Compress), [Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllText((Join-Path $Directory 'gpu_execution_provenance.json'),
        ($runtime | ConvertTo-Json -Depth 5 -Compress), [Text.UTF8Encoding]::new($false))
}

function New-FrozenSageTestManifestRow {
    param(
        [string]$SceneId = 'F1023_V70_D0117_P2',
        [string]$PrnLabel = 'G28',
        [string]$TrackingChannel = '1',
        [string]$MappingWarning = 'NONE',
        [string]$RunId = 'run_20261003_F1023_V70_D0117_P2_G28_ch1',
        [string]$OutputNamespace
    )

    if ([string]::IsNullOrWhiteSpace($OutputNamespace)) {
        $OutputNamespace = "scenes\$SceneId\sage_results\rerun_20261003_frozen_v3\${PrnLabel}_ch${TrackingChannel}"
    }
    [pscustomobject]@{
        run_id = $RunId
        scene_id = $SceneId
        prn = $PrnLabel
        tracking_channel = $TrackingChannel
        mapping_warning = $MappingWarning
        frozen_sage_sha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
        output_namespace = $OutputNamespace
        resume = 'false'
        execution_status = 'NOT_STARTED'
    }
}

function New-GpuExecutionPlanTestFixture {
    param(
        [string]$RunId = 'fixture_run_id',
        [string]$SceneId = 'F1023_V70_D0117_P2',
        [string]$PrnLabel = 'G28',
        [string]$TrackingChannel = '1',
        [hashtable]$PlanOverrides = @{}
    )

    $root = Join-Path $TestDrive ('gpu-plan-' + [guid]::NewGuid().ToString('N'))
    [void](New-Item -ItemType Directory -Path $root -Force)
    $manifestPath = Join-Path $root 'manifest.csv'
    $repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
    $contractPath = Join-Path $repoRoot 'experiments\sage_gpu\production_integration\PRODUCTION_GPU_SOURCE_CONTRACT.json'
    $entryPath = Join-Path $repoRoot 'scripts\sage_pipeline\run_nav_sage_pipeline_gpu_production.m'
    $planPath = Join-Path $root 'execution-plan.json'
    $manifestCsv = "run_id,scene_id,prn,tracking_channel`n$RunId,$SceneId,$PrnLabel,$TrackingChannel`n"
    [System.IO.File]::WriteAllText($manifestPath, $manifestCsv, [System.Text.UTF8Encoding]::new($false))
    $canonicalIdentity = "run_id=$RunId`nscene_id=$SceneId`nprn=$PrnLabel`ntracking_channel=$TrackingChannel`n"
    $taskIdentitySha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData(
        [Text.UTF8Encoding]::new($false).GetBytes($canonicalIdentity))).ToLowerInvariant()

    $plan = [ordered]@{
        schema_version = 'frozen-sage-gpu-execution-plan-v2'
        execution_mode = 'GPU_STAGE2_QUALIFIED'
        source_manifest_sha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
        resume = $false
        max_parallel_matlab = 1
        authorized_tasks = @([ordered]@{ run_id = $RunId; task_identity_sha256 = $taskIdentitySha256 })
    }
    foreach ($key in $PlanOverrides.Keys) { $plan[$key] = $PlanOverrides[$key] }
    [System.IO.File]::WriteAllText($planPath, ($plan | ConvertTo-Json -Depth 5), [System.Text.UTF8Encoding]::new($false))
    $script:ApprovedGpuExecutionPlanSha256 = (Get-FileHash -LiteralPath $planPath -Algorithm SHA256).Hash.ToLowerInvariant()
    return [pscustomobject]@{
        Root = $root
        RunId = $RunId
        SceneId = $SceneId
        PrnLabel = $PrnLabel
        TrackingChannel = [int]$TrackingChannel
        TaskIdentitySha256 = $taskIdentitySha256
        ManifestPath = $manifestPath
        SourceContractPath = $contractPath
        ProductionEntryPath = $entryPath
        ExecutionPlanPath = $planPath
    }
}

function New-GpuProductionSourceIdentityFixture {
    $repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
    $sourceContractPath = Join-Path $repoRoot 'experiments\sage_gpu\production_integration\PRODUCTION_GPU_SOURCE_CONTRACT.json'
    return [pscustomobject]@{
        RepoRoot = $repoRoot
        Frozen = 'E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_nav_sage_pipeline.m'
        ProductionEntry = Join-Path $repoRoot 'scripts\sage_pipeline\run_nav_sage_pipeline_gpu_production.m'
        Candidate = Join-Path $repoRoot 'experiments\sage_gpu\full_task_candidate\run_nav_sage_pipeline_gpu_candidate.m'
        Probe = Join-Path $repoRoot 'experiments\sage_gpu\stage2_window_173_gpu_probe.m'
        Selector = Join-Path $repoRoot 'experiments\sage_gpu\selectSeparatedResidualCandidate.m'
        SourceContract = $sourceContractPath
        ExecutionPlan = [pscustomobject]@{ ExecutionMode = 'GPU_STAGE2_QUALIFIED' }
    }
}

Describe 'Invoke-FrozenSageRerunSingle safety contract' {
    It 'defaults to CPU_FROZEN when no execution plan is supplied' {
        $result = Invoke-ProductionFunctionSafely -Name 'Resolve-FrozenSageExecutionPlan' -Arguments @{
            ExecutionPlanPath = $null
            RunId = 'fixture_run_id'
            ManifestPath = Join-Path $TestDrive 'unused-manifest.csv'
            SourceContractPath = Join-Path $TestDrive 'unused-contract.json'
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value.ExecutionMode | Should Be 'CPU_FROZEN'
        $result.Value.ExecutionPlanSha256 | Should Be ''
    }

    It 'does not accept a bare -Mode GPU CLI switch' {
        $errorText = ''
        try {
            & $wrapperPath -Mode GPU -RunId 'fixture_run_id' 2>&1 | Out-String
        } catch {
            $errorText = $_.Exception.Message
        }
        $errorText | Should Match 'Mode|parameter|named parameter'
    }

    It 'accepts a valid hashed GPU execution-plan fixture for its authorized run id' {
        $fixture = New-GpuExecutionPlanTestFixture
        $result = Invoke-ProductionFunctionSafely -Name 'Resolve-FrozenSageExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath
            RunId = $fixture.RunId
            ManifestPath = $fixture.ManifestPath
            SourceContractPath = $fixture.SourceContractPath
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value.ExecutionMode | Should Be 'GPU_STAGE2_QUALIFIED'
        $result.Value.Resume | Should Be $false
        $result.Value.MaxParallelMatlab | Should Be 1
        $result.Value.ExecutionPlanSha256 | Should Be (Get-FileHash -LiteralPath $fixture.ExecutionPlanPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $result.Value.TaskIdentitySha256 | Should Be $fixture.TaskIdentitySha256
    }

    It 'uses plan v2 without contract or entry hashes and binds the task identity to its manifest row' {
        $fixture = New-GpuExecutionPlanTestFixture
        $plan = Get-Content -Raw -LiteralPath $fixture.ExecutionPlanPath | ConvertFrom-Json
        @($plan.PSObject.Properties.Name) | Should Be @(
            'schema_version', 'execution_mode', 'source_manifest_sha256',
            'resume', 'max_parallel_matlab', 'authorized_tasks'
        )
        ($plan.PSObject.Properties.Name -contains 'gpu_source_contract_sha256') | Should Be $false
        ($plan.PSObject.Properties.Name -contains 'production_gpu_entry_sha256') | Should Be $false
        $plan.authorized_tasks[0].task_identity_sha256 | Should Be $fixture.TaskIdentitySha256
    }

    It 'uses the canonical UTF-8 task identity serialization and fixed digest' {
        $digest = Get-FrozenSageCanonicalTaskIdentitySha256 -RunId 'fixture_run_01' `
            -SceneId 'FIXTURE_SCENE' -PrnLabel 'G03' -TrackingChannel 2
        $digest | Should Be 'ab5f37a5c381215095ce77ff7394b89d5c307a902985eaa0096a3f86c458e1ba'
    }

    It 'fails closed when no GPU execution plan has been released' {
        $fixture = New-GpuExecutionPlanTestFixture
        $script:ApprovedGpuExecutionPlanSha256 = ''
        $result = Invoke-ProductionFunctionSafely -Name 'Resolve-FrozenSageExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath; RunId = $fixture.RunId
            ManifestPath = $fixture.ManifestPath; SourceContractPath = $fixture.SourceContractPath
        }
        $result.Error | Should Match 'GPU_EXECUTION_PLAN_NOT_RELEASED'
    }

    It 'rejects a schema-valid plan whose SHA is not the independent runner pin' {
        $fixture = New-GpuExecutionPlanTestFixture
        $script:ApprovedGpuExecutionPlanSha256 = 'f' * 64
        $result = Invoke-ProductionFunctionSafely -Name 'Resolve-FrozenSageExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath; RunId = $fixture.RunId
            ManifestPath = $fixture.ManifestPath; SourceContractPath = $fixture.SourceContractPath
        }
        $result.Error | Should Match 'GPU_EXECUTION_PLAN_SHA_MISMATCH'
    }

    It 'does not expose a caller-supplied expected plan SHA parameter' {
        $command = Get-Command -Name $wrapperPath -ErrorAction Stop
        @($command.Parameters.Keys | Where-Object { $_ -match 'Expected.*Sha|Plan.*Sha|Approved.*Plan' }).Count | Should Be 0
    }

    It 'rejects a self-consistent replacement contract and production entry against the external pins' {
        $fixture = New-GpuProductionSourceIdentityFixture
        $contract = Get-Content -Raw -LiteralPath $fixture.SourceContract | ConvertFrom-Json
        $fakeEntry = Join-Path $TestDrive 'caller-production-entry.m'
        [IO.File]::WriteAllText($fakeEntry, 'function caller_entry; end')
        $contract.production_entry_sha256 = (Get-FileHash -LiteralPath $fakeEntry -Algorithm SHA256).Hash.ToLowerInvariant()
        $replacementContract = Join-Path $TestDrive 'caller-source-contract.json'
        [IO.File]::WriteAllText($replacementContract, ($contract | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
        $identityPlan = [pscustomobject]@{ ExecutionMode = 'GPU_STAGE2_QUALIFIED' }
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageGpuSourceIdentity' -Arguments @{
            ExecutionPlan = $identityPlan; FrozenAuthorityPath = $fixture.Frozen
            QualifiedCandidatePath = $fixture.Candidate; QualifiedProbePath = $fixture.Probe
            QualifiedSelectorPath = $fixture.Selector; ProductionEntryPath = $fakeEntry
            SourceContractPath = $replacementContract
        }
        $result.Error | Should Match 'GPU_SOURCE_IDENTITY_MISMATCH.*source_contract_sha256'
    }

    It 'pins the production entry independently of a matching replacement contract' {
        $originalContractPin = $script:ApprovedGpuSourceContractSha256
        $fixture = New-GpuProductionSourceIdentityFixture
        $contract = Get-Content -Raw -LiteralPath $fixture.SourceContract | ConvertFrom-Json
        $fakeEntry = Join-Path $TestDrive 'alternate-production-entry.m'
        [IO.File]::WriteAllText($fakeEntry, 'function alternate_entry; end')
        $contract.production_entry_sha256 = (Get-FileHash -LiteralPath $fakeEntry -Algorithm SHA256).Hash.ToLowerInvariant()
        $replacementContract = Join-Path $TestDrive 'alternate-source-contract.json'
        [IO.File]::WriteAllText($replacementContract, ($contract | ConvertTo-Json -Depth 8), [Text.UTF8Encoding]::new($false))
        $script:ApprovedGpuSourceContractSha256 = (Get-FileHash -LiteralPath $replacementContract -Algorithm SHA256).Hash.ToLowerInvariant()
        $identityPlan = [pscustomobject]@{ ExecutionMode = 'GPU_STAGE2_QUALIFIED' }
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageGpuSourceIdentity' -Arguments @{
            ExecutionPlan = $identityPlan; FrozenAuthorityPath = $fixture.Frozen
            QualifiedCandidatePath = $fixture.Candidate; QualifiedProbePath = $fixture.Probe
            QualifiedSelectorPath = $fixture.Selector; ProductionEntryPath = $fakeEntry
            SourceContractPath = $replacementContract
        }
        $script:ApprovedGpuSourceContractSha256 = $originalContractPin
        $result.Error | Should Match 'GPU_SOURCE_IDENTITY_MISMATCH.*production_entry_sha256.*pinned'
    }

    It 'keeps CPU_FROZEN resolution independent of an unreleased GPU plan pin' {
        $script:ApprovedGpuExecutionPlanSha256 = ''
        $result = Invoke-ProductionFunctionSafely -Name 'Resolve-FrozenSageExecutionPlan' -Arguments @{
            ExecutionPlanPath = $null; RunId = 'fixture_run_id'
            ManifestPath = Join-Path $TestDrive 'unused-manifest.csv'
            SourceContractPath = Join-Path $TestDrive 'unused-contract.json'
        }
        $result.Error | Should Be $null
        $result.Value.ExecutionMode | Should Be 'CPU_FROZEN'
    }

    It 'keeps CPU runner lock payloads free of GPU release requirements' {
        $preflight = [pscustomobject]@{
            RunId='cpu_fixture'; SceneId='F1023_V70_D0117_P2'; Prn=28; TrackingChannel=1
            MappingWarning='NONE'; ExecutionMode='CPU_FROZEN'
        }
        $plan = [pscustomobject]@{ ExecutionPlanSha256='' }
        $payload = New-FrozenSageRunnerLockPayload -Preflight $preflight -ExecutionPlan $plan
        ($payload.Keys -contains 'execution_mode') | Should Be $false
        ($payload.Keys -contains 'execution_plan_sha256') | Should Be $false
        ($payload.Keys -contains 'gpu_source_contract_sha256') | Should Be $false
    }

    It 'rejects a plan with an unsupported schema version' {
        $fixture = New-GpuExecutionPlanTestFixture -PlanOverrides @{ schema_version = 'future-schema' }
        $result = Invoke-ProductionFunctionSafely -Name 'Resolve-FrozenSageExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath; RunId = $fixture.RunId
            ManifestPath = $fixture.ManifestPath; SourceContractPath = $fixture.SourceContractPath
        }
        $result.Available | Should Be $true
        $result.Error | Should Match 'SCHEMA'
    }

    It 'rejects a source manifest hash that differs from the current file' {
        $fixture = New-GpuExecutionPlanTestFixture -PlanOverrides @{ source_manifest_sha256 = ('0' * 64) }
        $result = Invoke-ProductionFunctionSafely -Name 'Resolve-FrozenSageExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath; RunId = $fixture.RunId
            ManifestPath = $fixture.ManifestPath; SourceContractPath = $fixture.SourceContractPath
        }
        $result.Available | Should Be $true
        $result.Error | Should Match 'MANIFEST.*SHA|SOURCE_MANIFEST'
    }

    It 'rejects a replaced source contract against the independent runner pin' {
        $fixture = New-GpuExecutionPlanTestFixture
        $replacementContract = Join-Path $TestDrive 'mutated-source-contract.json'
        [IO.File]::WriteAllText($replacementContract, (Get-Content -Raw -LiteralPath $fixture.SourceContractPath) + "`n ")
        $result = Invoke-ProductionFunctionSafely -Name 'Resolve-FrozenSageExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath; RunId = $fixture.RunId
            ManifestPath = $fixture.ManifestPath; SourceContractPath = $replacementContract
        }
        $result.Available | Should Be $true
        $result.Error | Should Match 'GPU_SOURCE_IDENTITY_MISMATCH field=source_contract_sha256'
    }

    It 'rejects resume enabled in a GPU plan' {
        $fixture = New-GpuExecutionPlanTestFixture -PlanOverrides @{ resume = $true }
        $result = Invoke-ProductionFunctionSafely -Name 'Resolve-FrozenSageExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath; RunId = $fixture.RunId
            ManifestPath = $fixture.ManifestPath; SourceContractPath = $fixture.SourceContractPath
        }
        $result.Available | Should Be $true
        $result.Error | Should Match 'RESUME'
    }

    It 'rejects GPU plans that permit parallel MATLAB workers' {
        $fixture = New-GpuExecutionPlanTestFixture -PlanOverrides @{ max_parallel_matlab = 2 }
        $result = Invoke-ProductionFunctionSafely -Name 'Resolve-FrozenSageExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath; RunId = $fixture.RunId
            ManifestPath = $fixture.ManifestPath; SourceContractPath = $fixture.SourceContractPath
        }
        $result.Available | Should Be $true
        $result.Error | Should Match 'PARALLEL'
    }

    It 'rejects a run id outside the execution plan authorized scope' {
        $fixture = New-GpuExecutionPlanTestFixture
        $result = Invoke-ProductionFunctionSafely -Name 'Resolve-FrozenSageExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath; RunId = 'not_authorized'
            ManifestPath = $fixture.ManifestPath; SourceContractPath = $fixture.SourceContractPath
        }
        $result.Available | Should Be $true
        $result.Error | Should Match 'UNAUTHORIZED_RUN_ID|RUN_ID.*SCOPE'
    }

    It 'rejects duplicate authorized run ids' {
        $fixture = New-GpuExecutionPlanTestFixture -PlanOverrides @{
            authorized_tasks = @(
                [ordered]@{ run_id = 'fixture_run_id'; task_identity_sha256 = '1' * 64 },
                [ordered]@{ run_id = 'fixture_run_id'; task_identity_sha256 = '1' * 64 }
            )
        }
        $result = Invoke-ProductionFunctionSafely -Name 'Resolve-FrozenSageExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath; RunId = $fixture.RunId
            ManifestPath = $fixture.ManifestPath; SourceContractPath = $fixture.SourceContractPath
        }
        $result.Available | Should Be $true
        $result.Error | Should Match 'DUPLICATE.*RUN_ID'
    }

    It 'rejects an unknown execution mode' {
        $fixture = New-GpuExecutionPlanTestFixture -PlanOverrides @{ execution_mode = 'GPU' }
        $result = Invoke-ProductionFunctionSafely -Name 'Resolve-FrozenSageExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath; RunId = $fixture.RunId
            ManifestPath = $fixture.ManifestPath; SourceContractPath = $fixture.SourceContractPath
        }
        $result.Available | Should Be $true
        $result.Error | Should Match 'UNKNOWN.*MODE|EXECUTION_MODE'
    }

    It 'validates Frozen, candidate, probe, selector, entry, and source-contract identity together' {
        $fixture = New-GpuProductionSourceIdentityFixture
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageGpuSourceIdentity' -Arguments @{
            ExecutionPlan = $fixture.ExecutionPlan
            FrozenAuthorityPath = $fixture.Frozen
            QualifiedCandidatePath = $fixture.Candidate
            QualifiedProbePath = $fixture.Probe
            QualifiedSelectorPath = $fixture.Selector
            ProductionEntryPath = $fixture.ProductionEntry
            SourceContractPath = $fixture.SourceContract
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value.ProductionEntrySha256 | Should Be (Get-FileHash -LiteralPath $fixture.ProductionEntry -Algorithm SHA256).Hash.ToLowerInvariant()
    }

    It 'rejects a Frozen authority source hash mismatch' {
        $fixture = New-GpuProductionSourceIdentityFixture
        $fakeFrozen = Join-Path $TestDrive 'not-frozen.m'
        [IO.File]::WriteAllText($fakeFrozen, 'function notFrozen()`nend`n')
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageGpuSourceIdentity' -Arguments @{
            ExecutionPlan = $fixture.ExecutionPlan
            FrozenAuthorityPath = $fakeFrozen
            QualifiedCandidatePath = $fixture.Candidate
            QualifiedProbePath = $fixture.Probe
            QualifiedSelectorPath = $fixture.Selector
            ProductionEntryPath = $fixture.ProductionEntry
            SourceContractPath = $fixture.SourceContract
        }
        $result.Error | Should Match 'FROZEN.*SHA|AUTHORITY.*MISMATCH'
    }

    It 'rejects a production entry hash mismatch' {
        $fixture = New-GpuProductionSourceIdentityFixture
        $fakeEntry = Join-Path $TestDrive 'changed-production-entry.m'
        [IO.File]::WriteAllText($fakeEntry, [IO.File]::ReadAllText($fixture.ProductionEntry) + "`n% changed`n")
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageGpuSourceIdentity' -Arguments @{
            ExecutionPlan = $fixture.ExecutionPlan
            FrozenAuthorityPath = $fixture.Frozen
            QualifiedCandidatePath = $fixture.Candidate
            QualifiedProbePath = $fixture.Probe
            QualifiedSelectorPath = $fixture.Selector
            ProductionEntryPath = $fakeEntry
            SourceContractPath = $fixture.SourceContract
        }
        $result.Error | Should Match 'PRODUCTION.*SHA|ENTRY.*MISMATCH'
    }

    It 'rejects a qualified selector hash mismatch' {
        $fixture = New-GpuProductionSourceIdentityFixture
        $fakeSelector = Join-Path $TestDrive 'changed-selector.m'
        [IO.File]::WriteAllText($fakeSelector, 'function selectSeparatedResidualCandidate()`nend`n')
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageGpuSourceIdentity' -Arguments @{
            ExecutionPlan = $fixture.ExecutionPlan
            FrozenAuthorityPath = $fixture.Frozen
            QualifiedCandidatePath = $fixture.Candidate
            QualifiedProbePath = $fixture.Probe
            QualifiedSelectorPath = $fakeSelector
            ProductionEntryPath = $fixture.ProductionEntry
            SourceContractPath = $fixture.SourceContract
        }
        $result.Error | Should Match 'SELECTOR.*SHA|SOURCE.*MISMATCH'
    }

    It 'rejects a plan task identity mismatch against the actual manifest row' {
        $fixture = New-GpuExecutionPlanTestFixture -PlanOverrides @{
            authorized_tasks = @([ordered]@{
                run_id = 'fixture_run_id'; task_identity_sha256 = ('0' * 64)
            })
        }
        $result = Invoke-ProductionFunctionSafely -Name 'Resolve-FrozenSageExecutionPlan' -Arguments @{
            ExecutionPlanPath = $fixture.ExecutionPlanPath
            RunId = $fixture.RunId
            ManifestPath = $fixture.ManifestPath
            SourceContractPath = $fixture.SourceContractPath
        }
        $result.Error | Should Match 'TASK_IDENTITY_MISMATCH'
    }

    It 'fails closed when the GPU MATLAB preflight is unavailable' {
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-GpuMatlabAvailabilitySmoke' -Arguments @{
            ExitCode = 3
            Stdout = 'MATLAB_STARTUP_OK'
        }
        $result.Available | Should Be $true
        $result.Error | Should Match 'GPU_NOT_AVAILABLE'
    }

    It 'builds a GPU-only MATLAB expression with verified code paths and provenance but no CPU fallback' {
        $result = Invoke-ProductionFunctionSafely -Name 'Get-GpuSageMatlabExpression' -Arguments @{
            SceneId = 'F1023_V70_D0117_P2'
            Prn = 28
            TrackingChannel = 1
            ProjectRoot = 'E:\GNSS_Multipath_Project'
            RunId = 'fixture_run_id'
            ExecutionPlanPath = 'C:\review\approved-plan.json'
            ProductionEntryPath = 'C:\review\scripts\sage_pipeline\run_nav_sage_pipeline_gpu_production.m'
            SelectorPath = 'C:\review\experiments\sage_gpu\selectSeparatedResidualCandidate.m'
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value | Should Match 'run_nav_sage_pipeline_gpu_production'
        $result.Value | Should Match 'ExecutionPlanPath'
        $result.Value | Should Not Match 'ExecutionPlanSha256|SourceManifestSha256'
        $result.Value | Should Match "'Resume',false"
        $result.Value | Should Not Match 'run_nav_sage_pipeline\('
        $result.Value | Should Match 'selectSeparatedResidualCandidate'
    }

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
        $accepted = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageManifestRow' -Arguments @{
            Row = $row
            ExpectedRunId = $row.run_id
        }
        $accepted.Available | Should Be $true
        $accepted.Error | Should Be $null
        $accepted.Value | Should Be $true

        $row.tracking_channel = '2'
        $rejected = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageManifestRow' -Arguments @{
            Row = $row
            ExpectedRunId = $row.run_id
        }
        $rejected.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($rejected.Error) | Should Be $false
    }

    It 'preserves a manifest tracking channel zero when frozen MATLAB accepts it' {
        $row = New-FrozenSageTestManifestRow `
            -SceneId 'F1023_V120_D0121_P2' `
            -PrnLabel 'G11' `
            -TrackingChannel '0' `
            -RunId 'run_20261003_F1023_V120_D0121_P2_G11_ch0'
        $accepted = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageManifestRow' -Arguments @{
            Row = $row
            ExpectedRunId = $row.run_id
        }
        $accepted.Available | Should Be $true
        $accepted.Error | Should Be $null
        $accepted.Value | Should Be $true
        $row.output_namespace | Should Be 'scenes\F1023_V120_D0121_P2\sage_results\rerun_20261003_frozen_v3\G11_ch0'

        $expression = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageMatlabExpression' -Arguments @{
            SceneId = $row.scene_id
            Prn = 11
            TrackingChannel = 0
            ProjectRoot = 'E:\GNSS_Multipath_Project'
        }
        $expression.Error | Should Be $null
        $expression.Value | Should Be "run_nav_sage_pipeline('F1023_V120_D0121_P2',11,'TrackingChannel',0,'ProjectRoot','E:/GNSS_Multipath_Project','Resume',false)"
    }

    It 'accepts the approved missing tracking-start warning without changing the channel namespace' {
        $warningRow = New-FrozenSageTestManifestRow `
            -SceneId 'F1023_V120_D0121_P2' `
            -PrnLabel 'G06' `
            -TrackingChannel '6' `
            -MappingWarning 'NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING' `
            -RunId 'run_20261003_F1023_V120_D0121_P2_G06_ch6'
        $accepted = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageManifestRow' -Arguments @{
            Row = $warningRow
            ExpectedRunId = $warningRow.run_id
        }

        $accepted.Available | Should Be $true
        $accepted.Error | Should Be $null
        $accepted.Value | Should Be $true
        $warningRow.mapping_warning | Should Be 'NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING'
        $warningRow.output_namespace | Should Be 'scenes\F1023_V120_D0121_P2\sage_results\rerun_20261003_frozen_v3\G06_ch6'
    }

    It 'rejects an unsupported warning and a namespace that omits the channel' {
        $row = New-FrozenSageTestManifestRow -MappingWarning 'UNEXPECTED_WARNING'
        $warningRejected = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageManifestRow' -Arguments @{
            Row = $row
            ExpectedRunId = $row.run_id
        }
        $warningRejected.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($warningRejected.Error) | Should Be $false

        $badNamespace = New-FrozenSageTestManifestRow -OutputNamespace 'scenes\F1023_V70_D0117_P2\sage_results\rerun_20261003_frozen_v3\G28'
        $namespaceRejected = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageManifestRow' -Arguments @{
            Row = $badNamespace
            ExpectedRunId = $badNamespace.run_id
        }
        [string]::IsNullOrWhiteSpace($namespaceRejected.Error) | Should Be $false
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

    It 'allocates a distinct active runner lock per manifest run id' {
        $root = Join-Path $TestDrive 'task-locks'
        $first = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageTaskRunnerLockPath' -Arguments @{
            ExecutionLogParent = $root
            RunId = 'run_fixture_scene_G03_ch1'
        }
        $second = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageTaskRunnerLockPath' -Arguments @{
            ExecutionLogParent = $root
            RunId = 'run_fixture_scene_G04_ch2'
        }
        $first.Available | Should Be $true
        $second.Available | Should Be $true
        $first.Error | Should Be $null
        $second.Error | Should Be $null
        $first.Value | Should Not Be $second.Value
        [System.IO.Path]::GetFileName($first.Value) | Should Match '^\.windows_runner_active_[A-Za-z0-9_-]+\.lock$'
    }

    It 'blocks two different run ids from acquiring the shared GPU execution lock' {
        $lockPath = Get-FrozenSageGpuGlobalLockPath -ExecutionLogParent $TestDrive
        [IO.Path]::GetFileName($lockPath) | Should Be '.gpu_stage2_qualified_active.lock'
        $first = Invoke-ProductionFunctionSafely -Name 'New-FrozenSageGpuGlobalLock' -Arguments @{
            ExecutionMode = 'GPU_STAGE2_QUALIFIED'; LockPath = $lockPath
            Payload = [pscustomobject]@{ run_id='run_A'; scene_id='scene_A'; prn=3; tracking_channel=1; execution_mode='GPU_STAGE2_QUALIFIED'; execution_plan_sha256=('a'*64); process_id=$PID; started_utc=[DateTimeOffset]::UtcNow.ToString('o') }
        }
        $first.Available | Should Be $true
        $first.Error | Should Be $null
        $second = Invoke-ProductionFunctionSafely -Name 'New-FrozenSageGpuGlobalLock' -Arguments @{
            ExecutionMode = 'GPU_STAGE2_QUALIFIED'; LockPath = $lockPath
            Payload = [pscustomobject]@{ run_id='run_B'; scene_id='scene_B'; prn=6; tracking_channel=2; execution_mode='GPU_STAGE2_QUALIFIED'; execution_plan_sha256=('b'*64); process_id=$PID; started_utc=[DateTimeOffset]::UtcNow.ToString('o') }
        }
        $second.Error | Should Match 'GPU_GLOBAL_LOCK_PRESENT'
        $first.Value.Stream.Dispose()
    }

    It 'does not acquire or reject a CPU run because a GPU global lock exists' {
        $lockPath = Join-Path $TestDrive '.gpu_stage2_qualified_cpu_policy.lock'
        [IO.File]::WriteAllText($lockPath, '{"execution_mode":"GPU_STAGE2_QUALIFIED"}')
        $cpu = Invoke-ProductionFunctionSafely -Name 'New-FrozenSageGpuGlobalLock' -Arguments @{
            ExecutionMode = 'CPU_FROZEN'; LockPath = $lockPath; Payload = [pscustomobject]@{}
        }
        $cpu.Available | Should Be $true
        $cpu.Error | Should Be $null
        $cpu.Value | Should Be $null
        (Test-Path -LiteralPath $lockPath) | Should Be $true
    }

    It 'moves a successful GPU global lock to an archive without deleting or overwriting' {
        $lockPath = Join-Path $TestDrive '.gpu_stage2_qualified_success.lock'
        $payload = [pscustomobject]@{ run_id='run_success'; scene_id='scene'; prn=3; tracking_channel=1; execution_mode='GPU_STAGE2_QUALIFIED'; execution_plan_sha256=('c'*64); process_id=$PID; started_utc=[DateTimeOffset]::UtcNow.ToString('o') }
        $created = New-FrozenSageGpuGlobalLock -ExecutionMode 'GPU_STAGE2_QUALIFIED' -LockPath $lockPath -Payload $payload
        $created.Stream.Dispose()
        $finalDirectory = Join-Path $TestDrive 'final'
        [void](New-Item -ItemType Directory -Path $finalDirectory -Force)
        $archivePath = Join-Path $finalDirectory 'gpu_stage2_global_lock_receipt.json'
        $moved = Move-FrozenSageGpuGlobalLockToArchive -LockPath $lockPath -DestinationPath $archivePath -ExpectedPayload $payload
        (Test-Path -LiteralPath $lockPath) | Should Be $false
        (Test-Path -LiteralPath $archivePath -PathType Leaf) | Should Be $true
        $moved.Sha256 | Should Be (Get-FileHash -LiteralPath $archivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    }

    It 'writes GPU provenance in the attempt lock before runtime gates' {
        $source = (Get-Command Invoke-FrozenSageRerunSingle).Definition
        $perRunLockPosition = $source.IndexOf('[System.IO.File]::Open($globalLockPath', [StringComparison]::Ordinal)
        $provenancePosition = $source.IndexOf('New-FrozenSageRunnerLockPayload', [StringComparison]::Ordinal)
        $lockPosition = $source.IndexOf('New-FrozenSageGpuGlobalLock', [StringComparison]::Ordinal)
        $identityPosition = $source.IndexOf('Assert-FrozenSageGpuSourceIdentity', [StringComparison]::Ordinal)
        $availabilityPosition = $source.IndexOf('Assert-GpuMatlabAvailabilitySmoke', [StringComparison]::Ordinal)
        $relocationPosition = $source.IndexOf('Move-ValidatedStageOutput', [StringComparison]::Ordinal)
        $archivePosition = $source.IndexOf('Move-FrozenSageGpuGlobalLockToArchive', [StringComparison]::Ordinal)
        $perRunLockPosition | Should BeGreaterThan -1
        $provenancePosition | Should BeGreaterThan $perRunLockPosition
        $lockPosition | Should BeGreaterThan -1
        $lockPosition | Should BeGreaterThan $provenancePosition
        $identityPosition | Should BeGreaterThan $lockPosition
        $availabilityPosition | Should BeGreaterThan $lockPosition
        $availabilityPosition | Should BeGreaterThan $identityPosition
        $archivePosition | Should BeGreaterThan $relocationPosition
    }

    It 'includes the approved plan and source identities in GPU attempt lock provenance' {
        $fixture = [pscustomobject]@{
            RunId = 'run_fixture'; SceneId = 'F1023_V70_D0117_P2'; Prn = 28; TrackingChannel = 1
            MappingWarning = 'NONE'; ExecutionMode = 'GPU_STAGE2_QUALIFIED'
        }
        $plan = [pscustomobject]@{ ExecutionPlanSha256 = 'a' * 64 }
        $result = Invoke-ProductionFunctionSafely -Name 'New-FrozenSageRunnerLockPayload' -Arguments @{
            Preflight = $fixture; ExecutionPlan = $plan
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $payload = $result.Value
        $payload.execution_mode | Should Be 'GPU_STAGE2_QUALIFIED'
        $payload.execution_plan_sha256 | Should Be ('a' * 64)
        $payload.gpu_source_contract_sha256 | Should Be $script:ApprovedGpuSourceContractSha256
        $payload.production_gpu_entry_sha256 | Should Be $script:ApprovedGpuProductionEntrySha256
        $payload.frozen_authority_sha256 | Should Be 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
        $payload.qualified_candidate_sha256 | Should Be '5ea69f6b0ebc5e5be13cb109e4ec3eec30f377b52a5f22beed224164a035be3b'
        $payload.qualified_selector_sha256 | Should Be 'a40c6459e66a384e85053589b270c5d2e112363872153fbf46da5c56fd4bb1f5'
    }

    It 'archives the GPU global lock with the controlled failure receipt and provenance' {
        $receiptRoot = Join-Path $TestDrive 'gpu-failure-receipts'
        [void](New-Item -ItemType Directory -Path $receiptRoot)
        $runnerLockPath = Join-Path $TestDrive '.windows_runner_active_gpu_failure.lock'
        $gpuLockPath = Join-Path $TestDrive '.gpu_stage2_failure_active.lock'
        $started = [DateTimeOffset]::UtcNow.ToString('o')
        $gpuPayload = [pscustomobject]@{
            run_id='gpu_failure'; scene_id='F1023_V70_D0117_P2'; prn=28; tracking_channel=1
            execution_mode='GPU_STAGE2_QUALIFIED'; execution_plan_sha256=('d'*64)
            gpu_source_contract_sha256=$script:ApprovedGpuSourceContractSha256
            production_gpu_entry_sha256=$script:ApprovedGpuProductionEntrySha256
            frozen_authority_sha256='bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
            qualified_candidate_sha256='5ea69f6b0ebc5e5be13cb109e4ec3eec30f377b52a5f22beed224164a035be3b'
            qualified_selector_sha256='a40c6459e66a384e85053589b270c5d2e112363872153fbf46da5c56fd4bb1f5'
            process_id=$PID; started_utc=$started
        }
        $created = New-FrozenSageGpuGlobalLock -ExecutionMode 'GPU_STAGE2_QUALIFIED' -LockPath $gpuLockPath -Payload $gpuPayload
        $created.Stream.Dispose()
        $runnerPayload = [pscustomobject]@{
            run_id='gpu_failure'; scene_id='F1023_V70_D0117_P2'; prn=28; tracking_channel=1
            mapping_warning='NONE'; process_id=$PID; started_utc=$started
            execution_mode='GPU_STAGE2_QUALIFIED'; execution_plan_sha256=('d'*64)
            gpu_source_contract_sha256=$gpuPayload.gpu_source_contract_sha256
            production_gpu_entry_sha256=$gpuPayload.production_gpu_entry_sha256
            frozen_authority_sha256=$gpuPayload.frozen_authority_sha256
            qualified_candidate_sha256=$gpuPayload.qualified_candidate_sha256
            qualified_selector_sha256=$gpuPayload.qualified_selector_sha256
        }
        [IO.File]::WriteAllText($runnerLockPath, ($runnerPayload | ConvertTo-Json -Depth 4))
        $result = Invoke-ProductionFunctionSafely -Name 'Move-FrozenRunnerLockToFailureReceipt' -Arguments @{
            GlobalLockPath=$runnerLockPath; ReceiptRoot=$receiptRoot; LockPayload=$runnerPayload
            FailureReason='GPU_NOT_AVAILABLE'; ErrorMessage='GPU_NOT_AVAILABLE'
            GpuGlobalLockPath=$gpuLockPath; GpuGlobalLockPayload=$gpuPayload
        }
        $result.Error | Should Be $null
        (Test-Path -LiteralPath $gpuLockPath) | Should Be $false
        (Test-Path -LiteralPath $result.Value.GpuGlobalLockReceiptPath -PathType Leaf) | Should Be $true
        $receipt = Get-Content -Raw -LiteralPath $result.Value.ReceiptPath | ConvertFrom-Json
        $receipt.failure_reason | Should Be 'GPU_NOT_AVAILABLE'
        $receipt.execution_mode | Should Be 'GPU_STAGE2_QUALIFIED'
        $receipt.gpu_source_contract_sha256 | Should Be $gpuPayload.gpu_source_contract_sha256
        $receipt.production_gpu_entry_sha256 | Should Be $gpuPayload.production_gpu_entry_sha256
        $receipt.qualified_selector_sha256 | Should Be $gpuPayload.qualified_selector_sha256
        $receipt.gpu_global_lock_receipt_sha256 | Should Be (Get-FileHash -LiteralPath $result.Value.GpuGlobalLockReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
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

    It 'builds the selected scene, PRN, and channel invocation with Resume=false' {
        $result = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageMatlabExpression' -Arguments @{
            SceneId = 'F1023_V120_D0121_P2'
            Prn = 6
            TrackingChannel = 6
            ProjectRoot = 'E:\GNSS_Multipath_Project'
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value | Should Be "run_nav_sage_pipeline('F1023_V120_D0121_P2',6,'TrackingChannel',6,'ProjectRoot','E:/GNSS_Multipath_Project','Resume',false)"
    }

    It 'passes -batch and the single-quoted MATLAB expression as separate native arguments' {
        $expression = "a='F1023_V70_D0117_P2';b='TrackingChannel';c='E:/GNSS_Multipath_Project';assert(strcmp(a,'F1023_V70_D0117_P2'));assert(strcmp(b,'TrackingChannel'));assert(strcmp(c,'E:/GNSS_Multipath_Project'));disp('MATLAB_ARGUMENT_TRANSPORT_OK')"
        $result = Invoke-ProductionFunctionSafely -Name 'New-FrozenMatlabProcessStartInfo' -Arguments @{
            MatlabPath = 'C:\MATLAB\bin\matlab.exe'
            Expression = $expression
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value.ArgumentList.Count | Should Be 2
        $result.Value.ArgumentList[0] | Should Be '-batch'
        $result.Value.ArgumentList[1] | Should Be $expression
        $result.Value.UseShellExecute | Should Be $false
        $result.Value.RedirectStandardOutput | Should Be $true
        $result.Value.RedirectStandardError | Should Be $true
        $result.Value.CreateNoWindow | Should Be $true
    }

    It 'checks raw IQ size against the audit without computing a raw SHA-256' {
        $rawFixture = Join-Path $TestDrive 'raw-size-fixture.bin'
        $stream = [System.IO.File]::Open($rawFixture, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
        $stream.WriteByte(1)
        $stream.Flush()
        try {
            $result = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageRawIqMetadata' -Arguments @{
                Path = $rawFixture
                ExpectedSizeBytes = 1
            }
            $result.Available | Should Be $true
            $result.Error | Should Be $null
            $result.Value.RawIqSizeBytes | Should Be 1
            $result.Value.RawIqSha256 | Should Be ''
            $result.Value.RawIqSha256Status | Should Be 'NOT_RECOMPUTED'
        } finally {
            $stream.Dispose()
        }
    }

    It 'moves a controlled failure lock and records the failure reason' {
        $receiptRoot = Join-Path $TestDrive 'runner-receipts'
        [void](New-Item -ItemType Directory -Path $receiptRoot)
        $lockPath = Join-Path $TestDrive '.windows_runner_active.lock'
        $lockText = '{"run_id":"run_fixture","scene_id":"F1023_V70_D0117_P2","prn":28,"tracking_channel":1,"process_id":999999,"started_utc":"2026-10-04T00:00:00Z"}'
        [System.IO.File]::WriteAllText($lockPath, $lockText)
        $lockPayload = $lockText | ConvertFrom-Json

        $result = Invoke-ProductionFunctionSafely -Name 'Move-FrozenRunnerLockToFailureReceipt' -Arguments @{
            GlobalLockPath = $lockPath
            ReceiptRoot = $receiptRoot
            LockPayload = $lockPayload
            FailureReason = 'MATLAB_ARGUMENT_TRANSPORT_FAILURE'
            ErrorMessage = 'MATLAB_ARGUMENT_TRANSPORT_FAILED'
        }

        $result.Available | Should Be $true
        $result.Error | Should Be $null
        (Test-Path -LiteralPath $lockPath) | Should Be $false
        (Test-Path -LiteralPath $result.Value.LockPath -PathType Leaf) | Should Be $true
        (Get-Content -LiteralPath $result.Value.LockPath -Raw) | Should Be $lockText
        $receiptText = Get-Content -LiteralPath $result.Value.ReceiptPath -Raw
        $receipt = $receiptText | ConvertFrom-Json
        $receipt.failure_reason | Should Be 'MATLAB_ARGUMENT_TRANSPORT_FAILURE'
        $receipt.run_id | Should Be 'run_fixture'
        $receipt.scene_id | Should Be 'F1023_V70_D0117_P2'
        $receipt.prn | Should Be 28
        $receipt.tracking_channel | Should Be 1
        $receipt.old_pid | Should Be 999999
        $receiptDocument = [System.Text.Json.JsonDocument]::Parse($receiptText)
        try {
            $receiptDocument.RootElement.GetProperty('lock_started_utc').GetString() | Should Be '2026-10-04T00:00:00Z'
        } finally {
            $receiptDocument.Dispose()
        }
    }

    It 'records the SAGE MATLAB process identity and confirmed end state in failure receipts' {
        $receiptRoot = Join-Path $TestDrive 'runner-process-receipts'
        [void](New-Item -ItemType Directory -Path $receiptRoot)
        $lockPath = Join-Path $TestDrive '.windows_runner_process_active.lock'
        $lockText = '{"run_id":"run_fixture","scene_id":"F1023_V120_D0121_P2","prn":6,"tracking_channel":6,"mapping_warning":"NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING","process_id":4321,"started_utc":"2026-10-04T00:00:00Z"}'
        [System.IO.File]::WriteAllText($lockPath, $lockText)

        $result = Invoke-ProductionFunctionSafely -Name 'Move-FrozenRunnerLockToFailureReceipt' -Arguments @{
            GlobalLockPath = $lockPath
            ReceiptRoot = $receiptRoot
            LockPayload = ($lockText | ConvertFrom-Json)
            FailureReason = 'STAGE0_NO_VALID_NAV_SYMBOLS'
            ErrorMessage = 'Stage0 produced no valid NAV symbols.'
            MatlabProcessState = [pscustomobject]@{
                Started = $true
                ProcessId = 8765
                ExitCode = 1
                ProcessEnded = $true
                StartedUtc = '2026-10-04T00:01:00Z'
                EndedUtc = '2026-10-04T00:02:00Z'
            }
        }

        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $receiptText = Get-Content -Raw -LiteralPath $result.Value.ReceiptPath
        $receipt = $receiptText | ConvertFrom-Json
        $receipt.failure_reason | Should Be 'STAGE0_NO_VALID_NAV_SYMBOLS'
        $receipt.run_id | Should Be 'run_fixture'
        $receipt.mapping_warning | Should Be 'NAV_MAPPING_VALID_TRACKING_START_LOG_MISSING'
        $receipt.matlab_started | Should Be $true
        $receipt.matlab_process_id | Should Be 8765
        $receipt.matlab_exit_code | Should Be 1
        $receipt.matlab_process_ended | Should Be $true
        $receiptDocument = [System.Text.Json.JsonDocument]::Parse($receiptText)
        try {
            $receiptDocument.RootElement.GetProperty('matlab_start_utc').GetString() | Should Be '2026-10-04T00:01:00Z'
            $receiptDocument.RootElement.GetProperty('matlab_end_utc').GetString() | Should Be '2026-10-04T00:02:00Z'
        } finally {
            $receiptDocument.Dispose()
        }
    }

    It 'classifies only explicit zero-row Stage0 catalogs as task-specific failures' {
        $output = Join-Path $TestDrive 'stage0-failure'
        [void](New-Item -ItemType Directory -Path $output)
        [System.IO.File]::WriteAllText((Join-Path $output 'stage0_valid_symbols.csv'), "symbol_id`n")
        [System.IO.File]::WriteAllText((Join-Path $output 'stage0_valid_40ms_windows.csv'), "window_id`n")
        $noSymbols = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageStage0FailureReason' -Arguments @{
            StagingPath = $output
        }
        $noSymbols.Available | Should Be $true
        $noSymbols.Error | Should Be $null
        $noSymbols.Value | Should Be 'STAGE0_NO_VALID_NAV_SYMBOLS'

        [System.IO.File]::WriteAllText((Join-Path $output 'stage0_valid_symbols.csv'), "symbol_id`n1`n")
        $noWindows = Invoke-ProductionFunctionSafely -Name 'Get-FrozenSageStage0FailureReason' -Arguments @{
            StagingPath = $output
        }
        $noWindows.Available | Should Be $true
        $noWindows.Error | Should Be $null
        $noWindows.Value | Should Be 'STAGE0_NO_VALID_40MS_WINDOWS'
    }

    It 'rejects empty Stage0 catalogs before any staging relocation' {
        $output = Join-Path $TestDrive 'stage0-empty-gate'
        [void](New-Item -ItemType Directory -Path $output)
        [System.IO.File]::WriteAllText((Join-Path $output 'stage0_valid_symbols.csv'), "symbol_id`n")
        [System.IO.File]::WriteAllText((Join-Path $output 'stage0_valid_40ms_windows.csv'), "window_id`n1`n")
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-FrozenSageStage0Ready' -Arguments @{ StagingPath = $output }
        $result.Available | Should Be $true
        [string]::IsNullOrWhiteSpace($result.Error) | Should Be $false
        $result.Error | Should Match 'STAGE0_NO_VALID_NAV_SYMBOLS'
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

    It 'requires zero exit code and the MATLAB argument marker in stdout' {
        $result = Invoke-ProductionFunctionSafely -Name 'Assert-MatlabArgumentTransportSmoke' -Arguments @{
            ExitCode = 0
            Stdout = 'MATLAB_ARGUMENT_TRANSPORT_OK'
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Value | Should Be $true

        $rejected = Invoke-ProductionFunctionSafely -Name 'Assert-MatlabArgumentTransportSmoke' -Arguments @{
            ExitCode = 1
            Stdout = 'MATLAB_ARGUMENT_TRANSPORT_OK'
        }
        [string]::IsNullOrWhiteSpace($rejected.Error) | Should Be $false

        $missingMarker = Invoke-ProductionFunctionSafely -Name 'Assert-MatlabArgumentTransportSmoke' -Arguments @{
            ExitCode = 0
            Stdout = 'MATLAB_ARGUMENT_TRANSPORT_DIAGNOSTIC_ONLY'
        }
        [string]::IsNullOrWhiteSpace($missingMarker.Error) | Should Be $false
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
            RawIqSha256 = ''
            RawIqSha256Status = 'NOT_RECOMPUTED'
            Resume = $false
            MatlabStartUtc = '2026-10-04T00:00:00Z'
            MatlabEndUtc = '2026-10-04T00:01:00Z'
            MatlabProcessId = 31415
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
        $receipt.raw_iq_sha256 | Should Be ''
        $receipt.raw_iq_sha256_status | Should Be 'NOT_RECOMPUTED'
        $receipt.matlab_process_id | Should Be 31415
        ($receipt.PSObject.Properties.Name -contains 'execution_mode') | Should Be $false
        ([datetime]$receipt.matlab_start_utc).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') | Should Be '2026-10-04T00:00:00Z'
        ([datetime]$receipt.matlab_end_utc).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ') | Should Be '2026-10-04T00:01:00Z'
    }

    It 'adds only the GPU provenance reference fields to a GPU relocation receipt' {
        $stage = Join-Path $TestDrive 'gpu-sage-results\nav_sage_v2\G28'
        $final = Join-Path $TestDrive 'gpu-sage-results\rerun_20261003_frozen_v3\G28_ch1'
        [void](New-Item -ItemType Directory -Path $stage -Force)
        $context = [pscustomobject]@{
            SceneId = 'F1023_V70_D0117_P2'; Prn = 28; TrackingChannel = 1
            RunId = 'fixture_run_id'; ExecutionPlanSha256 = 'a' * 64
            FrozenSageSha256 = 'bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
            RawIqSizeBytes = 1234; RawIqSha256 = ''; RawIqSha256Status = 'NOT_RECOMPUTED'
            MatlabStartUtc = '2026-10-04T00:00:00Z'; MatlabEndUtc = '2026-10-04T00:01:00Z'
            MatlabProcessId = 31415; MatlabExitCode = 0
        }
        New-GpuExecutionProvenanceTestFiles -Directory $stage -Context $context
        [IO.File]::WriteAllText((Join-Path $stage 'gpu_stage2_global_lock_receipt.json'), '{"run_id":"fixture_run_id","execution_mode":"GPU_STAGE2_QUALIFIED"}')
        $result = Invoke-ProductionFunctionSafely -Name 'Move-ValidatedStageOutput' -Arguments @{
            StagingPath = $stage; FinalPath = $final; Context = $context
            ExecutionMode = 'GPU_STAGE2_QUALIFIED'
        }
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $receipt = Get-Content -Raw -LiteralPath (Join-Path $final 'relocation_receipt.json') | ConvertFrom-Json
        $receipt.execution_mode | Should Be 'GPU_STAGE2_QUALIFIED'
        $receipt.gpu_execution_attempt_path | Should Be (Join-Path $final 'gpu_execution_attempt.json')
        $receipt.gpu_execution_attempt_sha256 | Should Be (Get-FileHash (Join-Path $final 'gpu_execution_attempt.json') -Algorithm SHA256).Hash.ToLowerInvariant()
        $receipt.gpu_execution_provenance_path | Should Be (Join-Path $final 'gpu_execution_provenance.json')
        $receipt.gpu_execution_provenance_sha256 | Should Be (Get-FileHash (Join-Path $final 'gpu_execution_provenance.json') -Algorithm SHA256).Hash.ToLowerInvariant()
        $receipt.gpu_global_lock_receipt_path | Should Be (Join-Path $final 'gpu_stage2_global_lock_receipt.json')
        $receipt.gpu_global_lock_receipt_sha256 | Should Be (Get-FileHash (Join-Path $final 'gpu_stage2_global_lock_receipt.json') -Algorithm SHA256).Hash.ToLowerInvariant()
        ($receipt.PSObject.Properties.Name -contains 'frozen_authority_sha256') | Should Be $false
    }

    It 'fails closed before relocation when GPU attempt provenance is missing' {
        $stage = Join-Path $TestDrive 'gpu-missing-attempt-stage'
        $final = Join-Path $TestDrive 'gpu-missing-attempt-final'
        [void](New-Item -ItemType Directory -Path $stage -Force)
        $context = [pscustomobject]@{
            SceneId='F1023_V70_D0117_P2'; Prn=28; TrackingChannel=1
            RunId='fixture_run_id'; ExecutionPlanSha256=('e'*64)
            FrozenSageSha256='bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
            RawIqSizeBytes=1; RawIqSha256=''; RawIqSha256Status='NOT_RECOMPUTED'
            MatlabStartUtc='2026-10-04T00:00:00Z'; MatlabEndUtc='2026-10-04T00:01:00Z'
            MatlabProcessId=31415; MatlabExitCode=0
        }
        $result = Invoke-ProductionFunctionSafely -Name 'Move-ValidatedStageOutput' -Arguments @{
            StagingPath=$stage; FinalPath=$final; Context=$context
            ExecutionMode='GPU_STAGE2_QUALIFIED'
        }
        $result.Available | Should Be $true
        $result.Error | Should Match 'GPU_EXECUTION_PROVENANCE_MISSING.*gpu_execution_attempt.json'
        (Test-Path -LiteralPath $stage -PathType Container) | Should Be $true
        (Test-Path -LiteralPath $final) | Should Be $false
    }

    It 'adds a hash-verified global GPU lock reference after relocation' {
        $stage = Join-Path $TestDrive 'gpu-late-lock-stage'
        $final = Join-Path $TestDrive 'gpu-late-lock-final'
        [void](New-Item -ItemType Directory -Path $stage -Force)
        $context = [pscustomobject]@{
            SceneId='F1023_V70_D0117_P2'; Prn=28; TrackingChannel=1
            RunId='fixture_run_id'; ExecutionPlanSha256=('d'*64)
            FrozenSageSha256='bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c'
            RawIqSizeBytes=1; RawIqSha256=''; RawIqSha256Status='NOT_RECOMPUTED'
            MatlabStartUtc='2026-10-04T00:00:00Z'; MatlabEndUtc='2026-10-04T00:01:00Z'
            MatlabProcessId=31415; MatlabExitCode=0
        }
        New-GpuExecutionProvenanceTestFiles -Directory $stage -Context $context
        $moved = Move-ValidatedStageOutput -StagingPath $stage -FinalPath $final -Context $context -ExecutionMode 'GPU_STAGE2_QUALIFIED'
        ($moved.PSObject.Properties.Name -contains 'gpu_global_lock_receipt_path') | Should Be $false
        $gpuReceiptPath = Join-Path $final 'gpu_stage2_global_lock_receipt.json'
        [IO.File]::WriteAllText($gpuReceiptPath, '{"run_id":"fixture_run_id"}')
        $updated = Add-FrozenSageGpuLockReferenceToRelocationReceipt -FinalPath $final -GpuGlobalLockReceiptPath $gpuReceiptPath
        $updated.gpu_global_lock_receipt_path | Should Be $gpuReceiptPath
        $updated.gpu_global_lock_receipt_sha256 | Should Be (Get-FileHash -LiteralPath $gpuReceiptPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $diskReceipt = Get-Content -Raw -LiteralPath (Join-Path $final 'relocation_receipt.json') | ConvertFrom-Json
        $diskReceipt.gpu_global_lock_receipt_sha256 | Should Be $updated.gpu_global_lock_receipt_sha256
    }
}
