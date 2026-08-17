# Raw-coarse v1.3 evidence infrastructure implementation

更新时间：2026-08-12

## 结论

v3 基础设施和离线验证 **PASS**。本轮没有读取 G16 的 2229 个 raw window，没有运行 G25、G11、MATLAB、SAGE、Stage2/Stage3/Stage4，也没有写入任何 `scenes/**/sage_results`。

这里的 PASS 仅表示代码、schema、冻结参数、synthetic fixture 和 Retry1 只读审计通过；它不是 raw-coarse 筛选能力通过，也不是正式 G16 执行批准。

## 新增代码

- `scripts/sage_pipeline/raw_coarse_v3_common.py`：v3 schema、参数、严格 hash、gold 隔离和 `new_only` 安全边界。
- `scripts/sage_pipeline/audit_raw_coarse_retry1_evidence_v3.py`：只读审计 Retry1 aggregate artifact。
- `scripts/sage_pipeline/run_raw_coarse_v3_evidence_capture.py`：future immutable task manifest 驱动的 per-subblock evidence capture；默认拒绝真实 raw，只允许显式 `--allow-real-raw`。
- `scripts/sage_pipeline/build_raw_coarse_v3_features.py`：consensus、secondary delay/Doppler consistency、B1/B2 cross-scale feature builder；不把 temporal persistence/local novelty 加入 v3.0 selector。
- `scripts/sage_pipeline/generate_raw_coarse_v3_manifest.py`：生成冻结参数/schema manifest。
- `scripts/sage_pipeline/test_raw_coarse_v3.py`：v3 单元和回归测试。

现有 `run_batch_sampling_raw_coarse_v1_2_v2.py` 未修改。其 SHA-256 仍为 `959141371075c7f417f945dbe3f915f362a9337bb77582306f2b3ef16919ddfb`；Pipeline V3 也未修改。

## Retry1 审计事实

审计输出位于：

`dataset_generation_logs/sampling_validation/batch_sampled_v1_3_retry1_evidence_audit_r3_20260812/`

三个 profile 均有 2229 个 window，window_id 顺序和跨 profile 对齐通过；每行 `task_id` 均为空。Retry1 保存的是窗口级 aggregate，不含 per-subblock evidence，因此以下字段没有被推测或重建：

- per-subblock sample/time mapping、valid sample count、RMS；
- secondary strength、secondary delay、secondary Doppler；
- deterministic tie-break/search status；
- B1/B2 cross-scale pair alignment。

旧 `promotion_manifest.csv` 使用历史参数 hash `3b4af3a384f1b8090b9776406363f742f36e9654be1db5d1bb66c43c4f716039`，与当前 aligned v2 hash `41d3fdedde8a306f14a7de649807857f8d64e7587008b2cf8c4acd1a9c798ed2` 不同；审计只报告该事实，没有静默修正。B1 的 `component_window_count=55561` 与 2229-window universe 不一致，也只标记为 anomaly。

## v3 evidence schema

每个 `task × window × profile × subblock` 输出一行 `subblock_evidence.csv`。字段覆盖 window/subblock identity、绝对 sample/time 映射、NAV symbol、valid sample count、RMS、main/secondary strength、ratio、delay、Doppler、tracking-relative Doppler、tie-break、search/secondary status、缺失原因和两个 hash。

v2 数值语义保持为只读 authority：10 ms primitive block、B1 `(0,1)/(2,3)`、B2 单块、delay `[-2,-1,0,1,2]`、D100 `[-100,0,+100] Hz`、D200 `[-200,0,+200] Hz`、`complex128`、稳定 first-winner tie-break。

没有合法 secondary 时使用 null/CSV 空值和 `secondary_status=none_admissible_delay`；raw short、invalid RMS、continuity gap 和 inconclusive 不使用 0 代替缺失。

## 冻结 manifest

当前最终冻结版本：

- 文件：`dataset_generation_logs/sampling_validation/batch_sampled_v1_3_parameter_manifest_r6_20260812/v3_parameter_schema_manifest.json`
- manifest SHA-256：`a83677564cbcf896c2bd2613a918b3efda7e7fdeeeb607e944822db356125d36`
- parameter SHA-256：`3f6330f8c88b4901feda2e0cb9bd9e8dcd6350aec6270fd0d3985f5ca2669642`
- `gold_labels_used_for_selection=false`
- source hash、v2 kernel hash、feature schema、secondary admissibility、cross-scale tolerance、component/closure rule 均写入 manifest。

v3 selector 输出的是 `coarse_promoted` / `not_promoted` / `inconclusive` 等 evidence state，不是 confirmed multipath、LOS 或 rejected candidate 标签。

## 离线验证产物

- Retry1 audit：`.../batch_sampled_v1_3_retry1_evidence_audit_r6_20260812/`
- synthetic evidence：`.../batch_sampled_v1_3_evidence_capture_fixture_r6_20260812/`，10 行，代表 1 个 window 的 2 个 B1 和 4+4 个 B2 subblock。
- synthetic feature builder：`.../batch_sampled_v1_3_feature_builder_fixture_r6_20260812/`，1 个 window feature、0 个 promotion component。

使用固定 NumPy 环境 `D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`：

- `py_compile` 通过；
- v3 测试和现有 v2 regression 共 28 项全部通过；
- fixture v3 correlation aggregate 与未修改 v2 `process_window_numpy` 在严格 tolerance 下通过。

## 下一条人工请求（仅模板，不执行）

正式 G16 evidence capture 仍需先生成一个新的 immutable task manifest，记录 metadata 派生的 raw path、Stage0 hash、raw source hash、上述 v3 parameter manifest path/SHA，以及新的 `batch_sampled_v1_3_*` output namespace。raw source hash 本轮没有读取，因而本轮不伪造 request SHA。

生成并人工审核该 request 后，未来命令形态为：

```powershell
D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe `
  E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_raw_coarse_v3_evidence_capture.py `
  --task-manifest <new-immutable-G16-v3-task-manifest.json> `
  --expected-manifest-sha256 <exact-request-sha256> `
  --allow-real-raw
```

该命令不得替代人工 review；在 request、raw/source hash、output namespace 和锁检查完成前不得运行。G16 后必须先做独立 QA；在 QA 通过前不得生成或运行 G25 request。
