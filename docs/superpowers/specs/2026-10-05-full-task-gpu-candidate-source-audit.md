# Frozen SAGE Full-Task GPU Candidate：源码边界审计

**审计类型：DESIGN SOURCE AUDIT ONLY — NOT IMPLEMENTATION**  
**审计日期：2026-10-06**  
**审阅对象：** docs/superpowers/specs/2026-10-05-full-task-gpu-candidate-design.md

## 权威源与审计边界

权威 Frozen 源仅使用本机 `E:/GNSS_Multipath_Project/scripts/sage_pipeline/run_nav_sage_pipeline.m`。

~~~text
AUTHORITATIVE_SOURCE_SHA256=bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c
DESIGN_SPEC_MODIFIED=NO
FROZEN_SOURCE_MODIFIED=NO
CANDIDATE_IMPLEMENTED=NO
IMPLEMENTATION_PLAN_CREATED=NO
MATLAB_EXECUTED=NO
GPU_EXECUTED=NO
RAW_IQ_READ=NO
BUSINESS_BRANCH_COMMIT_PUSH=NO
~~~

review branch 中旧 Frozen 文件的 `9a263f…` 版本未用于本审计，也未替换或改写。附带摘录不是完整 Frozen 源文件副本。本轮只读了两个已完成任务的 run-context JSON、Stage CSV 表头及指定 MAT 变量名/字段清单；没有打开 raw IQ、CIR/HDF5、MATLAB 或 GPU。当前业务工作树既存修改均未触碰。

函数体 SHA 的复核算法：取表中函数声明行至该函数最后一个 `end` 行，按 UTF-8 文本、CRLF/CR 统一为 LF 后计算 SHA-256，不追加终止换行。excerpt SHA 对其列明源码起止行用相同规则计算。

## Frozen 函数索引

| 函数 | 源码签名（续行以 `<br>` 表示） | 行范围 | 函数体 SHA-256 |
|---|---|---:|---|
| `run_sage_stage1_stage4_local` | function result = run_sage_stage1_stage4_local(windowCatalog, symbolCatalog, rawFile, outputDir, cfg) | 811–942 | `f08745e309cad19f800c5c88e3da58442bee2f011328ab12c954b23a01661e0a` |
| `runStage2` | function fits = runStage2(candidateIndices, windows, ...<br>    stage1, rawFile, dopplerSign, outputDir, cfg) | 1164–1208 | `96dc162a17cf87dde5300ccd902a8a08fa6c0c10643c0d7b446a214ff1eb8f8e` |
| `fitAllOrders` | function fit = fitAllOrders( ...<br>    row, scanRow, rawFile, dopplerSign, cfg) | 1211–1278 | `0a04e11ab2833fba843226d466f0cc5d36079557a50490e3371cba1ffb1cabc1` |
| `initializeResidualPath` | function newPath = initializeResidualPath( ...<br>    residual, existing, context, dopplerBound, cfg) | 1281–1311 | `f44cd27a2f6ec92b4fc2817e4625bf736e5cb10d883e8e0a362d737777b9c2e3` |
| `runSage` | function [paths, history] = runSage(paths, observed, context, ...<br>    referenceDoppler, dopplerBound, cfg) | 1314–1351 | `674801d9bb7d5d2a6de338cf1a8b7c45636646fa20fe8081edcc069dfa93a51a` |
| `evaluateModel` | function model = evaluateModel(paths, observed, context, ...<br>    referenceDoppler, dopplerBound, cfg) | 1354–1398 | `7a3e1fcb4d80ffd9deabfd617b41c874ede0e5258149c72b377377db2ebb9b40` |
| `flattenStage2` | function [modelTable, selectedTable, pathTable] = ...<br>    flattenStage2(fits, cfg) | 1415–1497 | `22c15b598ff84df379710b2ec9ce4d054855fb5a2fc4786c4b7d734da4b16d2c` |
| `evaluatePersistence` | function [persistence, reliable] = evaluatePersistence( ...<br>    fits, windows, cfg) | 1500–1585 | `221746eb016bdc94aacd9d95a5a89b4315c266a9418fd897f9962b3934940152` |
| `runJointStage` | function [jointFits, summaryTable, pathTable] = ...<br>    runJointStage(reliable, fits, symbols, windows, ...<br>    rawFile, dopplerSign, cfg) | 1588–1706 | `cc0ab1a13007aeceb805bde92f74b806de5136ed45a5e9f645544fc40707a52f` |

