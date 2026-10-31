# WP6 独立科学与数值验收报告

**状态：** WP6 `COMPLETED_WITH_LIMITATIONS`；Gate G `PENDING`。
**最终结果：** `wp6_20261029T154500Z_final/`。
**验收边界：** 本报告不把统计候选研究、代码测试或数值对账等同于 Gate G 通过。

## 1. 冻结总体与输入

复核使用 WP4 Gate E/F 已验收的两个固定输入，没有重新运行 SAGE、CIR、alpha 导出，也没有读取大型科学载荷：

| 输入 | SHA-256 | 行数 |
| --- | --- | ---: |
| `stage2_cir_pdp_window_features.csv` | `258d5d70081d9ee6fd82a64b1a4f9c405180bc18cd49280b0e2b799d9a482bf4` | 7,847 |
| `stage2_mpc_cir_alpha_linkage.csv` | `8db941db20e684108d13583d67ee20cde543bf2a36ca01013d1288b48231c80b` | 8,914 |

复核得到 83 个 run、13 个 scene、7,847 个唯一 `(run_id, window_id)` 选中窗口和 8,914 个唯一 `(run_id, window_id, path_id)` MPC。窗口计数 0/1/2/3 为 3,574/1,412/1,081/1,780；277,905 个未选中 Stage0 窗口没有被补成零 MPC。63 个 PDP 延迟网格边界峰全部保留。

## 2. 模型结果与可支持的结论

- 条件于 Stage2 选择的场景平衡经验计数模型覆盖 13/13 scene，宏平均留出 log-score 为 `-1.2973847631` nats/选中窗口。它只描述 Stage2 选中总体，不是 Stage0 全总体的 MPC 发生率模型。
- 嵌套完整 scene-LOSO 中，超额时延 Lognormal 为 13/13 折首选，多普勒 Student-t 为 13/13 折首选；相对功率 Student-t 为 8/13，Normal 为 5/13，说明其族选择仍不稳定。6 条拟合失败及 72/234 条低支持尾部诊断保留，没有被删去或包装成通过。
- 新增的逐选中窗口计数 + 路径产品边际因子化候选分数为 `-10.4342187429` nats/选中窗口，13/13 scene 可评分、0 个窗口因当前支持缺失而不可评分。它假设标记分布不随计数变化，且窗口内路径条件 iid/可交换；这些假设未被数据验证。因此这是条件 composite 候选评分，不是经验证的完整联合生成模型，也不与观测单位不同的边际评分直接比较。
- 当前连续 Gaussian Copula 点密度在有量化/并列时延的数据上不构成适当的混合/离散似然，不能用于模型排名。图和表保留诊断值，但已明确标为 diagnostic-only；不能据此宣称 Copula 有益或无益，也没有据此声称相关结构被排除。
- CIR/PDP 关联保持独立的窗口级 scene-LOSO 分析。PDP RMS code-delay width 的 scene-macro RMSE 由 2.485324 降至 2.446555，差值 `-0.038769` samples，线性模型在 10/13 scene 较好；peak-minus-SAGE-direct-delay RMSE 由 4.298158 降至 4.290361，差值 `-0.007798` samples，6/13 scene 较好。改善较小，输入测量链共享；这不是独立传播真值、物理 RMS 多径时延扩展或 SAGE 参数到 CIR 的物理重构验证。

## 3. 独立数值验证

独立 validator 不导入 WP6 拟合/评分函数。它核对冻结输入哈希、身份/计数、完整 scene 折隔离、逐选中窗口计数—标记复合分数、拟合失败清单、尾部分位数支持网格、PDP 逐窗与逐 scene 评分、摘要聚合及 direct-plus-MPC 延迟矩/功率和。最终状态 `PASS_WITH_LIMITATIONS`：窗口 7,847/7,847、MPC 8,914/8,914、联合评分 scene 13/13、联合未评分窗口 0、PDP scene/model/target 分数 52/52。延迟 centroid、RMS 和相对功率和的最大复算差分别为 `3.55e-15`、`1.78e-15` samples 和 `5.68e-14`，均为浮点舍入量级。

验证的是输入、键、分折和输出表的数值一致性，不是 8,914 条路径独立，也不是跨场景抽样独立、因果作用、普适生成能力或物理真值。

## 4. 独立代码/结果审阅与闭合

独立审阅无 Critical 或 Important 发现。初审的三个 Minor 项均已闭合：

1. Copula 图容易被误看成排名：最终图题和图内注释均说明“仅作诊断，不作模型排名”，并指出 ties/量化使当前连续点密度比较无效。
2. 生成 PNG 的中文缺字：最终三张图统一采用可读英文标题和轴标签。
3. manifest 正行数不匹配的测试覆盖：完整 validator 原本在读取真实源表后逐项拒绝行数不一致；新增正数行数被篡改的回归测试，验证该拒绝路径。

对上述最终修订，定向 WP6 测试 39/39、完整 channel-modeling 测试 222/222、Python 编译检查退出码 0。独立复核再次运行最终包 validator，仍为 `PASS_WITH_LIMITATIONS`，未提出新的 Critical/Important/Minor 发现。详细命令、时间和退出码见 `targeted_regression_evidence.md`。

## 5. 模型解释边界与最终判断

结果支持经验计数基线与训练折内嵌套选择的边际模型作为可复现的候选统计基线，并支持把已验收 CIR/PDP 特征作为单独的窗口级场景外关联目标。当前证据不足以确认计数—标记不变性、窗口内路径 iid、连续 Copula 排名、场景外复杂联合生成优势或共享输入 CIR/PDP 预测的物理意义。MPC、重叠窗口及 LOSO 折均不是相互独立的 scene 重复。

WP6 可作为 `COMPLETED_WITH_LIMITATIONS` 的候选研究交付；**Gate G 仍为 `PENDING`**，需由后续独立科学验收决定是否接受现有边界，或另行批准 ties-aware dependence/proper-scoring 与计数条件标记稳定性研究。Phase-2 生成模型保持 `PLANNED_ONLY`。本轮没有运行或干预 Task 5、MATLAB、SAGE、CIR 或其他科学生产。
