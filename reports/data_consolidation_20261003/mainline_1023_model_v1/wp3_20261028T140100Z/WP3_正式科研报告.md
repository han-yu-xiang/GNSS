# Mainline Stage2 WP3：环境、仰角与运动条件化多径参数建模

- 实际分析时间（UTC）：2026-10-28T14:04:02+00:00
- 分析状态：已完成本轮有界模型比较；科学结论为 `COMPLETED_WITH_LIMITATIONS`（需独立/Commander审阅，不代表Gate G/WP6通过）。
- 研究范围预先固定：Urban（6场景）与Mountain/Valley（3场景）为核心；Highway/Open与Special Reflective各2场景仅作描述和适用性补充。
- 数据总体：83个SAGE任务、13个场景、7,847个Stage2已选窗口、8,914条Stage2 MPC；本轮核心为
  4,901个已选窗口、6,335条MPC。未进入Stage2的Stage0窗口没有补成零MPC。
- 主体输入为已接受V0导出的CSV及经核实的轨迹overlay；WP1/WP2结果只作有总体差异标注的历史参照。没有读取MAT/HDF5、raw IQ或CIR载荷，也没有运行SAGE/CIR/MATLAB/GNSS-SDR。

## 身份、环境与条件支持

|环境|独立场景|已选窗口|Stage2 MPC|
|---|---:|---:|---:|
|Urban|6|2,927|3,698|
|Mountain/Valley|3|1,974|2,637|
|Highway/Open|2|1,290|575|
|Special Reflective|2|1,656|2,004|

各场景/来源明细见 `condition_support_by_scene.csv` 与 `condition_support_by_scene_source.csv`；场景参数分布见 `descriptive_by_scene.csv`、`descriptive_by_environment.csv`。零MPC的Stage2已选窗口保留在计数表中。

## 仰角来源

|核心来源|MPC数|窗口数|占核心窗口|解释边界|
|---|---:|---:|---:|---|
|EPHEMERIS_DERIVED/GGA_ELLIPSOIDAL_HEIGHT|163|206|4.2%|推算来源分层|
|EPHEMERIS_DERIVED/ZERO_HEIGHT_ASSUMPTION|787|701|14.3%|推算来源分层|
|GSV_MEASURED/NA|4,948|3,478|71.0%|实测GSV|
|MISSING/NA|437|516|10.5%|缺失保留|

核心窗口来源数合计：GSV实测3,478；星历推算/GGA高度206；星历推算/零高度假设701；仰角缺失516。对应MPC行分别为4,948、163、787、437。MPC行数不是独立样本数。M2分别在GSV、GGA推算、零高度推算子集中拟合，不跨来源合并；缺失不插补。

## 车辆运动

核心环境有速度值的已选窗口为3,372；按scene汇总仅有144个不同NMEA源记录，单个源记录最多复用于96个窗口。核心场景速度上界为142.378 m/s（完整场景范围和来源见`motion_source_support_by_scene.csv`）。源记录复用、场景覆盖不均及高速度记录尚未完成独立质量核验，因此本轮只作描述，不拟合M3、不删除/截断速度、不估计空间相关长度。

## 模型定义与估计

对每个参数分别比较固定候选边际族：超额时延（chips）Gamma/Lognormal/Weibull；相对Doppler（Hz）Normal/Laplace/Student-t；相对功率（dB，相对量）Normal/Laplace/Student-t。

- **M0**：核心9场景内全局边际分布 `f(x|θ)`。它是同一核心测试总体的基线，不等同于WP1的13场景模型。
- **M1**：按Urban与Mountain/Valley分别估计边际参数 `f(x|E=e, θ_e)`。
- **M2**：在每个仰角来源纯净子集中增加连续仰角；正支持分布令`log(scale)=α_e+β(E−45°)/10`，有符号分布令`location=α_e+β(E−45°)/10`，按环境设置基础形状/尺度，Student-t使用共享自由度。

拟合采用场景等权、场景内MPC-bearing窗口等权、窗口内路径分摊权重的伪似然；这不是独立路径的普通MLE，也不产生路径级独立标准误。Normal、Lognormal、Laplace静态族使用相应加权闭式MLE；Gamma、Weibull、Student-t及M2使用数值优化。预测分数对同一测试窗口等权，配对模型每折必须具有完全相同的测试身份SHA。无支持、非收敛、边界解和低支持折全部留表。