长摘录文件只包含 bffc 源文件连续行，未插入行号或说明文字：

| 文件 | SOURCE_FILE_SHA256 | SOURCE_LINE_START | SOURCE_LINE_END | EXCERPT_SHA256 |
|---|---|---:|---:|---|
| `reports/project_stage_review_20261005/source_audit/frozen_stage2_controller_excerpt.txt` | `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c` | 1164 | 1400 | `6afa385cf05188c8d2e44229f1e41aa2f7206c97f289b540022e4de85ed69aef` |
| `reports/project_stage_review_20261005/source_audit/frozen_stage2_downstream_excerpt.txt` | `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c` | 1415 | 1706 | `c608292da70db156fb656dda3620fe3eb83b36f9f0b2b8d5e1f51ef69813c995` |

## Stage 调度、保存与身份元数据

Stage0 保存段，权威源码 66–94，EXCERPT_SHA256=`4e61b809de6100b7c5afcbba2f204464bd86eb0ecbe8b3bb2c8b3456e9ed6188`：

~~~matlab
stage0Mat = fullfile(outputDir, "stage0_nav_catalog.mat");
stage0SymbolsCsv = fullfile(outputDir, ...
    "stage0_valid_symbols.csv");
stage0WindowsCsv = fullfile(outputDir, ...
    "stage0_valid_40ms_windows.csv");
overviewFile = fullfile(outputDir, ...
    prnLabel + "_nav_sage_overview.png");

%% Stage 0
if cfg.resumeExistingStages ...
        && checkpointConfigurationMatches(stage0Mat, cfg)
    loaded = load(stage0Mat, ...
        "symbolCatalog", "windowCatalog");
    symbolCatalog = loaded.symbolCatalog;
    windowCatalog = loaded.windowCatalog;
    fprintf("Stage 0 loaded: %d symbols, %d windows\n", ...
        height(symbolCatalog), height(windowCatalog));
else
    fprintf("Stage 0: building navigation-symbol catalog...\n");
    symbolCatalog = buildSymbolCatalog( ...
        telemetry, tracking, cfg);
    windowCatalog = buildFortyMsCatalog( ...
        symbolCatalog, nmeaUtcSod, nmeaSpeedKmh, cfg);
    assert(~isempty(windowCatalog), ...
        "No complete %s 40 ms windows were found.", prnLabel);
    writetable(symbolCatalog, stage0SymbolsCsv);
    writetable(windowCatalog, stage0WindowsCsv);
    save(stage0Mat, "symbolCatalog", ...
        "windowCatalog", "cfg");
~~~

输出路由，权威源码 255–284，EXCERPT_SHA256=`8052c77e66c7bfe0309a7ba45929921e0302ca22d76ced28a621efc8c8f5c599`：

~~~matlab
outputDir = fullfile(sceneDir, "sage_results", ...
    "nav_sage_v2", prnLabel);
if ~isfolder(outputDir)
    mkdir(outputDir);
end

context = struct();
context.contextVersion = 1;
context.sceneId = sceneId;
context.prn = prnNumber;
context.prnLabel = prnLabel;
context.trackingChannel = channel;
context.samplingRateHz = samplingRateHz;
context.projectRoot = projectRoot;
context.sceneDir = string(sceneDir);
context.metadataFile = string(metadataFile);
context.rawFile = rawFile;
context.gnssSdrDir = string(gnssSdrDir);
context.navigationDir = string(navigationDir);
context.trajectoryDir = string(trajectoryDir);
context.satelliteDir = string(satelliteDir);
context.telemetryFile = string(telemetryFile);
context.trackingFile = string(trackingFile);
context.nmeaFiles = absoluteFileNames(nmeaFiles);
context.rinexNavFiles = absoluteFileNames(navFiles);
context.satelliteFiles = absoluteFileNames(satelliteFiles);
context.outputDir = string(outputDir);
context.createdAtUtc = string(datetime("now", ...
    "TimeZone", "UTC", "Format", "yyyy-MM-dd'T'HH:mm:ssXXX"));
