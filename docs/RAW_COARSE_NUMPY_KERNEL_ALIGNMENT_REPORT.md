# Raw-coarse NumPy kernel alignment report

日期：2026-08-12  
范围：只做 NumPy v2 kernel 数值语义对齐、固定 G16 microbenchmark 和回归测试。没有运行正式 G16/G25 raw Phase A、G11、MATLAB、SAGE、Stage2/Stage3/Stage4，也没有生成 execution request。

## 最终结论

**KERNEL_ALIGNMENT_PASS：12/12。**

NumPy kernel 已在固定 G16 Stage0 catalog 位置 `[0, 743, 1486, 2228]` 上与 legacy/reference kernel 对齐：

- 12 个 window/profile 摘要记录全部通过。
- 40 个 subblock 比较全部通过。
- score tolerance：`1e-8`。
- peak-ratio tolerance：`1e-8 dB`。
- delay tolerance：`0 sample`。
- Doppler tolerance：`1e-8 Hz`。
- 所有 delay separation、main/secondary peak index、Doppler winner index 和 tie-break 结果一致。
- 最大 subblock score 差：约 `6.56e-13`。
- 最大 peak-ratio 差：约 `6.56e-13 dB`。
- 最大 best-correlation 复数绝对差：约 `1.43e-11`。

这些差异属于 NumPy complex128 与 legacy Python complex 累加顺序的微小浮点差异，远低于规定门槛；没有放宽任何容差。

## Root cause

旧 NumPy v2 kernel 在 `process_window_numpy()` 中按 profile 遍历，将结果追加到以 Doppler half-width 为 key 的 block 列表。B1-D100 与 B2-D100 共享同一个 half-width=100 key，因此同一 10 ms block 的结果被重复交错追加：

```text
B1 block 0 -> half=100 list
B2 block 0 -> half=100 list again
B1 block 1 -> half=100 list
B2 block 1 -> half=100 list again
```

B1 后续按 `(0,1)`、`(2,3)` 合并时，取到的不是连续的四个 10 ms block；这造成了约 1.76–3.37 dB 的 score 差异，并引发部分 delay separation 从 3→2、4→2 的变化。该问题是 block/family 索引语义错误，不是浮点噪声。

## 修复内容

修改文件：

`scripts/sage_pipeline/run_batch_sampling_raw_coarse_v1_2_v2.py`

主要修改：

1. 保持每个 Doppler half-width 的 block 列表只追加一次：每个 `block_index` 先构造 `block_results`，再按 half-width 一次追加。
2. B1 明确使用连续 10 ms block 组 `(0,1)`、`(2,3)` 表示两个独立 20 ms subblock。
3. B2 明确使用 `(0,)`、`(1,)`、`(2,)`、`(3,)` 表示四个独立 10 ms subblock。
4. 每个 10 ms block 的 NAV symbol 保持 legacy 语义：block 0/1 使用 `nav_symbol_1`，block 2/3 使用 `nav_symbol_2`。
5. 每个 block 的 sample index 仍以 window 起点加 `block_index * TEN_MS_SAMPLES` 计算；Doppler 相位保留绝对 block sample 起点，不改为 subblock 内部错误重置。
6. Doppler grid 保持真实冻结配置：

   - D100：`[-100, 0, +100] Hz`，叠加到 `±tracking_doppler_hz`。
   - D200：`[-200, 0, +200] Hz`，叠加到 `±tracking_doppler_hz`。

7. correlation 使用与 legacy 相同的负指数：`exp(-j*2*pi*f*t)`。
8. 增加显式 stable first-winner frequency selection，复制 legacy `max(..., key=abs)` 的相等值 tie-break，不使用可能改变等值选择的 `argpartition`。
9. 保持 secondary peak 排除规则：只允许与 main delay 至少相差 2 个原始 sample 的候选进入 secondary peak。
10. 新版本与新 parameter hash：

   - planner：`batch-sampled-v1.2-b1-b2-c1-prototype-v2-aligned`
   - kernel：`numpy-batched-complex128-v2-aligned`
   - parameter SHA-256：`41d3fdedde8a306f14a7de649807857f8d64e7587008b2cf8c4acd1a9c798ed2`

没有覆盖旧 v2 pre-fix namespace。

## Debug comparison

新增可选模式：