## LOSO场景外结果

完整场景作为外层留出单位。`loso_fold_scores.csv`保留各场景、候选族、来源、模型的训练/测试支持和精确测试身份摘要；`loso_equal_scene_macro_scores.csv`给每个候选模型可用折的等场景宏平均，`loso_paired_deltas.csv`与`loso_paired_delta_macro.csv`只对测试身份完全一致且两边PASS的折计算模型差；`loso_family_ranks_by_scene.csv`保留每折候选族排名；`loso_parameter_stability.csv`描述参数跨折变化；`loso_tail_diagnostics.csv`保留p05/p50/p95、加权经验分位数与加权覆盖。

核心M0在各参数中可用折的候选族胜出次数（仅在该折成功族之间排序；不把不同折的训练集当独立重复）：

- `excess_delay_chips`：成功候选族可评的场景折 9/9；rank-1 折数：lognormal 9.
- `doppler_offset_hz`：成功候选族可评的场景折 9/9；rank-1 折数：laplace 1, normal 2, student_t 6.
- `relative_power_db`：成功候选族可评的场景折 9/9；rank-1 折数：laplace 1, normal 4, student_t 4.

所有候选族逐折排名与失败记录见上述CSV。一个折中各候选族共享完全相同测试身份；但若不同候选拟合失败，跨折宏平均的场景支持数会不同，因此不得只按不等支持的宏分数宣称唯一最佳分布。

### 同身份配对预测变化

`Δ log score = 右侧模型 − 左侧模型`；正值偏向右侧。下表把各候选族的配对宏差作为范围展示，不把候选族当独立样本、不计算置信区间。

|参数|模型比较|候选族配对宏Δ范围|正/负候选族数|配对场景数范围|
|---|---|---:|---:|---:|
|excess_delay_chips|ALL_MPC M1-M0|-0.0837 … -0.0242|0/3|9–9|
|excess_delay_chips|GSV_MEASURED M2-M0|-0.8860 … -0.0448|0/3|9–9|
|excess_delay_chips|GSV_MEASURED M2-M1|-0.0085 … 0.0996|1/2|9–9|
|excess_delay_chips|EPHEMERIS_ZERO_HEIGHT M2-M0|-1.1857 … 0.0081|2/1|9–9|
|doppler_offset_hz|ALL_MPC M1-M0|-0.0459 … -0.0122|0/3|9–9|
|doppler_offset_hz|GSV_MEASURED M2-M0|-0.1131 … -0.0082|0/3|7–9|
|doppler_offset_hz|GSV_MEASURED M2-M1|-0.0220 … -0.0005|0/3|7–9|
|doppler_offset_hz|EPHEMERIS_ZERO_HEIGHT M2-M0|-0.0231 … -0.0042|0/3|9–9|
|relative_power_db|ALL_MPC M1-M0|-0.1519 … -0.0166|0/3|8–9|
|relative_power_db|GSV_MEASURED M2-M0|-0.1247 … 0.0120|1/2|8–9|
|relative_power_db|GSV_MEASURED M2-M1|0.0115 … 0.0800|3/0|8–9|
|relative_power_db|EPHEMERIS_ZERO_HEIGHT M2-M0|-0.0917 … -0.0066|0/3|1–9|

分环境目标场景的逐族配对结果见`loso_paired_delta_macro.csv`。仅同一场景/变量/族/来源范围、同一测试身份SHA的PASS折进入模型差值；缺少可比配对的记录保留为失败或不支持。Mountain/Valley只有3个独立场景，LOSO训练集高度重叠；以上为描述性场景敏感性，不是独立实验区间或显著性检验。

### 按环境拆分的场景外比较

下表为每个候选族在目标环境内的等场景配对Δ范围；正值偏向右侧模型。候选族是模型规格而非独立重复，范围仅描述折间敏感性，不作为区间估计。

