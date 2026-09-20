# 暗室现有资产索引

本文件用于结题材料导航。路径均指向原始资产位置；本材料目录不复制、覆盖或重命名既有科学产物。

## 1. 工程与模型说明

| 原始资产 | 用途 | 状态 |
|---|---|---|
| `docs/DARKROOM_GENERATOR_V2_2_REFERENCE.md` | v2.2 生成器、固定四槽位和 8 个基础组合说明 | 已整理参考 |
| `docs/DARKROOM_CHANNEL_MODELING_16_SCENARIO_PROGRESS_REPORT_CN.md` | 4 环境 × 2 质量 × 2 天气层的 16 个仿真组合总览 | 已完成并记录限制 |
| `docs/ENVIRONMENT_ELEVATION_PATH_DISTRIBUTION_MODEL_V1_REPORT.md` | 环境×仰角路径分布模型 | `COMPLETED_WITH_SPARSE_PRIOR_CELLS` |
| `docs/MAIN_PATH_COMMON_GAIN_FADE_MODEL_V1_REPORT.md` | 主径公共增益/可观测衰落模型 | `COMPLETED_WITH_LIMITATIONS` |
| `docs/NLOS_SLOT_ACTIVATION_MODEL_V1_REPORT.md` | 固定三个 NLOS 槽位激活层 | `COMPLETED_WITH_LIMITATIONS` |
| `docs/LOCK_AMPLITUDE_PHASE_RECOVERY_MODEL_V1_REPORT.md` | 失锁到幅度、相位和恢复层映射 | `COMPLETED_WITH_LIMITATIONS` |
| `docs/RAIN_STAGE3_EFFECT_LAYER_REPORT.md` | 基于 Stage3 的 Rain effect layer | `IMPLEMENTED_AND_QA_PASS` |

## 2. 暗室参数输出

| 原始资产 | 内容 |
|---|---|
| `dataset_generation_logs/channel_modeling/0828darkroomPar/` | 8 个基础环境×质量组合的 5 分钟参数生成资产 |
| `dataset_generation_logs/channel_modeling/rain_effect_layer_stage3_v1_20260830_r5/` | 8 个加载 RainPooled effect layer 的 5 分钟参数表 |
| `docs/DARKROOM_VEHICLE_GNSS_COMPARATIVE_TEST_REPORT_CN_v2.pptx` | 车机/GNSS-SDR 信道可用性汇报版 PPT |
| `docs/DARKROOM_VEHICLE_GNSS_COMPARATIVE_TEST_AND_REPORT_PLAN_CN.md` | 车机与 GNSS-SDR 对照测试方案 |

当前 16 个组合的结构为：4 类环境（Urban、Special Reflective、Mountain/Valley、Highway/Open）× 2 类质量（GOOD、POOR）× 2 类天气层（Dry/Base、RainPooled）。Urban/Poor 现在从车辆动态定位候选集中排除，但历史参数表仍保留。

## 3. GNSS-SDR 自发自收诊断资产

| 原始资产 | 用途 |
|---|---|
| `dataset_generation_logs/darkroom_rx_gnss_sdr/darkroom_rx_0913_gnss_sdr_v1_20260914/batch_manifest.json` | 8 个 0913 输入的 immutable manifest |
| `dataset_generation_logs/darkroom_rx_gnss_sdr/darkroom_rx_0913_gnss_sdr_v1_20260914/runs/` | 各 GOOD/POOR/RAIN 条件的 GNSS-SDR 输出 |
| `dataset_generation_logs/darkroom_rx_gnss_sdr_qa/darkroom_rx_0913_all8_20260915_r1/` | 全量 8 任务的只读 QA namespace |
| `docs/DARKROOM_RX_0913_ALL8_SIGNAL_QUALITY_REPORT_CN.md` | 8 任务定位输出、失锁和覆盖率汇总 |
| `docs/DARKROOM_RX_0913_CHANNEL_REPORT_CN.md` | 16 参数表自发自收报告方法，以及已有 8 个 GNSS-SDR 任务的信号时长、失锁、重捕获和定位汇总 |
| `docs/DARKROOM_RX_0913_GNSS_SDR_POSITIONING_DIAGNOSTIC.md` | 操作、审计语义和失锁/PVT 分层说明 |

关键参考值：Highway/Open Poor 为 103/105 个有效/期望定位历元、最长连续定位约 46 s；Urban Poor 为 12/12 个有效/期望定位历元，但可见定位段约 12 s，不能作为整段动态定位可用性的充分证据。

## 4. 主要脚本资产

### 参数生成与 Rain effect layer

- `scripts/analysis/channel_modeling/run_darkroom_generator_v2_2_batch.py`
- `scripts/analysis/channel_modeling/audit_darkroom_generator_v2_2.py`
- `scripts/analysis/channel_modeling/run_rain_stage3_effect_layer_v1.py`
- `scripts/analysis/channel_modeling/audit_rain_stage3_effect_layer_v1.py`
- `scripts/analysis/channel_modeling/rain_stage3_effect_layer_v1.py`
- `configs/channel_modeling/darkroom_multi_elevation_four_slot_generator_v2_2.json`

### GNSS-SDR 诊断

- `scripts/analysis/darkroom_rx/prepare_darkroom_rx_gnss_sdr_batch.py`
- `scripts/analysis/darkroom_rx/run_darkroom_rx_gnss_sdr_batch.py`
- `scripts/analysis/darkroom_rx/audit_darkroom_rx_signal_quality_v2.py`
- `scripts/analysis/darkroom_rx/tests/test_darkroom_rx_pipeline.py`

## 5. 结题材料使用顺序

1. 先读本目录的标准关系说明，明确“标准相关子系统”与“完整符合性”的边界；
2. 再读 16 场景模型和 Rain effect layer 报告，说明参数来源、固定槽位和经验假设；
3. 使用 GNSS-SDR 诊断报告说明信道可用性筛选，不把车机界面单独作为信号物理结论；
4. 复测阶段仅使用新的、独立的测试记录，不修改本索引列出的历史 artifact。