```powershell
& 'D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe' `
  'E:\GNSS_Multipath_Project\scripts\sage_pipeline\run_batch_sampling_raw_coarse_v1_2_v2.py' `
  --project-root 'E:\GNSS_Multipath_Project' `
  --microbenchmark-only `
  --debug-comparison `
  --alignment-root 'E:\GNSS_Multipath_Project\dataset_generation_logs\sampling_validation\batch_sampled_v1_2_kernel_alignment_v2'
```

Debug 输出目录：

`dataset_generation_logs/sampling_validation/batch_sampled_v1_2_kernel_alignment_v2/`

每个固定窗口均保存 old/new：

- NAV-wiped complex sample 摘要和 hash。
- sample index、绝对 sample/time index、10 ms block 起点。
- C/A code replica 摘要和 hash。
- Doppler grid、phasor 起点、每个 selected sample 的 phasor increment。
- 每个 Doppler/delay correlation。
- 每个 delay 的最佳 Doppler index、频率和 correlation。
- main peak、secondary peak、peak index、delay separation、residual proxy、score、peak ratio。
- B1 两个 20 ms subblock 的 block group。
- B2 四个 10 ms subblock 的 block group。

关键 receipt：

- `coarse_parameter.json`
- `coarse_parameter.sha256`
- `microbenchmark.json`
- `microbenchmark_records.csv`
- `run_manifest.json`
- `debug_manifest.json`
- `window_00001_comparison.json`
- `window_00744_comparison.json`
- `window_01487_comparison.json`
- `window_02229_comparison.json`

所有 debug manifest 都记录 `gold_labels_used_for_selection=false`。没有读取 Stage3/Stage4 事件位置。

## Microbenchmark result

候选解释器：

`D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`

NumPy：2.5.1；SciPy：1.18.0；OpenBLAS；Python 3.12.9 AMD64。

| 指标 | 结果 |
|---|---:|
| 固定窗口位置 | 0, 743, 1486, 2228 |
| profile 摘要记录 | 12 |
| subblock 记录 | 40 |
| 数值 mismatch | 0 |
| old kernel wall-clock | 0.1440799 s |
| new NumPy kernel wall-clock | 0.0610203 s |
| old/new speedup | 2.3612× |
| 最大 score 差 | 6.56e-13 |
| 最大 peak-ratio 差 | 6.56e-13 dB |
| 最大 correlation 绝对差 | 1.43e-11 |

这只是固定 deterministic microbenchmark，不代表 G16 全量 raw Phase-A wall-clock，也不等同 Stage1 或完整 pipeline runtime。

## Tests

默认项目 Python：

- `py_compile`：PASS。
- legacy + v2 测试：18 tests，17 PASS，1 个 NumPy 专属 tie-break 测试因当前解释器没有 NumPy 而安全 skip。

候选 compiled venv：

- `py_compile`：PASS。
- legacy + v2 测试：18/18 PASS。
- v2 专项测试：10/10 PASS。

新增/覆盖的回归语义包括：

- B1 20 ms×2 连续 block 组合。
- B2 10 ms×4 block 边界。
- D100/D200 Doppler grid。
- 负指数 Doppler phase。
- delay separation 与 secondary peak exclusion。
- stable first-winner tie-break。
- score/peak ratio 严格容差。
- synthetic zero-IQ 三 profile 输出结构。
- debug manifest 与 gold leakage 防护。

## Formal Phase-A decision

本任务只要求 kernel alignment，不运行正式 G16/G25 raw pass。当前状态：

```text
KERNEL_ALIGNMENT_PASS=true
NUMERIC_MICROBENCHMARK_PASS=true
FORMAL_G16_G25_PHASE_A_EXECUTED=false
G11_ALLOWED=false
```

因此，数值一致性阻塞已解除，但正式 G16→G25 Phase A 仍需单独执行前 QA、new namespace、输入完整性和 performance/scientific gates。不能把本次 12/12 microbenchmark 直接解释为 G16/G25 full-run 通过。

## 唯一下一步

在人工确认后，使用该已对齐的 NumPy kernel 和全新 output namespace，按固定 G16→G25 顺序执行正式 Phase A；仍不得运行 G11，直到 G16 recall/closure、非全窗口 promotion、成本门禁和 G25 control 全部通过。
