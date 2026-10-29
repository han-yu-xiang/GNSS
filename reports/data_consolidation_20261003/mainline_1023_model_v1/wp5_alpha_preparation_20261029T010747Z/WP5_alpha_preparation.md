# WP5 复数 alpha 导出与路径属性整合：准备阶段记录

核查时间：2026-10-29 09:14:25（Asia/Shanghai，UTC+08:00）
状态：IN_PROGRESS（实现候选已补充，尚未运行 MATLAB 测试；无 alpha 真实导出）
工作树：C:\Users\Jing_\.codex\worktrees\gnss-cir\GNSS_Multipath_Project
分支/HEAD：review/gnss-mainline-cir-model-20261022 / c748c2554ba09eff4dc3653d813ff92bead9599c

## 1. 范围与保护

本轮只检查小型 CSV、MATLAB 源码及 JSON 运行/relocation 凭据；没有读取、加载或反序列化 Stage2 MAT、HDF5、raw IQ 或 CIR 科学载荷，没有启动 MATLAB/SAGE/CIR，也没有修改 Task 5。Task 5 的 MATLAB 当前仍在运行，故 MATLAB 测试和真实 alpha 导出明确为 NOT_RUN。

WP1–WP3、Task 5 release/队列及已有科研结果未改。当前工作树已有多项 WP2/WP3 及计划文件未跟踪成果；它们全部保留。没有提交或推送。

## 2. Stage2 alpha 的实际含义

源码 scripts/sage_pipeline/run_nav_sage_pipeline.m 的 Stage2 路径求解使用每个 40 ms 窗口的 nav-wiped 复数 IQ。normalizeSignal 先减复数均值，再按该窗口复数 IQ 的 RMS 归一化。局部路径 replica 由窗口本地的码延迟和多普勒构造；时间索引从窗口起点归零。路径复系数由复数最小二乘直接解得：

alpha = replicas \ observed

因此这不是从相对功率反推的系数，也不是绝对校准接收电压。其幅度以窗口归一化信号为参考。Stage2 的路径排序按延迟样点升序，path_id 从 1 开始；当前实现中 path_id=1 是相对功率参考路径。相位为 angle(alpha) 的弧度主值。

源码用同一窗口的 alpha 计算：

relative_power_db = 10 log10(max(|alpha_i|^2, realmin) / max(|alpha_1|^2, realmin))

这验证的是导出映射及代数一致性，不是独立功率测量。由于每窗独立去均值、RMS 归一化及本地时间/replica 参考，不能据此声称不同窗口或不同 run 的 alpha 相位可相干比较；跨 PRN/run 的幅度也不是绝对接收功率。接收机增益、前端校准与同步差异未由此流程消除。

## 3. 数据总体与试点候选

V0 冻结抽取和 WP2/WP3 清单引用 83 个 run、13 个 scene、7,847 个 Stage2 已选窗口及 8,914 条 MPC。现有 CSV 的 (run_id,window_id,path_id) MPC 身份唯一；窗口表保留 7,847 个已选窗口，包括 mpc_count=0 的 3,574 个窗口。该总体条件于 Stage2 选择；不得把未选 Stage0 窗口补成零 MPC。零 MPC 的已选窗口留在独立的窗口表，不应伪造 alpha 路径行。

为将来单 run 真实 alpha pilot，选定候选：

- run：run_20261003_F1023_V70_D0117_P2_G32_ch11
- 已完成 Stage2 来源目录：E:\GNSS_Multipath_Project\scenes\F1023_V70_D0117_P2\sage_results\rerun_20261003_frozen_v3\G32_ch11
- Stage2 MAT：stage2_nav_sage_L1_L4.mat（仅查文件元数据/relocation receipt，未读载荷；文件 167,100 bytes）
- 路径 CSV：stage2_selected_paths.csv（344 行，117 个窗口：31 个单路径、86 个多路径窗口）
- relocation receipt 声明 MAT SHA-256：fac53e460ac6f89e55e03bed3bacdfc4932b7eb00c246f9df66572e5465419f3；路径 CSV SHA-256：845ba8379c80596b1248441e8b9ceeb18207c1b60a20361f0b5d6a1f271dd6b3。这是 receipt 中记录的值，本轮未重算这两个文件的 SHA。
- 最小窗口样本：window 38，selected_L=1, mpc_count=0；window 1007，selected_L=4, mpc_count=3。两窗口身份及路径顺序来自已存在的 Stage2 CSV。检查到该 run 的 227 条 MPC 与其路径 CSV 中 is_multipath=1 的 (window_id,path_id) 集合完全相同。

此候选覆盖直接路径和多路径窗口；在 pilot 前仍须重新读取该完成 run 的小型凭据，确认来源 SHA/身份及输出命名空间，真实 exporter 只应在 Task 5 MATLAB 空闲后执行。

## 4. 代码适配

候选实现仍处于当前科研分支工作树、尚未纳入提交。改动集中于：

