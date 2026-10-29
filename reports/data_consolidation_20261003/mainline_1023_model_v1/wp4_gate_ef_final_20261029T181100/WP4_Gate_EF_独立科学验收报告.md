# WP4 Gate E/F 独立科学验收报告

**验收日期：** 2026-10-29（Asia/Shanghai，UTC+08:00）

**最终汇总：** 2026-10-29 18:10:07–18:10:11 +08（10:10:07–10:10:11 UTC）

**结论：** Gate E=`PASS_WITH_LIMITATIONS`；Gate F=`PASS_WITH_LIMITATIONS`；WP4=`COMPLETED_WITH_LIMITATIONS`。

**边界：** 本报告完成 CIR/PDP 生产证据审计、全量载荷 read-back、Stage2 精确关联和窗口统计；不启动 WP6，不重跑 CIR，不改写冻结生产结果。

## 1. 总体结果

| 项目 | 实际核验结果 |
|---|---:|
| 冻结 run 身份 | 83 个唯一 run、13 个 scene |
| Task 5 正式 PASS | 80/80：43 个 successor release PASS + 37 个继承 PASS |
| 不计入正式 80 项的已保留验证 | 2 个 CIR pilot + 1 个历史 baseline read-back |
| Gate E 单 run 结果 | 82 `PASS` + 1 `PASS_WITH_LIMITATIONS`（旧 G28/ch1 baseline） |
| Gate F 单 run 结果 | 83 `PASS` |
| Stage0 窗口 / CIR snapshots / delay bins | 285,752 / 11,430,080 / 451 |
| HDF5 总体大小 | 129,896,466,978 bytes（约 120.976 GiB） |
| Stage2 窗口 | 7,847 个唯一 `(run_id, window_id)`；7,847/7,847 `CIR_PDP_VERIFIED` |
| Stage2 路径 | 16,761 个唯一 `(run_id, window_id, path_id)` = 7,847 个直达参考 + 8,914 个 MPC |
| Stage2 MPC—CIR/alpha 链接 | 8,914/8,914；缺失、额外、重复或错身份均为 0 |
| alpha / 相对功率一致性 | 16,761 路径均有可用有限 alpha；全路径状态与 MPC 独立重算均通过 |
| PDP 重算 | 最大绝对差 = 0；最大相对差 = 0 |
| PDP 边界峰 | 63/7,847 窗口（0.8028546%），全部保留并报告 |
| 最终异常表 | 0 条异常记录 |

正式生产计数只按 80 个 PASS 任务计算。旧失败 release 没有作为成功来源重复计数；pilot 和 baseline read-back 保留为独立证据，不增加正式生产分母。

## 2. 来源、身份与 Gate E

审计目标 release 为 `mainline_1023_cir_v1_20261028T120447205Z_task5successor43r1`，release request SHA-256 为 `1b95146f42a2383f26bbef0bfc1679f9096f3778e67c51fa765af953f04474df`。批次 completion receipt 为 PASS，SHA-256=`c1206c5e900e12db932eefa2b629b051a1efac9013917149f7c166532b8415d8`。其中 successor 当前 release 43/43 PASS，加上历史继承 37 项，累计 80/80。冻结 cohort SHA-256=`287e891fae0cd294a85c073080611a19b7389ece46240b89cb1d5dab4df90229`。

Stage2 ledger SHA-256=`bbb8cac8338194b5527e00812a6547129a58466cc5fdd7db36b8c44bba01e551`；WP5 全路径 alpha ledger SHA-256=`def2e1e249af309a5114c100d0630299ebd955cefef6e051407fecb68e5493d7`；WP5 input manifest SHA-256=`9a914f93ae0dd4aa5c75c53928d89a69ec8bdab685fd739e1355b635b5926b50`；WP5 provenance sidecar SHA-256=`54b7136ac9c4db33569bd4a43308c4571429e228dcaf441d2ee6c546ae72d89b`。审计清单逐项核对 run/scene/PRN/channel、request、Stage0/Stage2 来源、receipt、HDF5 结构及哈希状态。82 个 HDF5 有历史 receipt pin；没有把旧失败批次当作通过。