end
~~~

run-context 保存，权威源码 295–312，EXCERPT_SHA256=`c56ad627fc87b817d643e4b874b38eebb1052f1de6cada914fad7b365a346726`：

~~~matlab
function saveRunContext(context, cfg)
contextMat = fullfile(context.outputDir, "run_context.mat");
contextJson = fullfile(context.outputDir, "run_context.json");
if isfile(contextMat)
    loaded = load(contextMat, "runContext");
    assert(isfield(loaded, "runContext") ...
        && runContextsMatch(loaded.runContext, context), ...
        ['Existing output belongs to a different scene/PRN/channel. ', ...
        'Refusing to reuse: %s'], context.outputDir);
    return;
end
runContext = context; %#ok<NASGU>
save(contextMat, "runContext", "cfg");
fileId = fopen(contextJson, "wt", "n", "UTF-8");
assert(fileId >= 0, "Cannot write run context: %s", contextJson);
cleanup = onCleanup(@() fclose(fileId));
fwrite(fileId, jsonencode(context), "char");
end
~~~

Stage2/3/4 调度、Stage2 CSV 写出及 MAT 保存，权威源码 875–919，EXCERPT_SHA256=`4fc6e11b7a00b4e56a44d9e7fc33750cf27064327ef49f438ccc24a8d43dc26f`：

~~~matlab
candidateIndices = chooseStage2Candidates(stage1Table, windowCatalog, cfg);
fprintf("Stage 1 selected %d windows including neighbors.\n", numel(candidateIndices));

if cfg.resumeExistingStages && checkpointConfigurationMatches(stage2Mat, cfg)
    loaded = load(stage2Mat, "stage2Fits", "modelTable", "selectedTable", "pathTable");
    stage2Fits = loaded.stage2Fits;
    modelTable = loaded.modelTable;
    selectedTable = loaded.selectedTable;
    pathTable = loaded.pathTable;
    fprintf("Stage 2 loaded: %d fitted windows\n", numel(stage2Fits));
else
    fprintf("\nStage 2: NAV-wiped fractional SAGE L=1..4...\n");
    stage2Fits = runStage2(candidateIndices, windowCatalog, stage1Table, rawFile, dopplerSignUsed, outputDir, cfg);
    [modelTable, selectedTable, pathTable] = flattenStage2(stage2Fits, cfg);
    writetable(modelTable, stage2ModelsCsv);
    writetable(selectedTable, stage2SelectedCsv);
    writetable(pathTable, stage2PathsCsv);
    save(stage2Mat, "stage2Fits", "modelTable", "selectedTable", "pathTable", "cfg");
end

if cfg.resumeExistingStages && checkpointConfigurationMatches(stage3Mat, cfg)
    loaded = load(stage3Mat, "persistenceTable", "reliableTable");
    persistenceTable = loaded.persistenceTable;
    reliableTable = loaded.reliableTable;
    fprintf("Stage 3 loaded: %d reliable centers\n", height(reliableTable));
else
    fprintf("\nStage 3: adjacent-window persistence...\n");
    [persistenceTable, reliableTable] = evaluatePersistence(stage2Fits, windowCatalog, cfg);
    writetable(persistenceTable, stage3Csv);
    writetable(reliableTable, stage3ReliableCsv);
    save(stage3Mat, "persistenceTable", "reliableTable", "cfg");
end

if cfg.resumeExistingStages && checkpointConfigurationMatches(stage4Mat, cfg)
    loaded = load(stage4Mat, "jointFits", "jointSummaryTable", "jointPathTable");
    jointFits = loaded.jointFits;
    jointSummaryTable = loaded.jointSummaryTable;
    jointPathTable = loaded.jointPathTable;
    fprintf("Stage 4 loaded: %d joint estimates\n", height(jointSummaryTable));
else
    fprintf("\nStage 4: NAV-wiped joint 100 ms estimation...\n");
    [jointFits, jointSummaryTable, jointPathTable] = runJointStage(reliableTable, stage2Fits, symbolCatalog, windowCatalog, rawFile, dopplerSignUsed, cfg);
    writetable(jointSummaryTable, stage4SummaryCsv);
    writetable(jointPathTable, stage4PathsCsv);
    save(stage4Mat, "jointFits", "jointSummaryTable", "jointPathTable", "cfg");
