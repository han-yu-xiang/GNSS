# 10.23 MHz 原始采集 Scene 环境信息人工确认清单

本清单只整理 scene 级原始采集文件与 PRN 映射，供人工补充采集环境信息。程序没有根据文件名、scene ID、PRN 或路径推断环境类型、道路类型或车速；下列三个字段必须由了解真实采集过程的人员填写。

## 审计范围与来源

- 生产 inventory：`dataset_generation_logs/production_planning_10mhz_20260812/production_inventory_10MHz.csv`
- 生产 manifest：`dataset_generation_logs/production_planning_10mhz_20260812/production_task_manifest_10MHz_v1.json`
- 总 inventory：`dataset/dataset_inventory.csv`
- scene metadata：`scenes/<scene_id>/metadata.json`
- raw 路径来源：metadata 中记录的 raw IQ 路径，并与 inventory/production inventory 交叉核对。
- raw 文件检查：仅读取文件系统存在性和 `stat` 文件大小；没有打开或读取任何 `.bin` 内容，也没有重新计算 raw 内容 hash。
- `PRN` 数量和列表来自 production inventory 的全部 10.23 MHz scene-PRN 行；生产 manifest 是已通过生产规划门禁的 67 个任务子集，因此未用 manifest 子集替换完整 scene 任务清单。

## 覆盖摘要

- 10.23 MHz 唯一 scene：13
- 10.23 MHz production inventory scene-PRN 行：83
- production manifest 中的 10.23 MHz 任务：67
- `dataset/dataset_inventory.csv` 总 scene：19
- `dataset/dataset_inventory.csv` 中的 10.23 MHz scene：13
- 实际唯一 raw `.bin` 文件映射：13
- 13 个 10.23 MHz scene 均有存在且非零的 raw 文件；metadata、canonical inventory 与 production inventory 的 raw 路径一致，记录的文件大小与文件系统 `stat` 一致。
- 未发现 inventory scene 缺失 raw 映射。
- 未发现无法映射到 scene 的 raw 文件。

## 人工填写规则

每个 scene 需要人工确认并填写：

- `environment_type`：例如真实采集环境类别；不得由程序推断。
- `road_type`：例如道路/路段类型；不得由 scene 名称推断。
- `vehicle_speed`：真实采集车速或人工确认的速度信息；不得由文件大小、场景命名或轨迹文件自动替代。
- `notes`：采集人员认为有必要记录的环境说明。

CSV 对应字段位于 [`scene_environment_annotation_list.csv`](../dataset_generation_logs/production_planning_10mhz_20260812/scene_environment_annotation_list.csv)，目前 `environment_type_to_fill`、`road_type_to_fill`、`vehicle_speed_to_fill`、`notes_to_fill` 全部留空。

## Scene 清单

### F1023_V120_D0121_P2

- 原始文件：`F1023_V120_D0121_P2.bin`
- 路径：`E:\AAGNSSSDR_input\raw_data\F1023_V120_D0121_P2.bin`
- 文件大小：24,612,241,920 bytes
- 采样率：10.23 MHz（metadata `10230000` Hz）
- 对应 PRN：G03, G06, G11, G12, G19, G24, G25, G28, G29, G32
- 需要确认：`environment_type`、`road_type`、`vehicle_speed`、`notes`

### F1023_V70_D0117_P2

- 原始文件：`F1023_V70_D0117_P2.bin`
- 路径：`E:\GNSS_Multipath_Project\scenes\F1023_V70_D0117_P2\raw\F1023_V70_D0117_P2.bin`
- 文件大小：2,512,257,536 bytes
- 采样率：10.23 MHz（metadata `10230000` Hz）
- 对应 PRN：G06, G11, G12, G25, G28, G29, G32
- 需要确认：`environment_type`、`road_type`、`vehicle_speed`、`notes`

### F1023_V70_D0117_P4

- 原始文件：`F1023_V70_D0117_P4.bin`
- 路径：`E:\AAGNSSSDR_input\raw_data\F1023_V70_D0117_P4.bin`
- 文件大小：2,648,048,128 bytes
- 采样率：10.23 MHz（metadata `10230000` Hz）
- 对应 PRN：G11, G12, G25, G28, G29, G31, G32
- 需要确认：`environment_type`、`road_type`、`vehicle_speed`、`notes`

### F1023_V70_D0120_P1

- 原始文件：`F1023_V70_D0120_P1.bin`
- 路径：`E:\AAGNSSSDR_input\raw_data\F1023_V70_D0120_P1.bin`
- 文件大小：3,657,957,888 bytes
- 采样率：10.23 MHz（metadata `10230000` Hz）
- 对应 PRN：G18, G26, G27, G29, G31
- 需要确认：`environment_type`、`road_type`、`vehicle_speed`、`notes`

### F1023_V70_D0120_P5

