# WP4 定向回归执行记录

- 执行时区：UTC；本地时区 Asia/Shanghai = UTC+08:00
- 开始：2026-10-29T10:15:41.3255873Z（18:15:41 +08）
- 结束：2026-10-29T10:16:07.0812323Z（18:16:07 +08）
- MATLAB：R2025a Update 1（本机安装路径不纳入共享记录）
- 退出码：0
- `checkcode`：5 个实现文件，0 issues
- 测试：22 total / 22 passed / 0 failed / 0 incomplete
- 结果来源：隔离的 synthetic/temp fixtures；无生产 HDF5/MAT 输入，无 CIR/SAGE 任务启动

执行入口（MATLAB batch；`<repo-root>` 表示执行时隔离工作树根目录）：

```text
matlab.exe -batch "cd('<repo-root>'); addpath(fullfile('scripts','channel_modeling')); files={'test_audit_gnss_code_domain_cir_pdp.m','test_build_mainline_stage2_cir_gate_f_links.m','test_export_stage2_complex_alpha.m','test_build_mpc_modeling_ledger.m','test_sha256_file_streaming.m'}; testPaths=cellfun(@(f) fullfile('scripts','channel_modeling','tests',f),files,'UniformOutput',false); sourceFiles={'audit_gnss_code_domain_cir_pdp.m','build_mainline_stage2_cir_gate_f_links.m','run_mainline_1023_gate_ef_audit.m','finalize_mainline_gate_ef_baseline_supplement.m','sha256_file_streaming.m'}; issueCount=0; for k=1:numel(sourceFiles), issues=checkcode(fullfile('scripts','channel_modeling',sourceFiles{k}),'-id'); issueCount=issueCount+numel(issues); end; fprintf('CHECKCODE_FILES=%d ISSUES=%d\n',numel(sourceFiles),issueCount); assert(issueCount==0,'Static check reported issues'); results=run(testsuite(testPaths)); passed=sum([results.Passed]); failed=sum([results.Failed]); incomplete=sum([results.Incomplete]); fprintf('TARGETED_TESTS_TOTAL=%d PASSED=%d FAILED=%d INCOMPLETE=%d\n',numel(results),passed,failed,incomplete); assert(numel(results)==22 && passed==22 && failed==0 && incomplete==0,'Targeted suite acceptance failed');"
```

实际 stdout 摘要：

```text
CHECKCODE_FILES=5 ISSUES=0
test_audit_gnss_code_domain_cir_pdp       7 passed
test_build_mainline_stage2_cir_gate_f_links 7 passed
test_export_stage2_complex_alpha          4 passed
test_build_mpc_modeling_ledger            3 passed
test_sha256_file_streaming                1 passed
TARGETED_TESTS_TOTAL=22 PASSED=22 FAILED=0 INCOMPLETE=0
EXIT_CODE=0
```

原始逐字节 PowerShell/MATLAB 输出和包含本机绝对工作树路径的实际命令保留在本地文件 `targeted_regression_live_20261029.log`（SHA-256=`14245f3fb323ea0d57117f3d5f4fa28a310c04eb398d6e28106a2310b517e9f6`），不纳入共享 Git PR。此文件是本记录的来源；执行、测试和退出码均未变更。

## 独立审阅后的 fail-closed schema 修复与复测

独立审阅发现源 Stage2 CSV 或已汇总 Stage2 ledger 缺少属性列时，旧比较函数会跳过该列仍可能报告 PASS。将现有比较逻辑提取到共享函数 `verify_mainline_stage2_path_csv_attributes.m`，审计入口调用该函数，并要求源 CSV 与 ledger 都含 `window_id`、`path_id`、`is_multipath`、`delay_samples`、`excess_delay_samples`、`doppler_offset_hz`、`relative_power_db`。缺失必需列现在以 `GNSS:SAGE:GateEStage2CsvSchemaMismatch` fail closed。

TDD 红测（修复前）：完整 schema 对照通过 1 项；源 CSV 缺 `relative_power_db` 与 Stage2 ledger 缺该列两项均因没有抛出预期 schema 错误而失败，准确复现审阅发现。原始红测日志 SHA-256=`d14f1801a4d00479fd4430db89b2554809e1c08d1d1860782b2232091963f6d2`，仅本机保存，不进入 PR。

修复后 MATLAB R2025a Update 1 回归：2026-10-29 10:41:26.6907659–10:42:32.1699371 UTC（18:41:26–18:42:32 +08），`checkcode` 6 个实现文件、0 issues；六个测试文件 25/25 PASS、0 FAIL、0 INCOMPLETE，退出码 0。组成：CIR/PDP auditor 7、Stage2/CIR linker 7、alpha exporter 4、MPC ledger builder 3、SHA helper 1、Stage2 CSV schema guard 3。精确可复现入口：沿用上方命令，将 `test_mainline_stage2_path_csv_schema.m` 与 `verify_mainline_stage2_path_csv_attributes.m` 加入测试/实现文件清单，测试总数断言改为 25。绿色原始日志 SHA-256=`90132b3e4f486cc1d41bcb25c13d8980d8e42c836843d2bac3b0846980f37772`，包含本机路径，仅本机保存。

随后对真实、冻结的 Stage2 路径 CSV 做轻量只读复核（不读 MAT/HDF5/CIR 载荷）：输入 manifest SHA-256=`9a914f93ae0dd4aa5c75c53928d89a69ec8bdab685fd739e1355b635b5926b50`；83/83 个唯一 run 的路径 CSV 当前 SHA 均匹配 manifest，必需列均存在；用修复后的同一个生产比较函数逐 run 对照合并 Stage2 ledger，83/83 PASS，最大属性差 0。复核时间：2026-10-29 10:46:16.9388266–10:46:43.4707598 UTC（18:46:16–18:46:43 +08）。结果机器记录为 `stage2_csv_schema_recheck.json`。原始 stdout 日志 SHA-256=`6230648b6c99ff5fb2d6d7099ecfebf8bb057ed29aedb350b51efcd8365606a5`，仅本机保存。

这项补充没有重读 HDF5/MAT，没有改变既有表格数值；它验证了当时全量审计所用的 83 份 Stage2 CSV 所要求的列和属性映射，并加固后续审计对 malformed schema 的拒绝行为。初次两条诊断命令因 MATLAB batch 引号及默认导入选项不适用于该 manifest 而在比较前退出；修正后的正式复核如上通过，相关原始日志均保留于本地审计目录。