~~~

证据结论：Stage2 先返回 fits，再 flatten、写出三个 CSV 和最终 MAT；Stage3 直接使用内存中的 stage2Fits；Stage4 同样接收内存 fits 与 Stage3 reliableTable，不从 Stage2 CSV 重建运算状态。

实际两个已完成任务的 MAT 变量名与 Frozen 保存调用相符：

| MAT | 保存变量 |
|---|---|
| `stage0_nav_catalog.mat` | `symbolCatalog, windowCatalog, cfg` |
| `stage1_nav_fast_scan.mat` | `stage1Table, dopplerSignUsed, cfg` |
| `stage1_nav_progress.mat` | `records, completed, cfg` |
| `stage2_nav_progress.mat` | `fits, completed, candidateIndices, cfg` |
| `stage2_nav_sage_L1_L4.mat` | `stage2Fits, modelTable, selectedTable, pathTable, cfg` |
| `stage3_nav_persistence.mat` | `persistenceTable, reliableTable, cfg` |
| `stage4_nav_joint_100ms.mat` | `jointFits, jointSummaryTable, jointPathTable, cfg` |
| `run_context.mat` | `runContext, cfg` |

Stage2 progress checkpoint 保存整个 fits cell collection，不是只保存刚完成窗口的 fit；恢复分支读取 fits、completed、candidateIndices。

## runStage2 → fitAllOrders 边界

~~~text
RUNSTAGE2_CALLS_FITALLORDERS_DIRECTLY=YES
RUNSTAGE2_RETURN_TYPE=column cell array, one entry per candidate window
FITALLORDERS_SIGNATURE=(row, scanRow, rawFile, dopplerSign, cfg)
FITALLORDERS_SUCCESS_RETURN=scalar MATLAB struct
FITALLORDERS_FAILURE_RETURN=catch-created scalar struct, selectedOrder=NaN
RUNSTAGE2_PASSES_EXTRA_WORKSPACE_STATE=NO
RUNSTAGE2_SAVES_AFTER_EVERY_WINDOW=NO
RUNSTAGE2_CHECKPOINTS_WHOLE_FITS_COLLECTION=YES
RUNSTAGE2_BYTE_IDENTICAL_FEASIBLE=YES
~~~

runStage2 1182–1205 的实际直接调用：

~~~matlab
fits{position} = fitAllOrders( ...
    windows(index, :), stage1(index, :), ...
    rawFile, dopplerSign, cfg);
~~~

fitAllOrders 成功返回字段：windowId, catalogIndex, recordingTimeS, towS, models, selectedOrder, errorMessage。models 是按 L=1..4 排列的 cell。异常路径由 runStage2 catch 构造失败 struct，selectedOrder=NaN。

runStage2 显式接收 candidateIndices、windows、stage1、rawFile、dopplerSign、outputDir、cfg；没有隐式 CPU-only workspace 变量，也不传递其它 GPU execution context。它将 fit 返回值放入 fits{position}，每到 cfg.stage2CheckpointInterval（Frozen 默认值为 2）或最后一个候选保存整个 fits collection；没有每窗口即刻保存 fit 的单项文件写入。CPU cell/table/checkpoint 控制不约束窗口拟合必须由 CPU 算法执行。

## GPU device 与 gather 边界

当前 qualified probe `experiments/sage_gpu/stage2_window_173_gpu_probe.m` SHA-256=`bfe56ad02c99240257fddd212ba43ee5606a81740b3dda716c5947c433cbfa88`；共享 separated-candidate helper SHA-256=`a40c6459e66a384e85053589b270c5d2e112363872153fbf46da5c56fd4bb1f5`。

- probe entry 在约第 26 行调用一次 gpuDevice；不是 fitAllOrdersGpu 对每阶或每个 path 调用。
- fitAllOrdersGpu(row, scanRow, observed, context, dopplerSign, cfg) 不接收 GPU device/context 参数，使用 MATLAB 当前选中设备。
- fitAllOrdersGpu 构造含 GPU path alpha/score 的 fit；当前 probe wrapper 在 GPU helper 返回后才调用 gatherGpuFit。只移植 GPU helper 本体不能满足 Frozen fit/checkpoint contract。
- helper 已在产生处 gather delay/Doppler 选择值、score/grid maxima、RSS/coherence 与 relativePowerDb；residual initializer 会 gather metric matrix 后调用共享分离候选 selector。gatherGpuFit 再遍历 L1–L4 的 paths，将 alpha 与 score gather 回 CPU。

