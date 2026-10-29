# WP5 G32/ch11 复数 alpha 真实试点验收

核验时间：2026-10-29 13:19（Asia/Shanghai，+08）。本报告只覆盖两组定向 MATLAB 测试和一个已完成 SAGE run 的 alpha 导出；不代表 83-run 全量导出、WP4 Gate E/F 或 WP6 已完成。

## 结论

**单 run 真实试点：PASS。** 两个定向测试文件共 7 项测试全部通过。G32/ch11 的 Stage2 路径 CSV 有 344 条记录、117 个窗口，其中 117 条直达参考路径和 227 条 MPC。导出保留了全部 344 行；独立逐行映射得到 344/344 有效复数 alpha，227/227 个 MPC 均有有效 alpha，未发现缺失、非有限值、无法匹配或路径错位。344/344 条相对功率关系核对通过。Stage2 输入属性逐值保持不变。

本结果支持 WP5 进入受控的 83-run 全量 alpha 导出阶段；**本轮未启动全量导出**。单 run 结果不能替代逐 run 身份、缺失率、路径属性一致性及 provenance 验收。

## 输入身份和只读性

- run：`run_20261003_F1023_V70_D0117_P2_G32_ch11`
- 场景/卫星/通道：`F1023_V70_D0117_P2` / G32（PRN 32）/ ch11；采样率 10.23 MHz。
- 源目录：`E:\GNSS_Multipath_Project\scenes\F1023_V70_D0117_P2\sage_results\rerun_20261003_frozen_v3\G32_ch11`
- Stage2 MAT：`stage2_nav_sage_L1_L4.mat`，167,100 bytes，SHA-256 `fac53e460ac6f89e55e03bed3bacdfc4932b7eb00c246f9df66572e5465419f3`；与 relocation receipt 一致。
- Stage2 路径 CSV：`stage2_selected_paths.csv`，31,838 bytes，SHA-256 `845ba8379c80596b1248441e8b9ceeb18207c1b60a20361f0b5d6a1f271dd6b3`；与 relocation receipt 一致。
- 冻结 SAGE 脚本 SHA-256：`bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c`；与 relocation receipt 一致。
- 试点前后重新计算的三个源哈希一致；MAT 和原 Stage2 CSV 均未被写入或改动。仅读取已完成 run 的 167 KB Stage2 MAT 和小型路径 CSV；未运行 SAGE/CIR，也未读取 HDF5/raw IQ。

CSV 预盘点确认 344 个唯一 `(window_id,path_id)`、117 个窗口、31 个单路径窗口和 86 个多路径窗口。独立 Task 6 Stage2 ledger 的该 run 227 个 MPC 身份与 CSV 的 `is_multipath=1` 身份完全一致；其余 117 行为直达参考。

## 实际执行和证据

MATLAB：R2025a Update 1（`25.1.0.2973910`）。

1. 定向测试最终通过运行：`matlab.exe -batch "addpath('<repo>/scripts/channel_modeling'); addpath('<repo>/scripts/channel_modeling/tests'); results=runtests({'test_export_stage2_complex_alpha.m','test_build_mpc_modeling_ledger.m'}); disp(table(results)); assertSuccess(results);"`。2026-10-29 13:10:11.820 +08 开始，13:10:52.766 +08 结束，退出码 0；4 项 exporter 测试与 3 项 ledger 测试均 Passed，Failed/Incomplete 均为 0。完整输出：`matlab_targeted_tests_final.txt`；早期诊断运行输出分别在 `matlab_targeted_tests_diagnostic1.txt`–`matlab_targeted_tests_diagnostic3.txt`。
2. 试点导出使用 `export_stage2_complex_alpha`，读取上述 MAT/CSV 并将结果写到本目录的独立文件 `G32_ch11_stage2_alpha.csv`；2026-10-29 13:13:05.314 +08 开始，13:13:27.853 +08 结束，退出码 0，耗时约 22.54 秒，输出 344 行。完整输出：`pilot_export_output.txt`。
3. 独立验证器 `validate_wp5_alpha_G32ch11_pilot.m` 不调用 exporter；它重新读取原 MAT、源 CSV 与导出 CSV，按真实 `stage2Fits`、`windowId`、`selectedOrder`、`path_id` 逐行独立提取和比对，并核验 run/scene/PRN/channel/sample-rate、三个输入 SHA 和归一化标记。最终强化复核于 2026-10-29 13:18:46.232 +08 开始，13:19:08.315 +08 结束，退出码 0。机器可读结果：`independent_validation_final.json`；完整 stdout：`independent_validation_final_output.txt`。此前 13:14 的验证也通过，其输出为 `independent_validation_pass1.txt`；首次验证的类型错误日志保存在 `independent_validation_diagnostic1.txt`。
4. MATLAB 定向测试的早期尝试分别暴露测试 helper 命名误识别、首次命令漏加源码路径，以及 ledger 解析错误；`build_mpc_modeling_ledger.m` 中该条件表达式括号已最小修正。最终 7/7 测试已在修正后重跑通过。全部尝试日志均保留在本目录；不以早期失败冒充 PASS。