|参数|留出环境|比较|正/负/零候选族数|Δ范围|配对场景数范围|
|---|---|---|---:|---:|---:|
|excess_delay_chips|Urban|ALL_MPC M1-M0|0/3/0|-0.0326 … -0.0099|6–6|
|excess_delay_chips|Urban|GSV_MEASURED M2-M0|0/3/0|-0.0476 … -0.0226|6–6|
|excess_delay_chips|Urban|GSV_MEASURED M2-M1|1/2/0|-0.0127 … 0.0006|6–6|
|excess_delay_chips|Mountain/Valley|ALL_MPC M1-M0|0/3/0|-0.1859 … -0.0528|3–3|
|excess_delay_chips|Mountain/Valley|GSV_MEASURED M2-M0|0/3/0|-2.5813 … -0.0892|3–3|
|excess_delay_chips|Mountain/Valley|GSV_MEASURED M2-M1|2/1/0|-0.0167 … 0.2975|3–3|
|doppler_offset_hz|Urban|ALL_MPC M1-M0|1/2/0|-0.0419 … 0.0018|6–6|
|doppler_offset_hz|Urban|GSV_MEASURED M2-M0|2/1/0|-0.0715 … 0.0290|5–6|
|doppler_offset_hz|Urban|GSV_MEASURED M2-M1|2/1/0|-0.0022 … 0.0123|5–6|
|doppler_offset_hz|Mountain/Valley|ALL_MPC M1-M0|0/3/0|-0.0540 … -0.0402|3–3|
|doppler_offset_hz|Mountain/Valley|GSV_MEASURED M2-M0|0/3/0|-0.1965 … -0.1012|2–3|
|doppler_offset_hz|Mountain/Valley|GSV_MEASURED M2-M1|0/3/0|-0.0614 … -0.0070|2–3|
|relative_power_db|Urban|ALL_MPC M1-M0|1/2/0|-0.0415 … 0.0029|6–6|
|relative_power_db|Urban|GSV_MEASURED M2-M0|2/1/0|-0.0037 … 0.0524|6–6|
|relative_power_db|Urban|GSV_MEASURED M2-M1|3/0/0|0.0249 … 0.1007|6–6|
|relative_power_db|Mountain/Valley|ALL_MPC M1-M0|0/3/0|-0.4535 … -0.0748|2–3|
|relative_power_db|Mountain/Valley|GSV_MEASURED M2-M0|0/3/0|-0.3666 … -0.0687|2–3|
|relative_power_db|Mountain/Valley|GSV_MEASURED M2-M1|2/1/0|-0.0505 … 0.1877|2–3|
### 全核心 M1 参数差异（全数据拟合，仅描述）

每个变量按核心M0可用折宏分数最高的候选族列出M1全数据参数；此筛选复用同一LOSO结果，属探索性说明，不构成独立确认。

|参数|候选族|Urban估计|Mountain/Valley估计|
|---|---|---|---|
|excess_delay_chips|lognormal|`{"loc":0.0,"log_scale":-1.679398602512598,"scale":0.1864860945908455,"shape":0.44930233508776013}`|`{"loc":0.0,"log_scale":-1.599914553854674,"scale":0.20191377001092145,"shape":0.49338001728491665}`|
|doppler_offset_hz|student_t|`{"df":15.53740229204321,"loc":-2.256480015519166,"scale":58.04978964994336}`|`{"df":7.793185714822797,"loc":3.8539071188242633,"scale":75.52288573698796}`|
|relative_power_db|student_t|`{"df":92.83448913622924,"loc":-8.564023480478244,"scale":6.137505473710849}`|`{"df":3.095979866981573,"loc":-9.936266649713405,"scale":5.4329637266009785}`|

环境参数点估计反映可拟合的全核心样本，不是场景外参数估计；Mountain/Valley 3场景的参数不稳定性和拟合失败见全样本参数表与LOSO跨折参数表。正/负配对预测结果比全数据参数差异更能约束是否保留条件模型。

### M2 仰角斜率与尾部诊断

M2主分析为GSV实测子集；GGA推算和零高度是分开敏感性结果。下表分来源给出M2折间仰角斜率（单位/10°），只作场景敏感性描述。