~~~text
RECOMMENDED_GPU_DEVICE_LIFECYCLE=ONE_INITIALIZATION_PER_TASK_AT_CANDIDATE_ENTRY
REQUIRES_RUNSTAGE2_CHANGE=NO
REQUIRES_FITALLORDERS_SIGNATURE_CHANGE=NO
RECOMMENDED_GATHER_BOUNDARY=INSIDE_CANDIDATE_fitAllOrders_BEFORE_RETURN_TO_runStage2
~~~

candidate entry 在身份/source/output-collision preflight 通过后、Stage0 开始前为该 task 初始化当前 GPU 一次；每窗口 helper 不重复初始化。candidate fitAllOrders 保留 Frozen 签名，在返回前使 fit 完全为 CPU double/complex-double。gather 必须早于 runStage2 的 fits{position}=... 以及整个 fits checkpoint，否则 gpuArray 仍会进入 checkpoint，即使 flatten/Stage3/Stage4 前再 gather 也太晚。

结论：RUNSTAGE2_BYTE_IDENTICAL_FEASIBLE=YES。candidate 只需使用同签名 fitAllOrders body 并返回 Frozen-compatible CPU-resident fit；无需给 runStage2 或 fitAllOrders signature 添加 GPU execution-context 参数。

## Stage2 fit struct 的真实 contract 与下游消费

成功 fit 字段：windowId, catalogIndex, recordingTimeS, towS, models, selectedOrder, errorMessage。

model 字段：order, paths, rss, bic, valid, relativePowerDb, minimumSeparationSamples, minimumMultipathPowerDb, maximumRelativeDopplerHz, maximumCoherence, rssHistory；invalidModel 另含 errorMessage。

path 字段：delaySamples, dopplerHz, alpha, score。

| 对象/字段 | producer | flattenStage2 | Stage3 | Stage4 |
|---|---|---|---|---|
| fit.windowId | fitAllOrders | YES | YES：中心与邻居查找 | YES：按中心 ID 查 fit |
| fit.catalogIndex | fitAllOrders | NO | NO | NO |
| fit.recordingTimeS | fitAllOrders | YES | YES | NO：时间从 windows 读取 |
| fit.towS | fitAllOrders | YES | NO | NO |
| fit.selectedOrder | fitAllOrders | YES | YES：选择模型 | YES：summary 的 stage2_L |
| fit.models{1..4} | fitAllOrders | YES：逐 L | YES：只读 selected L | YES：遍历所有 L |
| fit.errorMessage | fitAllOrders/catch | NO | NO | NO |
| model.order | evaluateModel | NO：用循环序号写 model_order | NO | NO：用 cell 序号作为阶数 |
| model.valid | evaluateModel/invalidModel | YES | NO | YES：joint seed gate |
| model.rss, bic | evaluateModel | YES | NO | NO：Stage4 使用 joint 模型自己的量 |
| model.relativePowerDb | evaluateModel | YES | YES：持久性比较 | NO |
| model 的 separation/power/Doppler/coherence diagnostics | evaluateModel | YES | NO | NO |
| model.rssHistory/errorMessage | fitAllOrders/invalidModel | NO | NO | NO |
| path.delaySamples, dopplerHz | makePath/fit | YES | YES：相对 direct path 匹配 | YES：joint seed |
| path.alpha | solveAmplitudes | NO：Stage2 CSV 不导出 | NO | NO：Stage4 每 snapshot 重算 alpha |
| path.score | makePath/fit | NO | NO | NO |

Stage4 使用 Stage2 所有 L1–L4 model.valid 与 model.paths；joint seed 坐标是 delaySamples/DopplerHz。Stage4 每个 snapshot 调用 solveSnapshotAlpha 重新估计 alpha，因此不依赖 Stage2 path.alpha 或 score。Stage3 无持久 path UUID；其匹配基于相对 direct-path 的 excess delay、relative Doppler、relative power，multipath_id 是当前 delay-sorted path ordinal。

