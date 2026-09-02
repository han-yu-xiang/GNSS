# Darkroom Generator v2.2 Reference Handoff

> 本文是暗室参数生成支线的资产与结果参考文档，不是新的工程状态源。工程执行状态唯一以 [`GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`](./GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md) 为准；论文状态唯一以 [`GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`](./GNSS_SAGE_PAPER_HANDOFF_CURRENT.md) 为准。
>
> 本文根据项目当前实际文件整理，最后核对日期为 2026-08-27。本文不改变任何 SAGE、MATLAB、raw IQ 或既有实验 artifact。

## 1. 支线目标与范围

本支线提供一个独立的 Python-only 暗室参数生成器，用于按环境类别和接收质量状态生成固定格式的多仰角、四结构槽位参数表。它不是 GNSS raw IQ 处理器，也不是 MATLAB/SAGE 结果生成器。

当前固定矩阵为四类环境 × 两种质量状态：

| 环境类别 | 质量状态 | 含义 |
|---|---|---|
| Urban | `GOOD_TRACKED_BASELINE` / `POOR_CONDITIONAL` | 城市场景的跟踪良好基线与条件性质量退化 |
| Special Reflective | `GOOD_TRACKED_BASELINE` / `POOR_CONDITIONAL` | 特殊反射场景的跟踪良好基线与条件性质量退化 |
| Mountain/Valley | `GOOD_TRACKED_BASELINE` / `POOR_CONDITIONAL` | 山地/谷地场景的跟踪良好基线与条件性质量退化 |
| Highway/Open | `GOOD_TRACKED_BASELINE` / `POOR_CONDITIONAL` | 高速/开阔场景的跟踪良好基线与条件性质量退化 |

每个环境同时生成 `LOW`、`MID`、`HIGH` 三个仰角上下文，并以 `Low`、`Mid`、`High` 写入 `SatelliteID`。每个仰角上下文固定四个结构槽位：主径槽位 `0` 和 NLOS 槽位 `1/2/3`。因此一个环境/质量组合在每个毫秒输出 12 行，四环境 × 两状态共 8 张表。

这里的“固定四条路径”是输出结构合同，不是从实测数据推断每一时刻必然存在四条物理传播路径。v2.2 的条件性场景合同要求 NLOS 1/2/3 均激活且 `RelativeAmplitude` 严格为正；这不是经验多径发生率或实际失锁率的估计。

## 2. 当前状态总览

| 项目 | 当前状态 | 证据与边界 |
|---|---|---|
| v2.2 generator/core | Implemented | 独立配置、quality profile、core、request/runner/auditor 已存在；未改变生产 SAGE pipeline |
| 20 秒四环境配对 pilot | Completed + Validated | 8/8 run QA PASS、4/4 Good/Poor pair QA PASS、matrix QA PASS |
| 20 ms 八单元 smoke | Failed/Diagnostic | Urban Good 完成后 Urban Poor 因质量事件无法完整容纳而 fail-close；全部失败/部分 artifact 保留 |
| 5 分钟八单元生成 | Completed | 当前 `0828darkroomPar` receipt 为 `status=completed`、8/8、8 张表已导出 |
| 5 分钟独立矩阵 QA | Not separately recorded | 5 分钟 batch receipt 和 table-export receipt 证明生成/导出完成，但不能直接替代 20 秒的独立矩阵 QA |
| 暗室实际回放 | Not started | 尚无回放执行证据 |
| 完整统计信道模型 | Not started | 尚未完成拟合分布、发生率、时间相关性或物理功率标定 |
| 20.46 MHz 适配 | Not started/Blocked by scope | 当前支线仅允许 10.23 MHz 相关主线；v2.2 generator 配置为 10.23 MHz |

## 3. 八个目标组合与 5 分钟结果

5 分钟集合 ID 为 `0828darkroomPar`，matrix manifest SHA-256 为：

`61ff9777087b2c82f297b649adea2ae5406b658f53cb4fa56342aca9373fcbe9`