### 旧 G28/ch1 baseline 的限定验收

身份 `run_20261003_F1023_V70_D0117_P2_G28_ch1` 使用 `EXISTING_BASELINE_READBACK`，其旧 receipt SHA-256=`a566b4a70a23c85268f17189ebdc69d4ad8142bb3a9684f09fdf5efdb0752c60`。旧 receipt/request 未提供历史 cohort、Stage0 与 HDF5 SHA pin。现场核对显示 request SHA 与身份一致；冻结 SAGE SHA 与 WP5 manifest 一致；Stage2 CSV 由 manifest SHA 固定；邻接 Stage0 CSV 实测 SHA=`0a285872f2f0707b0ce21d379c57df9a69737e4a49c02c1d7a3b7790c2cd8277`，并逐窗与 HDF5 对齐；HDF5 实测 SHA=`73fc44e2a6c550f86030fcc40d2ec5a0c4a3ad30f099286831fd212f821ac53c`，但该 HDF5 没有历史 receipt pin。该项包含 898 个 Stage0 窗口、35,920 个快照、451 bins，PDP 最大绝对重算差为 0，Gate F 单 run PASS；Gate E 标记 `PASS_WITH_LIMITATIONS`，没有用事后观察哈希冒充历史 pin。

### 审计运行记录与 provenance 限制

- 全量审计首轮：2026-10-29 09:06:05–09:53:09 UTC（17:06:05–17:53:09 +08）。82 个 run 完成载荷审计；G28 因历史 metadata 缺少旧版 provenance 字段，在 HDF5 读取前被 fail-closed 拦下。首轮日志保留为失败审计记录，不被覆盖，也不据此单独宣称 83/83 通过。
- G28 定向补充：2026-10-29 09:59:05–09:59:10 UTC（17:59:05–17:59:10 +08），只读核验上述一个历史 baseline。
- 最终聚合：2026-10-29 10:10:07–10:10:11 UTC（18:10:07–18:10:11 +08），合并原 82 项与 G28 补充为 83-run 交付。
- 全量 audit runner 的 SHA 未在其进程启动时捕获，因此不能声称其精确运行时字节已由起始 SHA 证明。最终 manifest 将此字段明确记为 `NOT_CAPTURED_AT_PROCESS_START`。定向 supplement runner SHA=`99f776d0303f6620dbf9b2f5b88fb15766075e7a2fc2248e31c5d8d90059fff6`；流式 CIR/PDP auditor SHA=`a5e9a7734093510ecdccc2a9df477fcf022ccf7ce05b69c97b0a779f1866462c`；身份链接器 SHA=`48b9d048b511473a9ab8e3d7a9088606b36eab8f36413f50f201caa5eed31884`；SHA 工具 SHA=`a0a9ea810b46f8bd709080f981e6b80ff4923ccf8d1019722788b5a95c7537ac`；最终聚合器 SHA=`6ce105291ef05153822baee49674c184eb47b37d383f5f424fc1ca360beedec5`。

因此 Gate E 不是无条件 provenance PASS：G28 的历史输入 pin 缺口和 full-audit runner 起始 SHA 未记录均明示保留。它们没有导致可见身份、数据结构、数学或行数矛盾，但削弱了历史来源可追溯强度。

## 3. HDF5/CIR/PDP 的实际数据与数值检查

