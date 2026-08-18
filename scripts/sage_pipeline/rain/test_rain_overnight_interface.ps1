$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$rainDirectory = Split-Path -Parent $PSCommandPath
. (Join-Path $rainDirectory "validate_rain_interface.ps1")

$evaluator = @"
function result = run_rain_sage_stage1_stage4(windowCatalog, symbolCatalog, rawFile, outputDir, cfg)
end
"@

$multilineEntry = @"
function result = run_rain_sage_pipeline(sceneId, prn, varargin)
    coreResult = run_rain_sage_stage1_stage4( ...
        stage0.windowCatalog, stage0.symbolCatalog, ...
        stage0.raw_file, outputDir, stage0.cfg);
end
"@

$whitespaceEntry = @"
function result = run_rain_sage_pipeline(sceneId, prn, varargin)
    coreResult = run_rain_sage_stage1_stage4   (stage0.windowCatalog, ...
        stage0.symbolCatalog, stage0.raw_file, outputDir, stage0.cfg);
end
"@

$noCallEntry = @"
function result = run_rain_sage_pipeline(sceneId, prn, varargin)
    result.status = "RAIN_PREFLIGHT_ONLY";
end
"@

$productionEntry = $multilineEntry + "`nrun_nav_sage_pipeline(sceneId, prn);"
$sharedCoreEntry = $multilineEntry + "`nrun_sage_stage1_stage4_core;"

function Assert-InterfacePass {
    param([object]$Result)
    if (-not $Result.Pass) { throw "Expected interface PASS: $($Result.Reason)" }
}

function Assert-InterfaceFail {
    param([object]$Result, [string]$ExpectedReason)
    if ($Result.Pass) { throw "Expected interface FAIL." }
    if ($Result.Reason -notlike "*$ExpectedReason*") {
        throw "Unexpected interface failure reason: $($Result.Reason)"
    }
}

Assert-InterfacePass (Test-RainInterfaceSource -EntrySource $multilineEntry -EvaluatorSource $evaluator -EvaluatorPathExists $true)
Assert-InterfacePass (Test-RainInterfaceSource -EntrySource $whitespaceEntry -EvaluatorSource $evaluator -EvaluatorPathExists $true)
Assert-InterfaceFail (Test-RainInterfaceSource -EntrySource $noCallEntry -EvaluatorSource $evaluator -EvaluatorPathExists $true) "no call"
Assert-InterfaceFail (Test-RainInterfaceSource -EntrySource $productionEntry -EvaluatorSource $evaluator -EvaluatorPathExists $true) "production pipeline"
Assert-InterfaceFail (Test-RainInterfaceSource -EntrySource $sharedCoreEntry -EvaluatorSource $evaluator -EvaluatorPathExists $true) "shared-core"
Assert-InterfaceFail (Test-RainInterfaceSource -EntrySource $multilineEntry -EvaluatorSource $evaluator -EvaluatorPathExists $false) "missing"

Write-Output "RAIN_INTERFACE_TESTS=6/6 PASS"
