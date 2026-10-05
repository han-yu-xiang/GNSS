$guardPath = Join-Path $PSScriptRoot '..\Assert-GpuQualificationPrnIdentity.ps1'
if (Test-Path -LiteralPath $guardPath) {
    . $guardPath
}

Describe 'GPU qualification PRN identity guard' {
    It 'accepts a consistent PRN 3 task identity' {
        $result = Assert-GpuQualificationPrnIdentity `
            -ManifestPrn 'G03' `
            -FormalTaskPrn 'G03' `
            -ProductionCfgPrn 3 `
            -HelperRequestedPrn 3

        $result | Should Be 3
    }

    It 'accepts a consistent non-PRN-3 task identity' {
        $result = Assert-GpuQualificationPrnIdentity `
            -ManifestPrn 'G28' `
            -FormalTaskPrn 'G28' `
            -ProductionCfgPrn 28 `
            -HelperRequestedPrn 28

        $result | Should Be 28
    }

    It 'fails closed when manifest and production config PRNs differ' {
        $failureMessage = $null
        try {
            [void](Assert-GpuQualificationPrnIdentity `
                -ManifestPrn 'G03' `
                -FormalTaskPrn 'G03' `
                -ProductionCfgPrn 28 `
                -HelperRequestedPrn 3)
        }
        catch {
            $failureMessage = $_.Exception.Message
        }

        $failureMessage | Should BeLike '*INPUT_IDENTITY_VALIDATION=FAIL*'
    }
}