- scripts/channel_modeling/export_stage2_complex_alpha.m
  - 按 Stage2 path CSV 原行顺序输出，每个输入路径恰好一行；要求窗口内路径 ID 完整为 1:selected_L，拒绝重复键。
  - alpha 只从 stage2Fits.models{selectedOrder}.paths(path_id).alpha 读取；缺失/不唯一/模型顺序不符/alpha 非有限时输出 alpha_status=MISSING、NaN 数值及枚举原因，不把对应路径删掉。
  - 对可用 alpha 输出实部、虚部、幅度和弧度相位；保留原 Stage2 数值列，并记录 run/scene/PRN/channel、冻结 SAGE SHA、Stage2 MAT 与路径 CSV SHA/源路径及归一化提示。SHA 由调用方从已核验凭据提供，本 exporter 只校验格式并记录，不自行重算文件哈希。
  - 对照 Stage2 relative_power_db 计算代数检查，标为 PASS、MISMATCH 或未检查原因；不因 mismatch 改写科学列或丢行。
- scripts/channel_modeling/build_mpc_modeling_ledger.m
  - 仍保留每条 Stage2 输入 MPC；要求每个 MPC 的精确 alpha 键及同窗 path 1 参考存在。
  - 允许 alpha 导出中额外存在 path 1 直接路径行（包括已选但零 MPC 窗口）；其余无法映射的额外非直接路径拒绝。
  - 校验 alpha 组成量、missing reason、run provenance 与 Stage2 relative-power check 状态；将 missing 状态/原因和源路径传递进 MPC ledger。不得将缺失 alpha 的 MPC 删除。
- 定向 MATLAB 测试文件各有 4 项 exporter 用例、3 项 ledger 用例，覆盖多路径/单路径、缺失/非有限 alpha、relative-power mismatch、重复身份、输出冲突、missing alpha 行保留及歧义 Stage3 映射。

这些测试尚未执行，不记作 PASS。静态阅读也不构成 MATLAB 语法或运行正确性的证明。

## 5. 试点数据隔离与验收草案

Task 5 完成且不存在 MATLAB worker 后，使用单独的新目录导出以上候选 run，绝不覆盖 run 原目录或旧 pilot。运行前重新核对 receipt 声明的源文件 SHA、run_id、scene/PRN/channel、sample rate 与 frozen SAGE SHA。只加载一个已完成 run 的 Stage2 MAT；输出完整 344 个路径行，并逐项核验：

1. 窗口/路径键唯一，所有 117 个窗口的 path_id=1:selected_L 完整保留，且路径 CSV 的 Stage2 属性逐列不变；
2. alpha 可用/缺失数量及每个缺失原因均有明细；不删除任何 MPC；
3. alpha_real + j alpha_imag、hypot(real,imag)、angle(alpha) 一致；
4. 有可用直接路径 alpha 时，重算相对功率与 Stage2 relative_power_db 比较；保留所有 mismatch；
5. 输出身份、源文件 SHA/路径、release/source pin 和 receipt 相互一致；
6. 对 Stage2 7,847 窗口账本仅做身份关联；零 MPC 已选窗口按原 mpc_count 表保留，而未选 Stage0 不补零。

试点先通过后再决定其余已完成 run 的只读顺序导出；不要因为单个 pilot 成功就自动开始大批量生产。本轮没有执行上述 MAT 读取或试点导出。

## 6. Task 5 独立状态点

2026-10-29 09:14:25 +08 的只读进程检查看到 release mainline_1023_cir_v1_20261028T120447205Z_task5successor43r1 的 Coordinator PowerShell PID 17124、worker PowerShell PID 33048，以及 MATLAB launcher/worker PID 17628/47344。命令行显示当前任务为 run_20261003_F1023_v90_D0117_P7_G32_ch5，MATLAB 于 09:04:56 +08 创建；因此本轮未运行 MATLAB 测试。

2026-10-29 09:10:01 +08 hourly 快照标记 FRESH（相邻 30 分钟报告 09:05:01，年龄 5 分钟），audit RUNNING，79/80 PASS（37 继承），current G32/ch5、next G18/ch9；近一小时新增 3 PASS，最近 PASS 为 G29/ch11 @ 09:04:26 +08。快照报 E 盘剩余 268.7 GiB、最近一小时 storage errors 为 0、completion/stop receipts 均 absent。09:14 进程命令行与快照的 current run 相符。此为最新时间点证据，不替代独立 audit/receipt 验收；没有进行任何生产干预。

## 7. Git 与结论边界

本轮确认分支为 review/gnss-mainline-cir-model-20261022，HEAD 为 c748c2554ba09eff4dc3653d813ff92bead9599c，origin 跟踪分支同步。candidate 文件和既存 WP2/WP3 文件原为未跟踪，本轮保留；没有暂存、提交、推送或修改 main。

WP5 当前只到“静态实现准备”。没有真实 alpha 数据、MATLAB 测试结果、独立 alpha QA 或 WP5 验收。