导出 CSV：263,959 bytes，SHA-256 `4b786b762216da16e0196bf5965de34c5e481116a74184e7ed9dd75b7625c7ed`。

## 独立数值验收

| 检查 | 实际结果 |
|---|---:|
| Stage2 路径总行 / 唯一键 | 344 / 344 |
| 窗口数 | 117 |
| MPC / 直达参考行 | 227 / 117 |
| 有效 alpha / 缺失或无效 alpha | 344 / 0 |
| MPC 有效 alpha / 缺失或无效 | 227 / 0 |
| 相对功率对照 PASS / MISMATCH / 未检查 | 344 / 0 / 0 |
| 最大实部、虚部、幅度绝对差 | 分别 `5.00e-16`、`4.17e-16`、`5.00e-16` |
| 最大相位包裹差 | `4.89e-15 rad` |
| Stage2 delay、Doppler、relative-power 等源属性最大差 | 全部 0 |

候选窗口 38 为 `selected_L=1`，仅 path 1 直达参考、0 个 MPC；窗口 1007 为 `selected_L=4`，路径 1–4 均保留，其中 paths 2–4 为 3 个 MPC。两者均按原始窗口和路径身份导出，没有用路径数或 alpha 状态过滤记录。

## 科学解释边界

冻结 SAGE 源码中，观测先经过导航符号擦除、窗口去均值和 RMS 归一化；Stage2 对本地 C/A 延迟与多普勒副本组成的矩阵执行 `alpha = replicas \\ observed`。每个窗口的副本时间索引从本地 0 开始，因而 alpha 是该窗口归一化观测下、相对于本地 replica 约定的复数 LS 系数。它不是绝对接收电压或已校准信道增益；本次未审计接收机前端校准。

相位以弧度保存为主值 `angle(alpha)`。它适用于本次窗口内的复数路径描述；由于窗口 RMS/均值归一化、局部时间/副本参考及跨窗口载波相位连续性未被验证，不能据此宣称跨窗口相干演化或相位连续性模型有效。相对功率与 Stage2 每窗口路径系数平方幅度相对 path 1 一致；不应将其解释为绝对功率。

## 状态与下一步

- WP5：`单 run 真实试点 PASS；全量导出待执行/验收`，不是 WP5 完成。
- Task 5：本轮前后只读复核均为 successor audit `COMPLETE`、43/43 新任务 PASS，连同 37 项继承为 80/80；completion receipt `PASS`。没有 CIR/Coordinator/MATLAB 生产进程。该状态不代表 Gate E/F 已通过。
- 唯一优先事项：在同一冻结 Stage2 总体上执行受控的 83-run 全量 alpha 导出，每个 run 使用独立输入身份并保留所有 Stage2 路径/缺失原因；完成全量键覆盖、科学属性一致性、缺失分类和 receipt/provenance 独立验收后，再决定后续建模关联。不得将本次 1-run PASS 代替全量验收。
