# Rain Stage3 雨效应层报告

日期：2026-08-30

## 1. 当前状态

`RAIN_EFFECT_LAYER_STATUS=IMPLEMENTED_AND_QA_PASS`

本次对已经审计的 9 个 Rain 任务进行纯离线后处理，使用 Stage3 可靠/持续路径证据。Stage4 严格确认条件没有用于拟合、筛选或输出生成。最终生成的是可加载到现有暗室 canonical path table 的经验型天气条件变换层，不表示每一条 Stage3 路径都已经是物理意义上的 confirmed multipath path。

## 2. 输入证据

本次输入任务范围显式固定为：

- Clear: G24/ch10, G29/ch3, G13/ch8, G12/ch11
- MidRain: G24/ch8, G20/ch9
- HeavyRain: G02/ch1, G31/ch4, G01/ch7

证据提取器只保留 `persistence_pass=1` 且中心窗口出现在 `stage3_reliable_centers.csv` 中的路径行，共得到 90 条可靠路径证据和 26 个中心支持 episode。

| 天气状态 | 任务数 | Episode 数 | 可靠路径行数 |
|---|---:|---:|---:|
| Clear | 4 | 10 | 31 |
| MidRain | 2 | 8 | 17 |
| HeavyRain | 3 | 8 | 42 |
| RainPooled | 5 | 16 | 59 |

`RainPooled` 是 MidRain 与 HeavyRain 的合并雨效应层，用于本次要求的 8 张输出表。模型文件中仍保留 MidRain 和 HeavyRain 的独立分布。由于 Rain 证据没有经过验证的仰角条件化拟合，本次将同一 pooled 雨效应变换应用于 Low、Mid、High 三个输出频段。这是明确的可分离性假设，不是仰角统计结果。

## 3. 变换语义

v2.2 canonical table 的字段和行身份保持不变：

`ms, SatelliteID, NLOSPathID, RelativeDelay, RelativeDoppler, RelativeAmplitude, RelativePhase_rad`

- 主径 `NLOSPathID=0` 不受雨效应层改变。
- NLOS 槽位 1–3 接收确定性的分块变换。
- 每个 `SatelliteID × NLOSPathID × 40 ms block` 只采样一次变换，同一 block 内保持不变。
- 相对时延在内部以 ns 表示，并使用 Clear 与 Rain 的经验分位数差异进行对数域变换。
- 相对多普勒使用 Clear 与 Rain 的经验分位数差异进行加性变换。
- 相对幅度通过功率差异换算，并保持严格为正。
- Stage3 不提供相位，因此相位不是拟合结果，而是从 canonical 相位出发，按照输出多普勒进行连续 1 ms 演化。
- Clear 输出作为 identity 输出，用于 QA 和对照。

拟合权重依次采用任务均衡、任务内 episode 均衡、episode 内路径行均衡，以减少邻近窗口重复对分布的直接支配；但不能消除所有 scene/run 内相关性。

## 4. 最终输出集合

最终 new-only namespace：

`E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\rain_effect_layer_stage3_v1_20260830_r5`

共生成 8 张表，每张 3,600,000 行：

| 输出文件 | SHA-256 |
|---|---|
| `tables\urban__good__rain.csv` | `3a4b53e943e0e432b4a8fc90d2dbf158716191df71f50715cfbfe0e525e51ae8` |
| `tables\urban__poor__rain.csv` | `4a064c97e9ce3635d59900e70b88cd9212c6f09d5fcdf7287bd18ea9a3ef2e57` |
| `tables\special_reflective__good__rain.csv` | `d5634038902cec34d577ef0c19add00c9ea76e381a90964214f74f19578ffc38` |
| `tables\special_reflective__poor__rain.csv` | `e374483d6af0f39111d4fca7db933083b306fe0f05519a81ba35e0213e1485a3` |
| `tables\mountain_valley__good__rain.csv` | `4e084f1519499e9b354e7ffe710de77d5fbdb42f4817bf747dba1a248363d8de` |
| `tables\mountain_valley__poor__rain.csv` | `4f05d67bd5e1a0c5df3c2c14b11d824e248c6207adb98727a30a339e834eea30` |
| `tables\highway_open__good__rain.csv` | `bbd798f1d37598129e6c334c0f46a5a306f10475ca0a99705a0ea71e6bde9af6` |
| `tables\highway_open__poor__rain.csv` | `a136a2566680a520c80432cc8d23bc9f4bd6e98e4611e2abe5f2e19df8e8687a` |

## 5. Provenance 哈希

<!-- 以下哈希是最终 r5 namespace 的不可变 provenance。 -->
- 模型：`rain_effect_model.json` — `9e57ac9b24648f6e42a15d2185d9370fe19a5999507696e3e5ad765da36d3455`
- Collection manifest — `a7dd28086b5b76821b6202f8f9efe6c7386e7f6db4680ae4353682982825c621`
- Run manifest — `e171c37c50dd5fc02db02887a956e278eb8743ba6683044ddf298aa93f475605`
- Stage3 evidence CSV — `21ee74aef715e02fc2697b0e66612c8f616c3976d4d03ce8615a10564834fd8f`
- Episode catalog — `32bbb8bc91497ad8071a9a6942e4d7829f951e2a8c6aa59139472eb903afdbfd`
- Collection QA — `8b890163e9d0b501fe6f24c44217602340c7803cd413a03b40bb1e7604ab3efd`
- Kernel source — `7833082f66d2ed4687b831442ce5a617bc7cfcb618ac993aae01f075465b289b`
- Runner source — `a4c31129ad75aea089eed8fc87033ebbc0163687f6f76731d4f301b16e84f535`
- v2.2 canonical export manifest — `f2de55f4803f237449c9f6b7f4722343e5d3c00a6601a0cc62106c5178669feb`

Run manifest 记录的运行环境为 Python 3.12.9：`D:\Research\ChannelModeling-Agent\.venv\Scripts\python.exe`。本次明确记录：`raw_iq_read=false`、`matlab=false`、`sage=false`、`stage4_used_for_fit=false`、`gold_labels_used_for_selection=false`。

## 6. 独立 QA 结果

`RAIN_EFFECT_LAYER_QA=PASS`

独立 QA 验证了：

- 8/8 输出表存在，每张 3,600,000 行；
- evidence 90 行，episode 26 行；
- 输入源和输出文件哈希与 manifest 一致；
- 七列 canonical schema、行身份和行顺序保持一致；
- 主径在 `1e-10` 数值容差内保持不变；
- 所有 NLOS 幅度有限且严格为正；
- 每个 satellite/path/block 的 40 ms 效果保持恒定；
- 相位递推与输出多普勒一致；
- 输出 namespace 不在 `scenes/**/sage_results` 下；
- 拟合和筛选过程没有读取 Stage4/gold。

## 7. 限制与解释

该产物提供了可复用的经验型 Rain layer，可用于暗室参数表生成。它没有估计绝对 RF 衰减、LOS 概率、失锁概率，也不能证明因果性的雨效应。canonical GOOD/POOR 质量配置仍是原有质量状态模型；Rain layer 与该质量状态分开使用。Highway/Open 的 Rain 证据尤其稀疏，所有天气分布仍存在 run/scene 相关性限制。

此前的 r1、r2、r3、r4 namespace 均保留为诊断 artifact，不是最终推荐 namespace。没有删除或覆盖任何旧 artifact。