~~~text
STAGE3_READS_STAGE2_CSV=NO
STAGE3_READS_IN_MEMORY_FITS=YES
STAGE4_READS_IN_MEMORY_FITS=YES
STAGE4_READS_STAGE3_RELIABLE=YES
STAGE4_STAGE2_MODEL_SCOPE=ALL_L1_L4
~~~

## Stage2 MAT 保存变量与 CSV schema

~~~text
STAGE2_PROGRESS_SAVED_VARIABLES=fits,completed,candidateIndices,cfg
STAGE2_PROGRESS_RESTORED_VARIABLES=fits,completed,candidateIndices
STAGE2_FINAL_MAT_SAVED_VARIABLES=stage2Fits,modelTable,selectedTable,pathTable,cfg
STAGE2_MODEL_ORDERS_SCHEMA_MATCH=YES
STAGE2_SELECTED_WINDOWS_SCHEMA_MATCH=YES
STAGE2_SELECTED_PATHS_SCHEMA_MATCH=YES
STAGE2_SCHEMA_SPEC_MATCH=YES_ALL_THREE
~~~

Frozen 源码 emptyModelRecord/emptySelectedRecord/emptyPathRecord（lines 2187–2223）与 design spec 列序完全一致：

- model orders：window_id, recording_time_s, model_order, multipath_count, rss, bic, bic_gain_from_previous, rss_gain_percent_from_previous, model_valid, selected, minimum_multipath_power_db, minimum_separation_samples, maximum_relative_doppler_hz, maximum_coherence；
- selected windows：window_id, recording_time_s, tow_s, selected_L, multipath_count, selected_bic, selected_rss, minimum_multipath_power_db, maximum_relative_doppler_hz, maximum_coherence；
- selected paths：window_id, recording_time_s, selected_L, path_id, is_multipath, delay_samples, excess_delay_samples, excess_delay_chips, excess_path_length_m, doppler_hz, doppler_offset_hz, relative_power_db。

## Stage0 / Stage1 EXACT：科学输出与运行元数据分离

实际三个 CSV header 不含 output path、namespace 或 run timestamp。Stage0 symbols：

`symbol_id, telemetry_row, prn, tow_s, sample_start_zero_based, recording_time_s, nav_symbol, tracking_index, tracking_doppler_hz, code_frequency_hz, cn0_db_hz, carrier_lock_test, tracking_tow_ms, next_step_samples, next_tow_step_s, continuous_to_next`

Stage0 40-ms windows：

`window_id, symbol_index, sample_start_zero_based, recording_time_s, tow_s, nav_symbol_1, nav_symbol_2, split_samples, tracking_doppler_hz, code_frequency_hz, cn0_db_hz, vehicle_speed_kmh, speed_source, relative_doppler_bound_hz`

Stage1 fast scan：

`window_id, recording_time_s, tow_s, cn0_db_hz, nav_symbol_1, nav_symbol_2, scan_valid, main_delay_samples, main_doppler_hz, main_score, residual_peak1_delay_samples, residual_peak1_doppler_hz, residual_peak1_power_db, residual_peak2_delay_samples, residual_peak2_doppler_hz, residual_peak2_power_db, residual_peak3_delay_samples, residual_peak3_doppler_hz, residual_peak3_power_db, has_one_strong_residual, has_two_strong_residuals, screen_score_db, error_message`

Stage0 semantic MAT variables为 symbolCatalog/windowCatalog/cfg；Stage1 为 stage1Table/dopplerSignUsed/cfg。run_context.mat/json 另含 runContext.outputDir、createdAtUtc 和路径/provenance；cfg 没有 output location。现有 formal 输出已 relocation，因此 runContext.outputDir 仍指执行时旧 nav_sage_v2/<PRN>，与当前 rerun artifact 目录不同。Candidate outputDir/namespace 和 timestamp 也必然不同。Overview 是诊断图，不应用路径或字节比较作为 science gate。

~~~text
CSV_EXACT=YES
STAGE0_STAGE1_EXACT_POLICY_NEEDS_REFINEMENT=YES
EXPECTED_NONSCIENTIFIC_DIFFERENCES=runContext.outputDir/namespace, createdAtUtc, candidate output path, relocation/receipt metadata, overview path/bytes
~~~