83 个 run 的 HDF5 均实际读取并以 64 行 chunk 处理；没有把整批 CIR cube 一次性载入内存。所需数据集包括 `cir_real`、`cir_imag`、`time_s`、`delay_samples`、`window_id`、`snapshot_index_in_window`、样本起点及导航/跟踪元数据，以及 `pdp_window_id`、`pdp_time_s`、`pdp_start_sample_zero_based`、`pdp_interval_count` 和 `pdp_power`。CIR 与 PDP 均为 451-bin；全体 CIR 行数为 `40 × 285,752 = 11,430,080`，每个 Stage0 窗口恰有按 1–40 排序的一毫秒快照。延迟坐标与冻结网格 `-5:0.1:40` 完全一致。

审计逐块确认复数实部/虚部有限、窗口 ID 属于对应 Stage0 表、每窗快照序号和样本起点连续、时间轴单调且相邻快照间隔 1 ms。PDP 行按 Stage0 窗口 ID、顺序、时间和样本起点逐项对应。独立重算定义为逐延迟 bin 对 40 个快照功率取算术均值：`PDP(w,k) = (1/40) Σₘ |CIR(w,m,k)|²`。冻结的 absolute tolerance 为 0、relative tolerance 为 `64·eps(1) = 1.4210854715202e-14`；实际全量逐元素最大绝对差和最大相对差均为 0。这里的独立性指审计器单独读取并重新计算，而非独立接收机或传播真值。

CIR 是从原始 IQ、NAV/code/Doppler wipe 与 Stage0 tracking inputs 得到的 code-domain correlation 表示，不是由 SAGE alpha 重构出的独立传播真值。PDP 是非相干的 40 个 1-ms CIR 快照功率均值，而不是跨快照复数相干叠加。

## 4. Stage2 精确关联和 alpha 数值核查

Stage2 左连接基于严格身份键：窗口用 `(run_id, window_id)`；路径和 alpha 用 `(run_id, window_id, path_id)`。对 7,847 个 Stage2 窗口全部保留一行；每个窗口唯一映射到对应 run 的 Stage0/CIR/PDP。对 16,761 条 Stage2 路径与 WP5 alpha ledger 逐键核对，所有路径键唯一、无缺少或额外键；8,914 个 `is_multipath=1` MPC 均保留在 MPC linkage 表中，没有因 alpha/CIR 状态过滤。7,847 个直达参考路径用于参考/归一化核对，不并入 8,914 MPC 数量。

另以独立 PowerShell 数值核验从实部/虚部重算 `|alpha|` 与 `angle(alpha)`，分别得到最大绝对差 `9.8533e-16` 和最大 wrapped phase 差 `7.9936e-15 rad`。对 8,914 MPC，以各自同窗直接路径为参考，独立重算 `10·log10(|alpha_mpc|² / |alpha_direct|²)` 并与 Stage2 `relative_power_db` 比较，最大绝对差 `1.1369e-13 dB`，不匹配为 0。Stage2 delay/Doppler/power 原值未由关联程序改写；所有 16,761 条路径的 alpha 数值检查与源相对功率状态均通过。

关联成功表示精确数据键、窗口轴与属性映射成立，不意味着跨窗口相位相干已验证、alpha 是绝对校准增益，或路径身份等同于物理反射体跟踪。

## 5. 窗口特征及逐场景覆盖

有效窗口表每个 Stage2 窗口一行，含相对单位 PDP 总功率/峰值、峰值 code-delay 坐标、功率质心、加权 RMS code-delay 宽度、负延迟侧功率比例和网格边界峰标志。`pdp_rms_width_code_delay_samples` 是冻结延迟坐标上的相关响应宽度；未被验证为物理多径 RMS delay spread。所有 63 个边界 bin 峰保留，未裁剪、移动网格或删除窗口。

