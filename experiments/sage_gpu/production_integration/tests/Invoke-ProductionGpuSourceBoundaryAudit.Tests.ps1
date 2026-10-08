$auditScript = Join-Path $PSScriptRoot '..\Invoke-ProductionGpuSourceBoundaryAudit.ps1'
if (Test-Path -LiteralPath $auditScript -PathType Leaf) { . $auditScript }

function Get-TestMatlabFunctionBlock {
    param([string]$Path, [string]$Name)
    $text = [IO.File]::ReadAllText($Path)
    $matches = [regex]::Matches($text, '(?m)^[\t ]*function\b')
    for ($index = 0; $index -lt $matches.Count; $index++) {
        $start = $matches[$index].Index
        $end = if ($index + 1 -lt $matches.Count) { $matches[$index + 1].Index } else { $text.Length }
        $block = $text.Substring($start, $end - $start).TrimEnd([char[]]@("`r", "`n"))
        $prefix = $block.Substring(0, $block.IndexOf('('))
        $nameMatch = [regex]::Match($prefix, '(?<name>[A-Za-z][A-Za-z0-9_]*)[\t ]*$')
        if ($nameMatch.Success -and $nameMatch.Groups['name'].Value -ceq $Name) { return $block }
    }
    throw "TEST_FIXTURE_FUNCTION_MISSING name=$Name path=$Path"
}

function Get-TestRawFunctionSha256 {
    param([string]$Path, [string]$Name)
    $block = Get-TestMatlabFunctionBlock -Path $Path -Name $Name
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes($block)
    return [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($bytes)).ToLowerInvariant()
}

function New-ProductionGpuAuditFixture {
    param([string]$Root = $TestDrive)
    $rootPath = Join-Path $Root ([guid]::NewGuid().ToString('N'))
    [void](New-Item -ItemType Directory -Path $rootPath -Force)
    $frozen = Join-Path $rootPath 'frozen.m'
    $candidate = Join-Path $rootPath 'candidate.m'
    $entry = Join-Path $rootPath 'production.m'
    $contract = Join-Path $rootPath 'contract.json'
    $repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..'))
    $authorityFrozen = 'E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_nav_sage_pipeline.m'
    $authorityCandidate = Join-Path $repoRoot 'experiments\sage_gpu\full_task_candidate\run_nav_sage_pipeline_gpu_candidate.m'
    $selector = Join-Path $repoRoot 'experiments\sage_gpu\selectSeparatedResidualCandidate.m'
    $probe = Join-Path $repoRoot 'experiments\sage_gpu\stage2_window_173_gpu_probe.m'
    $authorityEntry = Join-Path $repoRoot 'scripts\sage_pipeline\run_nav_sage_pipeline_gpu_production.m'
    $authorityContract = Join-Path $repoRoot 'experiments\sage_gpu\production_integration\PRODUCTION_GPU_SOURCE_CONTRACT.json'
    Copy-Item -LiteralPath $authorityFrozen -Destination $frozen
    Copy-Item -LiteralPath $authorityCandidate -Destination $candidate
    Copy-Item -LiteralPath $authorityEntry -Destination $entry
    Copy-Item -LiteralPath $authorityContract -Destination $contract
    return [pscustomobject]@{
        Root = $rootPath; Frozen = $frozen; Candidate = $candidate; Entry = $entry
        Selector = $selector; Probe = $probe; Contract = $contract
    }
}

function Invoke-ProductionAuditFixture {
    param([pscustomobject]$Fixture)
    $command = Get-Command -Name 'Invoke-ProductionGpuSourceBoundaryAudit' -ErrorAction SilentlyContinue
    if ($null -eq $command) { return [pscustomobject]@{ Available = $false; Result = $null; Error = 'PRODUCTION_FUNCTION_MISSING' } }
    try {
        $result = Invoke-ProductionGpuSourceBoundaryAudit `
            -FrozenAuthorityPath $Fixture.Frozen `
            -QualifiedCandidatePath $Fixture.Candidate `
            -QualifiedProbePath $Fixture.Probe `
            -QualifiedSelectorPath $Fixture.Selector `
            -ProductionEntryPath $Fixture.Entry `
            -SourceContractPath $Fixture.Contract
        return [pscustomobject]@{ Available = $true; Result = $result; Error = $null }
    } catch {
        return [pscustomobject]@{ Available = $true; Result = $null; Error = $_.Exception.Message }
    }
}