集合执行 receipt 为 `dataset_generation_logs/channel_modeling/0828darkroomPar/batch_execution_receipt.json`，记录 `completed_count=8`、`request_count=8`、`duration_ms=300000`、`status=completed`，并明确 `raw_iq_read=false`、`matlab=false`、`sage=false`。执行时间为 `2026-08-27T07:00:26.687705Z` 至 `2026-08-27T07:59:12.479781Z`，集合 wall-clock 约 3526 s（58.77 min）。

| 环境 | 质量模式 | request id | 单表行数 | 单项 elapsed (s) | 集合导出表 |
|---|---|---|---:|---:|---|
| Urban | `GOOD_TRACKED_BASELINE` | `urban_good_5min_v2_2_0828darkroomPar_20260827` | 3,600,000 | 100.912 | `tables/urban__good.csv` |
| Urban | `POOR_CONDITIONAL` | `urban_poor_5min_v2_2_0828darkroomPar_20260827` | 3,600,000 | 100.173 | `tables/urban__poor.csv` |
| Special Reflective | `GOOD_TRACKED_BASELINE` | `special_reflective_good_5min_v2_2_0828darkroomPar_20260827` | 3,600,000 | 388.586 | `tables/special_reflective__good.csv` |
| Special Reflective | `POOR_CONDITIONAL` | `special_reflective_poor_5min_v2_2_0828darkroomPar_20260827` | 3,600,000 | 609.178 | `tables/special_reflective__poor.csv` |
| Mountain/Valley | `GOOD_TRACKED_BASELINE` | `mountain_valley_good_5min_v2_2_0828darkroomPar_20260827` | 3,600,000 | 581.621 | `tables/mountain_valley__good.csv` |
| Mountain/Valley | `POOR_CONDITIONAL` | `mountain_valley_poor_5min_v2_2_0828darkroomPar_20260827` | 3,600,000 | 580.428 | `tables/mountain_valley__poor.csv` |
| Highway/Open | `GOOD_TRACKED_BASELINE` | `highway_open_good_5min_v2_2_0828darkroomPar_20260827` | 3,600,000 | 581.163 | `tables/highway_open__good.csv` |
| Highway/Open | `POOR_CONDITIONAL` | `highway_open_poor_5min_v2_2_0828darkroomPar_20260827` | 3,600,000 | 564.712 | `tables/highway_open__poor.csv` |

八个 request 均在 `request_matrix.csv` 中记录为 accepted、`new_only=true`、`resume_allowed=false`，并在冻结时记录目标 run namespace 不存在。5 分钟 request SHA-256 如下：

| 环境/质量 | request SHA-256 |
|---|---|
| Urban / Good | `8a45351f99edeb01158914dc3e67fc9005e58dfee2520d2b3dad1051bf8c09a7` |
| Urban / Poor | `d726067032d8e9c887f0b6564d83b30afc2d9f89f50b53a01a0db5a6f901de9b` |
| Special Reflective / Good | `18ef58f6b8d6519889e145cb7daa5cd97faa4d20f549f5e57951ce432280e8fe` |
| Special Reflective / Poor | `fc8c5e48b7500c85ea142f521a4b7b47af5a0a082f4170dc4843f22f0b8639bb` |
| Mountain/Valley / Good | `cbb63412fea791a1873014c0fc808c4ab1718c747301607bd8abaa14c705e9f3` |
| Mountain/Valley / Poor | `3a7272f2ceaac9cbb46afcb5832f003a607a1c6df97959dbe679fd8afa5de8c2` |
| Highway/Open / Good | `e4fb84a2c09cfe616ec18a3351993982660f3e20d20212e152871f5f89bbd3af` |
| Highway/Open / Poor | `45c8e55a31b32344afc759f81bb1386afa911421a70a259d8caed073383dec2d` |

