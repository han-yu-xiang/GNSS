# Environment-Conditioned Receiver Lock-Loss Model v1

## 1. Status and scope

本报告记录一个基于现有 GNSS-SDR tracking 输出的、按采集环境条件化的接收机锁定状态模型。该模型的目标是为后续暗室信号生成器提供“接收机诊断层”的失锁进入率和失锁持续时间参数；它不是物理信号消失定律，也不是路径级多径统计信道模型。

```text
MODEL_BUILD = COMPLETED_WITH_LIMITATIONS
IMPLEMENTATION_QA = PASS
ENVIRONMENT_LOCK_LOSS_MODEL = BOUNDED_TRACKING_DIAGNOSTIC_MODEL
MULTIPATH_STATISTICAL_CHANNEL_MODEL = NOT_STARTED
RAW_IQ_READ = NO
MATLAB_EXECUTED = NO
SAGE_EXECUTED = NO
BATCH_EXECUTED = NO
```

本次只读使用已有数据库 provenance、已核验 scene context 和 GNSS-SDR tracking MAT 文件。没有打开 raw IQ，没有重新运行 MATLAB、SAGE 或 batch，也没有修改任何 `scenes/**/sage_results`、production artifact 或既有路径参数产物。

## 2. Frozen input and exclusion policy

输入解析严格来自以下现有文件：

- `dataset/multipath_event_database/v1/partitions/ingestion_id=ingestion_20260825_event_path_v1/facts/sage_runs.csv`
- `dataset/multipath_event_database/v1/partitions/alignment_id=alignment_20260825_tow_geometry_scene_v1/exports/modeling_run_eligibility.csv`
- `dataset/multipath_event_database/v1/partitions/alignment_id=alignment_20260825_tow_geometry_scene_v1/dimensions/scene_context.csv`
- 每个 eligible run 在 provenance 中指定的 GNSS-SDR tracking MAT 文件

共有 64 条审计运行记录，其中 63 条通过 `include_in_environment_modeling` 纳入本模型。G06 legacy 运行因缺少 `run_context.json` 被明确排除，但仍写入 `excluded_runs.csv` 作为可追溯排除记录；没有为它补造环境或运行上下文。

| 项目 | 数量/状态 |
|---|---:|
| 审计运行记录 | 64 |
| 纳入建模运行 | 63 |
| 明确排除运行 | 1（G06 legacy） |
| tracking 记录总数 | 894,470 |
| 有效 tracking 记录 | 808,133 |
| INCONCLUSIVE 记录 | 86,337 |
| 提取的去抖失锁区段 | 48 |

## 3. Receiver-lock semantics

### 3.1 Observation and time axis

模型读取 `PRN`、`PRN_start_sample_count`、`CN0_SNV_dB_Hz` 和 `carrier_lock_test`。时间轴使用：

\[
t = \frac{\texttt{PRN\_start\_sample\_count}}{10{,}230{,}000}\,\mathrm{s}.
\]

tracking 记录之间的大时间断点不会被连接为连续观测；断点标记为 `INCONCLUSIVE_GAP`，不转换成一次失锁事件。初始 acquisition 阶段的状态不计为内部失锁进入，末端未恢复的失锁区段保留为右删失语义。此次实际输出中各环境的右删失事件数均为 0，但拟合接口保留了右删失生存似然。

### 3.2 Lock state and debounce

- `carrier_lock_test < -0.5`：`LOCK_BAD`；
- 有限且 `>= -0.5`：`LOCK_GOOD`；
- 缺失或非有限：`INCONCLUSIVE`；
- 连续坏锁至少 20 ms 后才确认失锁进入；
- 连续好锁至少 100 ms 后才确认重新获得锁定。

这些阈值和去抖规则是 tracking-diagnostic 定义，不是多径确认准则，也不表示信号功率必然降为零。若后续暗室生成器将该状态映射为四路径幅度暂时置零，那属于独立的工程仿真策略，不能被解释为本数据估计出的绝对衰减。

## 4. Model construction

### 4.1 Environment-conditioned entry rate

每个环境组使用锁定暴露时间和确认失锁进入次数拟合 Gamma-Poisson 后验。先验固定为 shape=1、rate=1 s；后验均值再转换为每毫秒进入概率：

\[
p_{1\,\mathrm{ms}}=1-\exp(-\lambda/1000).
\]

观测到的锁定占用率单独报告，不把它当作独立 Bernoulli 概率。小样本环境保留 support/status 标记，并向全局持续时间拟合进行有限 partial pooling；没有把稀疏组包装成高置信度结论。

### 4.2 Duration model

在全局层面对 lognormal、Weibull 和 Gamma 候选族比较带右删失语义的似然，以 AICc 和固定顺序进行确定性选择。当前选择 Gamma；随后为各环境输出带 support status 的参数、median 和 P90。该持续时间模型描述的是被当前 tracking 规则确认的诊断失锁区段，不是多径路径 lifetime。

## 5. Fitted results

### 5.1 Environment-conditioned entry statistics

| 环境 | Runs | Scenes | Entries | Locked exposure (s) | Posterior entry rate (1/s) | Entry probability/ms | Observed occupancy | Support |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Highway/Open | 8 | 2 | 2 | 1825.516 | 0.0016424712 | 1.6424699e-06 | 0.002311 | `PARTIAL_POOLING_REQUIRED` |
| Mountain/Valley | 16 | 3 | 23 | 131.787 | 0.18074005 | 0.00018072372 | 0.225024 | `DATA_SUPPORTED_WITH_GROUPED_VALIDATION` |
| Special Reflective | 13 | 2 | 7 | 81.003 | 0.097557048 | 9.7552289e-05 | 0.155409 | `DATA_SUPPORTED_WITH_GROUPED_VALIDATION` |
| Urban | 26 | 6 | 16 | 132.453 | 0.12738525 | 0.00012737714 | 0.282133 | `DATA_SUPPORTED_WITH_GROUPED_VALIDATION` |