Describe 'Production GPU source boundary audit' {
    It 'passes a source set whose raw function blocks and file identities match the contract' {
        $fixture = New-ProductionGpuAuditFixture
        $result = Invoke-ProductionAuditFixture $fixture
        $result.Available | Should Be $true
        $result.Error | Should Be $null
        $result.Result.Status | Should Be 'PASS'
        $result.Result.UnexpectedDiffCount | Should Be 0
    }

    It 'blocks a mutation to a Frozen function block' {
        $fixture = New-ProductionGpuAuditFixture
        $text = [IO.File]::ReadAllText($fixture.Frozen).Replace('completed(position) = true;', 'completed(position) = false;')
        ($text -cne [IO.File]::ReadAllText($fixture.Frozen)) | Should Be $true
        [IO.File]::WriteAllText($fixture.Frozen, $text, [Text.UTF8Encoding]::new($false))
        $result = Invoke-ProductionAuditFixture $fixture
        $result.Result.Status | Should Be 'BLOCKED'
        $result.Result.UnexpectedDiffCount | Should BeGreaterThan 0
    }

    It 'blocks a mutation to a qualified GPU function block' {
        $fixture = New-ProductionGpuAuditFixture
        $text = [IO.File]::ReadAllText($fixture.Candidate).Replace('seed = makePath(scanRow.main_delay_samples, scanRow.main_doppler_hz);', 'seed = makePath(scanRow.main_delay_samples + 1, scanRow.main_doppler_hz);')
        ($text -cne [IO.File]::ReadAllText($fixture.Candidate)) | Should Be $true
        [IO.File]::WriteAllText($fixture.Candidate, $text, [Text.UTF8Encoding]::new($false))
        $result = Invoke-ProductionAuditFixture $fixture
        $result.Result.Status | Should Be 'BLOCKED'
        $result.Result.UnexpectedDiffCount | Should BeGreaterThan 0
    }

    It 'blocks a mutation to the exact-pinned gatherGpuFit function' {
        $fixture = New-ProductionGpuAuditFixture
        $text = [IO.File]::ReadAllText($fixture.Entry).Replace('model.relativePowerDb = reshape(', 'model.relativePowerDb = (')
        [IO.File]::WriteAllText($fixture.Entry, $text, [Text.UTF8Encoding]::new($false))
        $result = Invoke-ProductionAuditFixture $fixture
        $result.Result.Status | Should Be 'BLOCKED'
        $result.Result.UnexpectedDiffCount | Should BeGreaterThan 0
    }

    It 'blocks an unexpected production function even when the original functions remain' {
        $fixture = New-ProductionGpuAuditFixture
        [IO.File]::AppendAllText($fixture.Entry, "`nfunction extraProductionHook()`nend`n", [Text.UTF8Encoding]::new($false))
        $result = Invoke-ProductionAuditFixture $fixture
        $result.Result.Status | Should Be 'BLOCKED'
        $result.Result.UnexpectedDiffCount | Should BeGreaterThan 0
    }

    It 'rejects a contract that tries to authorize a new production function' {
        $fixture = New-ProductionGpuAuditFixture
        [IO.File]::AppendAllText($fixture.Entry, "`nfunction extraProductionHook()`nend`n", [Text.UTF8Encoding]::new($false))
        $contract = Get-Content -Raw -LiteralPath $fixture.Contract | ConvertFrom-Json
        $contract.production_entry_sha256 = (Get-FileHash -LiteralPath $fixture.Entry -Algorithm SHA256).Hash.ToLowerInvariant()
        $contract.expected_production_function_order = @($contract.expected_production_function_order) + 'extraProductionHook'
        $contract.function_contracts = @($contract.function_contracts) + @([pscustomobject]@{
            name = 'extraProductionHook'; classification = 'ALLOWED_PRODUCTION_PLUMBING'
            source = 'production'; sha256 = '0' * 64
        })
        [IO.File]::WriteAllText($fixture.Contract, ($contract | ConvertTo-Json -Depth 12), [Text.UTF8Encoding]::new($false))
        $result = Invoke-ProductionAuditFixture $fixture
        $result.Result.Status | Should Be 'BLOCKED'
        $codes = @($result.Result.Rows | ForEach-Object { [string]$_.Code })
        ($codes -contains 'PRODUCTION_FUNCTION_POLICY_ORDER_MISMATCH') | Should Be $true
        ($codes -contains 'SOURCE_CONTRACT_FUNCTION_POLICY_MISMATCH') | Should Be $true
    }
}