当前 5 分钟集合共导出 8 张表、28,800,000 行，导出表文件合计约 2,364,024,185 bytes。`table_export_manifest.json` SHA-256 为 `f2de55f4803f237449c9f6b7f4722343e5d3c00a6601a0cc62106c5178669feb`；该 manifest 的 `table_count=8`，并记录每张表的源文件、目标文件、大小和 SHA-256。

## 4. Canonical 参数表合同

### 4.1 列顺序与单位

所有 canonical table 固定使用以下七列，顺序不能改变：

```text
ms,SatelliteID,NLOSPathID,RelativeDelay,RelativeDoppler,RelativeAmplitude,RelativePhase_rad
```

| 列 | 单位/取值 | 语义 |
|---|---|---|
| `ms` | ms，1 到 duration | 接收机时间线上的毫秒索引 |
| `SatelliteID` | `Low` / `Mid` / `High` | 仰角上下文标签，不是实际 PRN；对应 LOW/MID/HIGH |
| `NLOSPathID` | `0,1,2,3` | 0 为主径结构槽位，1–3 为三个 NLOS 结构槽位 |
| `RelativeDelay` | ns | 相对时延参数；由冻结路径参数模型生成 |
| `RelativeDoppler` | Hz | 相对多普勒参数；由冻结路径参数模型生成 |
| `RelativeAmplitude` | 线性幅度比 | 相对幅度；v2.2 的 NLOS 1–3 严格大于 0 |
| `RelativePhase_rad` | rad | 相对相位；使用冻结的初始相位与连续演化假设 |

### 4.2 每毫秒行顺序

每一个 `ms` 必须严格按以下顺序排列：

```text
Low  path0, path1, path2, path3
Mid  path0, path1, path2, path3
High path0, path1, path2, path3
```

因此：

- 每毫秒 12 行；
- 20 秒单表 240,000 行；
- 5 分钟单表 3,600,000 行；
- 5 分钟八表合计 28,800,000 行。

### 4.3 路径与质量语义

- `NLOSPathID=1/2/3` 在 v2.2 的 `CONDITIONAL_MULTIPATH_SCENARIO` 合同下始终激活，幅度严格为正；这是用于构造暗室输入的条件性结构，不是实测多径发生率。
- `GOOD_TRACKED_BASELINE` 使用 `TRACKED_GOOD` 质量状态；配对实验中没有质量事件，质量 envelope 为 ones。
- `POOR_CONDITIONAL` 使用 `FADING_TO_LOCK_BAD → LOCK_BAD_HOLD → RECOVERING` 的条件性质量过程，每个仰角带安排一个完整质量事件；事件长度、深度和恢复来自冻结的环境锁定/恢复模型或父模型代理，并采用 `FAIL_CLOSED_NO_TRUNCATION`，不能为适应短时长而截断。
- Good/Poor 的 paired 设计保持共同 gain、path delay、Doppler、phase；质量差异由冻结 quality envelope 表达。它不是绝对 RF 功率校准，也不是硬件物理失锁概率。
- 初始相位和 1 ms Doppler 相位递推是明确的外加假设。当前没有暗室绝对功率范围，因此表格不能解释为绝对接收功率。

## 5. 环境、仰角与模型支持边界

v2.2 配置中的 source-scene provenance 为：

| 环境类别 | 配置引用的测量 scene |
|---|---|
| Urban | `F1023_V70_D0120_P1`, `F1023_V70_D0120_P5`, `F1023_V70_D0120_P7`, `F1023_V70_D0120_P8`, `F1023_V70_D0122_P1`, `F1023_v50_D0127_P1` |
| Special Reflective | `F1023_V70_D0120_P9`, `F1023_V70_D0122_P2` |
| Mountain/Valley | `F1023_V70_D0117_P2`, `F1023_V70_D0117_P4`, `F1023_v90_D0117_P7` |
| Highway/Open | `F1023_V120_D0121_P2`, `F1023_V80_D0117_P8` |