### 5.2 Environment-conditioned duration statistics

共同选择的持续时间族为 `gamma`。48 个事件的总体摘要为 median=`1348.5037 ms`、P90=`5237.0055 ms`、max=`5570.0275 ms`。

| 环境 | Events | Right-censored | Family | Median (s) | P90 (s) | Fit status |
|---|---:|---:|---|---:|---:|---|
| Highway/Open | 2 | 0 | gamma | 1.3015406 | 5.7672654 | `PRIOR_DOMINANT` |
| Mountain/Valley | 23 | 0 | gamma | 0.9116632 | 4.5999953 | `PARTIAL_POOLING` |
| Special Reflective | 7 | 0 | gamma | 1.2765817 | 5.4974410 | `PARTIAL_POOLING` |
| Urban | 16 | 0 | gamma | 1.9634207 | 7.1004999 | `PARTIAL_POOLING` |

全局候选持续时间拟合的 AICc 为：lognormal=`183.7958338`、Weibull=`175.1988685`、Gamma=`173.7871752`。这些是本次固定输入和固定诊断语义下的拟合选择，不是对未来所有采集条件的普适性证明。

## 6. What this model can and cannot support

### Can support

- 在当前 63 条 environment-eligible tracking runs 上，生成环境条件化的接收机 diagnostic lock-loss entry-rate 候选参数；
- 生成环境条件化的失锁持续时间候选参数；
- 对每个 run 保留锁定暴露、失锁占用、inconclusive gap 和 source provenance；
- 为暗室仿真提供一个可审计的“锁定状态事件层”初始输入。

### Cannot support

- 不能把 `LOCK_BAD` 解释为物理信号消失、绝对功率衰减或确定的 NLOS 状态；
- 不能由本模型推导路径级 delay、relative Doppler、relative amplitude 或 phase 分布；
- 不能估计 multipath occurrence probability、confirmed-event 到达率或 path lifetime；
- 不能从当前结果声明 elevation-conditioned lock-loss law；当前模型仅按环境条件化，直接按仰角拟合仍因事件时刻几何支持不足而 deferred；
- 不能替代 `parameters_20260825_stage4_path_v1` 路径参数数据，也不改变其 `MULTIPATH_STATISTICAL_CHANNEL_MODEL = NOT STARTED` 状态。

特别地，路径参数表只包含 confirmed multipath paths，不含 LOS/reference path；path 0 的仿真幅度约定、相位随机化及失锁时四路径如何处理，都必须作为后续生成器的独立明确假设或控制策略。

## 7. Immutable provenance

首选最终产物位于：

`dataset_generation_logs/channel_modeling/environment_lock_model_v1_20260826_r2/`

| Artifact | SHA-256 |
|---|---|
| `environment_lock_model_parameters.csv` | `47f0a070053eb6c44daf42a3665c304d3252f9165d297b757084d80865f512bb` |
| `excluded_runs.csv` | `382789a4284802ac51d7c182c26b8c0d40e0060da2f4f8c9ef7eb06ed173f737` |
| `lock_event_catalog.csv` | `0b2eec22b12b9e853bac8700a37a9a2698aec585be6d96dbfa104632bbeab876` |
| `lock_exposure_by_run.csv` | `f320898d5653d47663ddb54d00051740a1dbc8ce32bd7543e72c9edbff9796de` |
| `lock_model_manifest.json` | `21c04938cba559b3e042806b093eba82e4e86a44977e95831c715aa03ffc97a5` |
| `lock_model_qa_report.md` | `ace1686b38ad3ab51a0c1d3a979538feb243eec95cc1ebfb255c9cc26ffd32fb` |

模型生成脚本：`scripts/analysis/build_environment_lock_model.py`

- source SHA-256: `980eb2de3c8e1375119c1a5fd6f26a73bffe2c76b3f9b6211062468a4562b3e4`
- existing MAT reader source SHA-256: `7f4798f693fc1283d1d1a288c9336a6db0806ca8c7167791495a5f95d755391f`
- manifest SHA-256: `21c04938cba559b3e042806b093eba82e4e86a44977e95831c715aa03ffc97a5`

受保护生产入口 `scripts/sage_pipeline/run_nav_sage_pipeline.m` 仍为 SHA-256 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`。

## 8. Verification record

- 5 项针对阈值、断点、sample-counter duration、右删失、Gamma-Poisson、duration family 和 new-only namespace 的单元测试：`5 passed`；
- Python `py_compile`：PASS；
- r2 运行 receipt：`status=completed`；
- 输出 namespace 为独立的 `dataset_generation_logs/channel_modeling/...`，不在 `scenes/**/sage_results` 下；
- 既有 G06 exclusion、输入 provenance、输出 hash 和执行旗标已写入 `lock_model_manifest.json` / `run_receipt.json`。

本报告是结果整理与边界说明，不把 tracking-only 模型提升为已完成的完整统计信道模型。下一步是否把该锁定层接入暗室四路径生成器，需由用户/Commander 单独决定；在该决定前不自动生成仿真数据或新增实验。