| Scene | Runs | Stage2 窗口 | 已链接窗口 | MPC | 边界峰 |
|---|---:|---:|---:|---:|---:|
| F1023_V120_D0121_P2 | 13 | 841 | 841 | 104 | 54 |
| F1023_V70_D0117_P2 | 7 | 592 | 592 | 837 | 0 |
| F1023_V70_D0117_P4 | 7 | 761 | 761 | 1,093 | 0 |
| F1023_V70_D0120_P1 | 3 | 330 | 330 | 334 | 0 |
| F1023_V70_D0120_P5 | 5 | 483 | 483 | 671 | 2 |
| F1023_V70_D0120_P7 | 4 | 439 | 439 | 707 | 0 |
| F1023_V70_D0120_P8 | 4 | 447 | 447 | 442 | 0 |
| F1023_V70_D0120_P9 | 9 | 987 | 987 | 1,172 | 0 |
| F1023_V70_D0122_P1 | 8 | 842 | 842 | 1,429 | 0 |
| F1023_V70_D0122_P2 | 7 | 669 | 669 | 832 | 0 |
| F1023_V80_D0117_P8 | 5 | 449 | 449 | 471 | 1 |
| F1023_v50_D0127_P1 | 5 | 386 | 386 | 115 | 6 |
| F1023_v90_D0117_P7 | 6 | 621 | 621 | 707 | 0 |
| **总计** | **83** | **7,847** | **7,847** | **8,914** | **63** |

Stage2 已选窗口内 MPC 数量分布为 0/1/2/3/4+ = 3,574/1,412/1,081/1,780/0；其中 4,273 个已选窗口记录至少一个 MPC。`0 MPC` 仅表示该 Stage2 已选窗口的账本没有 MPC 行，不代表该窗口无物理多径；所有未进入 Stage2 的 Stage0 窗口仍不得补作零计数样本。由于 Stage0 窗口重叠，同场景窗口也不是独立观测。

## 6. 测试与复现证据

初始 MATLAB R2025a Update 1 定向测试在合成临时夹具运行，不读取真实 HDF5/MAT、不启动生产；22/22 PASS。随后独立审阅发现缺失 Stage2 属性列时验证器可能跳过比较，已提取并加固共享 CSV-schema 比较函数。修复前红测准确复现两种缺列情况未报错；修复后最新完整定向回归于 2026-10-29 10:41:26.6907659–10:42:32.1699371 UTC（18:41:26–18:42:32 +08）完成：6 个实现文件 `checkcode` 0 issues；6 个测试文件 25/25 PASS、0 FAIL、0 INCOMPLETE，退出码 0。覆盖 auditor 7 项、Stage2-CIR linker 7 项、alpha exporter 4 项、MPC ledger builder 3 项、streaming SHA helper 1 项和 schema guard 3 项。执行细节、命令及原始日志 SHA 见 `targeted_regression_evidence.md`；本机绝对路径日志保留在本地，不纳入共享 Git。

针对真实 Stage2 来源，随后以已修复的同一个生产比较函数对冻结输入作轻量只读复核：input manifest SHA=`9a914f93ae0dd4aa5c75c53928d89a69ec8bdab685fd739e1355b635b5926b50`；83/83 唯一 run 的源路径 CSV SHA 均匹配 manifest，所需身份及属性列齐全；83/83 与合并 Stage2 ledger 对照 PASS，最大属性差 0。复核时间 2026-10-29 10:46:16.9388266–10:46:43.4707598 UTC（18:46:16–18:46:43 +08），未读取任何 MAT/HDF5/CIR 载荷。机器记录见 `stage2_csv_schema_recheck.json`。该补充确认既有全量来源列 schema 与数值映射，不重跑全量 HDF5 audit，也未改变其数据结果。

可复现的轻量命令形式（在仓库根目录执行）：

```matlab
addpath(fullfile('scripts','channel_modeling'));
files = {'test_audit_gnss_code_domain_cir_pdp.m', ...
         'test_build_mainline_stage2_cir_gate_f_links.m', ...
         'test_export_stage2_complex_alpha.m', ...
         'test_build_mpc_modeling_ledger.m', ...
         'test_sha256_file_streaming.m', ...
         'test_mainline_stage2_path_csv_schema.m'};
paths = cellfun(@(f) fullfile('scripts','channel_modeling','tests',f), ...
                files, 'UniformOutput', false);
results = run(testsuite(paths));
passed = sum([results.Passed]);
failed = sum([results.Failed]);
incomplete = sum([results.Incomplete]);
assert(numel(results)==25 && passed==25 && failed==0 && incomplete==0);
```