这些是模型配置的来源场景集合，不表示本次生成了每个 scene 的独立拟合模型。20 秒 QA 明确记录：8 张表对应 24 个 environment × elevation × quality logical cells，但模型家族仍是四个环境级家族，而不是 13 个 scene-specific fitted models。

当前支持限制：

- Urban LOW 和 Highway/Open LOW 的 path support 保留 `PRIOR_ONLY` / partial-pooling 限制；
- Highway/Open 只有较弱的路径/质量支持，不能据此提出强泛化结论；
- `Low/Mid/High` 是生成器的仰角上下文标签，不是当前暗室表中重新计算出的事件级卫星几何；
- 生成器输出不是 Stage4 confirmed event/path，也不应回写 `scenes/**/sage_results`。

## 6. 资产盘点

### 6.1 权威状态与设计文档

| 状态/资产 | 路径 | 用途 |
|---|---|---|
| 工程唯一状态源 | `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` | 暗室 v2.2 当前工程状态在 Section 61–62 记录；本文只作导航 |
| 旧 Rain 支线 handoff | `docs/GNSS_DARKROOM_CHANNEL_EMULATION_HANDOFF_CURRENT.md` | Rain 支线历史/现状记录，不替代 v2.2 generator 状态 |
| v2.2 设计计划 | `docs/superpowers/plans/2026-08-27-darkroom-environment-quality-paired-generator-v2-2.md` | environment × quality 配对设计与门禁 |
| v2 固定四槽位计划 | `docs/superpowers/plans/2026-08-27-darkroom-multi-elevation-four-slot-generator-v2.md` | 多仰角固定结构槽位设计 |
| v1/reproducibility 计划 | `docs/superpowers/plans/2026-08-27-reproducible-darkroom-four-path-generator.md` | 父模型、随机性与可复现性背景 |

### 6.2 冻结配置与 Python 源码

| 资产 | 路径 | SHA-256 | 作用/状态 |
|---|---|---|---|
| v2.2 config | `configs/channel_modeling/darkroom_multi_elevation_four_slot_generator_v2_2.json` | `26003c7c0c0cabca45c6a9a175974f1ca336a301eff9c546a9c3bc99e38b5822` | schema、环境、仰角、质量和执行合同 |
| quality profile | `scripts/analysis/channel_modeling/darkroom_quality_profile_v2_2.py` | `9b1f3483e9f5a9eb9630afeb2111568aa015802dde6301b40546a8a0d9c3528b` | Good/Poor 条件性质量时间线 |
| generator core | `scripts/analysis/channel_modeling/darkroom_generator_v2_2_core.py` | `fb0253c83b82c978c625c9ae22977beee4095155b48b171625f1607097d016cc` | v2.2 生成数学与表输出 |
| request preparer | `scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_2_request.py` | `f6a15b9dcf0c6819dc9792816670a7a3a73526112211383bbe00d7f82713b642` | 单 request immutable freeze |
| matrix preparer | `scripts/analysis/channel_modeling/prepare_darkroom_generator_v2_2_matrix.py` | `6968c111b9e36e9adba96e2900cc9a4686803ae017106191631b35b71b166af0` | 八单元矩阵 freeze |
| single-run runner | `scripts/analysis/channel_modeling/run_darkroom_generator_v2_2.py` | `206d6924c8b2e56ba8a77194ee0ab8409b05af2fd50330af55625542b4e26fab` | validation-only / new-only generation |
| independent auditor | `scripts/analysis/channel_modeling/audit_darkroom_generator_v2_2.py` | `e8f1ad43697380562e68485a91b6d6067dcd03b0495f420e690a36b25f225b8c` | 单 run 输出/合同/哈希审计 |
| matrix summarizer | `scripts/analysis/channel_modeling/summarize_darkroom_generator_v2_2_matrix.py` | `f82f10b4593ae0ca3469f82ec74b06ca49545108315de16e34914a779f34ed10` | 矩阵级汇总与 pair QA |
| batch wrapper | `scripts/analysis/channel_modeling/run_darkroom_generator_v2_2_batch.py` | `5b420575aa3236a17394b1edc481c02a046f5a52f5061e08bc0590d3451b8140` | 固定顺序编排八单元、执行/receipt/表导出 |
| batch wrapper tests | `scripts/analysis/channel_modeling/tests/test_run_darkroom_generator_v2_2_batch.py` | `bf852b68e9cdee61790d3ab5ca76325a2e5adf649d79e88b744b70cc7d023fd3` | 批处理合同与安全边界聚焦测试 |

