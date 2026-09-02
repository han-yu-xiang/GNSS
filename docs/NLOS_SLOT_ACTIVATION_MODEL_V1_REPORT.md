# Fixed Three-NLOS-Slot Activation Model v1

## 1. Executive status

状态：`COMPLETED_WITH_LIMITATIONS`。本次已按固定三槽位激活计划完成离线构建和独立 QA。产物可以作为后续暗室生成器组合的输入层，但不是完整四路径毫秒级信号生成器，也不是已经完成的物理统计信道模型。

本次仅读取既有数据库分区、既有 Stage0 窗口目录和已验证 geometry 数据；没有读取 raw IQ，没有运行 MATLAB、SAGE、batch，也没有处理 20.46 MHz。既有 SAGE、reference、生产结果、旧模型 namespace 和源数据均未修改。

关键结论：

- `READY_FOR_GENERATOR_COMPOSITION=YES`；
- `FINAL_DARKROOM_GENERATOR=NOT_STARTED`；
- `PHYSICAL_MULTIPATH_OCCURRENCE_PROBABILITY=NOT_IDENTIFIED`；
- 零 confirmed-event 暴露不能解释为 LOS 或物理上没有多径；
- 当前层只定义 NLOS 槽位的激活/数量规则，主径公共增益、相位、失锁映射、路径寿命和最终四行输出仍是独立层。

## 2. Frozen inputs and provenance

正式输出目录：

