# 10.23 MHz Scene Metadata 覆盖检查报告

## 结论

已建立 10.23 MHz full SAGE production 的独立 scene metadata 层：

[`dataset_generation_logs/production_planning_10mhz_20260812/scene_metadata_10MHz.csv`](../dataset_generation_logs/production_planning_10mhz_20260812/scene_metadata_10MHz.csv)

该文件按唯一 `scene_id` 保存人工确认的采集环境、特殊条件、道路类别、人工测量速度和原始文件 provenance。它是新增的 metadata layer；本次没有原地修改任何 `scenes/*/metadata.json`，也没有修改 production manifest、execution request、SAGE 结果或其他实验 artifact。

## 覆盖检查

| 检查项 | 结果 |
|---|---:|
| production inventory 中 10.23 MHz 唯一 scene | 13 |
| scene metadata 行数 | 13 |
| metadata 覆盖 | 13/13 |
| 每个 scene 的 `scenes/<scene_id>/metadata.json` | 13/13 存在且 scene/sample rate 一致 |
| raw 路径与 metadata/inventory 一致 | 13/13 |
| raw 文件存在性与文件大小 | 13/13 一致；仅使用文件系统属性检查 |
| 20.46 MHz scene 纳入数量 | 0 |
| 历史未纳入 10.23 production 的 scene 纳入数量 | 0 |
| 缺失 scene metadata | 无 |
| inventory scene 无法关联 metadata | 无 |

production inventory 的 10.23 MHz 任务总数为 83 个；scene metadata 按 scene 去重，因此输出 13 行，而不是 83 行。PRN 数量和列表沿用既有 scene annotation 清单与 production inventory，不对 PRN 或 channel 做重新推断。

## 环境类别分布

| environment_class | scene 数量 |
|---|---:|
| Urban | 6 |
| Mountain/Valley | 3 |
| Highway/Open | 2 |
| Special Reflective | 2 |

## 速度分布

| vehicle_speed_kmh | scene 数量 |
|---:|---:|
| 50 | 1 |
| 70 | 9 |
| 80 | 1 |
| 90 | 1 |
| 120 | 1 |

速度字段按附件给出的人工采集记录规则，从 scene 标识中的 V 值写入，并将 provenance 固定为 `human_measurement_description`；这不是由 raw、轨迹或 SAGE 结果计算出的速度。

## 来源与字段语义

- 环境类别、特殊条件和人类描述：来自本次任务附件提供的人工确认采集记录。
- `road_type`：对附件人工描述进行明确、可审计的类别化记录；不是由 raw IQ、轨迹、elevation 或 SAGE 结果自动推断。
- raw 文件名、绝对路径、文件大小、采样率、PRN 列表和任务数：来自已存在的 `scene_environment_annotation_list.csv`、production inventory 和 scene `metadata.json` 的交叉核对。
- `metadata_source`：所有行均为 `human_measurement_description`。
- `annotation_source_file`：`dataset_generation_logs/production_planning_10mhz_20260812/scene_environment_annotation_list.csv`。
- 本次没有打开或读取任何 `.bin` 内容，也没有重新计算 raw 内容 hash；文件大小检查不等同于 raw 内容 hash 验证。

项目中未找到附件要求引用的 `SCENE_METADATA_GUIDE.md`；因此本报告不把不存在的指南当作事实来源，实际字段依据以附件中的人工确认信息及当前 production inventory/scene metadata 为准。

## 13 个 scene 摘要

| scene_id | environment_class | special_condition | road_type | speed (km/h) | PRN tasks |
|---|---|---|---|---:|---:|
| F1023_V120_D0121_P2 | Highway/Open | high speed highway environment | highway | 120 | 10 |
| F1023_V70_D0117_P2 | Mountain/Valley | valley terrain | valley road | 70 | 7 |
| F1023_V70_D0117_P4 | Mountain/Valley | mountain ascending road | mountain ascending road | 70 | 7 |
| F1023_V70_D0120_P1 | Urban | high-rise buildings | urban road | 70 | 5 |
| F1023_V70_D0120_P5 | Urban | low-rise residential area | urban residential road | 70 | 5 |
| F1023_V70_D0120_P7 | Urban | tram infrastructure and moving tram | urban tram road | 70 | 4 |
| F1023_V70_D0120_P8 | Urban | general urban road | urban road | 70 | 4 |
| F1023_V70_D0120_P9 | Special Reflective | bridge over wide water surface | bridge over water | 70 | 9 |
| F1023_V70_D0122_P1 | Urban | street environment | urban street | 70 | 8 |
| F1023_V70_D0122_P2 | Special Reflective | railway, communication tower and vegetation | urban road near railway | 70 | 7 |
| F1023_V80_D0117_P8 | Highway/Open | open road | open road | 80 | 6 |
| F1023_v50_D0127_P1 | Urban | rain condition | urban road | 50 | 5 |
| F1023_v90_D0117_P7 | Mountain/Valley | open mountain winding road | open mountain winding road | 90 | 6 |

## 任务边界

- production manifest：未修改。
- execution request：未修改或生成。
- existing SAGE/Pipeline/v3 artifact：未修改。
- scene 原始 `metadata.json`：未修改；仅做一致性读取。
- raw IQ 内容：未读取。
- MATLAB、SAGE、batch：均未运行。

## Handoff impact

新增了可供论文数据组织和后续 event/path 数据库关联使用的 10.23 MHz scene metadata layer，因此论文 handoff 需要记录“10.23 MHz scene metadata layer established”；没有改变 pipeline、执行状态或 artifact 保护规则，工程 handoff 不需要状态更新。