全量 HDF5 audit 首轮和 G28 定向 supplement 的原日志分别保存在同级目录 `../wp4_gate_ef_20261029T090700Z/gate_e_f_execution.log` 与 `../wp4_gate_ef_g28_legacy_supplement_20261029T180000/gate_e_f_execution.log`；两者均已保留，不把首轮 G28 metadata 拦截抹去。原始 `execution_manifest.json` 与 `gate_e_f_finalization.log` 为本机保留、未纳入 Git；PR 中的来源清单和聚合记录使用 `execution_manifest_git.json` 与 `gate_e_f_finalization_git.log`。

## 7. 交付物与 SHA-256

最终权威机器可读汇总目录：`reports/data_consolidation_20261003/mainline_1023_model_v1/wp4_gate_ef_final_20261029T181100/`。

原始 `execution_manifest.json`、`gate_e_f_summary.json`、`gate_e_run_inventory.csv` 与原始 MATLAB 日志在隔离工作树本地保留，不纳入 Git；为避免公开本机用户名/工作树或机器卷路径，Git 提交 `execution_manifest_git.json`、`gate_e_f_summary_git.json`、`gate_e_run_inventory_git.csv`、`gate_e_f_finalization_git.log`、`targeted_regression_evidence.md` 和 `stage2_csv_schema_recheck.json`。sanitized 汇总保留科学字段和 SHA，inventory 仅将本机项目根路径前缀规范化为项目相对路径；行身份、顺序、数值和 receipt/output 哈希均未改变。

| 文件 | SHA-256 |
|---|---|
| `gate_e_f_summary.json`（原始本地文件，绝对路径不纳入 PR） | `1f10dca4be8f367f51790c770a1dcf6d822b6fd5f660c2f0c64ffcc7b5783b8d` |
| `gate_e_f_summary_git.json`（路径 sanitized；除两个路径字段外机器值完全一致） | `8866843231b6e391b3496907d4fef1f856a598b3466353cacf7f804aa29b8617` |
| `execution_manifest_git.json`（移除本机绝对工作树路径的提交副本） | `dbce99d6e717ddac60eaa564c3ae21ed394630b13d20dd0cdbd3b04351704e93`；源 manifest SHA=`fc7032fe8749210f28671a08f87344320f7ba24e3c4c5856fea6cb8ce437d35d` |
| `gate_e_run_inventory.csv`（原始本地文件，E: 绝对路径不纳入 PR） | `da34edfa275d2a31f53ee377da24e3036f329efa9a08d8b1fb12f940d1f38322` |
| `gate_e_run_inventory_git.csv`（83 行、字段和值一致，路径为项目相对路径） | `87aa16e031f144372b8b0b3810771046d9a5bff5dfe46f4d8f7258a2795a7916` |
| `stage2_cir_pdp_window_features.csv` | `258d5d70081d9ee6fd82a64b1a4f9c405180bc18cd49280b0e2b799d9a482bf4` |
| `stage2_mpc_cir_alpha_linkage.csv` | `8db941db20e684108d13583d67ee20cde543bf2a36ca01013d1288b48231c80b` |
| `gate_f_scene_summary.csv` | `5155602a058f83eb3147d5c1e6488346596753ecb21d72f726ba70ce3db35cd9` |
| `gate_e_f_anomalies.csv` | `a593bf80ac7dcbb76636737109dd16c82a89ac8efeda4f92c4109fffe0c62b6a`（0 data rows） |
| `gate_e_f_finalization.log`（原始本地日志，保留绝对工作树路径，不纳入 PR） | `8c552c7b60bf6a9707a055487001a0c67530649bfab4aeb9257b8094aa7ed03b` |
| `gate_e_f_finalization_git.log`（相对路径共享副本） | `b9e6a1cb187cca907afed685c7fe3cf6424aaa3e39681986ab2ceea534ae0c48` |
| `targeted_regression_live_20261029.log`（原始逐字节日志，仅本地保留，不纳入 PR） | `14245f3fb323ea0d57117f3d5f4fa28a310c04eb398d6e28106a2310b517e9f6` |
| `targeted_regression_evidence.md`（规范化路径的可复现记录，提交至 PR） | `afc79126cc0f974b21f4fbf852707ba50e28b37f72470000552672dd715a27e4` |
| `stage2_csv_schema_recheck.json`（独立审阅后的真实 83-run source schema/attribute recheck） | `6f680bc3827cd0158b60963c4275f6a1bda61e3d6e07053ce084220890f16dd4` |
| `../wp4_gate_ef_20261029T090700Z/gate_e_f_execution.log` | `87e390534c5f343b76904bafbe96fc8ef92c4c08bdc5931734458e30a47181cb` |
| `../wp4_gate_ef_g28_legacy_supplement_20261029T180000/gate_e_f_execution.log` | `5f6415ff7838bcba69a846a65b7cac0a2c6e5972e37bf555959fb8f54a5925c6` |