|来源|参数|候选族|可用折|斜率中位数|最小…最大|
|---|---|---|---:|---:|---:|
|EPHEMERIS_GGA|doppler_offset_hz|laplace|5|-2.7322|-2.7322 … -2.7322|
|EPHEMERIS_GGA|doppler_offset_hz|normal|5|-3.2802|-3.2802 … -3.2802|
|EPHEMERIS_GGA|doppler_offset_hz|student_t|5|-3.2753|-3.2753 … -3.2753|
|EPHEMERIS_GGA|excess_delay_chips|gamma|5|0.0159|0.0159 … 0.0159|
|EPHEMERIS_GGA|excess_delay_chips|lognormal|5|0.0079|0.0079 … 0.0079|
|EPHEMERIS_GGA|excess_delay_chips|weibull|5|0.0274|0.0274 … 0.0274|
|EPHEMERIS_GGA|relative_power_db|laplace|5|-0.9251|-0.9251 … -0.9251|
|EPHEMERIS_GGA|relative_power_db|normal|5|-0.5884|-0.5884 … -0.5884|
|EPHEMERIS_ZERO_HEIGHT|doppler_offset_hz|laplace|9|1.8397|-3.2191 … 5.8808|
|EPHEMERIS_ZERO_HEIGHT|doppler_offset_hz|normal|9|0.3429|-1.2952 … 2.7508|
|EPHEMERIS_ZERO_HEIGHT|doppler_offset_hz|student_t|9|0.9491|-0.6749 … 2.8493|
|EPHEMERIS_ZERO_HEIGHT|excess_delay_chips|gamma|9|-0.0079|-0.0186 … 0.0403|
|EPHEMERIS_ZERO_HEIGHT|excess_delay_chips|lognormal|9|0.0263|0.0171 … 0.0483|
|EPHEMERIS_ZERO_HEIGHT|excess_delay_chips|weibull|9|-0.0449|-0.0510 … 0.0283|
|EPHEMERIS_ZERO_HEIGHT|relative_power_db|laplace|9|-0.8522|-0.9642 … -0.4981|
|EPHEMERIS_ZERO_HEIGHT|relative_power_db|normal|9|-0.4170|-0.4756 … -0.3157|
|EPHEMERIS_ZERO_HEIGHT|relative_power_db|student_t|2|-0.3704|-0.4240 … -0.3167|
|GSV_MEASURED|doppler_offset_hz|laplace|9|6.6682|1.7803 … 8.2025|
|GSV_MEASURED|doppler_offset_hz|normal|9|2.8209|-0.9606 … 4.5979|
|GSV_MEASURED|doppler_offset_hz|student_t|7|1.9019|0.7516 … 2.2073|
|GSV_MEASURED|excess_delay_chips|gamma|9|-0.0186|-0.0287 … 0.0058|
|GSV_MEASURED|excess_delay_chips|lognormal|9|0.0089|0.0000 … 0.0176|
|GSV_MEASURED|excess_delay_chips|weibull|9|-0.0480|-0.0588 … -0.0117|
|GSV_MEASURED|relative_power_db|laplace|9|-1.2023|-1.4640 … -0.9968|
|GSV_MEASURED|relative_power_db|normal|9|-1.1725|-1.3249 … -0.7280|
|GSV_MEASURED|relative_power_db|student_t|8|-1.0670|-1.1740 … -0.7161|

正/负斜率不等于因果效应；LOSO训练集互相重叠，不能从折间范围构造普通置信区间。尾部经验分位数按同一场景/窗口权重计算；名义尾部路径行数不是有效样本量。
本轮尾部表有2,268条p05/p50/p95诊断，其中279条因拟合不可用而没有校准值；579条记录的名义目标尾部路径行数小于10。由于窗口重叠和同窗MPC相关，后一个计数仅作低支持提醒，不是有效独立样本量。无尾部整体PASS声明。

## 补充环境与历史基线

Highway/Open、Special Reflective各2个场景，基础统计和逐场景支持完整保留。核心训练的M0/M1及来源纯净M2仅对补充场景做适用性评分，不把补充环境重新纳入核心训练或模型选择；M1/M2拟合/评分失败也逐条保留。细节见`descriptive_by_environment.csv`与`supplement_applicability_scores.csv`。
WP1的13场景Global LOSO和WP2候选排名见`external_13scene_baseline_context.csv`，是行加权、不同训练总体的历史参照；不得与本轮9场景、场景/窗口加权的配对分数直接相减。

## 科学判定与限制

