<#!
No-MATLAB static validation for Invoke-BatchSageWindows.ps1.
This file parses the wrapper and checks that the immutable request contract is
forwarded to the Python executor.  It never invokes the wrapper or MATLAB.
#>
[CmdletBinding()]
param(
    [string]$WrapperPath = ''
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($WrapperPath)) {
    $scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
    $WrapperPath = Join-Path -Path $scriptDirectory -ChildPath 'Invoke-BatchSageWindows.ps1'
}

if (-not (Test-Path -LiteralPath $WrapperPath -PathType Leaf)) {
    throw "Wrapper does not exist: $WrapperPath"
}

$tokens = $null
$parseErrors = $null
[System.Management.Automation.Language.Parser]::ParseFile(
    $WrapperPath,
    [ref]$tokens,
    [ref]$parseErrors
) | Out-Null
if ($parseErrors.Count -gt 0) {
    throw (($parseErrors | ForEach-Object { $_.Message }) -join '; ')
}

$source = Get-Content -LiteralPath $WrapperPath -Raw -Encoding UTF8
foreach ($requiredText in @(
    "'--request-manifest'",
    "'--expected-request-sha256'",
    "'--execute'"
)) {
    if ($source -notmatch [regex]::Escape($requiredText)) {
        throw "Wrapper is missing required executor argument: $requiredText"
    }
}

Write-Output 'POWERSHELL_AST_PASS'
Write-Output 'REQUEST_FORWARDING_STATIC_PASS'