固定数值环境：

```text
Python: D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe
Python version: 3.12.9
NumPy: 2.5.1
SciPy: 1.18.0
OpenBLAS: 0.3.33.112.0
```

### 6.3 受保护的主线资产

主线 `scripts/sage_pipeline/run_nav_sage_pipeline.m` 未被 v2.2 改动，当前核对 SHA-256 为：

`bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`

父模型与 v2.2 request 中使用的冻结 manifest SHA 为：

| 模型/manifest | SHA-256 |
|---|---|
| path parameter model | `4f24dd3a5532526ef9966288ea7de9d863fabd812abe07a811647095e5368f3c` |
| common gain/fade model | `6f36dab892622c9b9dc61ecde91fda85ff12ca60eeea4f81fe37760f0acb1e45` |
| lock model | `21c04938cba559b3e042806b093eba82e4e86a44977e95831c715aa03ffc97a5` |
| recovery model | `9eb1847eac27618f80475ceafe62616285a346c5da847afdb0e8f2c5fc63a3ee` |

### 6.4 生成与 QA 资产

**20 秒已验证矩阵**

- run root：`dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_runs/`
- 八个 run namespace：`*_good_20s_v2_2_r3_20260827` 与 `*_poor_20s_v2_2_r3_20260827`
- matrix namespace：`dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_matrices/environment_quality_pair_20s_v2_2_r3_20260827/`
- matrix manifest SHA-256：`389917e6810ae243434bec81df3409563a6491a81515b99f557dc3a2198f4a0a`
- QA namespace：`dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_matrices/environment_quality_pair_20s_v2_2_r3_qa2_20260827/`
- `matrix_qa_summary.csv` SHA-256：`88ebc27971c5c60b33cbdda723d73a9ef145c2a2e45cb7dca5c01d5d313d8fcd`
- `matrix_qa_report.md` SHA-256：`eab068ac949abb5b1a5d177610bd5d1ed41dab0c811fc1de4ec2098f618cc7a5`

**5 分钟集合**

- collection：`dataset_generation_logs/channel_modeling/0828darkroomPar/`
- `matrix_manifest.json` SHA-256：`61ff9777087b2c82f297b649adea2ae5406b658f53cb4fa56342aca9373fcbe9`
- `matrix_manifest.sha256` 文件记录上述 manifest digest；该 sidecar 文件本身不是 manifest digest 的替代物
- `request_matrix.csv` SHA-256：`303925e84fad0c02701332dc6110667b50e0866959be2894c24336d0f8ec7832`
- `batch_execution_receipt.json` SHA-256：`c78a030006851fb2b1ff87fd5792368235b54a183d7750e2dd0e06dfc4e69d63`
- `table_export_manifest.json` SHA-256：`f2de55f4803f237449c9f6b7f4722343e5d3c00a6601a0cc62106c5178669feb`
- `table_export_manifest.sha256` 文件记录上述 export manifest digest
- 8 个 batch log：`0828darkroomPar/logs/*.log`
- 8 个 authoritative per-request run namespace：`dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_runs/*_5min_v2_2_0828darkroomPar_20260827/`

**20 ms 诊断 smoke**

- collection：`dataset_generation_logs/channel_modeling/0828darkroomPar_smoke_20ms_20260827/`
- matrix manifest SHA-256：`4cfaf245c5af033c811993bf22109b8dcf462c4291925f1fcf5cbb6fc9f7e45d`
- batch receipt 为 `status=failed`、`completed_count=1/8`
- Urban Good 生成 240 行并正常结束；Urban Poor 因 `QUALITY_EPISODE_DOES_NOT_FIT` 失败；其余六项未启动
- 该 namespace 是不可变诊断证据，不是可复用的生产集合

