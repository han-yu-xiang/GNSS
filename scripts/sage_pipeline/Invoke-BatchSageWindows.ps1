<#
.SYNOPSIS
Runs one hash-approved NAV-SAGE batch request from a normal Windows user session.

.DESCRIPTION
This wrapper is deliberately not a second SAGE executor.  It only enforces the
normal-user identity boundary, immutable-request hashes, the current 10.23 MHz
single-task scope, a cross-execution lock, and a MATLAB startup smoke test.  All
task/input/reference/output gates remain in run_batch_sage.py.

Default mode is validation only.  MATLAB can be reached only when BOTH
-Execute and -ConfirmPilot are supplied by TJ-Channel\Jing_.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$RequestManifest,

    [Parameter(Mandatory)]
    [ValidatePattern('^[A-Fa-f0-9]{64}$')]
    [string]$ExpectedRequestSha256,

    [switch]$Execute,

    [switch]$ConfirmPilot
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$RequiredSampleRateHz = 10230000
$RequiredSchema = 'windows_execution_request_v1'

function Get-FileSha256 {
    param([Parameter(Mandatory)][string]$LiteralPath)

    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
        throw "Required file does not exist: $LiteralPath"
    }
    return (Get-FileHash -LiteralPath $LiteralPath -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Resolve-ExistingFile {
    param([Parameter(Mandatory)][string]$LiteralPath, [Parameter(Mandatory)][string]$Label)

    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Leaf)) {
        throw "$Label is not an existing file: $LiteralPath"
    }
    return (Resolve-Path -LiteralPath $LiteralPath).Path
}

function Resolve-ExistingDirectory {
    param([Parameter(Mandatory)][string]$LiteralPath, [Parameter(Mandatory)][string]$Label)

    if (-not (Test-Path -LiteralPath $LiteralPath -PathType Container)) {
        throw "$Label is not an existing directory: $LiteralPath"
    }
    return (Resolve-Path -LiteralPath $LiteralPath).Path
}

function Resolve-RequestFilePath {
    param(
        [Parameter(Mandatory)][string]$RequestedPath,
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][string]$Label
    )

    $candidate = if ([System.IO.Path]::IsPathRooted($RequestedPath)) {
        $RequestedPath
    } else {
        Join-Path -Path $ProjectRoot -ChildPath $RequestedPath
    }
    return Resolve-ExistingFile -LiteralPath $candidate -Label $Label
}

