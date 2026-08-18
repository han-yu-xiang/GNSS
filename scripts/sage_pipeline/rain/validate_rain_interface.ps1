Set-StrictMode -Version Latest

function Remove-MatlabLineComments {
    param([Parameter(Mandatory = $true)][string]$Source)
    return [regex]::Replace($Source, '(?m)%[^\r\n]*', '')
}

function Test-RainInterfaceSource {
    param(
        [Parameter(Mandatory = $true)][string]$EntrySource,
        [Parameter(Mandatory = $true)][string]$EvaluatorSource,
        [Parameter(Mandatory = $true)][bool]$EvaluatorPathExists
    )

    if (-not $EvaluatorPathExists) {
        return [pscustomobject]@{
            Pass = $false
            Reason = "standalone evaluator file is missing"
        }
    }

    $entryCode = Remove-MatlabLineComments -Source $EntrySource
    $evaluatorCode = Remove-MatlabLineComments -Source $EvaluatorSource
    $primaryFunctionPattern = '(?im)^\s*function\s+result\s*=\s*run_rain_sage_stage1_stage4\s*\('
    if ($evaluatorCode -notmatch $primaryFunctionPattern) {
        return [pscustomobject]@{
            Pass = $false
            Reason = "standalone evaluator primary function name does not match file contract"
        }
    }

    $callPattern = '(?is)(?<![A-Za-z0-9_])run_rain_sage_stage1_stage4\s*\('
    if ($entryCode -notmatch $callPattern) {
        return [pscustomobject]@{
            Pass = $false
            Reason = "Rain entry has no call to the standalone Stage1-Stage4 evaluator"
        }
    }
    if ($entryCode -match '(?is)(?<![A-Za-z0-9_])run_nav_sage_pipeline\s*\(') {
        return [pscustomobject]@{
            Pass = $false
            Reason = "Rain entry calls the production pipeline"
        }
    }
    if (($entryCode + "`n" + $evaluatorCode) -match '(?is)run_sage_stage1_stage4_core') {
        return [pscustomobject]@{
            Pass = $false
            Reason = "Rain route references the shared-core evaluator"
        }
    }

    return [pscustomobject]@{
        Pass = $true
        Reason = "Rain standalone evaluator exists, has the expected primary function, and is called by the Rain entry"
    }
}