## 7. 20 秒 pilot 的已验证事实

20 秒矩阵 QA 报告位于：

`dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_matrices/environment_quality_pair_20s_v2_2_r3_qa2_20260827/matrix_qa_report.md`

报告记录：

- `RUN_QA_PASS = PASS (8/8)`；
- `PAIR_QA_PASS = PASS (4/4)`；
- `CANONICAL_TABLES = PASS (8 tables, 1,920,000 rows)`；
- `LOGICAL_CONDITION_CELLS = PASS (24)`；
- raw/MATLAB/SAGE/batch/gold-label generation gates 全部 false；
- 每张表 240,000 行；每个 Good run 质量事件数为 0；每个 Poor run 质量事件数为 3（Low/Mid/High 各一个）；矩阵共 12 个 Poor 条件事件；
- Good/Poor paired audit 验证 common gain、path delay/Doppler/phase invariant，差异来自质量 envelope；
- 所有 NLOS 1/2/3 行幅度严格为正。

这组证据验证的是生成器合同、配对关系、可复现性和输出完整性，不是测量数据统计结论，也不是暗室硬件失锁概率标定。

## 8. 5 分钟结果的正确解释

当前 5 分钟 artifact 可以确认：

1. 八个预先冻结的 environment × quality request 均实际完成，exit code 均为 0；
2. 每个 request 生成 3,600,000 行 canonical table；
3. batch wrapper 完成了 8 张表的 hash-traceable export；
4. 生成过程没有 raw IQ、MATLAB、SAGE 或 20.46 MHz 操作。

当前 5 分钟 artifact 不能单独证明：

1. 这些参数已经被暗室硬件回放验证；
2. 质量事件对应真实物理失锁概率；
3. 四环境已经形成可泛化的统计信道模型；
4. 5 分钟表已经获得与 20 秒矩阵等价的独立全量 QA，除非后续另有独立 QA artifact。

如果后续需要补做 5 分钟独立 QA，应创建新的 QA namespace，只读检查现有 receipt、manifest、table export manifest 和表文件；不得重写表、修改参数、复用已有 output namespace 或把 5 分钟生成结果回写 SAGE 目录。

## 9. 执行和恢复规则

### 9.1 namespace 与新执行

- 单 run authoritative output 固定在 `dataset_generation_logs/channel_modeling/darkroom_generator_v2_2_runs/`。
- 集合级文件固定在对应 collection namespace 的 `matrix_manifest.json`、`request_matrix.csv`、`batch_execution_receipt.json`、`table_export_manifest.json`、`logs/` 和 `tables/`。
- `new_only=true`、`resume_allowed=false`；已存在 namespace 不得重新执行、覆盖或 resume。
- 后续任何新时长、新 seed 或新合同都必须使用全新的 versioned request/collection/run namespace，并生成新的 manifest/hash。
- partial、failed、inconclusive、旧 namespace 和释放锁 marker 都是审计证据，不能删除或静默整理。

### 9.2 批处理顺序与门禁

固定环境顺序为：

```text
Urban
Special Reflective
Mountain/Valley
Highway/Open
```

每个环境内固定先 `GOOD_TRACKED_BASELINE`，再 `POOR_CONDITIONAL`。批处理只在显式确认下执行；一项失败时按 wrapper 策略停止后续项，不自动删除或 resume 已产生输出。

20 ms 只能作为合同/短时长诊断 validation；因为 Poor quality profile 需要完整事件，当前八单元 execute 合同只允许 300,000 ms（5 分钟）。

### 9.3 后续读取方式

