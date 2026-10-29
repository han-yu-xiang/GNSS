# WP5 全量复数 alpha 导出与独立科学验收

**状态：`COMPLETED_WITH_LIMITATIONS`（83-run 数据导出及本报告范围内的独立验收通过）**
**核验日期：** 2026-10-29（Asia/Shanghai）
**全量数据目录：** `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\mainline_1023_wp5_alpha_full_83run_20261029T055629Z\`

## 结论

冻结 Mainline Stage2 总体的 83/83 run 均完成串行 alpha 导出；独立验证也为 83/83 PASS。16,761 条 Stage2 路径全部保留，其中 7,847 条直达参考和 8,914 条 MPC；有效复数 alpha 为 16,761，缺失 0、非有限值 0。路径身份、窗口内顺序、源 Stage2 参数及相对功率关系均通过核验，未发现重复、缺失、额外、跨 run 或错序记录。

这表示该数据集可作为 WP6 后续分析的候选复数路径属性输入；不表示 WP4 Gate E/F 已通过，也不表示完整 CIR 特征关联或 WP6 模型已完成。WP5 保留 `COMPLETED_WITH_LIMITATIONS`，主要限制是 5 个 Stage2 MAT 缺少历史逐文件 SHA pin、alpha 采用窗口归一化且跨窗口相位参考未验证。

## 冻结总体、身份与输入来源

| 项目 | 实际证据 |
|---|---|
| SAGE runs / scenes | 83 / 13 |
| Stage2 选中窗口 | 7,847 |
| MPC / 直达参考 | 8,914 / 7,847 |
| 全部 Stage2 路径记录 | 16,761 |
| Stage2 全 MPC 账本 | `E:\GNSS_Multipath_Project\dataset_generation_logs\channel_modeling\mainline_1023_model_v1_20261023T135341Z\stage2_ledger.csv`，SHA-256 `bbb8cac8338194b5527e00812a6547129a58466cc5fdd7db36b8c44bba01e551` |
| 冻结 cohort | SHA-256 `287e891fae0cd294a85c073080611a19b7389ece46240b89cb1d5dab4df90229` |
| Stage4 pin manifest | SHA-256 `32c10789efefe4e87cabee4ac8978cd36a4a132f4d3b5640c8e4b8b0851a635d` |
| 冻结 SAGE runner | `scripts/sage_pipeline/run_nav_sage_pipeline.m`，SHA-256 `bffc123c97af77f0a797f417d3866e9a34feab7729c5c1575352f53bc3571b9c` |
| 本次输入 manifest | SHA-256 `9a914f93ae0dd4aa5c75c53928d89a69ec8bdab685fd739e1355b635b5926b50` |

83 个 MAT 源文件中，78 个具有历史 receipt 中的逐文件 SHA pin；其余 5 个旧 receipt 没有逐 MAT SHA，执行前对当时可用的源 MAT 重算 SHA 并写入本次 manifest。83 个文件均通过本次输入校验，且独立复核未发现哈希变化。对这 5 个文件，本结果证明“本次处理的文件与本次 manifest 一致”，但不能追溯声称其 SHA 曾被历史 receipt 固定。

完整输入清单、源预检及 83-run 处理审计保存在上述全量数据目录的 `input_manifest.csv`、`source_preflight.json` 和 `run_export_audit.csv`。全量输出及逐 run 科学 CSV 仅保留在 E 盘科研数据目录，不纳入 Git。

## 导出实现与复数系数定义

批量入口 `scripts/channel_modeling/run_mainline_wp5_alpha_full_batch.m` 串行调用既有 `export_stage2_complex_alpha.m` 和 `build_mpc_modeling_ledger.m`。导出器逐行保留 Stage2 路径身份和原始属性；alpha 直接来自冻结 MAT 中 `stage2Fits.models{selectedOrder}.paths(path_id).alpha`，没有从相对功率反推系数，也没有补造相位。

冻结 SAGE 实现的 alpha 是以本窗口观测向量对本地延迟/多普勒副本矩阵做复数最小二乘得到的系数。输入先经过导航符号擦除、窗口去均值及 40 ms 窗口 RMS 归一化。导出列满足 `alpha_magnitude=abs(alpha)`、`alpha_phase_rad=angle(alpha)`（弧度主值）；Stage2 相对功率按同窗口参考路径核对：`10 log10(|alpha_l|^2 / |alpha_1|^2)`，与源 `relative_power_db` 的差值阈值遵循已验收实现的定义。该系数是局部归一化数据及副本参考下的相对 LS 系数，不是接收机校准后的绝对信道增益。

## 全量结果与独立验收

| 检查 | 实际结果 |
|---|---:|
| 导出 run / 独立验证通过 | 83/83 / 83/83 |
| 导出失败 / 预检拒绝 | 0 / 0 |
| 输出路径记录 / 唯一身份 | 16,761 / 16,761 |
| MPC / 直达参考 | 8,914 / 7,847 |
| 有效 alpha / 缺失 / 非有限 | 16,761 / 0 / 0 |
| 相对功率 PASS / mismatch | 16,761 / 0 |
| 路径身份、顺序、重复/遗漏/额外行错误 | 0 |
| 源 SHA 错误 | 0 |
| Stage2 时延、多普勒、功率等属性最大绝对差 | 0 |
| 独立重建复数分量最大绝对差 | `4.9960036108132044e-16` |

验证器 `scripts/channel_modeling/validate_mainline_wp5_alpha_full_batch.m` 不调用 exporter；它逐 run 重新读取 source `stage2Fits` 并独立按 `(run_id, window_id, path_id)` 重建 alpha，再核对全量冻结 Stage2 ledger、每 run 输出、合并输出、顺序、源属性及 alpha 数值。全量机器可读独立摘要为 `independent_validation_summary.json`，逐 run 细项为 `independent_validation_per_run.csv`（E 盘数据目录）。

报告仓库内的小型交付清单为本目录的 `per_run_output_manifest.csv` 和 `wp5_alpha_full_summary.json`。它们绑定每 run 输入身份、SHA pin 来源、行数、输出文件 SHA/字节数、alpha/功率状态及独立验证状态。组合 alpha CSV SHA-256 为 `eeb20d3f638cf937529922d2d932503e201ec92ba866eeb3d86e0dd3a91e97e9`（12,705,179 bytes）；组合属性账本 SHA-256 为 `def2e1e249af309a5114c100d0630299ebd955cefef6e051407fecb68e5493d7`（13,623,712 bytes）。E 盘完整 batch 目录共 180 个文件、52,927,454 bytes（约 50.48 MiB，包含逐 run 与合并 CSV、审计和日志）。

## 执行与测试证据

- MATLAB 定向测试最终运行：`matlab.exe -logfile <batch-root>\matlab_targeted_tests_commit_final.log -batch "addpath(genpath('<repo>\scripts\channel_modeling')); testFiles={fullfile('<repo>','scripts','channel_modeling','tests','test_export_stage2_complex_alpha.m'),fullfile('<repo>','scripts','channel_modeling','tests','test_build_mpc_modeling_ledger.m'),fullfile('<repo>','scripts','channel_modeling','tests','test_run_mainline_wp5_alpha_full_batch.m')}; results=runtests(testFiles); assertSuccess(results);"`。提交前最终重跑日志 `matlab_targeted_tests_commit_final.log` 报告 9/9 PASS（exporter 4、ledger 3、batch/validator 合成集成 2），失败 0、不完整 0、MATLAB 退出码 0。此前详细计数版本的日志 `matlab_targeted_tests_final.log` 也保留。
- 冻结总体预检：`py -3 scripts/channel_modeling/prepare_wp5_alpha_full_cohort.py ...`，创建独立输出目录中的 manifest 和 preflight；实际状态 `PREFLIGHT_PASS`，83 ready、0 rejected。命令和冻结 SHA 参数按同目录 `source_preflight.json`/`input_manifest.csv` 可复现。
- 串行全量执行：MATLAB batch 入口 `run_mainline_wp5_alpha_full_batch(projectRoot, outputRoot)`；审计时间范围 2026-10-29 05:58:38.232Z–06:00:04.610Z（UTC，按 83 条逐 run 记录），83 条串行记录 elapsed 合计 81.189 s；batch 汇总生成于 06:00:17.349Z。最终状态 `COMPLETE`。
- 独立验证：MATLAB batch 入口 `validate_mainline_wp5_alpha_full_batch(projectRoot, outputRoot, task6LedgerPath, expectedLedgerSha256)`，通过时生成 83/83 PASS；摘要时间 2026-10-29 06:04:30.691Z UTC。首次调用因命令传入的 ledger 路径错误而在读取输入时失败，未改动输出；纠正到实际冻结 ledger 路径后独立验收 PASS。两份日志均保留，失败调用不计作通过。
- 本次 Python 清单/预检定向测试提交前最终重跑 5/5 PASS，`py_compile` 通过；命令、UTC 起止时间、结果和退出码在仓库报告目录 `python_targeted_tests_commit_final.log`。清单生成器只读取既有小型审计 JSON/CSV 和导出 CSV，拒绝覆盖已有报告目录；未读取 MAT/HDF5 载荷。

## 科学解释范围与后续

全量结果支持：在各个 Stage2 选中窗口内，将真实 SAGE 复数路径系数与对应 `(run_id, window_id, path_id)`、超额时延、相对多普勒和相对功率共同描述，并作为 WP6 候选路径级输入。它不证明不同窗口间载波相位连续或可相干比较，不证明物理反射体路径跨窗口跟踪，不提供绝对接收增益，也不替代 CIR/PDP 的 Gate E/F 对照验收。样本仍是 Stage2 选择总体，不能把未选 Stage0 窗口解释为零 MPC。

**下一步唯一优先事项：** 在不改变本数据集的前提下，由 Commander 审阅此全量数据和独立验收，再决定是否批准 WP6 的 alpha/CIR 关联与模型工作。不得仅凭 WP5 完成自动启动 WP6；WP4 Gate E/F 仍是独立待验收项。
