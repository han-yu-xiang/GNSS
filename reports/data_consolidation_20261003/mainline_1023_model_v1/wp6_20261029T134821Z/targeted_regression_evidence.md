# WP6 定向验证执行证据

所有时间为 UTC；项目本地时间为 UTC+08。日志均位于本结果目录。测试未读取大型 MAT/HDF5/raw-IQ 载荷，也未修改冻结输入或生产结果。

| 检查 | 实际命令/方式 | 起止时间 (UTC) | 结果 |
|---|---|---|---|
| WP6 定向单元/runner/validator 测试（最终，含多路径不可评分回归） | `python -m unittest discover -s scripts/channel_modeling/tests -p test_mainline_stage2_wp6.py -v` | 2026-10-29 14:45:05.6472873–14:45:11.6855291 | 33 tests, 33 pass, 0 fail, exit 0；完整输出：`wp6_focused_unittest_postreview_20261029.log`。较早的 32/32 pre-review 运行仍保留 |
| channel-modeling 全部测试（最终） | `python -m unittest discover -s scripts/channel_modeling/tests -p 'test*.py' -v` | 2026-10-29 14:45:28.4608139–14:45:50.9595981 | 216 tests, 216 pass, 0 fail, exit 0；完整输出：`channel_modeling_unittest_postreview_20261029.log`。较早的 213/215 次运行均保留，不作为最终结果 |
| Python 编译检查（最终） | `python -m py_compile scripts/channel_modeling/mainline_stage2_wp6.py scripts/channel_modeling/run_mainline_stage2_wp6.py scripts/channel_modeling/validate_mainline_stage2_wp6.py scripts/channel_modeling/tests/test_mainline_stage2_wp6.py` | 2026-10-29 14:46:05.4803399–14:46:05.7199915 | exit 0；输出：`wp6_py_compile_postreview_20261029.log`；较早编译记录亦保留 |
| 增强独立验证器（隔离写入新验证结果） | 对成功分析目录调用 `validate_result_package`；结果写入 `independent_validation_review_20261029.json`，不覆盖初次 `independent_validation.json` | 2026-10-29 14:29:22.5751045–14:29:52.1604863 | `PASS_WITH_LIMITATIONS`，exit 0；Git-safe 摘要：`independent_validation_review_20261029_git.json` |

独立验证器逐一核对 7,847 个 `(run_id, window_id)` 计数键及其源 scene/held-out scene，并从逐窗口预测重新计算 52/52 个 PDP `(scene, model, target)` MAE/RMSE 行及汇总。最大分数误差为 `1.78e-15`；最大独立延迟矩/功率和差异分别为 centroid `3.55e-15` samples、RMS `1.78e-15` samples、直接路径加 MPC 相对功率和 `5.68e-14`。输入 SHA 与固定 WP4 CSV 匹配；最终范围和散列见 `independent_validation_review_20261029_git.json`。原始验证器终端日志与原始机器路径 JSON 仍保留在本地结果包但不纳入 Git；Git-safe 结果和此处的命令/时间记录可供审查。

测试优先修复记录：新增了“计数折的 held-out scene 必须与其窗口源 scene 相符”和“从逐窗口预测重算每个 PDP scene 分数”的两个回归。首次 RED 执行观察到二者分别因未拒绝错 scene、未拒绝被篡改分数而失败；之后修复验证器并通过。随后增加不可评分多路径窗口回归；RED 输出复现 `pandas.errors.MergeError: Merge keys are not unique in left dataset`，原因是失败分支把 MPC 行直接当成唯一窗口行。最小修复先按 `(run_id,window_id)` 去重并保留 `path_n`，GREEN 后 33/33 及全套 216/216 通过。该 RED 终端转录未单独落盘，失败信息来自当次执行输出，不能作为通过证据；最终 GREEN 完整日志已保留。

这些测试和算术对账不验证当前 Gaussian Copula 在量化时延 ties 下的统计适用性，也不证明 13 个重叠 LOSO 训练集是独立实验。科学解释边界见 `WP6_独立数值验收与模型选型报告.md` 第 7 节。