读取 5 分钟表时应使用 `table_export_manifest.json` 选择目标文件并先核对表 hash；按 `environment_class`、质量模式（由 export manifest 和 request 关联）以及 `SatelliteID` 分组。不要把 `SatelliteID=Low/Mid/High` 当作实际 PRN，也不要把任意生成行标记为 confirmed path。

## 10. 与主线 GNSS/SAGE 的边界

暗室生成器与主线 full SAGE 之间的关系为：

```text
GNSS raw IQ -> GNSS-SDR -> Stage0-Stage4 -> confirmed paths

冻结路径/质量模型 -> darkroom v2.2 -> canonical darkroom parameter tables
```

两条链共享的是项目研究背景和部分参数模型 provenance，不是同一类 artifact。暗室表不应写入：

```text
scenes/**/sage_results
```

不应修改 `run_nav_sage_pipeline.m`、scene、metadata、inventory 或历史 SAGE 结果。v2.2 也不改变 Stage0–Stage4 的 confirmed criterion。

## 11. 后续工作状态与建议

### 已完成 / 已验证

- v2.2 environment × quality generator infrastructure 已实现；
- 20 秒八单元 pilot 的 run QA、pair QA、matrix QA 已通过；
- 5 分钟八单元生成与八张 canonical table export 已完成；
- 所有关键 request、source、config、receipt、export hash 均可追溯。

### 已实现但不应过度解释

- `POOR_CONDITIONAL` 质量层是条件性 receiver-diagnostic model；
- 四结构槽位和全正 NLOS 是生成合同；
- phase 是外加的初始均匀/连续演化假设；
- relative amplitude 不是绝对功率。

### 仍未开始或需要单独决策

- 5 分钟表的独立全量 QA；
- 暗室硬件回放；
- 将暗室输出与真实设备的锁定/失锁行为校准；
- 事件发生率、持续时间和时间相关性的实测模型；
- 经过数据支持的完整统计信道模型；
- 20.46 MHz 处理。

当前最稳妥的后续动作是：若需要将 5 分钟结果用于暗室回放，先做独立只读 QA 并记录新的 QA namespace；在该 QA 之前不要把 5 分钟生成完成等同于暗室系统验收或统计模型完成。

## 12. 保护约束清单

以下约束持续有效：

- 不删除任何 source、request、manifest、receipt、log、partial 或 failed artifact；
- 不覆盖 v1/v2/v2.1/v2.2 旧 namespace；
- 不使用 `resume` 继续已有暗室输出；
- 不把暗室参数表写回 `sage_results`；
- 不运行 raw IQ、MATLAB 或 SAGE 来生成暗室表；
- 不在未经单独适配和批准的情况下处理 20.46 MHz；
- 不把 NLOS 条件性结构解释为真实多径发生率；
- 不把 Poor 条件性事件解释为硬件校准失锁概率；
- 不把 Low/Mid/High 生成标签解释为事件级实测卫星几何；
- 不把生成器结果或 20 秒 pilot 直接写成论文统计模型结果；
- 工程状态变化同步到 Engineering Handoff，论文事实只有在产生真实论文可用证据时才同步到 Paper Handoff。

## 13. 当前交接结论

截至 2026-08-27，暗室支线拥有一套可复现的 v2.2 四环境 × 两质量状态 × 三仰角上下文生成合同。20 秒矩阵已通过独立 QA；`0828darkroomPar` 的 5 分钟八张表已经实际生成并完成 hash-traceable export。5 分钟结果当前应标记为 **generation/export completed**，而不是未经独立 QA 的“暗室最终验收”或“完整统计信道模型”。

后续接手者首先应读取：

1. `docs/GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md` Section 61–62；
2. `dataset_generation_logs/channel_modeling/0828darkroomPar/batch_execution_receipt.json`；
3. `dataset_generation_logs/channel_modeling/0828darkroomPar/table_export_manifest.json`；
4. 本文第 3、4、8、9 节；
5. 20 秒矩阵 QA 报告及其 hash。

本参考文档本身不授权新的 batch、暗室回放、SAGE 或论文结论。