function Get-CanonicalPathForBoundary {
    param([Parameter(Mandatory)][string]$LiteralPath)

    # GetFullPath collapses ``.`` and ``..`` before the boundary check.  Keep a
    # volume root (for example ``E:\``) intact, but remove trailing directory
    # separators from ordinary paths so a single canonical representation is
    # compared below.
    $fullPath = [System.IO.Path]::GetFullPath($LiteralPath)
    $volumeRoot = [System.IO.Path]::GetPathRoot($fullPath)
    if ([string]::IsNullOrWhiteSpace($volumeRoot)) {
        throw "Unable to determine a Windows volume root for path: $LiteralPath"
    }
    if ([string]::Equals($fullPath, $volumeRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $volumeRoot
    }
    return $fullPath.TrimEnd([char[]]@(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    ))
}

function Test-PathInsideRoot {
    param([Parameter(Mandatory)][string]$LiteralPath, [Parameter(Mandatory)][string]$ProjectRoot)

    $fullPath = Get-CanonicalPathForBoundary -LiteralPath $LiteralPath
    $fullRoot = Get-CanonicalPathForBoundary -LiteralPath $ProjectRoot
    if ([string]::Equals($fullPath, $fullRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }

    # Do not use a bare string prefix: E:\GNSS_Multipath_Project_Evil must not
    # be accepted as a child of E:\GNSS_Multipath_Project.  The explicit one
    # character separator is the directory-boundary proof.
    $rootPrefix = if ($fullRoot.EndsWith([string][System.IO.Path]::DirectorySeparatorChar) -or
        $fullRoot.EndsWith([string][System.IO.Path]::AltDirectorySeparatorChar)) {
        $fullRoot
    } else {
        $fullRoot + [System.IO.Path]::DirectorySeparatorChar
    }
    return $fullPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-CanonicalProjectPath {
    param([Parameter(Mandatory)][string]$RequestedPath, [Parameter(Mandatory)][string]$ProjectRoot)

    # Plan paths are normally absolute.  Treat a relative form as explicitly
    # project-root-relative so ``.``/``..`` are normalized deterministically,
    # never relative to the caller's current directory.
    $candidate = if ([System.IO.Path]::IsPathRooted($RequestedPath)) {
        $RequestedPath
    } else {
        Join-Path -Path $ProjectRoot -ChildPath $RequestedPath
    }
    return Get-CanonicalPathForBoundary -LiteralPath $candidate
}

function Get-ExpectedNavSageOutputPath {
    param(
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][string]$SceneId,
        [Parameter(Mandatory)][string]$Prn
    )

    # Build one component at a time.  This avoids relying on PowerShell string
    # escaping for Windows separators and keeps the namespace contract exact.
    $sceneRoot = Join-Path -Path $ProjectRoot -ChildPath 'scenes'
    $sceneRoot = Join-Path -Path $sceneRoot -ChildPath $SceneId
    $sageRoot = Join-Path -Path $sceneRoot -ChildPath 'sage_results'
    $namespaceRoot = Join-Path -Path $sageRoot -ChildPath 'nav_sage_v2'
    return Get-CanonicalPathForBoundary -LiteralPath (Join-Path -Path $namespaceRoot -ChildPath $Prn)
}

function Test-ExactNavSageOutputPath {
    param(
        [Parameter(Mandatory)][string]$OutputPath,
        [Parameter(Mandatory)][string]$ProjectRoot,
        [Parameter(Mandatory)][string]$SceneId,
        [Parameter(Mandatory)][string]$Prn
    )

    $actualOutput = Get-CanonicalProjectPath -RequestedPath $OutputPath -ProjectRoot $ProjectRoot
    $expectedOutput = Get-ExpectedNavSageOutputPath -ProjectRoot $ProjectRoot -SceneId $SceneId -Prn $Prn
    return [string]::Equals($actualOutput, $expectedOutput, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-StrictTrue {
    param([AllowNull()][object]$Value)

    return [string]::Equals([string]$Value, 'true', [System.StringComparison]::OrdinalIgnoreCase) -or
        [string]::Equals([string]$Value, '1', [System.StringComparison]::OrdinalIgnoreCase)
}

function Resolve-PythonExecutablePath {
    param([Parameter(Mandatory)][string]$RequestedPython)

    # The request is the selector.  An absolute path is therefore authoritative;
    # a command name is resolved only through ApplicationInfo.Path (never Source,
    # which can become an array when Get-Command returns multiple candidates).
    if ([System.IO.Path]::IsPathRooted($RequestedPython)) {
        $resolvedAbsolute = Resolve-ExistingFile -LiteralPath $RequestedPython -Label 'Requested Python executable'
        $absoluteItem = Get-Item -LiteralPath $resolvedAbsolute -Force
        if ($absoluteItem -isnot [System.IO.FileInfo] -or $absoluteItem.Extension -ne '.exe') {
            throw "Requested Python path is not a Windows executable file: $resolvedAbsolute"
        }
        return [string]$resolvedAbsolute
    }

    $commands = @(Get-Command -Name $RequestedPython -CommandType Application -All -ErrorAction Stop)
    $candidates = @()
    foreach ($command in $commands) {
        $commandPath = [string]$command.Path
        if ([string]::IsNullOrWhiteSpace($commandPath)) {
            continue
        }
        $resolvedPath = Resolve-ExistingFile -LiteralPath $commandPath -Label "Python candidate $($command.Name)"
        $item = Get-Item -LiteralPath $resolvedPath -Force
        if ($item -isnot [System.IO.FileInfo] -or $item.Extension -ne '.exe') {
            continue
        }
        $candidates += [pscustomobject]@{
            Path = [string]$resolvedPath
            # WindowsApps/python.exe is the Windows App Execution Alias, not a
            # pinned project interpreter.  It is intentionally not preferred.
            IsWindowsAppsAlias = [string]::Equals(
                $item.Directory.Name,
                'WindowsApps',
                [System.StringComparison]::OrdinalIgnoreCase
            )
        }
    }
    $uniqueCandidates = @($candidates | Sort-Object -Property Path -Unique)
    $realCandidates = @($uniqueCandidates | Where-Object { -not $_.IsWindowsAppsAlias })

    if ($realCandidates.Count -eq 1) {
        return [string]$realCandidates[0].Path
    }
    if ($realCandidates.Count -gt 1) {
        $paths = ($realCandidates | ForEach-Object { $_.Path }) -join '; '
        throw "Multiple real Python executable candidates were found for '$RequestedPython'. Freeze an absolute interpreter path in a new reviewed request: $paths"
    }
    if ($uniqueCandidates.Count -eq 1) {
        # Keep a nonstandard but unambiguous ApplicationInfo executable usable;
        # its resolved full path is still recorded in the eventual receipt.
        return [string]$uniqueCandidates[0].Path
    }
    if ($uniqueCandidates.Count -eq 0) {
        throw "No executable Python candidate was found for '$RequestedPython'."
    }
    $paths = ($uniqueCandidates | ForEach-Object { $_.Path }) -join '; '
    throw "Python executable candidates are ambiguous for '$RequestedPython': $paths"
}

function Start-ManagedProcess {
    param(
        [Parameter(Mandatory)][string]$FilePath,
        [Parameter(Mandatory)][string[]]$Arguments,
        [Parameter(Mandatory)][string]$WorkingDirectory,
        [Parameter(Mandatory)][string]$StdoutPath,
        [Parameter(Mandatory)][string]$StderrPath
    )

    $start = [System.DateTimeOffset]::UtcNow
    $info = [System.Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $FilePath
    $info.WorkingDirectory = $WorkingDirectory
    $info.UseShellExecute = $false
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.CreateNoWindow = $true
    foreach ($argument in $Arguments) {
        [void]$info.ArgumentList.Add([string]$argument)
    }

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $info
    if (-not $process.Start()) {
        throw "Unable to start process: $FilePath"
    }
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    $utf8 = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($StdoutPath, $stdout, $utf8)
    [System.IO.File]::WriteAllText($StderrPath, $stderr, $utf8)
    $end = [System.DateTimeOffset]::UtcNow

    return [pscustomobject]@{
        ExitCode = $process.ExitCode
        Stdout = $stdout
        Stderr = $stderr
        StartedUtc = $start.ToString('o')
        EndedUtc = $end.ToString('o')
        DurationSeconds = [Math]::Round(($end - $start).TotalSeconds, 3)
    }
}

function Write-Utf8Json {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][object]$Value)

    $utf8 = [System.Text.UTF8Encoding]::new($false)
    $json = $Value | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($Path, $json + [Environment]::NewLine, $utf8)
}

function Get-ExecutorOutputValue {
    param([Parameter(Mandatory)][string]$Text, [Parameter(Mandatory)][string]$Key)

    $prefix = $Key + '='
    foreach ($line in ($Text -split "`r?`n")) {
        if ($line.StartsWith($prefix, [System.StringComparison]::Ordinal)) {
            return $line.Substring($prefix.Length).Trim()
        }
    }
    return $null
}

if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw 'PowerShell 7 or newer is required. Start this wrapper from an interactive pwsh session.'
}

$manifestPath = Resolve-ExistingFile -LiteralPath $RequestManifest -Label 'Execution request manifest'
$actualRequestHash = Get-FileSha256 -LiteralPath $manifestPath
if (-not [string]::Equals($actualRequestHash, $ExpectedRequestSha256.ToLowerInvariant(), [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Execution request SHA-256 mismatch. Expected $ExpectedRequestSha256; actual $actualRequestHash."
}

$request = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($request.schema_version -ne $RequiredSchema) {
    throw "Unsupported execution request schema: $($request.schema_version)"
}
if ([string]::IsNullOrWhiteSpace([string]$request.request_id)) {
    throw 'Execution request does not contain request_id.'
}

$projectRoot = Resolve-ExistingDirectory -LiteralPath ([string]$request.project_root) -Label 'Project root'
$planPath = Resolve-RequestFilePath -RequestedPath ([string]$request.plan_path) -ProjectRoot $projectRoot -Label 'Batch plan'
$selectionPath = Resolve-RequestFilePath -RequestedPath ([string]$request.selected_tasks_snapshot_path) -ProjectRoot $projectRoot -Label 'Selected-task snapshot'
$pipelinePath = Resolve-RequestFilePath -RequestedPath ([string]$request.pipeline_path) -ProjectRoot $projectRoot -Label 'SAGE pipeline entrypoint'
$executorPath = Resolve-RequestFilePath -RequestedPath ([string]$request.python_executor_path) -ProjectRoot $projectRoot -Label 'Python batch executor'

foreach ($pathToCheck in @($manifestPath, $planPath, $selectionPath, $pipelinePath, $executorPath)) {
    if (-not (Test-PathInsideRoot -LiteralPath $pathToCheck -ProjectRoot $projectRoot)) {
        throw "Request-referenced path escapes project root: $pathToCheck"
    }
}

foreach ($pair in @(
    @{ Label = 'plan'; Path = $planPath; Expected = [string]$request.plan_sha256 },
    @{ Label = 'selected-task snapshot'; Path = $selectionPath; Expected = [string]$request.selected_tasks_sha256 },
    @{ Label = 'pipeline'; Path = $pipelinePath; Expected = [string]$request.pipeline_sha256 },
    @{ Label = 'Python executor'; Path = $executorPath; Expected = [string]$request.python_executor_sha256 }
)) {
    if ([string]::IsNullOrWhiteSpace($pair.Expected)) {
        throw "Execution request has no SHA-256 for $($pair.Label)."
    }
    $actualHash = Get-FileSha256 -LiteralPath $pair.Path
    if (-not [string]::Equals($actualHash, $pair.Expected.ToLowerInvariant(), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$($pair.Label) SHA-256 mismatch. Expected $($pair.Expected); actual $actualHash."
    }
}

$orderedTaskIds = @($request.ordered_task_ids | ForEach-Object { [string]$_ })
if ($orderedTaskIds.Count -ne 1 -or [string]::IsNullOrWhiteSpace($orderedTaskIds[0])) {
    throw 'This wrapper requires exactly one non-empty approved task ID in the immutable request.'
}
$approvedTaskId = $orderedTaskIds[0]
if (@($request.allowed_sample_rates_hz | ForEach-Object { [int]$_ }) -notcontains $RequiredSampleRateHz) {
    throw "Execution request does not permit the required sample rate $RequiredSampleRateHz."
}
if (@($request.allowed_sample_rates_hz).Count -ne 1) {
    throw 'This wrapper requires exactly one allowed sample rate: 10230000 Hz.'
}
if ($request.experiment_namespace -ne 'nav_sage_v2' -or $request.execution_mode -ne 'new_only' -or
    [bool]$request.resume_allowed -or [int]$request.max_parallel_matlab -ne 1 -or
    -not [bool]$request.startup_smoke_required) {
    throw 'Execution request violates fixed single-task execution policy.'
}

$selectedRows = @(Import-Csv -LiteralPath $selectionPath)
if ($selectedRows.Count -ne 1 -or [string]$selectedRows[0].task_id -ne $approvedTaskId) {
    throw 'Selected-task snapshot must contain only the approved request task in the approved order.'
}
$planRows = @(Import-Csv -LiteralPath $planPath)
$approvedRows = @($planRows | Where-Object { [string]$_.task_id -eq $approvedTaskId })
if ($approvedRows.Count -ne 1) {
    throw "Immutable plan must contain exactly one approved task row; found $($approvedRows.Count)."
}
$approvedTask = $approvedRows[0]
$approvedSceneId = [string]$approvedTask.scene_id
$approvedPrn = ([string]$approvedTask.prn).ToUpperInvariant()
$approvedChannel = [int]$approvedTask.tracking_channel
if ([string]::IsNullOrWhiteSpace($approvedSceneId) -or $approvedPrn -notmatch '^G\d{2}$' -or
    $approvedChannel -lt 0 -or [int]$approvedTask.sample_rate_hz -ne $RequiredSampleRateHz) {
    throw 'Approved plan row has an invalid scene, GPS PRN, channel, or unsupported sample rate.'
}
if ([string]$approvedTask.scene_role -eq 'reference_scene' -or $approvedSceneId -eq 'F1023_V70_D0117_P2') {
    throw 'Reference scene execution is not allowed by this Windows wrapper.'
}
if ([string]$approvedTask.status -ne 'ready' -or -not (Test-StrictTrue $approvedTask.execution_allowed) -or
    (Test-StrictTrue $approvedTask.requires_manual_channel_selection) -or
    -not [string]::IsNullOrWhiteSpace([string]$approvedTask.hard_gate_failures)) {
    throw 'Approved plan row is not eligible for execution; Python executor remains the authoritative task gate.'
}
$expectedTaskId = "$approvedSceneId`__$approvedPrn`__ch$approvedChannel`__nav_sage_v2"
if ($approvedTaskId -ne $expectedTaskId) {
    throw "Approved task ID does not match the plan scene/PRN/channel namespace: $approvedTaskId"
}
$expectedOutput = Get-ExpectedNavSageOutputPath -ProjectRoot $projectRoot -SceneId $approvedSceneId -Prn $approvedPrn
if (-not (Test-ExactNavSageOutputPath -OutputPath ([string]$approvedTask.output_path) -ProjectRoot $projectRoot -SceneId $approvedSceneId -Prn $approvedPrn)) {
    throw 'Approved output path does not match the fixed nav_sage_v2 namespace.'
}
if (Test-Path -LiteralPath $expectedOutput) {
    throw "Approved output path already exists; no overwrite or resume is permitted: $expectedOutput"
}
if (-not [string]::Equals([string]$approvedTask.pipeline_sha256, [string]$request.pipeline_sha256, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Plan pipeline SHA-256 does not match the immutable request.'
}

$matlabPath = Resolve-ExistingFile -LiteralPath ([string]$request.matlab_executable) -Label 'MATLAB executable'
$currentIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
$currentIdentityName = $currentIdentity.Name
$expectedIdentity = [string]$request.expected_windows_identity
if ($currentIdentityName -match '(?i)codexsandboxoffline') {
    throw "Codex sandbox identity is permanently denied: $currentIdentityName"
}
if (-not [string]::Equals($currentIdentityName, $expectedIdentity, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Current Windows identity is not approved. Expected $expectedIdentity; actual $currentIdentityName."
}
$principal = [System.Security.Principal.WindowsPrincipal]::new($currentIdentity)
if ($principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Run from a normal non-elevated TJ-Channel\\Jing_ PowerShell session, not an Administrator shell.'
}

Write-Output "REQUEST_VALIDATED request_id=$($request.request_id)"
Write-Output "APPROVED_SCOPE=$approvedSceneId/$approvedPrn/ch$approvedChannel/$RequiredSampleRateHz"
Write-Output "MATLAB_EXECUTABLE=$matlabPath"
Write-Output 'MATLAB is blocked by default. Supply both -Execute and -ConfirmPilot only after human review.'

if (-not $Execute) {
    Write-Output 'VALIDATION_ONLY_OK matlab_invoked=false'
    return
}
if (-not $ConfirmPilot) {
    throw 'Execution denied. -Execute requires the separate explicit -ConfirmPilot switch.'
}

$executionLogParent = Join-Path -Path $projectRoot -ChildPath 'dataset_generation_logs\\batch_sage_execution'
$wrapperRootParent = Join-Path -Path $executionLogParent -ChildPath 'windows_runner_receipts'
$timestamp = [System.DateTimeOffset]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
$wrapperRoot = Join-Path -Path $wrapperRootParent -ChildPath ("$($request.request_id)_$timestamp")
[void](New-Item -ItemType Directory -Path $wrapperRoot -Force:$false)

$globalLockPath = Join-Path -Path $executionLogParent -ChildPath '.windows_runner_active.lock'
$lockStream = $null
$controlledEnd = $false
$executionRoot = $null
try {
    try {
        $lockStream = [System.IO.File]::Open(
            $globalLockPath,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::ReadWrite,
            [System.IO.FileShare]::None
        )
    } catch [System.IO.IOException] {
        throw "Global Windows SAGE runner lock already exists. Stop and inspect it manually: $globalLockPath"
    }
    $lockPayload = [ordered]@{
        request_id = [string]$request.request_id
        request_sha256 = $actualRequestHash
        windows_identity = $currentIdentityName
        windows_sid = $currentIdentity.User.Value
        process_id = $PID
        started_utc = [System.DateTimeOffset]::UtcNow.ToString('o')
    }
    $lockWriter = [System.IO.StreamWriter]::new($lockStream, [System.Text.UTF8Encoding]::new($false), 1024, $true)
    $lockWriter.Write(($lockPayload | ConvertTo-Json -Depth 4))
    $lockWriter.Flush()
    $lockWriter.Dispose()

    $smoke = Start-ManagedProcess -FilePath $matlabPath -Arguments @('-batch', "disp('MATLAB_STARTUP_OK')") `
        -WorkingDirectory $projectRoot -StdoutPath (Join-Path $wrapperRoot 'matlab_startup_smoke.stdout.log') `
        -StderrPath (Join-Path $wrapperRoot 'matlab_startup_smoke.stderr.log')
    $matlabFileVersion = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($matlabPath).FileVersion
    $environmentReceipt = [ordered]@{
        request_id = [string]$request.request_id
        request_sha256 = $actualRequestHash
        windows_identity = $currentIdentityName
        windows_sid = $currentIdentity.User.Value
        powershell_version = $PSVersionTable.PSVersion.ToString()
        matlab_executable = $matlabPath
        matlab_file_version = $matlabFileVersion
        working_directory = $projectRoot
        smoke_exit_code = $smoke.ExitCode
        smoke_started_utc = $smoke.StartedUtc
        smoke_ended_utc = $smoke.EndedUtc
        smoke_duration_seconds = $smoke.DurationSeconds
        smoke_marker_present = $smoke.Stdout.Contains('MATLAB_STARTUP_OK')
    }
    Write-Utf8Json -Path (Join-Path $wrapperRoot 'environment_receipt.json') -Value $environmentReceipt
    if ($smoke.ExitCode -ne 0 -or -not $smoke.Stdout.Contains('MATLAB_STARTUP_OK')) {
        throw 'MATLAB startup smoke test failed; the Python executor and SAGE pipeline were not called.'
    }

    $pythonPath = Resolve-PythonExecutablePath -RequestedPython ([string]$request.python_executable)
    $executor = Start-ManagedProcess -FilePath $pythonPath -Arguments @(
        $executorPath,
        '--project-root', $projectRoot,
        '--plan', $planPath,
        '--selected-tasks', $selectionPath,
        '--request-manifest', $manifestPath,
        '--expected-request-sha256', $actualRequestHash,
        '--matlab-executable', $matlabPath,
        '--execute'
    ) -WorkingDirectory $projectRoot -StdoutPath (Join-Path $wrapperRoot 'python_executor.stdout.log') `
        -StderrPath (Join-Path $wrapperRoot 'python_executor.stderr.log')

    $executionLogPath = Get-ExecutorOutputValue -Text $executor.Stdout -Key 'execution_log'
    $executionReportPath = Get-ExecutorOutputValue -Text $executor.Stdout -Key 'execution_report'
    if ([string]::IsNullOrWhiteSpace($executionLogPath) -or -not (Test-Path -LiteralPath $executionLogPath -PathType Leaf)) {
        throw 'Python executor did not produce a readable batch_execution_log.csv.'
    }
    $executionRoot = Split-Path -Path $executionLogPath -Parent
    $taskResults = @(Import-Csv -LiteralPath $executionLogPath)
    $approvedResults = @($taskResults | Where-Object { [string]$_.task_id -eq $approvedTaskId })
    $approvedCompleted = $approvedResults.Count -eq 1 -and [string]$approvedResults[0].status -eq 'completed'
    $executionReceipt = [ordered]@{
        request_id = [string]$request.request_id
        request_sha256 = $actualRequestHash
        windows_identity = $currentIdentityName
        windows_sid = $currentIdentity.User.Value
        python_executable = $pythonPath
        python_exit_code = $executor.ExitCode
        python_started_utc = $executor.StartedUtc
        python_ended_utc = $executor.EndedUtc
        python_duration_seconds = $executor.DurationSeconds
        execution_log = $executionLogPath
        execution_report = $executionReportPath
        approved_task_id = $approvedTaskId
        approved_task_completed = $approvedCompleted
        task_results = $taskResults
        generated_utc = [System.DateTimeOffset]::UtcNow.ToString('o')
    }
    Write-Utf8Json -Path (Join-Path $wrapperRoot 'execution_receipt.json') -Value $executionReceipt
    if ($executor.ExitCode -ne 0 -or -not $approvedCompleted) {
        throw 'Approved task execution is not successful. Inspect the immutable wrapper receipt and Python execution log; do not retry automatically.'
    }
    $controlledEnd = $true
    Write-Output "WINDOWS_TASK_COMPLETED execution_log=$executionLogPath"
} catch {
    $controlledEnd = $true
    $failureReceipt = [ordered]@{
        request_id = [string]$request.request_id
        request_sha256 = $actualRequestHash
        windows_identity = $currentIdentityName
        error = $_.Exception.Message
        generated_utc = [System.DateTimeOffset]::UtcNow.ToString('o')
    }
    Write-Utf8Json -Path (Join-Path $wrapperRoot 'windows_runner_failure.json') -Value $failureReceipt
    throw
} finally {
    if ($null -ne $lockStream) {
        $lockStream.Dispose()
    }
    if ($controlledEnd -and (Test-Path -LiteralPath $globalLockPath -PathType Leaf)) {
        $lockArchiveRoot = if ($null -ne $executionRoot -and (Test-Path -LiteralPath $executionRoot -PathType Container)) {
            $executionRoot
        } else {
            $wrapperRoot
        }
        Move-Item -LiteralPath $globalLockPath -Destination (Join-Path $lockArchiveRoot 'windows_runner_global_lock.json') -ErrorAction Stop
    }
}