原 design spec 已把 run-context/overview 单列为运行 metadata/diagnostics，但 Stage0/1 exact 条款仍应明确限定到科学 CSV 与 semantic MAT variables；输入 provenance 要验证同一输入对象，必要时规范化路径分隔符，不应把运行输出目录当作科学字段。

## 设计稿源证据后的修正清单

~~~text
DESIGN_SPEC_CORRECTIONS_REQUIRED=BLOCKING_AND_NON_BLOCKING
~~~

**BLOCKING（implementation plan 前补明确）：**

1. 固定 GPU device lifecycle：candidate entry 每 task 初始化一次；不要在 fitAllOrders/per-window helper 重复初始化。
2. 明确 gather 在 candidate fitAllOrders 返回前完成，早于 runStage2 写入 fits 与 progress checkpoint。原 spec 已要求 flatten/Stage3/Stage4 前 gather，但没有明确 checkpoint 前边界。

**NON_BLOCKING（validator 实施前澄清）：**

1. Stage0/Stage1 EXACT 明确为 science CSV 逐单元格一致、MAT semantic variables 一致；排除 run-context 路径、时间戳、overview 文件路径/字节。

其余源证据未发现 runStage2 必须改动或 fitAllOrders signature 必须扩展的理由；Stage2 CSV schema 与 MAT 变量名均匹配。

## 小型权威源摘录（内嵌）

### Stage2 path constructor：lines 2081–2087；EXCERPT_SHA256=`9d0b7187a87840537c4a1409a10ac6ae758e03540a6f4845418450f6f376049b`

~~~matlab
function path = makePath(delaySamples, dopplerHz)
path = struct( ...
    "delaySamples", double(delaySamples), ...
    "dopplerHz", double(dopplerHz), ...
    "alpha", complex(0), ...
    "score", 0);
end
~~~

### Stage2 record/schema constructors：lines 2187–2223；EXCERPT_SHA256=`fc2c2db3afc3bd421158b08ce6f7a47c3369d14deecef53845f8276cfe31939f`

~~~matlab
function record = emptyModelRecord()
record = struct( ...
    "window_id", nan, "recording_time_s", nan, ...
    "model_order", nan, "multipath_count", nan, ...
    "rss", nan, "bic", nan, ...
    "bic_gain_from_previous", nan, ...
    "rss_gain_percent_from_previous", nan, ...
    "model_valid", false, "selected", false, ...
    "minimum_multipath_power_db", nan, ...
    "minimum_separation_samples", nan, ...
    "maximum_relative_doppler_hz", nan, ...
    "maximum_coherence", nan);
end


function record = emptySelectedRecord()
record = struct( ...
    "window_id", nan, "recording_time_s", nan, ...
    "tow_s", nan, "selected_L", nan, ...
    "multipath_count", nan, "selected_bic", nan, ...
    "selected_rss", nan, ...
    "minimum_multipath_power_db", nan, ...
    "maximum_relative_doppler_hz", nan, ...
    "maximum_coherence", nan);
end


function record = emptyPathRecord()
record = struct( ...
    "window_id", nan, "recording_time_s", nan, ...
    "selected_L", nan, "path_id", nan, ...
    "is_multipath", false, "delay_samples", nan, ...
    "excess_delay_samples", nan, ...
    "excess_delay_chips", nan, ...
    "excess_path_length_m", nan, ...
    "doppler_hz", nan, "doppler_offset_hz", nan, ...
    "relative_power_db", nan);
~~~

## Completion

~~~text
SOURCE_AUDIT_CREATED=YES
SOURCE_AUDIT_ONLY=YES
DESIGN_SPEC_MODIFIED=NO
CANDIDATE_IMPLEMENTED=NO
IMPLEMENTATION_PLAN_CREATED=NO
MATLAB_EXECUTED=NO
GPU_EXECUTED=NO
RAW_IQ_READ=NO
OTHER_SAGE_TASKS_STARTED=NO
REMAINING_BATCH_RESUMED=NO
BUSINESS_BRANCH_COMMIT_PUSH=NO
NEXT_STEP=GPT_REVIEW_SOURCE_AUDIT
~~~