核心脚本：`scripts/channel_modeling/audit_gnss_code_domain_cir_pdp.m`、`build_mainline_stage2_cir_gate_f_links.m`、`run_mainline_1023_gate_ef_audit.m`、`finalize_mainline_gate_ef_baseline_supplement.m`、`sha256_file_streaming.m`。大型 HDF5 与源 MAT 不纳入 Git；逐 run 路径、receipt、大小和 SHA 状态列在 run inventory。WP5 alpha 完整数据仍保留在其独立 E: 输出目录。

## 8. 科学结论与使用范围

1. Gate E 的 83 个来源身份和输出均有可追溯记录；80 个正式 Task 5 PASS 与三个额外 pilot/baseline 的计数分开。G28 的历史 pin 缺失和 full-audit runner 起始 SHA 未捕获作为来源限制保留，因此 Gate E=`PASS_WITH_LIMITATIONS`。
2. Gate F 的 83 个 run HDF5 结构/数值 QA 均通过；Stage2 7,847 个窗口全部精确关联，8,914 个 MPC 与 WP5 alpha 一一对应，重算 PDP 与保存 PDP 数值一致。作为实现和数据内部一致性验收，Gate F=`PASS_WITH_LIMITATIONS`。
3. CIR 是 code-domain correlation，PDP 是窗口内非相干 snapshot-power 平均。`total/peak PDP power` 是相对单位；目前不存在足以称为绝对接收功率/标定增益的证据。
4. 输出 RMS code-delay width 不能直接称作物理传播 RMS delay spread。delay grid 的边缘峰（63 个，0.803%）说明有限窗口截断可能影响该统计；应在 WP6 中作为解释限制或敏感性标记，而不是删除或改网格。
5. 共享原始 IQ/Stage0 跟踪输入的内部 CIR/PDP 与 SAGE/alpha 一致性，不是外部信道真值验证。alpha 的身份匹配不验证跨窗口相位相干、物理反射体连续身份或绝对增益。
6. 本总体是 Stage2 条件选择后的 7,847 窗口和 8,914 MPC 候选集。重叠窗口不独立；不能将已选窗口的 0-MPC 状态解释为未选窗口的 0 MPC，也不推断无物理多径。

因此，WP4 可标记 `COMPLETED_WITH_LIMITATIONS`。WP6 所需的精确窗口级 CIR/PDP 特征和全路径 alpha 数据接口现已可用作经 Commander 授权后的输入；本验收不拟合任何模型、不确定最终特征选择、不验证跨窗口复相干，且没有启动 WP6。
