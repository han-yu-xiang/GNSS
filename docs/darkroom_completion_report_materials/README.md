# 暗室信道仿真结题报告材料目录

**建立日期：** 2026-09-15
**用途：** 汇总暗室 GNSS 信道参数模型、雨效应层、GNSS-SDR 自发自收诊断，以及 GB/T 45086.1-2024 相关性分析，供结题汇报和后续人工复测使用。

本目录是结题材料集合，不是新的工程状态源。工程状态仍以 [`../GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md`](../GNSS_SAGE_ENGINEERING_HANDOFF_CURRENT.md) 为准；论文状态仍以 [`../GNSS_SAGE_PAPER_HANDOFF_CURRENT.md`](../GNSS_SAGE_PAPER_HANDOFF_CURRENT.md) 为准。

## 材料清单

| 文件 | 内容 | 状态 |
|---|---|---|
| `01_GB_T_45086_1_2024_PROJECT_RELATION_CN.md` | GB/T 45086.1-2024 官方出处、项目能力边界和汇报表述 | 已整理 |
| `02_AUTOMOTIVE_GNSS_TEST_STANDARDS_AND_LITERATURE_CN.md` | 汽车 GNSS 测试标准和中文优先文献清单 | 已整理 |
| `03_DARKROOM_SIGNAL_USABILITY_AND_URBAN_POOR_EXCLUSION_CN.md` | Urban/Poor 排除决定与跨车辆复测门禁 | 已整理 |
| `04_EXISTING_DARKROOM_ASSET_INDEX_CN.md` | 现有模型、脚本、输出和诊断证据索引 | 已整理 |

## 当前工程决策摘要

- `Urban/Poor` 的 GNSS-SDR 结果只有一段较短的有效定位输出，虽然满足旧审计中的短时 `SUSTAINED_FIX` 分类，但不满足“动态轨迹信道应能相对长时间持续定位”的当前可用性目标。因此，Urban/Poor 从**车辆动态定位测试的候选信道集**中排除。
- 该排除是用途筛选，不是删除、覆盖或修改。原始参数表、GNSS-SDR 输出、receipt、日志和 QA 报告全部保留。
- 另一辆车复测时，GNSS-SDR 作为独立参考链路必须在预先定义的整段回放中保持相对长时间的有效 PVT；具体覆盖率、最大允许中断时长和重复次数应在复测前冻结，不能事后按结果修改。
- 目前只有“车机失败但 GNSS-SDR 持续定位”时，才可以把问题优先归因到车机兼容性、恢复逻辑或集成链路；不能仅凭车机界面判断信道失败。

## 标准全文说明

本目录保存官方标准信息页和项目关系分析，不复制受版权保护的标准全文。需要逐条声称符合性或使用具体数值门限时，应通过正式渠道取得并核对 GB/T 45086.1-2024 全文。

## 执行边界

本材料整理没有运行 MATLAB、SAGE、GNSS-SDR 或 batch，也没有读取 raw IQ 内容；没有修改既有模型、参数表、SAGE 结果、receipt、manifest 或 QA artifact。
