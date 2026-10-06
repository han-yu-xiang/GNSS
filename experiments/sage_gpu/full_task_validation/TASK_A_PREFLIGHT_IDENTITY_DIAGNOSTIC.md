# Task A Preflight Identity Diagnostic

**Status:** `READ_ONLY_ROOT_CAUSE_INVESTIGATION_COMPLETE`
**Classification:** `D_RUNNER_PARSE_OR_CAST_BUG`
**Scope:** Task A identity metadata only. No Task A preflight rerun, candidate execution, pipeline execution, or raw-IQ content read occurred.

## TaskSpec values from the current runner

Values were obtained by dot-sourcing the runner only to load its definitions and calling `Get-FullTaskGpuTaskSpec -Task TaskA`; no preflight function was called.

```ini
SceneId=F1023_V70_D0117_P2
Prn=28
TrackingChannel=1
SampleRateHz=10230000
CandidateRequest=(SceneId,Prn,TrackingChannel) from this TaskSpec
CandidateCfg=(SceneId,TargetPrn,TrackingChannel,FsHz) from this TaskSpec
HelperRequestedPrn=28
```

## Formal reference JSON

Reference: `scenes/F1023_V70_D0117_P2/sage_results/rerun_20261003_frozen_v3/G28_ch1/run_context.json`

The runner reads this file with `ConvertFrom-Json -AsHashtable`. The parsed object is `System.Management.Automation.OrderedHashtable`.

| Field | Exists | Raw JSON value | Parsed .NET type | Runner-cast value | Expected | Exact match |
|---|---:|---|---|---|---|---:|
| `sceneId` | YES | `"F1023_V70_D0117_P2"` | `System.String` | `""` via `$FormalContext.SceneId` | `F1023_V70_D0117_P2` | NO |
| `prn` | YES | `28` | `System.Int64` | `0` via `[double]$FormalContext.Prn` | `28` | NO |
| `trackingChannel` | YES | `1` | `System.Int64` | `0` via `[double]$FormalContext.TrackingChannel` | `1` | NO |
| `samplingRateHz` | YES | `10230000.0` | `System.Double` | `0` via `[double]$FormalContext.SamplingRateHz` | `10230000` | NO |

All four JSON keys exist with the expected values. Exact-case dictionary lookup confirms `sceneId` exists while `SceneId` does not; the same lower-camel/PascalCase mismatch is present for the other three fields. Thus these are not absent JSON fields or alternate-schema aliases. The runner's PascalCase property lookups return null, which then casts to an empty string or numeric zero.

Top-level JSON keys:

```text
contextVersion, sceneId, prn, prnLabel, trackingChannel, samplingRateHz,
projectRoot, sceneDir, metadataFile, rawFile, gnssSdrDir, navigationDir,
trajectoryDir, satelliteDir, telemetryFile, trackingFile, nmeaFiles,
rinexNavFiles, satelliteFiles, outputDir, createdAtUtc
```

No top-level `sampleRateHz`, `fsHz`, `sampling_rate_hz`, `channel`, or `targetPrn` key is present. The authoritative fields are present under the names shown above.

## JSON / MAT identity consistency

`run_context.mat` was read in MATLAB using `ProcessStartInfo.ArgumentList` with a metadata-only `load` of `runContext` and `cfg`, printing only the scalar/string fields below. MATLAB exited with code `0`; no pipeline or candidate function was called.

| Identity | Expected | JSON | MAT `runContext` | MAT `cfg` |
|---|---|---|---|---|
| Scene | `F1023_V70_D0117_P2` | `F1023_V70_D0117_P2` | `F1023_V70_D0117_P2` | `sceneId=F1023_V70_D0117_P2` |
| PRN | `28` | `28` | `28` | `targetPrn=28` |
| Tracking channel | `1` | `1` | `1` | `trackingChannel=1` |
| Sample rate (Hz) | `10230000` | `10230000` | `10230000` | `fsHz=10230000` |

`JSON_MAT_IDENTITY_MATCH=YES`

The JSON parser's relevant .NET values were `String`, `Int64`, `Int64`, and `Double`, respectively. The MAT scalar/string values agree with both JSON and TaskSpec.

## Runner-equivalent unique-count reproduction

The four value groups below were assembled from the in-memory TaskSpec, runner-parsed JSON, and TaskSpec-derived candidate config, then passed through the runner's `Select-Object -Unique` expression. The identity assertion itself and all preflight functions were not called.

```ini
SCENE_UNIQUE_COUNT=2
SCENE_VALUES=[F1023_V70_D0117_P2],[],[F1023_V70_D0117_P2]

PRN_UNIQUE_COUNT=2
PRN_VALUES=[28],[0],[28],[28]

CHANNEL_UNIQUE_COUNT=2
CHANNEL_VALUES=[1],[0],[1]

RATE_UNIQUE_COUNT=2
RATE_VALUES=[0],[10230000]
```

Each group therefore trips the generic `scene_prn_channel_or_sample_rate_mismatch` condition when evaluated independently. The first scene group alone is sufficient to fail the runner's short-circuiting `-or` condition.

```ini
MISSING_FIELD_ROOT_CAUSE_CANDIDATE=NO
ROOT_CAUSE_FIELD=FormalContext.SceneId,FormalContext.Prn,FormalContext.TrackingChannel,FormalContext.SamplingRateHz
ROOT_CAUSE_CLASSIFICATION=D_RUNNER_PARSE_OR_CAST_BUG
```

**Explanation:** `Read-CandidateJsonFile` returns a case-sensitive `OrderedHashtable` from the lower-camel-case JSON keys. `Assert-FullTaskGpuTaskIdentity` accesses the formal context using PascalCase member names. Those lookups miss; explicit casts turn the missing values into `""`/`0`, causing a fail-closed identity mismatch even though the formal JSON and MAT describe the expected task. No compatibility alias or remediation was applied in this investigation.

## Directory and Stage2 sanity

```ini
REFERENCE_DIRECTORY_SCENE=F1023_V70_D0117_P2
REFERENCE_DIRECTORY_PRN_LABEL=G28
REFERENCE_DIRECTORY_CHANNEL=1
REFERENCE_SANITY_SELECTED_WINDOWS=54
REFERENCE_SANITY_SELECTED_PATHS=77
```

The formal directory is `scenes/F1023_V70_D0117_P2/sage_results/rerun_20261003_frozen_v3/G28_ch1`. The two existing Stage2 CSVs contain 54 selected-window rows and 77 selected-path rows, respectively. These counts are secondary sanity evidence, not the basis of the root-cause classification.

## Scope and execution state

```ini
TASK_A_PREFLIGHT_RERUN=NO
TASK_A_EXECUTED=NO
RAW_IQ_READ=NO
MATLAB_METADATA_READ=YES
MATLAB_PIPELINE_EXECUTED=NO
RUNNER_MODIFIED=NO
CANDIDATE_MODIFIED=NO
FORMAL_REFERENCE_MODIFIED=NO
```