`E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\nlos_slot_activation_v1_20260826_r1\`

主模型 manifest：

`dataset_generation_logs/channel_modeling/nlos_slot_activation_v1_20260826_r1/model_manifest.json`

SHA-256：`b47b2a09f9acc5f1ccd65dcf923623dbeea27e3aec3e3e3f04c2e094a3e486d2`

冻结配置：

`configs/channel_modeling/nlos_slot_activation_v1.json`

配置 SHA-256：`bd8d3aec2c576598a3ddeb0c24f14c520c0e5e6d1f7c8d321c5d586380da04aa`

代码 provenance（以下为当前源码；r1 独立 QA 产物在 geometry 诊断字段修正前已生成并保持不变）：

| Component | Path | SHA-256 |
|---|---|---|
| Core | `scripts/analysis/channel_modeling/nlos_slot_activation_core.py` | `371e19362a86dcff3fcc936397cb872d1a5af543b819eea5ede7a281d71c089b` |
| Builder | `scripts/analysis/channel_modeling/build_nlos_slot_activation_model.py` | `374ee7108ff28b9581d3d786d063203fc1b01708b8c6c09f11bae140325eb1ed` |
| Independent auditor | `scripts/analysis/channel_modeling/audit_nlos_slot_activation_model.py` | `20c8b7fb8d0f4b3f0a42a3b12f3f8901ed9b76543a2bf1f12f95b6f6b784e372` |
| Protected production pipeline | `scripts/sage_pipeline/run_nav_sage_pipeline.m` | `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c` |

执行环境：`D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`，CPython 3.12.9，Windows 64-bit，NumPy 2.5.1，SciPy 1.18.0，OpenBLAS 0.3.33.112.0。构建耗时约 482.685 s；该时间是本次 Python 离线构建时间，不是 SAGE runtime。

源数据 hash 由 model manifest 冻结，核心来源包括：

- Stage4 event/path parameter partition：`path_parameters.csv` SHA-256 `2a44913d1c06f78d2748428b1d72f1b4712a6b5d3f33fc598a14fe17a3e3414a`；`event_parameters.csv` SHA-256 `a182c740961dde0fbe9e1df8525ae15bc42e0d4e4992060b77656f45bc2f7e91`；
- Stage4 audit facts：`events.csv` SHA-256 `b1340bb1f17bb2e52e2857234d61aa084fbc734cf352f32be7bdb4275661c9d1`；`event_paths.csv` SHA-256 `80e0f0eb6a8bcaebb7dd50398994751aa422a0b5e8bd2c2833424d3e3731da2a`；
- run/exposure provenance：`sage_runs.csv` SHA-256 `f4303749beeb73e922758ef6a1cfb0eef7b4e69d49b2f49ad8b6bf29cb3a7ae5`；`run_summary.csv` SHA-256 `b2251b2393ab6c7545dc444028e00f9d06e4200086d713211be26011a93e7a87`；
- aligned geometry/scene source：`event_context_aligned.csv` SHA-256 `38b5cdc8aedb1c4576952d7e9fd2344b3414f67ddca2443e4a20a63ca813e41f`；`scene_context.csv` SHA-256 `8a50fcc3196a2256735c45c77119d8a8b6447523aeb5a075e103ed1877e3`；
- parent path model manifest SHA-256 `4f24dd3a5532526ef9966288ea7de9d863fabd812abe07a811647095e5368f3c`；parent common-gain manifest SHA-256 `6f36dab892622c9b9dc61ecde91fda85ff12ca60eeea4f81fe37760f0acb1e45`。

## 3. Frozen population and exposure accounting

本模型使用 64 条 audit run 中的 63 条 modeling-eligible run；缺少 `run_context.json` 的 G06 legacy run 保留在审计数据中但不进入本模型。输入规模为：

| Quantity | Count | Meaning |
|---|---:|---|
| Eligible runs | 63 | 通过 modeling eligibility 的 run |
| Stage0 exposure windows | 169,637 | 全量 40 ms Stage0 暴露母集 |
| Strict confirmed events | 94 | 仅满足冻结 Stage4 规则的事件 |
| Confirmed NLOS paths | 100 | 仅 `is_multipath=1` 的 confirmed path |
| Environment × elevation cells | 12 | 4 environments × LOW/MID/HIGH |
| Closure memberships | 470 | 94 个事件各自 center ±2 的完整闭包 |

Stage4 标签使用严格条件：`joint_valid=1`、`joint_multipath_count>0`，且对应 path 行 `is_multipath=1`。Stage1 candidate、Stage2 模型阶数和 Stage3 reliable center 均没有被当作激活标签。

每个 confirmed event 的 center ±2 窗口首先在同一 run、连续 Stage0 时间轴内取唯一 union，得到保守的 `Stage4-confirmed-support` 暴露标签。该标签用于估计“当前确认准则下的支持暴露”，不是任意时刻物理多径发生率。`require_continuity_for_closure=true`、窗口长度 40 ms、步长 20 ms、geometry 最大时间差 0.011 s，未使用插值或场景均值替代窗口级 geometry。

## 4. Activation model

### 4.1 Two-level state

对环境和仰角单元 (c=(e,h))，模型将“是否激活”和“激活时有几条 NLOS 路径”分开：

\[
Z_c \sim \operatorname{Bernoulli}(p_c),
\]

\[
K_c\mid Z_c=1 \sim \operatorname{Categorical}(q_{c,1},q_{c,2},q_{c,3}),
\qquad K_c\mid Z_c=0=0.
\]

其中 (p_c) 是基于 confirmed center ±2 support 的 bounded proxy；(q_{c,k}) 是在已经处于 active 状态时的 confirmed event path-count 分布。当前实现没有把二者合并成单一 coarse score，也没有从 Stage1/Stage2/Stage3 构造替代标签。

### 4.2 Occupancy/support layer

occupancy 使用 scene-balanced Beta pseudo-posterior，基础先验为 Beta(0.5, 0.5)，父层等效 scene 数为 8。每个 cell 的输出位于 `cell_occupancy_parameters.csv`，包含 alpha、beta、posterior mean、2.5/50/97.5% 分位数、直接 scene/event 支持数、exposure windows、support windows 和原始 time-weighted support fraction。

各 cell 的 posterior mean 与支持状态如下；数值是 bounded confirmed-support proxy，不是物理发生率：

| Environment | LOW | MID | HIGH |
|---|---:|---:|---:|
| Urban | 0.014712 (`EXPOSURE_ONLY_ZERO_CONFIRMED`) | 0.016516 (`DATA_SUPPORTED_WITH_GROUPED_VALIDATION`) | 0.015098 (`DATA_SUPPORTED_WITH_GROUPED_VALIDATION`) |
| Special Reflective | 0.027157 (`DATA_SUPPORTED_WITH_GROUPED_VALIDATION`) | 0.025819 (`SPARSE_PARTIAL_POOLING`) | 0.025865 (`SPARSE_PARTIAL_POOLING`) |
| Mountain/Valley | 0.022609 (`SPARSE_PARTIAL_POOLING`) | 0.022535 (`SPARSE_PARTIAL_POOLING`) | 0.022514 (`SPARSE_PARTIAL_POOLING`) |
| Highway/Open | 0.025132 (`EXPOSURE_ONLY_ZERO_CONFIRMED`) | 0.025475 (`SPARSE_PARTIAL_POOLING`) | 0.025570 (`SPARSE_PARTIAL_POOLING`) |

其中两个 zero-confirmed exposure cell 仍有 Stage0 暴露和先验后验记录；它们不表示 LOS。稀疏 cell 的标签明确表示 partial pooling，不能与有充分直接事件支持的 cell 等同解读。

### 4.3 Conditional multiplicity layer

`cell_multiplicity_parameters.csv` 使用 event-level confirmed path count 的 hierarchical Dirichlet，类别固定为 (K\in\{1,2,3\})，基础 Dirichlet 先验为 (0.5, 0.5, 0.5)，父层等效事件数为 8。观测到的全局事件级分布为：

| Confirmed NLOS path count K | Events |
|---:|---:|
| 1 | 89 |
| 2 | 4 |
| 3 | 1 |

该计数是“在 confirmed active event 中”的条件分布，不能转换成整个测量过程中的 path-count occurrence。Urban–LOW 与 Highway/Open–LOW 没有直接 confirmed event，multiplicity 使用 `PRIOR_ONLY`；其它稀疏 cell 的 `SPARSE_PARTIAL_POOLING` 或 `PRIOR_DOMINANT` 状态保留在产物中。

## 5. Fixed three-slot contract

模型为暗室输出预留三个 NLOS 槽位；主径/公共增益不在本层内占用这三个槽位。固定 mask 为：

| K | Slot 1 | Slot 2 | Slot 3 |
|---:|---:|---:|---:|
| 0 | inactive | inactive | inactive |
| 1 | active | inactive | inactive |
| 2 | active | active | inactive |
| 3 | active | active | active |

有效路径在 event 内按 `relative_delay_ns` 升序、`relative_amplitude_linear` 降序、`relative_doppler_hz` 升序、稳定 source path ID 升序排序。inactive slot 使用 `PathActive=0`、`PathStatus=INACTIVE_NO_PATH`、amplitude 0；delay、Doppler 和 phase 保持 null，而不是用 0 伪造缺失值。槽位是块内确定的输出位置，不代表跨 block 的持续反射体身份。

`slot_activation_contract.json` 和 `observed_slot_assignment_audit.csv` 记录了该契约；观察审计共 282 行，即 94 个 confirmed event × 3 个 NLOS slot。

## 6. Determinism and uncertainty QA

- scene-block bootstrap：1000 个 replicate，seed=`20260828`；重采样单位为 scene block，不在 window 层随机抽样；
- QA draws：24 个 cell/mode summary，每个 4096 次，seed=`20260829`；
- `EMPIRICAL_CONFIRMED_SUPPORT` mode 从各 cell bounded support occupancy 抽样，QA 中 active fraction 约为 0.01538–0.02832；
- `CONDITIONAL_ACTIVE_STRESS` mode 强制 (Z=1)，其 active fraction 为 1，这是压力测试而非 occurrence estimate；
- 独立 QA 的 deterministic stream、bootstrap、slot mask、inactive null 和 hash 检查通过；bootstrap 1000 行均保留在 `bootstrap_uncertainty.csv`，QA 24 行保留在 `qa_draw_summary.csv`。

独立 QA 文件：

`dataset_generation_logs/channel_modeling/nlos_slot_activation_v1_20260826_r1/independent_qa_report.md`

`MODEL_QA=PASS_WITH_LIMITATIONS`，`READY_FOR_GENERATOR_COMPOSITION=YES`。审计硬门禁 `source_provenance`、Stage4 label、exposure/closure、occupancy、multiplicity、slot contract、determinism 和 namespace/hash 均通过；occupancy/multiplicity 仍以 `PASS_WITH_LIMITATIONS` 表示稀疏支持限制。

QA artifact 说明：正式构建前置验证记录了 geometry time-match `169,637/169,637`、geometry-valid `160,450/169,637`。首次独立 QA JSON 的 `checks.geometry_matched_windows` 仅是一个不参与门禁的诊断字段，因审计器早期统计表达式未读取 exposure 行而保存为 0；没有影响任何 gate、模型文件或参数。审计器源码已修正为按 exposure 行计算，该修正不回写、不覆盖本次 immutable r1 QA artifact。后续若需重新生成审计证据，应使用新的 versioned namespace。

## 7. Output inventory

核心输出包括：

- `source_preflight.csv`：源文件、hash、计数和离线策略门禁；
- `stage0_source_manifest.csv`：63 个 run 的 Stage0 文件身份、hash 和窗口数；
- `activation_exposure_grid.csv.gz`：全量 Stage0 暴露及 environment/elevation/support provenance；
- `confirmed_support_membership.csv`：confirmed event center ±2 的连续闭包成员；
- `scene_cell_exposure.csv`：scene-balanced occupancy 的暴露单元；
- `cell_occupancy_parameters.csv`、`cell_multiplicity_parameters.csv`：12 个 cell 的激活代理与条件 K 参数；
- `multiplicity_event_catalog.csv`：94 个 confirmed event 的 event-level path-count 目录；
- `observed_slot_assignment_audit.csv`：固定三槽位 mask/ordering/inactive semantics 审计；
- `bootstrap_uncertainty.csv`、`qa_draw_summary.csv`：不确定性与确定性 QA 记录；
- `slot_activation_contract.json`、`nlos_slot_activation_model.json`：供后续组合读取的机器契约；
- `model_manifest.json`、`build_receipt.json`、`model_report.md`：hash、来源和执行收据。

14 个 builder artifact 的 hash 已记录在 model manifest；model manifest SHA-256 为 `b47b2a09f9acc5f1ccd65dcf923623dbeea27e3aec3e3e3f04c2e094a3e486d2`，build receipt SHA-256 为 `50069f6798c15ec801356dd920342c2b17d29c0f25c8003122a8567fe1ba6076`。独立 QA report SHA-256 为 `533c85016fe27b0d6e3d155e1bf466713641a635021391cfdcd52604c10c6883`，QA result SHA-256 为 `7dc097938961b0c1cc56a4ef7f583e0e53dd89e57fbc590a8eeeeb7cf86021d3`。

## 8. What this layer does and does not establish

可以直接使用的内容：

1. 在给定 environment/elevation cell 下，用 bounded Stage4-confirmed-support proxy 采样 NLOS 槽位是否激活；
2. 在 active 条件下按 cell 的条件 multiplicity 采样 K=1/2/3，并通过固定 prefix mask 映射到 1/2/3 个 NLOS 槽位；
3. 以明确的 inactive/null 语义输出三槽位结构，并在块内保持状态固定；
4. 通过 scene-block bootstrap 和固定随机流提供可复现的 QA/不确定性输入。

仍不能从本层得出的内容：

- 任意时刻真实物理 multipath occurrence probability；
- zero-confirmed-event 状态下的 LOS 判定；
- absolute RF power 或物理 LOS 强度；
- phase 初始化/连续演化；
- receiver lock-loss 与 NLOS 激活/恢复之间的联合物理映射；
- path lifetime、跨块 persistence、arrival process；
- 最终 4 行 `ms × SatelliteID × NLOSPathID × RelativeDelay/Doppler/Amplitude/Phase` 仿真表。

这些缺失项不是本次 builder 的失败，而是保持层次解耦后的后续组合接口。后续组合必须继续保留 `gold_labels_used_for_selection=false`、`raw_iq_read=false`、`matlab=false`、`sage=false`、`batch=false` 和 `process_20_46_mhz=false`。

## 9. Status and next controlled step

| Layer | Status | Interpretation |
|---|---|---|
| Fixed three-NLOS-slot activation layer | `Completed with limitations` | 已构建、已独立 QA，可作为组合输入 |
| Main/common gain and observable fade layer | `Completed with limitations` | 独立 tracking diagnostic/gain layer |
| Environment × elevation NLOS path distributions | `Completed with limitations` | confirmed-NLOS 条件分布，含稀疏/prior cells |
| Phase and lock-loss composition | `Planned / Not started` | 尚未冻结联合映射 |
| Path lifetime/inter-block persistence | `Planned / Not started` | 尚未从现有数据派生 |
| Final four-path millisecond generator | `Not started` | 不得把当前层当成完整生成器 |

唯一建议的下一步是：在全新、独立、new-only 的组合 namespace 中，先设计并审计主径增益、phase、lock-loss 和三 NLOS 槽位的接口契约；只有该组合设计通过独立 QA 后，才考虑生成器原型。不得直接把本模型输出写回 `scenes/**/sage_results`，也不得以本层结果恢复 SAGE 或生产任务。
