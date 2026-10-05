function ConvertTo-GpuQualificationPrnNumber {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [object]$Value,

        [Parameter(Mandatory = $true)]
        [string]$SourceName
    )

    $text = if ($null -eq $Value) { '' } else { ([string]$Value).Trim() }
    if ($text -notmatch '^(?i:G)?(?<digits>\d{1,2})$') {
        throw "INPUT_IDENTITY_VALIDATION=FAIL: invalid PRN value for $SourceName."
    }

    $number = [int]::Parse(
        $Matches['digits'],
        [System.Globalization.CultureInfo]::InvariantCulture
    )
    if ($number -lt 1 -or $number -gt 32) {
        throw "INPUT_IDENTITY_VALIDATION=FAIL: PRN for $SourceName is outside the supported GPS PRN range."
    }

    return $number
}

function Assert-GpuQualificationPrnIdentity {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory = $true)]
        [object]$ManifestPrn,

        [Parameter(Mandatory = $true)]
        [object]$FormalTaskPrn,

        [Parameter(Mandatory = $true)]
        [object]$ProductionCfgPrn,

        [Parameter(Mandatory = $true)]
        [object]$HelperRequestedPrn
    )

    $sourceNames = @('manifest', 'formal task', 'production cfg', 'helper request')
    $sourceValues = @($ManifestPrn, $FormalTaskPrn, $ProductionCfgPrn, $HelperRequestedPrn)
    $normalizedValues = @()

    for ($index = 0; $index -lt $sourceValues.Count; $index++) {
        $normalizedValues += ConvertTo-GpuQualificationPrnNumber `
            -Value $sourceValues[$index] `
            -SourceName $sourceNames[$index]
    }

    $expectedPrn = [int]$normalizedValues[0]
    for ($index = 1; $index -lt $normalizedValues.Count; $index++) {
        if ([int]$normalizedValues[$index] -ne $expectedPrn) {
            $identityValues = for ($identityIndex = 0; $identityIndex -lt $sourceValues.Count; $identityIndex++) {
                '{0}={1}' -f $sourceNames[$identityIndex], $sourceValues[$identityIndex]
            }
            throw 'INPUT_IDENTITY_VALIDATION=FAIL: ' + ($identityValues -join '; ')
        }
    }

    return $expectedPrn
}