- 原始文件：`F1023_V70_D0120_P5.bin`
- 路径：`E:\AAGNSSSDR_input\raw_data\F1023_V70_D0120_P5.bin`
- 文件大小：2,541,355,520 bytes
- 采样率：10.23 MHz（metadata `10230000` Hz）
- 对应 PRN：G16, G18, G23, G26, G27
- 需要确认：`environment_type`、`road_type`、`vehicle_speed`、`notes`

### F1023_V70_D0120_P7

- 原始文件：`F1023_V70_D0120_P7.bin`
- 路径：`E:\AAGNSSSDR_input\raw_data\F1023_V70_D0120_P7.bin`
- 文件大小：3,537,240,576 bytes
- 采样率：10.23 MHz（metadata `10230000` Hz）
- 对应 PRN：G16, G18, G26, G31
- 需要确认：`environment_type`、`road_type`、`vehicle_speed`、`notes`

### F1023_V70_D0120_P8

- 原始文件：`F1023_V70_D0120_P8.bin`
- 路径：`E:\AAGNSSSDR_input\raw_data\F1023_V70_D0120_P8.bin`
- 文件大小：2,493,841,920 bytes
- 采样率：10.23 MHz（metadata `10230000` Hz）
- 对应 PRN：G16, G18, G23, G26
- 需要确认：`environment_type`、`road_type`、`vehicle_speed`、`notes`

### F1023_V70_D0120_P9

- 原始文件：`F1023_V70_D0120_P9.bin`
- 路径：`E:\AAGNSSSDR_input\raw_data\F1023_V70_D0120_P9.bin`
- 文件大小：3,405,578,752 bytes
- 采样率：10.23 MHz（metadata `10230000` Hz）
- 对应 PRN：G05, G16, G18, G23, G26, G27, G28, G29, G31
- 需要确认：`environment_type`、`road_type`、`vehicle_speed`、`notes`

### F1023_V70_D0122_P1

- 原始文件：`F1023_V70_D0122_P1.bin`
- 路径：`E:\AAGNSSSDR_input\raw_data\F1023_V70_D0122_P1.bin`
- 文件大小：2,491,810,304 bytes
- 采样率：10.23 MHz（metadata `10230000` Hz）
- 对应 PRN：G12, G13, G14, G15, G17, G19, G22, G24
- 需要确认：`environment_type`、`road_type`、`vehicle_speed`、`notes`

### F1023_V70_D0122_P2

- 原始文件：`F1023_V70_D0122_P2.bin`
- 路径：`E:\AAGNSSSDR_input\raw_data\F1023_V70_D0122_P2.bin`
- 文件大小：5,097,652,736 bytes
- 采样率：10.23 MHz（metadata `10230000` Hz）
- 对应 PRN：G10, G12, G13, G15, G19, G23, G24
- 需要确认：`environment_type`、`road_type`、`vehicle_speed`、`notes`

### F1023_V80_D0117_P8

- 原始文件：`F1023_V80_D0117_P8.bin`
- 路径：`E:\AAGNSSSDR_input\raw_data\F1023_V80_D0117_P8.bin`
- 文件大小：2,609,840,640 bytes
- 采样率：10.23 MHz（metadata `10230000` Hz）
- 对应 PRN：G12, G25, G28, G29, G31, G32
- 需要确认：`environment_type`、`road_type`、`vehicle_speed`、`notes`

### F1023_v50_D0127_P1

- 原始文件：`F1023_v50_D0127_P1.bin`
- 路径：`E:\AAGNSSSDR_input\raw_data\F1023_v50_D0127_P1.bin`
- 文件大小：3,882,222,080 bytes
- 采样率：10.23 MHz（metadata `10230000` Hz）
- 对应 PRN：G11, G25, G28, G29, G31
- 需要确认：`environment_type`、`road_type`、`vehicle_speed`、`notes`

### F1023_v90_D0117_P7

- 原始文件：`F1023_v90_D0117_P7.bin`
- 路径：`E:\AAGNSSSDR_input\raw_data\F1023_v90_D0117_P7.bin`
- 文件大小：2,496,070,144 bytes
- 采样率：10.23 MHz（metadata `10230000` Hz）
- 对应 PRN：G11, G12, G25, G28, G29, G32
- 需要确认：`environment_type`、`road_type`、`vehicle_speed`、`notes`

## 异常与待人工复核项

本次只读审计未发现以下异常：

- inventory 中存在但找不到 raw 的 10.23 MHz scene：无
- raw 文件无法映射到 scene：无
- metadata sample rate 不是 10.23 MHz：无
- production inventory 与 canonical inventory/raw provenance 不一致：无
- production inventory 记录的 raw size 与当前文件系统 size 不一致：无

注意：raw 内容 hash 没有在本次任务中重新计算，因为任务明确禁止读取 raw IQ 内容；“存在且非零”不等同于内容 hash 已验证。

## 本次任务边界

- Experiment executed：否
- raw IQ read：否（仅文件系统 `stat`）
- MATLAB：否
- SAGE：否
- batch：否
- data/artifact modified：仅新增本清单 CSV 与本 Markdown；未修改 scene、metadata、inventory、SAGE 结果或 handoff。