1. 分布候选：核心M0的超额时延Lognormal在9/9个场景折排名第一；Doppler的Student-t在6/9折排名第一；相对功率Normal与Student-t各在4/9折排名第一，故功率没有单一稳定胜者。排名仅限成功拟合候选之间。
2. 环境差异：M1全数据参数点估计存在差异，但核心合并场景的配对M1−M0宏Δ在三个参数的全部候选族中均为负；分环境拆分的异质性见上表。因此当前证据不支持把M1宣称为稳定的场景外预测改进。
3. 仰角：GSV实测M2对相对功率的M2−M1在候选族总体配对宏分数上均为正，但M2−M0的候选族结果混合；按环境拆分后收益也不一致。延迟/Doppler未显示跨环境稳定增益。故仰角可保留为候选解释变量，但M2尚不作为已验证的普适预测模型。
4. Stage2总体受Stage1/Stage2筛选条件化；不代表285,752个Stage0有效窗口的无条件多径总体。
5. 同场景多PRN、重叠窗口与同窗多MPC相关。Mountain/Valley仅3个独立场景；不以路径总数虚增独立样本量、不报告行级CI或p值。候选族筛选和LOSO宏排名也是探索性，不是预留独立测试集。
6. 运动条件仅描述，不拟合M3；不做空间相关长度或联合依赖模型。补充环境仅作适用性分析。Gate G、WP6、alpha真实导出和Gate E/F均未完成；alpha导出试点继续暂缓。

**WP3本轮计算与内部一致性检查已完成，建议状态：`COMPLETED_WITH_LIMITATIONS`，等待Commander独立科学审阅。该状态不代表条件模型已获最终采纳或Gate G/WP6通过。**

## 产物

- `condition_support_by_scene.csv`
- `condition_support_by_scene_source.csv`
- `motion_source_support_by_scene.csv`
- `window_mpc_count_support_by_scene.csv`
- `descriptive_by_scene.csv`
- `descriptive_by_environment.csv`
- `loso_fold_manifest.csv`
- `loso_fold_scores.csv`
- `loso_equal_scene_macro_scores.csv`
- `loso_paired_deltas.csv`
- `loso_paired_delta_macro.csv`
- `loso_family_ranks_by_scene.csv`
- `loso_tail_diagnostics.csv`
- `loso_parameter_stability.csv`
- `full_data_model_parameters.csv`
- `m1_environment_parameter_contrasts.csv`
- `supplement_applicability_scores.csv`
- `external_13scene_baseline_context.csv`
- `figures\core_environment_scene_medians.png`
- `figures\gsv_elevation_window_medians.png`
- `figures\loso_paired_score_deltas.png`
- `independent_validation_final.json`
- `analysis_execution.txt`
- `focused_test_execution.txt`

## 输入来源SHA-256

|输入|SHA-256|
|---|---|
|mpc_rows|`a2c26d0de655e0f6cf4a60cf2906bf4cfff7aa16bbc5f74bffb4e9b80dab306c`|
|selected_windows|`fbc784ff169fca6d95907e39a56510d9be0b61ec3c1ef42e15235002be40061c`|
|stage2_artifact_manifest|`a47b056e8764e70987e9df733fa9855955fa4dade7e782f3fdd5c394c3200da6`|
|wp1_scene_fold_scores|`faad49468cb7d36ed070e54a8b9fdc564cdaa9bc3f682fed1eb391cfebbf03ca`|
|wp1_report|`41f4711790823bcfa0fe8c7bece68bbc40c492b086cfd7349984e2153400356d`|
|wp2_marginal_summary|`5439b0c7e3d8df2ee97b06c04b5b67c14180c6a5a480fb1fafd9175e0df00db5`|
|wp2_power_delay_summary|`295f84904aaadbb8f9b5b1562f361a6cfbb475b51f4dc7b6d8d0067f6c1e7922`|
|wp3_plan|`4245ca034114ff982df8e835a6be052e8725f9280bf012ca8169da47785714a1`|
|trajectory_overlay|`1f7385663341d89cdb42c459c1e9d8c36a0ef4ca6f5d6a4f0c667944de0f0c93`|

测试执行命令、UTC时间、退出码与完整输出另见结果包中的`focused_test_execution.txt`。
