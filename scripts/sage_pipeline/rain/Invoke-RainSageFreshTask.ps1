[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$RequestManifest,
    [Parameter(Mandatory = $true)][string]$ExpectedRequestSha256,
    [switch]$Execute,
    [switch]$ConfirmRainSageRerun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ProjectRoot = "E:\GNSS_Multipath_Project"
$MatlabExecutable = "D:\Program Files\Matlab\bin\matlab.exe"
$ExpectedProtectedProductionSha256 = "bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c"
$ExpectedOutputNamespaceName = "rain_sage_rerun_v1_20260827_r4"
$REQUIRED_OUTPUT_FILES = @(
    "stage0_valid_symbols.csv",
    "stage0_valid_40ms_windows.csv",
    "stage1_nav_fast_scan.csv",
    "stage2_model_orders.csv",
    "stage2_selected_windows.csv",
    "stage2_selected_paths.csv",
    "stage3_persistence.csv",
    "stage3_reliable_centers.csv",
    "stage4_joint_summary.csv",
    "stage4_joint_paths.csv",
    "doppler_sign.mat",
    "stage0_nav_catalog.mat",
    "stage1_nav_fast_scan.mat",
    "stage1_nav_progress.mat",
    "stage2_nav_progress.mat",
    "stage2_nav_sage_L1_L4.mat",
    "stage3_nav_persistence.mat",
    "stage4_nav_joint_100ms.mat",
    "rain_stage0_provenance.json"
)
$MutexName = "Local\GNSS_SAGE_RAIN_FRESH_TASK"
$ManifestPath = [System.IO.Path]::GetFullPath($RequestManifest)
$Manifest = $null
$Mutex = $null
$MutexAcquired = $false

function Get-FileSha256 {
    param([Parameter(Mandatory = $true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Assert-EqualText {
    param(
        [Parameter(Mandatory = $true)][string]$Actual,
        [Parameter(Mandatory = $true)][string]$Expected,
        [Parameter(Mandatory = $true)][string]$Message
    )
    if (-not $Actual.Equals($Expected, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Message expected=$Expected actual=$Actual"
    }
}

function Get-CanonicalPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    return [System.IO.Path]::GetFullPath($Path).TrimEnd([char[]]@('\', '/'))
}

function Test-PathWithin {
    param(
        [Parameter(Mandatory = $true)][string]$Candidate,
        [Parameter(Mandatory = $true)][string]$Root
    )
    $candidateFull = Get-CanonicalPath $Candidate
    $rootFull = Get-CanonicalPath $Root
    if ($candidateFull.Equals($rootFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    return $candidateFull.StartsWith(
        $rootFull + [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-InputRecord {
    param([Parameter(Mandatory = $true)][object]$Value)
    if ($null -eq $Value) { throw "input record is null" }
    return $Value
}

function Assert-InputFile {
    param(
        [Parameter(Mandatory = $true)][object]$Record,
        [Parameter(Mandatory = $true)][string]$Name,
        [switch]$VerifyHash
    )
    $path = [string]$Record.path
    if ([string]::IsNullOrWhiteSpace($path) -or -not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "input file missing: $Name $path"
    }
    $item = Get-Item -LiteralPath $path
    if ([int64]$item.Length -ne [int64]$Record.size_bytes) {
        throw "input size changed: $Name expected=$($Record.size_bytes) actual=$($item.Length)"
    }
    if ($VerifyHash -and $Record.PSObject.Properties.Name -contains "sha256") {
        Assert-EqualText (Get-FileSha256 $path) ([string]$Record.sha256) "input hash changed: $Name"
    }
}

function Assert-SourceFiles {
    param([Parameter(Mandatory = $true)][object]$SourceRecords)
    foreach ($property in $SourceRecords.PSObject.Properties) {
        $record = Get-InputRecord $property.Value
        Assert-InputFile -Record $record -Name $property.Name -VerifyHash
    }
}

function New-MatlabPath {
    param([Parameter(Mandatory = $true)][string]$Path)
    # Keep the native Windows separator.  The fresh MATLAB entry compares
    # outputDir with fullfile(...); converting only the caller's path to '/'
    # makes an otherwise identical path fail that strict contract.
    return (Get-CanonicalPath $Path)
}

function New-MatlabExpression {
    param([Parameter(Mandatory = $true)][object]$Task)
    $rainDir = New-MatlabPath (Join-Path $ProjectRoot "scripts\sage_pipeline\rain")
    $root = New-MatlabPath $ProjectRoot
    $output = New-MatlabPath ([string]$Manifest.output.namespace)
    $expression = "addpath('$rainDir'); result=run_rain_sage_fresh_task('$($Task.scene_id)','$($Task.prn)','$output','TrackingChannel',$($Task.tracking_channel),'ProjectRoot','$root','Resume',false); disp(result);"
    if ($expression -match "(?i)'Resume'\s*,\s*true") {
        throw "generated MATLAB expression contains Resume=true"
    }
    if ($expression -notmatch "(?i)'Resume'\s*,\s*false") {
        throw "generated MATLAB expression does not contain Resume=false"
    }
    return $expression
}

function Assert-GlobalMutexAvailable {
    $probe = [System.Threading.Mutex]::new($false, $MutexName)
    $acquired = $false
    try {
        $acquired = $probe.WaitOne(0)
        if (-not $acquired) {
            throw "another Rain fresh task currently owns the global lock"
        }
        Write-Output "GLOBAL_LOCK=AVAILABLE"
    }
    finally {
        if ($acquired) { $probe.ReleaseMutex() | Out-Null }
        $probe.Dispose()
    }
}

function Write-NewJson {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][object]$Value
    )
    $parent = Split-Path -Parent $Path
    if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
        New-Item -ItemType Directory -Path $parent | Out-Null
    }
    $payload = (($Value | ConvertTo-Json -Depth 30) + [Environment]::NewLine)
    $stream = [System.IO.File]::Open(
        $Path,
        [System.IO.FileMode]::CreateNew,
        [System.IO.FileAccess]::Write,
        [System.IO.FileShare]::None)
    try {
        $writer = [System.IO.StreamWriter]::new(
            $stream,
            [System.Text.UTF8Encoding]::new($false))
        try { $writer.Write($payload); $writer.Flush() }
        finally { $writer.Dispose() }
    }
    finally {
        if ($stream) { $stream.Dispose() }
    }
}

function Assert-Manifest {
    if (-not (Test-Path -LiteralPath $ManifestPath -PathType Leaf)) {
        throw "manifest does not exist: $ManifestPath"
    }
    Assert-EqualText (Get-FileSha256 $ManifestPath) $ExpectedRequestSha256 "request manifest SHA-256 mismatch"
    $script:Manifest = Get-Content -LiteralPath $ManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    if ([string]$Manifest.schema_version -ne "rain-sage-fresh-rerun-request-v1") { throw "unsupported request schema" }
    if ([string]$Manifest.project_root -ne $ProjectRoot) { throw "project root mismatch" }
    if ([int]$Manifest.task.sample_rate_hz -ne 10230000) { throw "Rain rerun supports only 10.23 MHz" }
    if ([string]$Manifest.execution.execution_mode -ne "new_only") { throw "execution mode is not new_only" }
    if (-not [bool]$Manifest.execution.new_only) { throw "new_only must be true" }
    if ([bool]$Manifest.execution.resume_allowed) { throw "resume_allowed must be false" }
    if ([int]$Manifest.execution.max_parallel_matlab -ne 1) { throw "max_parallel_matlab must be one" }
    if ([bool]$Manifest.provenance.gold_labels_used_for_selection) { throw "gold labels cannot be used for selection" }
    $scene = [string]$Manifest.task.scene_id
    $prn = [string]$Manifest.task.prn
    $expected = Join-Path $ProjectRoot ("scenes\{0}\sage_results\{1}\{2}" -f $scene, $ExpectedOutputNamespaceName, $prn)
    Assert-EqualText ([string]$Manifest.output.namespace) $expected "output namespace mismatch"
    if ([string]$Manifest.output.output_namespace_name -ne $ExpectedOutputNamespaceName) { throw "output namespace version mismatch" }
    if ([string]$Manifest.task.previous_output_namespace -match "rain_sage_rerun") { throw "previous namespace cannot be a rerun namespace" }
    if (Test-Path -LiteralPath ([string]$Manifest.output.namespace)) { throw "fresh output namespace already exists; no reuse/resume is allowed" }
    $outputRoot = Join-Path $ProjectRoot ("scenes\{0}\sage_results\{1}" -f $scene, $ExpectedOutputNamespaceName)
    if (-not (Test-PathWithin -Candidate ([string]$Manifest.output.namespace) -Root $outputRoot)) { throw "output namespace escapes fresh Rain root" }
    if ([string]$Manifest.output.namespace -match "nav_sage_v2|rain_sage_v1") { throw "output namespace points to a protected/legacy namespace" }
    if ([string]$Manifest.sources.protected_production_entry.sha256 -ne $ExpectedProtectedProductionSha256) { throw "protected production hash in request is wrong" }
    Assert-EqualText (Get-FileSha256 ([string]$Manifest.sources.protected_production_entry.path)) $ExpectedProtectedProductionSha256 "protected production pipeline changed"
    foreach ($property in $Manifest.inputs.PSObject.Properties) {
        $verifyHash = ($property.Name -ne "raw_iq")
        Assert-InputFile -Record (Get-InputRecord $property.Value) -Name $property.Name -VerifyHash:$verifyHash
    }
    Assert-SourceFiles -SourceRecords $Manifest.sources
    if ([string]$Manifest.inputs.raw_iq.sha256_status -eq "COMPUTED") {
        Assert-EqualText (Get-FileSha256 ([string]$Manifest.inputs.raw_iq.path)) ([string]$Manifest.inputs.raw_iq.sha256) "raw IQ hash changed"
    }
}

function Assert-NormalUser {
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    if ($identity.Name -ne "TJ-CHANNEL\Jing_") { throw "formal Rain execution requires TJ-CHANNEL\Jing_; actual=$($identity.Name)" }
    $principal = [System.Security.Principal.WindowsPrincipal]::new($identity)
    if ($principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) { throw "formal Rain execution must not run elevated" }
}

function Get-OutputFileRecords {
    $output = [string]$Manifest.output.namespace
    if (-not (Test-Path -LiteralPath $output -PathType Container)) { return @() }
    return @(Get-ChildItem -LiteralPath $output -File -Recurse | ForEach-Object {
        [ordered]@{
            path = $_.FullName
            bytes = $_.Length
            sha256 = Get-FileSha256 $_.FullName
        }
    })
}

function Get-MissingRequiredOutputFiles {
    $output = [string]$Manifest.output.namespace
    return @($REQUIRED_OUTPUT_FILES | Where-Object {
        -not (Test-Path -LiteralPath (Join-Path $output $_) -PathType Leaf)
    })
}

function Invoke-MatlabBatch {
    param(
        [Parameter(Mandatory = $true)][string]$Expression,
        [Parameter(Mandatory = $true)][string]$StdoutPath,
        [Parameter(Mandatory = $true)][string]$StderrPath
    )
    $startUtc = (Get-Date).ToUniversalTime()
    $process = $null
    $stdout = ""
    $stderr = ""
    $launchError = $null
    $exitCode = $null
    $processId = $null
    $argumentMode = "ProcessStartInfo.Arguments"
    try {
        $info = [System.Diagnostics.ProcessStartInfo]::new()
        $info.FileName = $MatlabExecutable
        $info.WorkingDirectory = $ProjectRoot
        $info.UseShellExecute = $false
        $info.CreateNoWindow = $true
        $info.RedirectStandardOutput = $true
        $info.RedirectStandardError = $true

        # PowerShell 7/.NET uses ArgumentList so the complete MATLAB batch
        # expression remains one argv item.  The Arguments fallback preserves
        # the same quoting contract for Windows PowerShell/.NET Framework.
        $argumentListProperty = $info.PSObject.Properties["ArgumentList"]
        if ($null -ne $argumentListProperty) {
            [void]$info.ArgumentList.Add("-batch")
            [void]$info.ArgumentList.Add($expression)
            $argumentMode = "ProcessStartInfo.ArgumentList"
        }
        else {
            $escapedExpression = $Expression.Replace('"', '\\"')
            $info.Arguments = '-batch "' + $escapedExpression + '"'
        }

        $process = [System.Diagnostics.Process]::new()
        $process.StartInfo = $info
        if (-not $process.Start()) {
            throw "MATLAB process did not start"
        }
        $processId = $process.Id
        $stdoutTask = $process.StandardOutput.ReadToEndAsync()
        $stderrTask = $process.StandardError.ReadToEndAsync()
        $process.WaitForExit()
        $stdout = $stdoutTask.GetAwaiter().GetResult()
        $stderr = $stderrTask.GetAwaiter().GetResult()
        $exitCode = $process.ExitCode
    }
    catch {
        $launchError = [string]$_.Exception.Message
        if ([string]::IsNullOrEmpty($stderr)) { $stderr = $launchError }
    }
    finally {
        if ($null -ne $process) { $process.Dispose() }
    }
    if ($null -eq $stdout) { $stdout = "" }
    if ($null -eq $stderr) { $stderr = "" }
    [System.IO.File]::WriteAllText($StdoutPath, $stdout, [System.Text.UTF8Encoding]::new($false))
    [System.IO.File]::WriteAllText($StderrPath, $stderr, [System.Text.UTF8Encoding]::new($false))
    return [pscustomobject]@{
        ProcessId = $processId
        ArgumentMode = $argumentMode
        StartUtc = $startUtc.ToString("o")
        EndUtc = (Get-Date).ToUniversalTime().ToString("o")
        ExitCode = $exitCode
        LaunchError = $launchError
    }
}

Assert-Manifest
$expression = New-MatlabExpression -Task $Manifest.task
Assert-GlobalMutexAvailable

if (-not $Execute) {
    $matlab_invoked = $false
    Write-Output "EXECUTION_ELIGIBLE=true"
    Write-Output "MATLAB_INVOKED=false"
    Write-Output "RAW_IQ_OPENED=false"
    Write-Output "SAGE_EXECUTED=false"
    Write-Output "TASK=$($Manifest.task.scene_id)/$($Manifest.task.prn)/ch$($Manifest.task.tracking_channel)"
    Write-Output "OUTPUT_NAMESPACE=$($Manifest.output.namespace)"
    Write-Output "MATLAB_EXPRESSION=$expression"
    exit 0
}

if (-not $ConfirmRainSageRerun) { throw "--execute requires --confirm-rain-sage-rerun" }
Assert-NormalUser
if (-not (Test-Path -LiteralPath $MatlabExecutable -PathType Leaf)) { throw "MATLAB executable is missing: $MatlabExecutable" }

$receiptDirectory = [string]$Manifest.request_paths.execution_receipt_directory
if (-not (Test-Path -LiteralPath $receiptDirectory -PathType Container)) {
    New-Item -ItemType Directory -Path $receiptDirectory | Out-Null
}
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$stdoutPath = Join-Path $receiptDirectory ("{0}_{1}_stdout.log" -f $Manifest.request_id, $stamp)
$stderrPath = Join-Path $receiptDirectory ("{0}_{1}_stderr.log" -f $Manifest.request_id, $stamp)
$receiptPath = Join-Path $receiptDirectory ("{0}_{1}_receipt.json" -f $Manifest.request_id, $stamp)

try {
    $Mutex = [System.Threading.Mutex]::new($false, $MutexName)
    if (-not $Mutex.WaitOne(0)) { throw "another fresh Rain task is already running" }
    $MutexAcquired = $true
    $startUtc = (Get-Date).ToUniversalTime()
    $processResult = Invoke-MatlabBatch -Expression $expression -StdoutPath $stdoutPath -StderrPath $stderrPath
    $endUtc = (Get-Date).ToUniversalTime()
    $outputFiles = @(Get-OutputFileRecords)
    $missingOutputFiles = @(Get-MissingRequiredOutputFiles)
    $outputNamespaceExists = Test-Path -LiteralPath ([string]$Manifest.output.namespace) -PathType Container
    if ($null -eq $processResult.ExitCode) {
        $status = "FAILED_PROCESS_LAUNCH"
    }
    elseif ($processResult.ExitCode -ne 0) {
        $status = "FAILED"
    }
    elseif ($missingOutputFiles.Count -gt 0) {
        $status = "FAILED_OUTPUT_MISSING"
    }
    else {
        $status = "COMPLETED"
    }
    $receipt = [ordered]@{
        schema_version = "rain-sage-fresh-execution-receipt-v1"
        status = $status
        request_id = [string]$Manifest.request_id
        request_manifest = $ManifestPath
        request_manifest_sha256 = $ExpectedRequestSha256.ToLowerInvariant()
        task = $Manifest.task
        output_namespace = [string]$Manifest.output.namespace
        execution_mode = "new_only"
        resume_allowed = $false
        gold_labels_used_for_selection = $false
        matlab_invoked = $true
        matlab_expression = $expression
        matlab_argument_mode = $processResult.ArgumentMode
        process_id = $processResult.ProcessId
        matlab_exit_code = $processResult.ExitCode
        matlab_launch_error = $processResult.LaunchError
        start_utc = $startUtc.ToString("o")
        end_utc = $endUtc.ToString("o")
        stdout_path = $stdoutPath
        stderr_path = $stderrPath
        required_output_files = @($REQUIRED_OUTPUT_FILES)
        missing_output_files = $missingOutputFiles
        output_namespace_exists = $outputNamespaceExists
        output_files = $outputFiles
    }
    Write-NewJson -Path $receiptPath -Value $receipt
    Write-Output "EXECUTION_STATUS=$status"
    Write-Output "EXECUTION_RECEIPT=$receiptPath"
    if ($status -ne "COMPLETED") {
        $failureExitCode = if ($null -ne $processResult.ExitCode -and $processResult.ExitCode -ne 0) { [int]$processResult.ExitCode } else { 1 }
        exit $failureExitCode
    }
}
catch {
    Write-Error "RAIN_FRESH_EXECUTOR_FAILED=$($_.Exception.Message)"
    throw
}
finally {
    if ($MutexAcquired -and $null -ne $Mutex) { $Mutex.ReleaseMutex() | Out-Null }
    if ($null -ne $Mutex) { $Mutex.Dispose() }
}
